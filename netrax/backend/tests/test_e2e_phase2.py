"""
NETRA-X Phase 1 + Phase 2 End-to-End System Integration Test

Validates complete pipeline:
Document Ingestion -> Text/Entity Extraction -> Verification ->
Entity Resolution (Deduplication) -> Canonical Entities ->
Relationship Extraction (CDR/Financial/FIR) -> Knowledge Graph (Neo4j / PostgreSQL projection) ->
Shortest Path (BFS) -> Intelligence Dashboard
"""

import asyncio
import os
import uuid
from pathlib import Path
from httpx import AsyncClient, ASGITransport

from app.main import app, lifespan
from app.database import init_db


async def run_phase2_e2e():
    print("=" * 75)
    print("  NETRA-X — PHASE 1 + PHASE 2 FULL END-TO-END VERIFICATION")
    print("=" * 75)

    data_dir = Path(__file__).resolve().parent.parent.parent / "data" / "synthetic"
    fir_file = data_dir / "fir" / "FIR_001.txt"
    cdr_file = data_dir / "cdr" / "CDR_001.csv"
    txn_file = data_dir / "financial" / "transactions_001.csv"

    assert fir_file.exists(), f"FIR test file not found at {fir_file}"
    assert cdr_file.exists(), f"CDR test file not found at {cdr_file}"
    assert txn_file.exists(), f"Txn test file not found at {txn_file}"

    async with lifespan(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:

            # [1] System Health
            print("\n[1/10] Verifying System Health...")
            resp = await client.get("/health")
            assert resp.status_code == 200
            print(f"  [OK] System online: {resp.json()}")

            # [2] Create Investigation Case
            print("\n[2/10] Initializing Investigation Case...")
            unique_case = f"CASE/2026/NX-{uuid.uuid4().hex[:6].upper()}"
            case_resp = await client.post("/api/cases", json={
                "case_number": unique_case,
                "title": "Operation Netra-Strike — Syndicate & Financial Trail",
                "description": "Cross-jurisdiction investigation into syndicate accounts, communications, and assets.",
                "status": "UNDER_INVESTIGATION",
            })
            assert case_resp.status_code in (200, 201)
            case_data = case_resp.json()
            case_id = case_data["id"]
            print(f"  [OK] Case created: ID={case_id}, Number={case_data['case_number']}")

            # [3] Ingest FIR Document
            print("\n[3/10] Uploading & Processing FIR Evidence Document...")
            with open(fir_file, "rb") as f:
                upload_resp = await client.post(
                    "/api/documents/upload",
                    data={
                        "case_id": case_id,
                        "document_type": "FIR",
                        "source": "State Police FIR Records",
                        "description": "Initial crime report naming suspects and seized vehicles",
                    },
                    files={"file": (fir_file.name, f, "text/plain")},
                )
            assert upload_resp.status_code in (200, 201)
            fir_doc = upload_resp.json()
            print(f"  [OK] FIR uploaded: ID={fir_doc['id']}, Filename={fir_doc['filename']}")

            # Wait for processing
            await client.post(f"/api/documents/{fir_doc['id']}/process")
            entities_resp = await client.get(f"/api/documents/{fir_doc['id']}/entities")
            assert entities_resp.status_code == 200
            fir_entities = entities_resp.json()["entities"]
            print(f"  [OK] Extracted {len(fir_entities)} entities from FIR")

            # Verify entities in FIR
            verified_count = 0
            for ent in fir_entities[:10]:
                v_resp = await client.post(f"/api/entities/{ent['id']}/verify", json={
                    "verified_by": "lead_investigator",
                    "notes": "Verified against FIR narrative",
                })
                if v_resp.status_code == 200:
                    verified_count += 1
            print(f"  [OK] Human investigator verified {verified_count} entities")

            # [4] Ingest CDR Document
            print("\n[4/10] Ingesting Call Detail Records (CDR)...")
            with open(cdr_file, "rb") as f:
                cdr_resp = await client.post(
                    "/api/documents/upload",
                    data={
                        "case_id": case_id,
                        "document_type": "CDR",
                        "source": "Telecom Service Provider Tower Dump",
                        "description": "Intercepted CDR tower exchanges",
                    },
                    files={"file": (cdr_file.name, f, "text/csv")},
                )
            assert cdr_resp.status_code in (200, 201)
            cdr_doc = cdr_resp.json()
            await client.post(f"/api/documents/{cdr_doc['id']}/process")
            cdr_entities = (await client.get(f"/api/documents/{cdr_doc['id']}/entities")).json()["entities"]
            print(f"  [OK] Extracted {len(cdr_entities)} telecommunication entities from CDR")
            for ent in cdr_entities[:8]:
                await client.post(f"/api/entities/{ent['id']}/verify", json={"verified_by": "telecom_analyst"})

            # [5] Entity Resolution: Candidate Generation
            print("\n[5/10] Running Entity Resolution Engine (Multi-feature string/phonetic/identifier matching)...")
            res_run_resp = await client.post("/api/resolution/run", json={
                "case_id": case_id,
                "min_score": 0.45,
            })
            assert res_run_resp.status_code == 200
            run_data = res_run_resp.json()
            print(f"  [OK] Resolution scan completed: {run_data['candidates_generated']} candidate pairs identified")

            # [6] Review & Confirm Match Candidate -> Canonical Entity
            print("\n[6/10] Reviewing Match Candidates & Forming Canonical Entity...")
            cand_resp = await client.get("/api/resolution/candidates", params={"status": "PENDING"})
            assert cand_resp.status_code == 200
            candidates = cand_resp.json()["candidates"]

            confirmed_canonical_id = None
            if len(candidates) > 0:
                top_cand = candidates[0]
                conf_resp = await client.post(
                    f"/api/resolution/candidates/{top_cand['id']}/confirm",
                    json={
                        "reviewed_by": "senior_superintendent",
                        "canonical_name": top_cand["entity_a_value"],
                        "notes": "Confirmed match across separate document citations",
                    },
                )
                assert conf_resp.status_code == 200
                canonical = conf_resp.json()
                confirmed_canonical_id = canonical["id"]
                print(f"  [OK] Candidate Confirmed! Canonical Entity Created: '{canonical['canonical_name']}' (ID: {canonical['id'][:8]}...)")
                print(f"       Linked Aliases: {len(canonical.get('aliases', []))}")
            else:
                print("  [INFO] No pending cross-document matches required merging in this run")

            # [7] List Canonical Entities
            print("\n[7/10] Fetching Resolved Canonical Entity Profiles...")
            can_list = await client.get("/api/canonical-entities", params={"limit": 10})
            assert can_list.status_code == 200
            can_data = can_list.json()
            print(f"  [OK] Master Canonical Registry: {can_data['total']} resolved profiles online")

            # [8] Extract Evidence-Backed Relationships
            print("\n[8/10] Running Evidence-Backed Relationship Extraction...")
            extract_resp = await client.post("/api/relationships/extract", json={"case_id": case_id})
            assert extract_resp.status_code == 200
            extract_data = extract_resp.json()
            print(f"  [OK] Relationship Extraction completed: {extract_data['relationships_created']} relationships extracted")

            # List and Verify a Relationship
            rels_resp = await client.get("/api/relationships", params={"case_id": case_id, "limit": 10})
            assert rels_resp.status_code == 200
            rels_list = rels_resp.json()["relationships"]
            print(f"  [OK] Retrieved {len(rels_list)} relationships for case")

            if len(rels_list) > 0:
                first_rel = rels_list[0]
                verify_rel_resp = await client.post(
                    f"/api/relationships/{first_rel['id']}/verify",
                    json={"verified_by": "case_officer", "notes": "Corroborated by call records"}
                )
                assert verify_rel_resp.status_code == 200
                print(f"  [OK] Verified Relationship: [{first_rel['source_entity_name']}] --({first_rel['relationship_type']})--> [{first_rel['target_entity_name']}]")

            # [9] Build & Query Knowledge Graph Projection
            print("\n[9/10] Building Knowledge Graph & Running BFS Shortest Path...")
            graph_build = await client.post(f"/api/graph/build/{case_id}", json={"include_unverified": True})
            assert graph_build.status_code == 200
            gb_data = graph_build.json()
            print(f"  [OK] Graph Projection Built: {gb_data['nodes_created']} nodes, {gb_data['relationships_created']} edges")

            graph_query = await client.get(f"/api/graph/{case_id}", params={"include_unverified": True})
            assert graph_query.status_code == 200
            g_data = graph_query.json()
            print(f"  [OK] Cytoscape Graph Data Ready: {len(g_data['nodes'])} nodes, {len(g_data['edges'])} edges")

            # Test BFS Shortest Path
            if len(g_data["nodes"]) >= 2:
                n1 = g_data["nodes"][0]["id"]
                n2 = g_data["nodes"][1]["id"]
                path_resp = await client.post("/api/graph/path", json={
                    "source_entity_id": n1,
                    "target_entity_id": n2,
                    "max_depth": 5,
                })
                assert path_resp.status_code == 200
                p_data = path_resp.json()
                print(f"  [OK] BFS Path Search: Path found={p_data['found']}, Hops={p_data['length']}")

            # Validate Graph
            val_resp = await client.get(f"/api/graph/validate/{case_id}")
            assert val_resp.status_code == 200
            val_data = val_resp.json()
            print(f"  [OK] Graph Consistency Validation: Valid={val_data['valid']}, Orphan Rels={val_data['orphan_relationships']}")

            # [10] Phase 2 Operations Dashboard
            print("\n[10/10] Verifying Operations Intelligence Dashboard...")
            dash_resp = await client.get("/api/dashboard/phase2-stats")
            assert dash_resp.status_code == 200
            dash_stats = dash_resp.json()
            print(f"  [OK] Phase 2 Dashboard Metrics: Canonical Profiles={dash_stats['canonical_entities']}, "
                  f"Total Relationships={dash_stats['total_relationships']}, Graph Nodes={dash_stats['graph_nodes']}")

    print("\n" + "=" * 75)
    print("  ALL PHASE 1 + PHASE 2 TESTS PASSED SUCCESSFULLY! (100% OPERATIONAL)")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(run_phase2_e2e())
