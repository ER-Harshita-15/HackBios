/**
 * NETRA-X TypeScript Type Definitions — Phase 1 & Phase 2
 */

// ─── Cases ─────────────────────────────────────────────────────────

export interface Case {
  id: string;
  case_number: string;
  title: string;
  description: string | null;
  status: string;
  document_count: number;
  created_at: string;
  updated_at: string;
}

export interface CaseCreate {
  case_number: string;
  title: string;
  description?: string;
  status?: string;
}

export interface CaseListResponse {
  cases: Case[];
  total: number;
}

// ─── Documents ────────────────────────────────────────────────────

export interface Document {
  id: string;
  case_id: string;
  filename: string;
  original_filename: string;
  document_type: string;
  mime_type: string;
  file_size: number;
  file_hash: string;
  source: string | null;
  description: string | null;
  processing_status: string;
  processing_error: string | null;
  total_pages: number | null;
  uploaded_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
}

export interface DocumentPage {
  id: string;
  page_number: number;
  raw_text: string | null;
  cleaned_text: string | null;
  ocr_applied: boolean;
  created_at: string;
}

export interface ProcessingStatus {
  document_id: string;
  status: string;
  total_pages: number | null;
  error: string | null;
  progress: string | null;
}

// ─── Entities ─────────────────────────────────────────────────────

export interface EntityMention {
  id: string;
  page_number: number;
  text_start: number | null;
  text_end: number | null;
  context: string | null;
  confidence: number;
  extraction_method: string;
  created_at: string;
}

export interface Entity {
  id: string;
  document_id: string;
  entity_type: string;
  value: string;
  normalized_value: string;
  confidence: number;
  extraction_method: string;
  verification_status: string;
  verified_by: string | null;
  verified_at: string | null;
  notes: string | null;
  mentions: EntityMention[];
  created_at: string;
  updated_at: string;
}

export interface EntityListResponse {
  document_id: string;
  status: string;
  entities: Entity[];
  total: number;
}

export interface EntityUpdate {
  value?: string;
  entity_type?: string;
  notes?: string;
}

export interface EntityVerifyRequest {
  verified_by: string;
  notes?: string;
}

export interface EntityRejectRequest {
  verified_by: string;
  reason?: string;
}

// ─── Phase 2: Entity Resolution ────────────────────────────────────

export interface MatchFeature {
  feature_name: string;
  score: number;
  description: string;
}

export interface MatchCandidate {
  id: string;
  entity_a_id: string;
  entity_b_id: string;
  entity_a_value: string;
  entity_b_value: string;
  entity_a_type: string;
  entity_b_type: string;
  entity_a_document_id?: string;
  entity_b_document_id?: string;
  match_score: number;
  matching_features: MatchFeature[];
  explanation: string;
  status: string;
  created_at: string;
  reviewed_by?: string;
  reviewed_at?: string;
}

export interface MatchCandidateListResponse {
  candidates: MatchCandidate[];
  total: number;
}

export interface MatchConfirmRequest {
  reviewed_by: string;
  canonical_name?: string;
  notes?: string;
}

export interface MatchRejectRequest {
  reviewed_by: string;
  reason?: string;
}

export interface ResolutionRunRequest {
  case_id?: string;
  min_score?: number;
}

export interface ResolutionRunResponse {
  candidates_generated: number;
  case_id?: string;
}

// ─── Phase 2: Canonical Entities ───────────────────────────────────

export interface EntityAlias {
  id: string;
  entity_id: string;
  alias_value: string;
  normalized_value: string;
  source_document_id?: string;
  created_at: string;
}

export interface CanonicalEntity {
  id: string;
  entity_type: string;
  canonical_name: string;
  normalized_name: string;
  status: string;
  aliases: EntityAlias[];
  relationship_count: number;
  case_ids: string[];
  source_document_count: number;
  created_at: string;
  updated_at: string;
}

export interface CanonicalEntityListResponse {
  entities: CanonicalEntity[];
  total: number;
}

export interface CanonicalEntityDetail extends CanonicalEntity {
  source_entities: any[];
  mentions: any[];
}

// ─── Phase 2: Relationships ────────────────────────────────────────

export interface Relationship {
  id: string;
  relationship_type: string;
  source_entity_id: string;
  target_entity_id: string;
  source_entity_name: string;
  target_entity_name: string;
  source_entity_type: string;
  target_entity_type: string;
  source_document_id?: string;
  source_document_name?: string;
  source_page?: number;
  source_record_id?: string;
  extraction_method: string;
  confidence: number;
  verification_status: string;
  properties: Record<string, any>;
  case_id?: string;
  created_at: string;
  updated_at: string;
  verified_by?: string;
  verified_at?: string;
}

export interface RelationshipListResponse {
  relationships: Relationship[];
  total: number;
}

export interface RelationshipVerifyRequest {
  verified_by: string;
  notes?: string;
}

export interface RelationshipExtractRequest {
  case_id?: string;
  document_id?: string;
}

export interface RelationshipExtractResponse {
  relationships_created: number;
  case_id?: string;
  document_id?: string;
}

// ─── Phase 2: Knowledge Graph ──────────────────────────────────────

export interface GraphNode {
  id: string;
  label: string;
  entity_type: string;
  properties: {
    color?: string;
    icon?: string;
    shape?: string;
    normalized_name?: string;
    status?: string;
    [key: string]: any;
  };
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relationship_type: string;
  label: string;
  properties: Record<string, any>;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  case_id?: string;
}

export interface GraphBuildResponse {
  case_id: string;
  nodes_created: number;
  relationships_created: number;
  status: string;
}

export interface GraphPathRequest {
  source_entity_id: string;
  target_entity_id: string;
  max_depth?: number;
}

export interface GraphPathResponse {
  found: boolean;
  path: GraphNode[];
  edges: GraphEdge[];
  length: number;
}

export interface GraphSearchResult {
  id: string;
  label: string;
  entity_type: string;
  match_field: string;
}

export interface GraphValidationResponse {
  valid: boolean;
  orphan_nodes: number;
  orphan_relationships: number;
  missing_sources: number;
  details: string[];
}

export interface GraphConnectionsResponse {
  entity: GraphNode;
  connections: GraphNode[];
  edges: GraphEdge[];
}

// ─── Dashboard ────────────────────────────────────────────────────

export interface DashboardStats {
  total_documents: number;
  processed_documents: number;
  total_entities: number;
  pending_verification: number;
  verified_entities: number;
  rejected_entities: number;
  failed_documents: number;
  total_cases: number;
}

export interface Phase2DashboardStats extends DashboardStats {
  canonical_entities: number;
  potential_matches: number;
  confirmed_matches: number;
  rejected_matches: number;
  pending_review: number;
  total_relationships: number;
  verified_relationships: number;
  graph_nodes: number;
  graph_relationships: number;
  cross_case_connections: number;
}

// ─── Enums & Constants ─────────────────────────────────────────────

export const DOCUMENT_TYPES = [
  { value: 'FIR', label: 'FIR (First Information Report)' },
  { value: 'CDR', label: 'CDR (Call Detail Record)' },
  { value: 'FINANCIAL_RECORD', label: 'Financial Record' },
  { value: 'SURVEILLANCE', label: 'Surveillance Report' },
  { value: 'CRIMINAL_RECORD', label: 'Criminal Record' },
  { value: 'INTELLIGENCE_REPORT', label: 'Intelligence Report' },
  { value: 'OTHER', label: 'Other' },
] as const;

export const ENTITY_TYPES = [
  'PERSON', 'PHONE', 'LOCATION', 'ORGANIZATION',
  'ACCOUNT', 'VEHICLE', 'CASE', 'DATE', 'DEVICE', 'EMAIL',
] as const;

export const RELATIONSHIP_TYPES = [
  'CALLED', 'MEMBER_OF', 'LOCATED_AT', 'TRANSFERRED_TO',
  'ACCUSED_IN', 'OWNS', 'ASSOCIATED_WITH', 'COMMUNICATED_WITH',
] as const;

export const VERIFICATION_STATUSES = {
  UNVERIFIED: { label: 'Unverified', color: 'warning' },
  VERIFIED: { label: 'Verified', color: 'success' },
  REJECTED: { label: 'Rejected', color: 'error' },
  MODIFIED: { label: 'Modified', color: 'info' },
} as const;

export const PROCESSING_STATUSES = {
  UPLOADED: { label: 'Uploaded', icon: '📤', color: 'slate' },
  PROCESSING: { label: 'Processing', icon: '⟳', color: 'blue' },
  TEXT_EXTRACTED: { label: 'Text Extracted', icon: '📝', color: 'indigo' },
  ENTITY_EXTRACTION: { label: 'Extracting Entities', icon: '🔍', color: 'purple' },
  READY_FOR_REVIEW: { label: 'Ready for Review', icon: '⚠', color: 'amber' },
  COMPLETED: { label: 'Completed', icon: '✓', color: 'emerald' },
  FAILED: { label: 'Failed', icon: '✕', color: 'red' },
} as const;
