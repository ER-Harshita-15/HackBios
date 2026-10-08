"""
NETRA-X Phase 1 End-to-End Integration Verification Script
Tests the full lifecycle:
Case creation -> File upload -> Pipeline processing -> Text extraction ->
Entity extraction -> Evidence traceability -> Entity review (Verify/Reject/Edit) -> Dashboard stats
"""

import asyncio
import os
import uuid
from pathlib import Path
from httpx import AsyncClient, ASGITransport

from app.main import app, lifespan
from app.database import init_db, async_session_factory
from app.models.document import Document, ProcessingStatus
from app.services.processing.pipeline import get_pipeline


async def run_end_to_end_verification():
    print("=" * 70)
    print("  NETRA-X PHASE 1 — END-TO-END INTEGRATION TEST")
    print("=" * 70)

    data_dir = Path(__file__).resolve().parent.parent.parent / "data" / "synthetic"
    fir_file = data_dir / "fir" / "FIR_001.txt"
    cdr_file = data_dir / "cdr" / "CDR_001.csv"
    txn_file = data_dir / "financial" / "transactions_001.csv"

    assert fir_file.exists(), f"FIR test file not found at {fir_file}"
    assert cdr_file.exists(), f"CDR test file not found at {cdr_file}"
    assert txn_file.exists(), f"Txn test file not found at {txn_file}"

    async with lifespan(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:

            # 1. Health check
            print("\n[1/7] Testing /health endpoint...")
            resp = await client.get("/health")
            assert resp.status_code == 200, f"Health check failed: {resp.text}"
            print(f"  [OK] Health Check Passed: {resp.json()}")

            # 2. Create Case
            print("\n[2/7] Creating Investigation Case...")
            unique_case_num = f"CASE/2024/{uuid.uuid4().hex[:6].upper()}"
            case_payload = {
                "case_number": unique_case_num,
                "title": "Operation Shadow Net — Financial Cheating & Conspiracy",
                "description": "Multi-jurisdictional investigation into shell entity ABC Trading Co.",
                "status": "UNDER_INVESTIGATION",
            }
            resp = await client.post("/api/cases", json=case_payload)
            assert resp.status_code in (200, 201), f"Create case failed: {resp.text}"
            case_data = resp.json()
            case_id = case_data["id"]
            print(f"  [OK] Case Created: ID={case_id}, Number={case_data['case_number']}")

            # 3. Upload & Process FIR Document
            print("\n[3/7] Uploading and processing synthetic FIR document...")
            with open(fir_file, "rb") as f:
                upload_resp = await client.post(
                    "/api/documents/upload",
                    data={
                        "case_id": case_id,
                        "document_type": "FIR",
                        "source": "Central Kotwali Police Station",
                        "description": "First Information Report regarding IPC 420/120B",
                    },
                    files={"file": ("FIR_001.txt", f, "text/plain")},
                )
            assert upload_resp.status_code == 201, f"Document upload failed: {upload_resp.text}"
            doc_data = upload_resp.json()
            doc_id = doc_data["id"]
            print(f"  [OK] Document Uploaded: ID={doc_id}, Filename={doc_data['original_filename']}")

            # Run pipeline processing synchronously for test verification
            print("  Running document processing pipeline...")
            async with async_session_factory() as db:
                from sqlalchemy import select
                doc = (await db.execute(select(Document).where(Document.id == doc_id))).scalar_one()
                pipeline = get_pipeline()
                await pipeline.process(doc, db)

            # Check status
            status_resp = await client.get(f"/api/documents/{doc_id}/status")
            assert status_resp.status_code == 200
            print(f"  [OK] Processing Status: {status_resp.json()['status']}")
            assert status_resp.json()["status"] == "READY_FOR_REVIEW"

            # 4. Verify Pages & Extracted Text
            print("\n[4/7] Verifying document pages and extracted text...")
            pages_resp = await client.get(f"/api/documents/{doc_id}/pages")
            assert pages_resp.status_code == 200
            pages = pages_resp.json()
            assert len(pages) > 0, "No pages extracted!"
            page1 = pages[0]
            assert "FIRST INFORMATION REPORT" in page1["raw_text"]
            assert len(page1["cleaned_text"]) > 0
            print(f"  [OK] Extracted {len(pages)} page(s). Cleaned text length: {len(page1['cleaned_text'])} chars")

            # 5. Verify Extracted Entities & Traceability
            print("\n[5/7] Verifying extracted entities & mention traceability...")
            entities_resp = await client.get(f"/api/documents/{doc_id}/entities")
            assert entities_resp.status_code == 200
            entities_data = entities_resp.json()
            entities = entities_data["entities"]
            print(f"  [OK] Total Unique Entities Extracted: {len(entities)}")

            entity_types_found = {e["entity_type"] for e in entities}
            print(f"  [OK] Entity Types Detected: {sorted(list(entity_types_found))}")

            # Verify key expected entities from FIR_001
            values = {e["value"] for e in entities}
            normalized = {e["normalized_value"] for e in entities}

            # Check Phone
            assert any("9876543210" in v for v in values), "Phone 9876543210 not extracted"
            assert any("9988776655" in v for v in values), "Phone 9988776655 not extracted"

            # Check Vehicle
            assert any("CG10AB1234" in v for v in normalized), "Vehicle CG10AB1234 not extracted"

            # Check Email
            assert any("rahul.sharma@email.com" in v for v in values), "Email not extracted"

            # Check Mentions Traceability
            for ent in entities:
                assert len(ent["mentions"]) > 0, f"Entity {ent['value']} has no mentions!"
                for m in ent["mentions"]:
                    assert m["page_number"] >= 1, "Mention missing valid page number"
                    assert m["confidence"] > 0, "Mention confidence must be > 0"
                    assert m["context"] is not None, "Mention context snippet must be preserved"

            print(f"  [OK] Traceability Verified: 100% of entities link to document page and context snippet")

            # 6. Human-in-the-Loop Review (Verify, Reject, Edit)
            print("\n[6/7] Testing Human-in-the-loop Entity Review Workflow...")
            target_entity = entities[0]
            target_id = target_entity["id"]

            # Test Verify
            v_resp = await client.post(f"/api/entities/{target_id}/verify", json={"verified_by": "Inspector Sharma"})
            assert v_resp.status_code == 200
            assert v_resp.json()["verification_status"] == "VERIFIED"
            print(f"  [OK] Entity Verified: {target_entity['value']} -> status={v_resp.json()['verification_status']}")

            # Test Reject another entity
            if len(entities) > 1:
                reject_entity = entities[1]
                r_resp = await client.post(f"/api/entities/{reject_entity['id']}/reject", json={"notes": "False positive"})
                assert r_resp.status_code == 200
                assert r_resp.json()["verification_status"] == "REJECTED"
                print(f"  [OK] Entity Rejected: {reject_entity['value']} -> status={r_resp.json()['verification_status']}")

            # Test Edit entity value
            if len(entities) > 2:
                edit_entity = entities[2]
                e_resp = await client.put(f"/api/entities/{edit_entity['id']}", json={"value": edit_entity["value"] + " (Corrected)", "notes": "Updated during review"})
                assert e_resp.status_code == 200
                assert e_resp.json()["verification_status"] == "MODIFIED"
                print(f"  [OK] Entity Edited: New Value='{e_resp.json()['value']}' -> status={e_resp.json()['verification_status']}")

            # 7. Dashboard Stats & Cross-Check
            print("\n[7/7] Testing Dashboard Metrics & Recent Feeds...")
            stats_resp = await client.get("/api/dashboard/stats")
            assert stats_resp.status_code == 200
            stats = stats_resp.json()
            print(f"  [OK] Dashboard Stats: Total Documents={stats['total_documents']}, Total Entities={stats['total_entities']}, Verified={stats['verified_entities']}")
            assert stats["total_documents"] >= 1
            assert stats["total_entities"] >= len(entities)

            recent_resp = await client.get("/api/dashboard/recent-documents")
            assert recent_resp.status_code == 200
            print(f"  [OK] Recent Documents Feed: {len(recent_resp.json())} item(s)")

    print("\n" + "=" * 70)
    print("  ALL END-TO-END INTEGRATION TESTS PASSED SUCCESSFULLY! (100%)")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_end_to_end_verification())
