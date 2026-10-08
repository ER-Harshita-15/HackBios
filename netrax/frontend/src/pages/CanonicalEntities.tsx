import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Users, Search, Filter, Loader2, FileText, Share2, Tag,
  ExternalLink, X, Shield, RefreshCw
} from 'lucide-react';
import { listCanonicalEntities, getCanonicalEntity, syncCanonicalEntities } from '../services/api';
import { ENTITY_TYPES } from '../types';

export default function CanonicalEntities() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [selectedType, setSelectedType] = useState<string>('');
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['canonical-entities', selectedType, search],
    queryFn: () => listCanonicalEntities({
      entity_type: selectedType || undefined,
      search: search || undefined,
      limit: 100,
    }),
  });

  const syncMutation = useMutation({
    mutationFn: () => syncCanonicalEntities(true),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['canonical-entities'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      queryClient.invalidateQueries({ queryKey: ['phase2-stats'] });
    },
  });

  const { data: detailData, isLoading: isDetailLoading } = useQuery({
    queryKey: ['canonical-entity-detail', selectedEntityId],
    queryFn: () => (selectedEntityId ? getCanonicalEntity(selectedEntityId) : null),
    enabled: !!selectedEntityId,
  });

  const entities = data?.entities || [];

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Users className="w-6 h-6 text-indigo-400" />
            Canonical Entities
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Master deduplicated entity profiles resolved from multi-source investigative evidence.
          </p>
        </div>
        <button
          onClick={() => syncMutation.mutate()}
          disabled={syncMutation.isPending}
          className="btn-primary flex items-center gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
          {syncMutation.isPending ? 'Syncing...' : 'Sync Extracted Entities'}
        </button>
      </div>

      {/* Filter / Search Bar */}
      <div className="glass-card p-4 flex flex-col md:flex-row gap-4 items-center justify-between">
        <div className="relative flex-1 w-full">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search canonical entities or normalized aliases..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-lg bg-slate-900 border border-slate-700/80 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div className="flex items-center gap-2 w-full md:w-auto overflow-x-auto pb-1 md:pb-0">
          <Filter className="w-4 h-4 text-slate-400 shrink-0" />
          <button
            onClick={() => setSelectedType('')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${
              !selectedType
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-800 text-slate-400 hover:text-white'
            }`}
          >
            All Types
          </button>
          {ENTITY_TYPES.slice(0, 6).map((type) => (
            <button
              key={type}
              onClick={() => setSelectedType(type)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${
                selectedType === type
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:text-white'
              }`}
            >
              {type}
            </button>
          ))}
        </div>
      </div>

      {/* List / Grid */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center p-16 text-slate-500">
          <Loader2 className="w-8 h-8 animate-spin mb-3 text-indigo-500" />
          <p className="text-sm">Loading canonical entity profiles...</p>
        </div>
      ) : entities.length === 0 ? (
        <div className="glass-card p-12 text-center text-slate-400 space-y-4">
          <Users className="w-12 h-12 text-slate-600 mx-auto" />
          <p className="text-base font-medium text-slate-300">No canonical entities found</p>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Resolved profiles are formed automatically from verified entities or by synchronizing extracted entities across cases.
          </p>
          <button
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            className="btn-primary inline-flex items-center gap-2 mx-auto"
          >
            <RefreshCw className={`w-4 h-4 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
            {syncMutation.isPending ? 'Syncing...' : 'Sync Extracted Entities Now'}
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {entities.map((ent) => (
            <div
              key={ent.id}
              onClick={() => setSelectedEntityId(ent.id)}
              className="glass-card p-5 hover:border-indigo-500/60 cursor-pointer transition-all border border-slate-800 flex flex-col justify-between group"
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-950/60 text-indigo-300 border border-indigo-800/40">
                    {ent.entity_type}
                  </span>
                  <div className="flex items-center gap-2 text-[11px] text-slate-400">
                    <span className="flex items-center gap-1">
                      <Share2 className="w-3 h-3 text-cyan-400" />
                      {ent.relationship_count} rels
                    </span>
                  </div>
                </div>

                <h3 className="text-base font-bold text-white group-hover:text-indigo-300 transition-colors">
                  {ent.canonical_name}
                </h3>
                {ent.normalized_name && ent.normalized_name !== ent.canonical_name && (
                  <p className="text-xs text-slate-400 font-mono mt-0.5">
                    Norm: {ent.normalized_name}
                  </p>
                )}

                {/* Aliases Pills */}
                {ent.aliases && ent.aliases.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {ent.aliases.map((alias, i) => (
                      <span
                        key={i}
                        className="text-[10px] px-2 py-0.5 rounded bg-slate-800/90 text-slate-300 border border-slate-700/60"
                      >
                        {alias.alias_value}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div className="pt-4 mt-4 border-t border-slate-800/60 flex items-center justify-between text-xs text-slate-500">
                <span className="flex items-center gap-1">
                  <FileText className="w-3.5 h-3.5" />
                  {ent.source_document_count} doc{ent.source_document_count !== 1 ? 's' : ''}
                </span>
                <span className="text-indigo-400 flex items-center gap-1 text-[11px] font-medium group-hover:underline">
                  Inspect Profile <ExternalLink className="w-3 h-3" />
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Entity Profile Drawer / Modal */}
      {selectedEntityId && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="glass-card max-w-2xl w-full p-6 space-y-5 animate-slide-up border border-slate-700 max-h-[90vh] overflow-y-auto">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-indigo-900/50 text-indigo-300">
                  {detailData?.entity_type}
                </span>
                <h2 className="text-xl font-bold text-white mt-1.5">
                  {detailData?.canonical_name || 'Loading profile...'}
                </h2>
                <p className="text-xs text-slate-400 font-mono mt-0.5">
                  ID: {detailData?.id}
                </p>
              </div>
              <button
                onClick={() => setSelectedEntityId(null)}
                className="p-1.5 rounded-lg bg-slate-800 text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {isDetailLoading ? (
              <div className="p-8 text-center text-slate-500">
                <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-500" />
                <p className="text-xs">Loading detail records...</p>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Stats row */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 text-center">
                    <div className="text-lg font-bold text-white">{detailData?.aliases?.length || 0}</div>
                    <div className="text-[10px] text-slate-400 uppercase tracking-wider">Known Aliases</div>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 text-center">
                    <div className="text-lg font-bold text-white">{detailData?.relationship_count || 0}</div>
                    <div className="text-[10px] text-slate-400 uppercase tracking-wider">Relationships</div>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 text-center">
                    <div className="text-lg font-bold text-white">{detailData?.source_document_count || 0}</div>
                    <div className="text-[10px] text-slate-400 uppercase tracking-wider">Source Docs</div>
                  </div>
                </div>

                {/* Aliases List */}
                <div>
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-1.5">
                    <Tag className="w-3.5 h-3.5 text-indigo-400" />
                    Source Mentions & Variations
                  </h4>
                  <div className="space-y-2">
                    {detailData?.aliases?.map((alias, idx) => (
                      <div
                        key={idx}
                        className="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 flex items-center justify-between text-xs"
                      >
                        <span className="font-medium text-white">{alias.alias_value}</span>
                        <span className="text-slate-500 font-mono text-[11px]">
                          Norm: {alias.normalized_value}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Mentions / Evidence */}
                {detailData?.mentions && detailData.mentions.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-1.5">
                      <Shield className="w-3.5 h-3.5 text-emerald-400" />
                      Document Evidence Snippets
                    </h4>
                    <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                      {detailData.mentions.map((m: any, idx: number) => (
                        <div
                          key={idx}
                          className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800/80 text-xs space-y-1"
                        >
                          <div className="flex items-center justify-between text-[10px] text-slate-500">
                            <span>Page {m.page_number}</span>
                            <span>Method: {m.extraction_method}</span>
                          </div>
                          {m.context && (
                            <p className="text-slate-300 italic font-serif">
                              &quot;{m.context}&quot;
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
