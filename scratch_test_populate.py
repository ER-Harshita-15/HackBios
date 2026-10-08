import asyncio
import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, r"g:\criminal analysis\netrax\backend")

from app.database import async_session_factory, init_db
from app.services.resolution.entity_resolution import EntityResolutionService
from app.services.resolution.relationship_extraction import RelationshipExtractionService
from app.services.resolution.graph_sync import GraphSyncService
from sqlalchemy import select, func
from app.models.canonical_entity import CanonicalEntity
from app.models.relationship import Relationship
from app.models.entity_match_candidate import EntityMatchCandidate

async def main():
    await init_db()
    async with async_session_factory() as db:
        res_service = EntityResolutionService()
        rel_service = RelationshipExtractionService()
        graph_service = GraphSyncService()

        print("=== 1. Syncing Entities ===")
        synced = await res_service.sync_all_entities(db, include_unverified=True)
        print(f"Synced {synced} canonical entities.")

        print("=== 2. Extracting Relationships ===")
        rels_extracted = await rel_service.extract_all(db)
        print(f"Extracted {rels_extracted} relationships.")

        print("=== 3. Generating Match Candidates ===")
        candidates = await res_service.generate_candidates(db, min_score=0.4, include_unverified=True)
        print(f"Generated {candidates} match candidates.")

        print("=== 4. Testing Graph Projection ===")
        graph = await graph_service.build_graph(db, limit=100)
        print(f"Graph nodes: {len(graph.nodes)}, Graph edges: {len(graph.edges)}")

        ce_count = (await db.execute(select(func.count(CanonicalEntity.id)))).scalar()
        rel_count = (await db.execute(select(func.count(Relationship.id)))).scalar()
        cand_count = (await db.execute(select(func.count(EntityMatchCandidate.id)))).scalar()

        print(f"\nFinal DB counts: CanonicalEntities={ce_count}, Relationships={rel_count}, Candidates={cand_count}")
        await db.commit()

if __name__ == "__main__":
    asyncio.run(main())
