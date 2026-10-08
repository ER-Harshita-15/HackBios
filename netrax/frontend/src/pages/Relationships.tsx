import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Share2, CheckCircle, XCircle, Play, Filter, Loader2,
  FileText, ArrowRight, ShieldCheck
} from 'lucide-react';
import { listRelationships, verifyRelationship, rejectRelationship, extractRelationships, listCases } from '../services/api';
import { RELATIONSHIP_TYPES } from '../types';

export default function Relationships() {
  const queryClient = useQueryClient();
  const [selectedType, setSelectedType] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [selectedCaseId, setSelectedCaseId] = useState<string>('');
  const [showExtractModal, setShowExtractModal] = useState<boolean>(false);

  const { data: casesData } = useQuery({
    queryKey: ['cases'],
    queryFn: listCases,
  });

  const { data, isLoading } = useQuery({
    queryKey: ['relationships', selectedType, selectedStatus, selectedCaseId],
    queryFn: () => listRelationships({
      relationship_type: selectedType || undefined,
      status: selectedStatus || undefined,
      case_id: selectedCaseId || undefined,
      limit: 100,
    }),
  });

  const verifyMutation = useMutation({
    mutationFn: (id: string) => verifyRelationship(id, { verified_by: 'investigator' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['relationships'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      queryClient.invalidateQueries({ queryKey: ['graph'] });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: (id: string) => rejectRelationship(id, { verified_by: 'investigator' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['relationships'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      queryClient.invalidateQueries({ queryKey: ['graph'] });
    },
  });

  const extractMutation = useMutation({
    mutationFn: () => extractRelationships({ case_id: selectedCaseId || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['relationships'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      setShowExtractModal(false);
    },
  });

  const relationships = data?.relationships || [];

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Share2 className="w-6 h-6 text-cyan-400" />
            Evidence-Backed Relationships
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Relationships extracted from CDR, financial transactions, FIR co-occurrences, and intelligence records.
          </p>
        </div>
        <button
          onClick={() => setShowExtractModal(true)}
          className="btn-primary flex items-center gap-2"
        >
          <Play className="w-4 h-4" />
          Extract Relationships
        </button>
      </div>

      {/* Investigative Safeguard */}
      <div className="p-3.5 rounded-xl bg-cyan-950/30 border border-cyan-800/40 flex items-center gap-3">
        <ShieldCheck className="w-5 h-5 text-cyan-400 shrink-0" />
        <p className="text-xs text-cyan-200/90 leading-relaxed">
          <strong className="text-cyan-300">Investigative Safeguard:</strong> Extracted relationships state what the documentary evidence records (e.g. phone call made, bank transfer executed). They do not infer criminal culpability.
        </p>
      </div>

      {/* Filter Toolbar */}
      <div className="glass-card p-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={selectedCaseId}
            onChange={(e) => setSelectedCaseId(e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-white focus:outline-none focus:border-cyan-500"
          >
            <option value="">All Cases</option>
            {casesData?.cases.map((c) => (
              <option key={c.id} value={c.id}>
                {c.case_number} — {c.title}
              </option>
            ))}
          </select>

          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-white focus:outline-none focus:border-cyan-500"
          >
            <option value="">All Relationship Types</option>
            {RELATIONSHIP_TYPES.map((rt) => (
              <option key={rt} value={rt}>
                {rt}
              </option>
            ))}
          </select>

          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-white focus:outline-none focus:border-cyan-500"
          >
            <option value="">All Statuses</option>
            <option value="UNVERIFIED">Unverified</option>
            <option value="VERIFIED">Verified</option>
            <option value="REJECTED">Rejected</option>
          </select>
        </div>

        <div className="text-xs text-slate-400 font-mono">
          Showing {relationships.length} of {data?.total || 0} relationships
        </div>
      </div>

      {/* Relationships Cards */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center p-16 text-slate-500">
          <Loader2 className="w-8 h-8 animate-spin mb-3 text-cyan-500" />
          <p className="text-sm">Loading relationships and evidence trails...</p>
        </div>
      ) : relationships.length === 0 ? (
        <div className="glass-card p-12 text-center text-slate-400 space-y-3">
          <Share2 className="w-12 h-12 text-slate-600 mx-auto" />
          <p className="text-base font-medium text-slate-300">No relationships found</p>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Click &quot;Extract Relationships&quot; to parse communications, money flows, and associations from your uploaded documents.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {relationships.map((rel) => {
            const confPct = Math.round(rel.confidence * 100);
            return (
              <div
                key={rel.id}
                className="glass-card p-4 hover:border-slate-600 transition-all border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                {/* Node-to-Node Visual */}
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  {/* Source */}
                  <div className="p-3 rounded-lg bg-slate-900/90 border border-slate-800 flex-1 min-w-0">
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-blue-900/40 text-blue-300">
                      {rel.source_entity_type || 'ENTITY'}
                    </span>
                    <p className="text-sm font-semibold text-white truncate mt-1">
                      {rel.source_entity_name || rel.source_entity_id.slice(0, 8)}
                    </p>
                  </div>

                  {/* Relationship Badge */}
                  <div className="flex flex-col items-center shrink-0 px-2">
                    <span className="text-[10px] font-mono font-bold uppercase px-2.5 py-1 rounded-full bg-cyan-950 text-cyan-300 border border-cyan-800/60 shadow-sm">
                      {rel.relationship_type}
                    </span>
                    <ArrowRight className="w-4 h-4 text-cyan-500/70 mt-1" />
                  </div>

                  {/* Target */}
                  <div className="p-3 rounded-lg bg-slate-900/90 border border-slate-800 flex-1 min-w-0">
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-indigo-900/40 text-indigo-300">
                      {rel.target_entity_type || 'ENTITY'}
                    </span>
                    <p className="text-sm font-semibold text-white truncate mt-1">
                      {rel.target_entity_name || rel.target_entity_id.slice(0, 8)}
                    </p>
                  </div>
                </div>

                {/* Provenance & Metadata */}
                <div className="flex flex-wrap md:flex-col items-start md:items-end justify-between gap-2 shrink-0 md:min-w-[200px]">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-mono text-slate-400">
                      Method: <strong className="text-slate-300">{rel.extraction_method}</strong>
                    </span>
                    <span className="text-[11px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-cyan-400">
                      {confPct}% conf
                    </span>
                  </div>

                  {rel.source_document_name && (
                    <div className="flex items-center gap-1 text-[11px] text-slate-400 truncate max-w-[220px]">
                      <FileText className="w-3 h-3 shrink-0 text-slate-500" />
                      <span className="truncate">{rel.source_document_name}</span>
                      {rel.source_page && <span>(p.{rel.source_page})</span>}
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex items-center gap-2 mt-1">
                    {rel.verification_status === 'UNVERIFIED' ? (
                      <>
                        <button
                          onClick={() => verifyMutation.mutate(rel.id)}
                          disabled={verifyMutation.isPending}
                          className="px-2.5 py-1 rounded bg-emerald-600/80 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1 transition-all"
                        >
                          <CheckCircle className="w-3.5 h-3.5" /> Verify
                        </button>
                        <button
                          onClick={() => rejectMutation.mutate(rel.id)}
                          disabled={rejectMutation.isPending}
                          className="px-2.5 py-1 rounded bg-rose-600/20 hover:bg-rose-600/30 text-rose-400 border border-rose-800/40 text-xs font-semibold flex items-center gap-1 transition-all"
                        >
                          <XCircle className="w-3.5 h-3.5" /> Reject
                        </button>
                      </>
                    ) : rel.verification_status === 'VERIFIED' ? (
                      <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-400">
                        <CheckCircle className="w-3.5 h-3.5" /> Verified
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs font-medium text-rose-400">
                        <XCircle className="w-3.5 h-3.5" /> Rejected
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Extract Modal */}
      {showExtractModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="glass-card max-w-md w-full p-6 space-y-4 animate-slide-up border border-slate-700">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Play className="w-5 h-5 text-cyan-400" />
              Extract Documentary Relationships
            </h3>
            <p className="text-xs text-slate-300 leading-relaxed">
              Processes CDR records for calls/durations, financial ledgers for monetary flows, and FIR/case narratives for co-occurrences.
            </p>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowExtractModal(false)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium"
              >
                Cancel
              </button>
              <button
                onClick={() => extractMutation.mutate()}
                disabled={extractMutation.isPending}
                className="btn-primary text-xs"
              >
                {extractMutation.isPending ? 'Extracting...' : 'Run Extraction'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
