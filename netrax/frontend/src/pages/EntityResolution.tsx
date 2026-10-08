import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  GitMerge, CheckCircle, XCircle, Play,
  Loader2, Filter, Sparkles, ArrowRight, ShieldCheck
} from 'lucide-react';
import { listMatchCandidates, confirmMatch, rejectMatch, runResolution } from '../services/api';
import type { MatchCandidate } from '../types';

export default function EntityResolution() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>('PENDING');
  const [minScore, setMinScore] = useState<number>(0.5);
  const [showRunModal, setShowRunModal] = useState<boolean>(false);
  const [selectedCandidate, setSelectedCandidate] = useState<MatchCandidate | null>(null);
  const [customCanonicalName, setCustomCanonicalName] = useState<string>('');

  const { data, isLoading } = useQuery({
    queryKey: ['candidates', statusFilter, minScore],
    queryFn: () => listMatchCandidates({ status: statusFilter, min_score: minScore }),
  });

  const confirmMutation = useMutation({
    mutationFn: ({ id, canonicalName }: { id: string; canonicalName?: string }) =>
      confirmMatch(id, { reviewed_by: 'investigator', canonical_name: canonicalName }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['candidates'] });
      queryClient.invalidateQueries({ queryKey: ['canonical-entities'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      setSelectedCandidate(null);
      setCustomCanonicalName('');
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id }: { id: string }) =>
      rejectMatch(id, { reviewed_by: 'investigator', reason: 'Investigator rejected linkage' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['candidates'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      setSelectedCandidate(null);
    },
  });

  const runMutation = useMutation({
    mutationFn: () => runResolution({ min_score: minScore }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['candidates'] });
      setShowRunModal(false);
    },
  });

  const candidates = data?.candidates || [];

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <GitMerge className="w-6 h-6 text-blue-400" />
            Entity Resolution
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Resolve cross-document duplicate entities into deduplicated canonical profiles.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowRunModal(true)}
            className="btn-primary flex items-center gap-2"
          >
            <Play className="w-4 h-4" />
            Run Resolution
          </button>
        </div>
      </div>

      {/* Disclaimers & Ethics */}
      <div className="p-3.5 rounded-xl bg-blue-950/30 border border-blue-800/40 flex items-center gap-3">
        <ShieldCheck className="w-5 h-5 text-blue-400 shrink-0" />
        <p className="text-xs text-blue-200/90 leading-relaxed">
          <strong className="text-blue-300">Investigative Safeguard:</strong> Match scores represent record-linkage confidence across documents, NOT suspicion or guilt. Every candidate match requires human investigator review.
        </p>
      </div>

      {/* Filter Toolbar */}
      <div className="glass-card p-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Status:</span>
          {(['PENDING', 'CONFIRMED', 'REJECTED'] as const).map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                statusFilter === s
                  ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/30'
                  : 'bg-slate-800/60 text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-400">Min Score:</span>
          <input
            type="range"
            min="0.4"
            max="1.0"
            step="0.05"
            value={minScore}
            onChange={(e) => setMinScore(parseFloat(e.target.value))}
            className="w-24 accent-blue-500 cursor-pointer"
          />
          <span className="text-xs font-mono font-semibold text-blue-400">
            {(minScore * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      {/* Candidates List */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center p-16 text-slate-500">
          <Loader2 className="w-8 h-8 animate-spin mb-3 text-blue-500" />
          <p className="text-sm">Evaluating entity match candidates...</p>
        </div>
      ) : candidates.length === 0 ? (
        <div className="glass-card p-12 text-center text-slate-400 space-y-3">
          <GitMerge className="w-12 h-12 text-slate-600 mx-auto" />
          <p className="text-base font-medium text-slate-300">No {statusFilter.toLowerCase()} match candidates</p>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Click &quot;Run Resolution&quot; to compare verified entities across documents and discover potential duplicates.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {candidates.map((candidate) => {
            const scorePct = Math.round(candidate.match_score * 100);
            const scoreColor =
              scorePct >= 85 ? 'text-emerald-400 bg-emerald-950/60 border-emerald-800/60'
              : scorePct >= 70 ? 'text-blue-400 bg-blue-950/60 border-blue-800/60'
              : 'text-amber-400 bg-amber-950/60 border-amber-800/60';

            return (
              <div
                key={candidate.id}
                className="glass-card p-5 hover:border-slate-600 transition-all border border-slate-800/80 rounded-xl space-y-4"
              >
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  {/* Entity Pair */}
                  <div className="flex items-center gap-4 flex-1">
                    {/* Entity A */}
                    <div className="flex-1 p-3.5 rounded-lg bg-slate-900/80 border border-slate-800">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-blue-900/50 text-blue-300">
                          {candidate.entity_a_type}
                        </span>
                        <span className="text-[11px] text-slate-500">Record A</span>
                      </div>
                      <p className="text-sm font-semibold text-white tracking-wide">
                        {candidate.entity_a_value}
                      </p>
                    </div>

                    <ArrowRight className="w-5 h-5 text-slate-600 shrink-0" />

                    {/* Entity B */}
                    <div className="flex-1 p-3.5 rounded-lg bg-slate-900/80 border border-slate-800">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-blue-900/50 text-blue-300">
                          {candidate.entity_b_type}
                        </span>
                        <span className="text-[11px] text-slate-500">Record B</span>
                      </div>
                      <p className="text-sm font-semibold text-white tracking-wide">
                        {candidate.entity_b_value}
                      </p>
                    </div>
                  </div>

                  {/* Score & Actions */}
                  <div className="flex items-center gap-4 shrink-0">
                    <div className={`px-3 py-2 rounded-lg border text-center ${scoreColor}`}>
                      <div className="text-lg font-bold font-mono">{scorePct}%</div>
                      <div className="text-[10px] tracking-wider uppercase font-medium">Confidence</div>
                    </div>

                    {candidate.status === 'PENDING' && (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => {
                            setSelectedCandidate(candidate);
                            setCustomCanonicalName(candidate.entity_a_value);
                          }}
                          className="px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-lg shadow-emerald-600/20 transition-all"
                        >
                          <CheckCircle className="w-4 h-4" />
                          Confirm Match
                        </button>
                        <button
                          onClick={() => rejectMutation.mutate({ id: candidate.id })}
                          disabled={rejectMutation.isPending}
                          className="px-3 py-2 rounded-lg bg-rose-600/20 hover:bg-rose-600/30 text-rose-400 border border-rose-800/40 text-xs font-semibold flex items-center gap-1.5 transition-all"
                        >
                          <XCircle className="w-4 h-4" />
                          Reject
                        </button>
                      </div>
                    )}

                    {candidate.status === 'CONFIRMED' && (
                      <span className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium bg-emerald-950/60 text-emerald-400 border border-emerald-800/50">
                        <CheckCircle className="w-3.5 h-3.5" /> Resolved & Merged
                      </span>
                    )}

                    {candidate.status === 'REJECTED' && (
                      <span className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium bg-rose-950/60 text-rose-400 border border-rose-800/50">
                        <XCircle className="w-3.5 h-3.5" /> Rejected
                      </span>
                    )}
                  </div>
                </div>

                {/* Match Features Breakdown */}
                {candidate.matching_features && candidate.matching_features.length > 0 && (
                  <div className="pt-2 border-t border-slate-800/60 flex flex-wrap items-center gap-2">
                    <span className="text-[11px] text-slate-500 flex items-center gap-1">
                      <Sparkles className="w-3 h-3 text-cyan-400" /> Evidence:
                    </span>
                    {candidate.matching_features.map((feat, idx) => (
                      <span
                        key={idx}
                        className="text-[11px] px-2 py-0.5 rounded bg-slate-800/90 text-slate-300 border border-slate-700/60"
                        title={feat.description}
                      >
                        {feat.feature_name}: <strong className="text-cyan-300">{(feat.score * 100).toFixed(0)}%</strong>
                      </span>
                    ))}
                    {candidate.explanation && (
                      <span className="text-[11px] text-slate-400 italic ml-2">
                        &quot;{candidate.explanation}&quot;
                      </span>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Confirm Modal */}
      {selectedCandidate && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="glass-card max-w-md w-full p-6 space-y-4 animate-slide-up border border-slate-700">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <CheckCircle className="w-5 h-5 text-emerald-400" />
              Confirm Canonical Entity Match
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              These records will be merged under one Canonical Entity profile. Both original document citations and evidence mentions remain intact.
            </p>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300">Canonical Display Name</label>
              <input
                type="text"
                value={customCanonicalName}
                onChange={(e) => setCustomCanonicalName(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm text-white focus:outline-none focus:border-blue-500"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setSelectedCandidate(null)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium"
              >
                Cancel
              </button>
              <button
                onClick={() =>
                  confirmMutation.mutate({
                    id: selectedCandidate.id,
                    canonicalName: customCanonicalName,
                  })
                }
                disabled={confirmMutation.isPending}
                className="btn-primary text-xs"
              >
                {confirmMutation.isPending ? 'Merging...' : 'Confirm & Merge'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Run Resolution Modal */}
      {showRunModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="glass-card max-w-md w-full p-6 space-y-4 animate-slide-up border border-slate-700">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Play className="w-5 h-5 text-blue-400" />
              Run Entity Resolution Engine
            </h3>
            <p className="text-xs text-slate-300 leading-relaxed">
              Scans all verified entities across documents, applies Jaro-Winkler, Levenshtein, phonetics, and exact identifier matching to propose link candidates.
            </p>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowRunModal(false)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium"
              >
                Cancel
              </button>
              <button
                onClick={() => runMutation.mutate()}
                disabled={runMutation.isPending}
                className="btn-primary text-xs"
              >
                {runMutation.isPending ? 'Scanning...' : 'Start Scan'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
