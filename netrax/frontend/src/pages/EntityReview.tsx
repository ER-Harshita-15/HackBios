import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Shield, CheckCircle2, XCircle, Edit3, Loader2,
  FileText, Search, Eye, X, Save
} from 'lucide-react';
import {
  listDocuments, getDocumentEntities, getDocumentPages,
  verifyEntity, rejectEntity, updateEntity
} from '../services/api';
import {
  formatConfidence, getEntityTypeColor, getVerificationColor
} from '../utils';
import type { Entity, DocumentPage } from '../types';

export default function EntityReview() {
  const { documentId } = useParams<{ documentId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const activeDocId = documentId || '';
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
  const [filterType, setFilterType] = useState('ALL');
  const [filterStatus, setFilterStatus] = useState('ALL');
  const [editingEntity, setEditingEntity] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');

  // Fetch documents for picker
  const { data: docsData } = useQuery({
    queryKey: ['documents'],
    queryFn: () => listDocuments(),
    enabled: !documentId,
  });

  // Fetch entities
  const { data: entitiesData, isLoading: entitiesLoading } = useQuery({
    queryKey: ['entities', activeDocId],
    queryFn: () => getDocumentEntities(activeDocId),
    enabled: !!activeDocId,
  });

  // Fetch pages for evidence viewer
  const { data: pages } = useQuery({
    queryKey: ['document-pages', activeDocId],
    queryFn: () => getDocumentPages(activeDocId),
    enabled: !!activeDocId,
  });

  // Verify mutation
  const verifyMutation = useMutation({
    mutationFn: (entityId: string) =>
      verifyEntity(entityId, { verified_by: 'investigator' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entities', activeDocId] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
    },
  });

  // Reject mutation
  const rejectMutation = useMutation({
    mutationFn: (entityId: string) =>
      rejectEntity(entityId, { verified_by: 'investigator', reason: 'Incorrect extraction' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entities', activeDocId] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
    },
  });

  // Edit mutation
  const editMutation = useMutation({
    mutationFn: ({ entityId, value }: { entityId: string; value: string }) =>
      updateEntity(entityId, { value }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entities', activeDocId] });
      setEditingEntity(null);
    },
  });

  // Filtered entities
  const filteredEntities = useMemo(() => {
    if (!entitiesData?.entities) return [];
    return entitiesData.entities.filter((e) => {
      if (filterType !== 'ALL' && e.entity_type !== filterType) return false;
      if (filterStatus !== 'ALL' && e.verification_status !== filterStatus) return false;
      return true;
    });
  }, [entitiesData, filterType, filterStatus]);

  // Get context for selected entity
  const selectedMention = selectedEntity?.mentions?.[0];
  const selectedPage = pages?.find(
    (p) => p.page_number === selectedMention?.page_number
  );

  // Highlight text in context
  const renderHighlightedContext = (page: DocumentPage, entity: Entity) => {
    const text = page.cleaned_text || page.raw_text || '';
    const mention = entity.mentions?.find(
      (m) => m.page_number === page.page_number
    );
    if (!mention || mention.text_start == null || mention.text_end == null) {
      // Try to find entity value in text
      const idx = text.toLowerCase().indexOf(entity.value.toLowerCase());
      if (idx === -1) return <span>{text}</span>;
      return (
        <>
          <span>{text.slice(Math.max(0, idx - 200), idx)}</span>
          <mark className="evidence-highlight">{text.slice(idx, idx + entity.value.length)}</mark>
          <span>{text.slice(idx + entity.value.length, idx + entity.value.length + 200)}</span>
        </>
      );
    }

    const start = Math.max(0, mention.text_start - 200);
    const end = Math.min(text.length, mention.text_end + 200);

    return (
      <>
        <span>{text.slice(start, mention.text_start)}</span>
        <mark className="evidence-highlight">
          {text.slice(mention.text_start, mention.text_end)}
        </mark>
        <span>{text.slice(mention.text_end, end)}</span>
      </>
    );
  };

  // Document picker for review page without documentId
  if (!activeDocId) {
    const reviewableDocs = docsData?.documents.filter(
      (d) => d.processing_status === 'READY_FOR_REVIEW' || d.processing_status === 'COMPLETED'
    );
    return (
      <div className="space-y-6 animate-fade-in">
        <div>
          <h1 className="text-2xl font-bold text-white">Entity Review</h1>
          <p className="text-slate-400 text-sm mt-1">
            Select a document to review extracted entities
          </p>
        </div>
        {reviewableDocs && reviewableDocs.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {reviewableDocs.map((doc) => (
              <div
                key={doc.id}
                className="glass-card p-5 cursor-pointer hover:border-blue-500/30 transition-colors"
                onClick={() => navigate(`/review/${doc.id}`)}
              >
                <div className="flex items-center gap-3 mb-3">
                  <FileText className="w-5 h-5 text-blue-400" />
                  <h3 className="text-sm font-medium text-white truncate">
                    {doc.original_filename}
                  </h3>
                </div>
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <span>{doc.document_type}</span>
                  <span>•</span>
                  <span>{doc.total_pages ?? '?'} pages</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-20 text-slate-500">
            <Shield className="w-12 h-12 mx-auto mb-4 text-slate-700" />
            <p>No documents ready for review</p>
            <p className="text-sm mt-1">Upload and process documents first.</p>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Entity Review</h1>
          <p className="text-slate-400 text-sm mt-1">
            AI-Extracted Entities — {filteredEntities.length} entities
          </p>
        </div>
        <div className="flex gap-2">
          <select
            className="nx-select text-xs w-auto"
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
          >
            <option value="ALL">All Types</option>
            {['PERSON', 'PHONE', 'LOCATION', 'ORGANIZATION', 'EMAIL', 'VEHICLE', 'CASE', 'DATE', 'DEVICE', 'ACCOUNT'].map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <select
            className="nx-select text-xs w-auto"
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
          >
            <option value="ALL">All Statuses</option>
            <option value="UNVERIFIED">Unverified</option>
            <option value="VERIFIED">Verified</option>
            <option value="REJECTED">Rejected</option>
            <option value="MODIFIED">Modified</option>
          </select>
        </div>
      </div>

      {/* Split Screen */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 min-h-[600px]">
        {/* Left: Entity List */}
        <div className="glass-card p-4 overflow-auto max-h-[75vh]">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 px-1">
            Extracted Entities
          </h3>
          {entitiesLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-5 h-5 animate-spin text-blue-400" />
            </div>
          ) : filteredEntities.length > 0 ? (
            <div className="space-y-2">
              {filteredEntities.map((entity) => (
                <div
                  key={entity.id}
                  className={`p-3 rounded-lg border transition-all cursor-pointer
                    ${selectedEntity?.id === entity.id
                      ? 'border-blue-500/40 bg-blue-500/5'
                      : 'border-white/5 bg-white/[0.02] hover:bg-white/[0.04]'
                    }`}
                  onClick={() => setSelectedEntity(entity)}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`entity-badge ${getEntityTypeColor(entity.entity_type)}`}>
                          {entity.entity_type}
                        </span>
                        <span className={`entity-badge ${getVerificationColor(entity.verification_status)}`}>
                          {entity.verification_status}
                        </span>
                      </div>

                      {editingEntity === entity.id ? (
                        <div className="flex items-center gap-2 mt-2">
                          <input
                            className="nx-input text-sm py-1"
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            autoFocus
                          />
                          <button
                            className="p-1 text-emerald-400 hover:text-emerald-300"
                            onClick={(e) => {
                              e.stopPropagation();
                              editMutation.mutate({ entityId: entity.id, value: editValue });
                            }}
                          >
                            <Save className="w-4 h-4" />
                          </button>
                          <button
                            className="p-1 text-slate-400 hover:text-slate-300"
                            onClick={(e) => { e.stopPropagation(); setEditingEntity(null); }}
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      ) : (
                        <p className="text-white font-medium text-sm truncate mt-1">
                          {entity.value}
                        </p>
                      )}

                      <div className="flex items-center gap-3 mt-2">
                        <div className="flex items-center gap-1.5">
                          <div className="confidence-bar w-16">
                            <div
                              className="confidence-fill"
                              style={{
                                width: `${entity.confidence * 100}%`,
                                background: entity.confidence > 0.9
                                  ? '#10b981'
                                  : entity.confidence > 0.7
                                  ? '#f59e0b'
                                  : '#ef4444',
                              }}
                            />
                          </div>
                          <span className="text-xs text-slate-400">
                            {formatConfidence(entity.confidence)}
                          </span>
                        </div>
                        <span className="text-[10px] text-slate-600 uppercase">
                          {entity.extraction_method}
                        </span>
                        {entity.mentions?.length > 0 && (
                          <span className="text-[11px] text-slate-500">
                            Page {entity.mentions[0].page_number}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Action buttons */}
                    {entity.verification_status === 'UNVERIFIED' && (
                      <div className="flex flex-col gap-1 flex-shrink-0">
                        <button
                          className="btn-success text-[10px] py-1 px-2"
                          onClick={(e) => {
                            e.stopPropagation();
                            verifyMutation.mutate(entity.id);
                          }}
                          disabled={verifyMutation.isPending}
                        >
                          <CheckCircle2 className="w-3 h-3" /> Verify
                        </button>
                        <button
                          className="btn-danger text-[10px] py-1 px-2"
                          onClick={(e) => {
                            e.stopPropagation();
                            rejectMutation.mutate(entity.id);
                          }}
                          disabled={rejectMutation.isPending}
                        >
                          <XCircle className="w-3 h-3" /> Reject
                        </button>
                        <button
                          className="btn-secondary text-[10px] py-1 px-2"
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditingEntity(entity.id);
                            setEditValue(entity.value);
                          }}
                        >
                          <Edit3 className="w-3 h-3" /> Edit
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-slate-500">
              <Search className="w-8 h-8 mx-auto mb-2 text-slate-700" />
              <p className="text-sm">No entities found</p>
            </div>
          )}
        </div>

        {/* Right: Evidence Viewer */}
        <div className="glass-card p-4 overflow-auto max-h-[75vh]">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 px-1">
            Source Document
          </h3>

          {selectedEntity && selectedPage ? (
            <div className="space-y-4">
              {/* Entity Info */}
              <div className="p-3 rounded-lg bg-blue-500/5 border border-blue-500/20">
                <div className="flex items-center gap-2 mb-2">
                  <Eye className="w-4 h-4 text-blue-400" />
                  <span className="text-sm font-medium text-white">
                    Evidence for: {selectedEntity.value}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs text-slate-400">
                  <span className={`entity-badge ${getEntityTypeColor(selectedEntity.entity_type)}`}>
                    {selectedEntity.entity_type}
                  </span>
                  <span>Confidence: {formatConfidence(selectedEntity.confidence)}</span>
                  <span>Page {selectedMention?.page_number}</span>
                </div>
              </div>

              {/* Context */}
              {selectedMention?.context && (
                <div className="p-4 rounded-lg bg-black/30 border border-white/5">
                  <p className="text-[10px] uppercase tracking-wider text-slate-600 mb-2">
                    Extraction Context
                  </p>
                  <p className="text-sm text-slate-300 leading-relaxed font-mono">
                    "...{selectedMention.context}..."
                  </p>
                </div>
              )}

              {/* Full Page Text with Highlight */}
              <div>
                <p className="text-[10px] uppercase tracking-wider text-slate-600 mb-2 px-1">
                  Page {selectedPage.page_number} — Full Text
                </p>
                <div className="p-4 bg-black/30 rounded-lg border border-white/5 max-h-[400px] overflow-auto">
                  <pre className="text-sm text-slate-300 whitespace-pre-wrap font-mono leading-relaxed">
                    {renderHighlightedContext(selectedPage, selectedEntity)}
                  </pre>
                </div>
              </div>

              {/* All mentions */}
              {selectedEntity.mentions.length > 1 && (
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-slate-600 mb-2 px-1">
                    All Mentions ({selectedEntity.mentions.length})
                  </p>
                  <div className="space-y-2">
                    {selectedEntity.mentions.map((m) => (
                      <div key={m.id} className="p-3 rounded-lg bg-white/[0.02] border border-white/5 text-xs">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-slate-400">Page {m.page_number}</span>
                          <span className="text-slate-600">•</span>
                          <span className="text-slate-400">
                            {formatConfidence(m.confidence)} ({m.extraction_method})
                          </span>
                        </div>
                        {m.context && (
                          <p className="text-slate-300 font-mono truncate">
                            "...{m.context}..."
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : selectedEntity ? (
            <div className="text-center py-12 text-slate-500">
              <p className="text-sm">Loading evidence...</p>
            </div>
          ) : (
            <div className="text-center py-20 text-slate-500">
              <Eye className="w-10 h-10 mx-auto mb-3 text-slate-700" />
              <p className="text-sm">Select an entity to view its source evidence</p>
              <p className="text-xs text-slate-600 mt-1">
                Click on any entity in the left panel
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Disclaimer */}
      <div className="text-center text-[10px] text-slate-600 mt-4">
        ⚠️ Confidence scores represent extraction confidence, not guilt or criminality.
        All results require human verification.
      </div>
    </div>
  );
}
