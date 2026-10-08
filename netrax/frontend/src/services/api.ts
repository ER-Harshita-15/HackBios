/**
 * NETRA-X API Client — Phase 1 & Phase 2
 * Centralized API service for communicating with the FastAPI backend.
 */

import axios from 'axios';
import type {
  Case, CaseCreate, CaseListResponse,
  Document, DocumentListResponse, DocumentPage,
  ProcessingStatus,
  Entity, EntityListResponse,
  DashboardStats, Phase2DashboardStats,
  EntityUpdate, EntityVerifyRequest, EntityRejectRequest,
  MatchCandidateListResponse, MatchCandidate, MatchConfirmRequest, MatchRejectRequest,
  ResolutionRunRequest, ResolutionRunResponse,
  CanonicalEntity, CanonicalEntityListResponse, CanonicalEntityDetail,
  Relationship, RelationshipListResponse, RelationshipVerifyRequest,
  RelationshipExtractRequest, RelationshipExtractResponse,
  GraphResponse, GraphBuildResponse, GraphPathRequest, GraphPathResponse,
  GraphSearchResult, GraphValidationResponse, GraphConnectionsResponse,
} from '../types';

const API_BASE = import.meta.env.VITE_API_URL || '';

const api = axios.create({
  baseURL: API_BASE ? `${API_BASE}/api` : '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// ─── Cases ─────────────────────────────────────────────────────────

export async function createCase(data: CaseCreate): Promise<Case> {
  const res = await api.post('/cases', data);
  return res.data;
}

export async function listCases(): Promise<CaseListResponse> {
  const res = await api.get('/cases');
  return res.data;
}

export async function getCase(caseId: string): Promise<Case> {
  const res = await api.get(`/cases/${caseId}`);
  return res.data;
}

// ─── Documents ────────────────────────────────────────────────────

export async function uploadDocument(formData: FormData): Promise<Document> {
  const res = await api.post('/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

export async function listDocuments(caseId?: string): Promise<DocumentListResponse> {
  const params = caseId ? { case_id: caseId } : {};
  const res = await api.get('/documents', { params });
  return res.data;
}

export async function getDocument(documentId: string): Promise<Document> {
  const res = await api.get(`/documents/${documentId}`);
  return res.data;
}

export async function processDocument(documentId: string): Promise<ProcessingStatus> {
  const res = await api.post(`/documents/${documentId}/process`);
  return res.data;
}

export async function getProcessingStatus(documentId: string): Promise<ProcessingStatus> {
  const res = await api.get(`/documents/${documentId}/status`);
  return res.data;
}

export async function getDocumentPages(documentId: string): Promise<DocumentPage[]> {
  const res = await api.get(`/documents/${documentId}/pages`);
  return res.data;
}

// ─── Entities ─────────────────────────────────────────────────────

export async function getDocumentEntities(documentId: string): Promise<EntityListResponse> {
  const res = await api.get(`/entities/by-document/${documentId}`);
  return res.data;
}

export async function getEntity(entityId: string): Promise<Entity> {
  const res = await api.get(`/entities/${entityId}`);
  return res.data;
}

export async function updateEntity(entityId: string, data: EntityUpdate): Promise<Entity> {
  const res = await api.patch(`/entities/${entityId}`, data);
  return res.data;
}

export async function verifyEntity(entityId: string, data: EntityVerifyRequest): Promise<Entity> {
  const res = await api.post(`/entities/${entityId}/verify`, data);
  return res.data;
}

export async function rejectEntity(entityId: string, data: EntityRejectRequest): Promise<Entity> {
  const res = await api.post(`/entities/${entityId}/reject`, data);
  return res.data;
}

// ─── Phase 2: Entity Resolution ────────────────────────────────────

export async function listMatchCandidates(params?: {
  status?: string;
  min_score?: number;
  skip?: number;
  limit?: number;
}): Promise<MatchCandidateListResponse> {
  const res = await api.get('/resolution/candidates', { params });
  return res.data;
}

export async function confirmMatch(
  candidateId: string,
  data?: MatchConfirmRequest
): Promise<CanonicalEntity> {
  const res = await api.post(`/resolution/candidates/${candidateId}/confirm`, data || { reviewed_by: 'investigator' });
  return res.data;
}

export async function rejectMatch(
  candidateId: string,
  data?: MatchRejectRequest
): Promise<MatchCandidate> {
  const res = await api.post(`/resolution/candidates/${candidateId}/reject`, data || { reviewed_by: 'investigator' });
  return res.data;
}

export async function runResolution(data: ResolutionRunRequest): Promise<ResolutionRunResponse> {
  const res = await api.post('/resolution/run', data);
  return res.data;
}

// ─── Phase 2: Canonical Entities ───────────────────────────────────

export async function listCanonicalEntities(params?: {
  entity_type?: string;
  status?: string;
  search?: string;
  skip?: number;
  limit?: number;
}): Promise<CanonicalEntityListResponse> {
  const res = await api.get('/canonical-entities', { params });
  return res.data;
}

export async function getCanonicalEntity(id: string): Promise<CanonicalEntityDetail> {
  const res = await api.get(`/canonical-entities/${id}`);
  return res.data;
}

export async function syncCanonicalEntities(includeUnverified = false, caseId?: string): Promise<{ message: string; synced: number }> {
  const res = await api.post('/canonical-entities/sync', null, { params: { include_unverified: includeUnverified, case_id: caseId } });
  return res.data;
}

// ─── Phase 2: Relationships ────────────────────────────────────────

export async function listRelationships(params?: {
  case_id?: string;
  relationship_type?: string;
  status?: string;
  skip?: number;
  limit?: number;
}): Promise<RelationshipListResponse> {
  const res = await api.get('/relationships', { params });
  return res.data;
}

export async function getRelationship(id: string): Promise<Relationship> {
  const res = await api.get(`/relationships/${id}`);
  return res.data;
}

export async function verifyRelationship(
  id: string,
  data?: RelationshipVerifyRequest
): Promise<Relationship> {
  const res = await api.post(`/relationships/${id}/verify`, data || { verified_by: 'investigator' });
  return res.data;
}

export async function rejectRelationship(
  id: string,
  data?: RelationshipVerifyRequest
): Promise<Relationship> {
  const res = await api.post(`/relationships/${id}/reject`, data || { verified_by: 'investigator' });
  return res.data;
}

export async function extractRelationships(
  data: RelationshipExtractRequest
): Promise<RelationshipExtractResponse> {
  const res = await api.post('/relationships/extract', data);
  return res.data;
}

// ─── Phase 2: Knowledge Graph ──────────────────────────────────────

export async function buildGraph(caseId: string, includeUnverified = false): Promise<GraphBuildResponse> {
  const res = await api.post(`/graph/build/${caseId}`, { include_unverified: includeUnverified });
  return res.data;
}

export async function getGraph(caseId: string, params?: {
  entity_types?: string;
  relationship_types?: string;
  include_unverified?: boolean;
}): Promise<GraphResponse> {
  const res = await api.get(`/graph/${caseId}`, { params });
  return res.data;
}

export async function findGraphPath(data: GraphPathRequest): Promise<GraphPathResponse> {
  const res = await api.post('/graph/path', data);
  return res.data;
}

export async function getEntityConnections(entityId: string, depth = 1): Promise<GraphConnectionsResponse> {
  const res = await api.get(`/graph/entity/${entityId}/connections`, { params: { depth } });
  return res.data;
}

export async function searchGraph(query: string, entityTypes?: string): Promise<{ results: GraphSearchResult[]; total: number }> {
  const res = await api.get('/graph/search', { params: { query, entity_types: entityTypes } });
  return res.data;
}

export async function validateGraph(caseId: string): Promise<GraphValidationResponse> {
  const res = await api.get(`/graph/validate/${caseId}`);
  return res.data;
}

export async function getCrossCaseConnections(caseId: string): Promise<any[]> {
  const res = await api.get(`/graph/cross-case/${caseId}`);
  return res.data;
}

// ─── Dashboard ────────────────────────────────────────────────────

export async function getDashboardStats(): Promise<DashboardStats> {
  const res = await api.get('/dashboard/stats');
  return res.data;
}

export async function getPhase2DashboardStats(): Promise<Phase2DashboardStats> {
  const res = await api.get('/dashboard/phase2-stats');
  return res.data;
}

export async function getRecentDocuments(): Promise<Document[]> {
  const res = await api.get('/dashboard/recent-documents');
  return res.data;
}
