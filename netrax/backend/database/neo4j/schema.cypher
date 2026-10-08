// =====================================================================
// NETRA-X — Neo4j Schema, Constraints & Indexes (Phase 2)
// =====================================================================

// Node Uniqueness Constraints
CREATE CONSTRAINT unique_canonical_entity IF NOT EXISTS
FOR (e:CanonicalEntity) REQUIRE e.id IS UNIQUE;

CREATE CONSTRAINT unique_person IF NOT EXISTS
FOR (p:Person) REQUIRE p.id IS UNIQUE;

CREATE CONSTRAINT unique_phone IF NOT EXISTS
FOR (p:Phone) REQUIRE p.id IS UNIQUE;

CREATE CONSTRAINT unique_account IF NOT EXISTS
FOR (a:Account) REQUIRE a.id IS UNIQUE;

CREATE CONSTRAINT unique_vehicle IF NOT EXISTS
FOR (v:Vehicle) REQUIRE v.id IS UNIQUE;

CREATE CONSTRAINT unique_location IF NOT EXISTS
FOR (l:Location) REQUIRE l.id IS UNIQUE;

CREATE CONSTRAINT unique_organization IF NOT EXISTS
FOR (o:Organization) REQUIRE o.id IS UNIQUE;

CREATE CONSTRAINT unique_case IF NOT EXISTS
FOR (c:Case) REQUIRE c.id IS UNIQUE;

// Indexes for High-Performance Queries
CREATE INDEX entity_name_idx IF NOT EXISTS
FOR (e:CanonicalEntity) ON (e.canonical_name);

CREATE INDEX entity_type_idx IF NOT EXISTS
FOR (e:CanonicalEntity) ON (e.entity_type);

CREATE INDEX entity_case_idx IF NOT EXISTS
FOR (e:CanonicalEntity) ON (e.case_id);

CREATE INDEX relationship_case_idx IF NOT EXISTS
FOR ()-[r:RELATIONSHIP]-() ON (r.case_id);

CREATE INDEX relationship_type_idx IF NOT EXISTS
FOR ()-[r:RELATIONSHIP]-() ON (r.type);
