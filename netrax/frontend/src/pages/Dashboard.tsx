import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  FileText, Search, Shield,
  FolderOpen, ArrowRight, Loader2, GitMerge, Users,
  Share2, Network, Sparkles
} from 'lucide-react';
import { getPhase2DashboardStats, getRecentDocuments } from '../services/api';
import { formatDate, formatFileSize, getProcessingStatusColor } from '../utils';
import { PROCESSING_STATUSES } from '../types';

export default function Dashboard() {
  const navigate = useNavigate();

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['phase2-dashboard-stats'],
    queryFn: getPhase2DashboardStats,
    refetchInterval: 5000,
  });

  const { data: recentDocs, isLoading: docsLoading } = useQuery({
    queryKey: ['recent-documents'],
    queryFn: getRecentDocuments,
    refetchInterval: 5000,
  });

  const phase1Cards = [
    {
      label: 'Total Cases',
      value: stats?.total_cases ?? 0,
      icon: FolderOpen,
      accent: '#3b82f6',
      onClick: () => navigate('/cases'),
    },
    {
      label: 'Documents Uploaded',
      value: stats?.total_documents ?? 0,
      icon: FileText,
      accent: '#8b5cf6',
      onClick: () => navigate('/documents'),
    },
    {
      label: 'Entities Extracted',
      value: stats?.total_entities ?? 0,
      icon: Search,
      accent: '#06b6d4',
      onClick: () => navigate('/documents'),
    },
    {
      label: 'Verified Entities',
      value: stats?.verified_entities ?? 0,
      icon: Shield,
      accent: '#10b981',
      onClick: () => navigate('/review'),
    },
  ];

  const phase2Cards = [
    {
      label: 'Canonical Profiles',
      value: stats?.canonical_entities ?? 0,
      icon: Users,
      accent: '#6366f1',
      description: 'Deduplicated master records',
      onClick: () => navigate('/canonical'),
    },
    {
      label: 'Pending Match Reviews',
      value: stats?.potential_matches ?? 0,
      icon: GitMerge,
      accent: '#f59e0b',
      description: 'Potential cross-doc duplicates',
      onClick: () => navigate('/resolution'),
    },
    {
      label: 'Document Relationships',
      value: stats?.total_relationships ?? 0,
      icon: Share2,
      accent: '#06b6d4',
      description: 'CDR, financial & FIR links',
      onClick: () => navigate('/relationships'),
    },
    {
      label: 'Knowledge Graph Nodes',
      value: stats?.graph_nodes ?? 0,
      icon: Network,
      accent: '#ec4899',
      description: 'Interactive graph elements',
      onClick: () => navigate('/graph'),
    },
  ];

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            Intelligence Operations Center
          </h1>
          <p className="text-slate-400 mt-1 text-sm">
            Phase 1 (Ingestion & Extraction) + Phase 2 (Entity Resolution & Knowledge Graph)
          </p>
        </div>
        <button
          onClick={() => navigate('/graph')}
          className="btn-primary flex items-center gap-2"
        >
          <Network className="w-4 h-4" />
          Open Knowledge Graph
        </button>
      </div>

      {/* Phase 2 Intelligence Highlights */}
      <div>
        <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-pink-400" />
          Phase 2 — Graph & Intelligence Metrics
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {phase2Cards.map((card) => (
            <div
              key={card.label}
              className="stat-card cursor-pointer border border-slate-800 hover:border-slate-600 transition-all"
              style={{ '--accent': card.accent } as React.CSSProperties}
              onClick={card.onClick}
            >
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs text-slate-400 font-medium uppercase tracking-wider">
                    {card.label}
                  </p>
                  <p className="text-3xl font-bold text-white mt-1.5 font-mono">
                    {statsLoading ? (
                      <Loader2 className="w-6 h-6 animate-spin text-slate-600" />
                    ) : (
                      card.value.toLocaleString()
                    )}
                  </p>
                  <p className="text-[11px] text-slate-500 mt-1">
                    {card.description}
                  </p>
                </div>
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
                  style={{ background: `${card.accent}20` }}
                >
                  <card.icon className="w-5 h-5" style={{ color: card.accent }} />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Phase 1 Ingestion Stats */}
      <div>
        <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">
          Phase 1 — Document Processing & Verification
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {phase1Cards.map((card) => (
            <div
              key={card.label}
              className="stat-card cursor-pointer border border-slate-800/80"
              style={{ '--accent': card.accent } as React.CSSProperties}
              onClick={card.onClick}
            >
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">
                    {card.label}
                  </p>
                  <p className="text-2xl font-bold text-white mt-1 font-mono">
                    {statsLoading ? (
                      <Loader2 className="w-6 h-6 animate-spin text-slate-600" />
                    ) : (
                      card.value.toLocaleString()
                    )}
                  </p>
                </div>
                <div
                  className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
                  style={{ background: `${card.accent}15` }}
                >
                  <card.icon className="w-4 h-4" style={{ color: card.accent }} />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Quick Action Workflows */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div
          onClick={() => navigate('/upload')}
          className="glass-card p-5 cursor-pointer hover:border-blue-500/50 transition-all border border-slate-800 group"
        >
          <FileText className="w-6 h-6 text-blue-400 mb-2 group-hover:scale-110 transition-transform" />
          <h3 className="text-sm font-bold text-white">Ingest New Evidence</h3>
          <p className="text-xs text-slate-400 mt-1">Upload FIRs, CDR records, bank statements or PDFs.</p>
        </div>

        <div
          onClick={() => navigate('/resolution')}
          className="glass-card p-5 cursor-pointer hover:border-amber-500/50 transition-all border border-slate-800 group"
        >
          <GitMerge className="w-6 h-6 text-amber-400 mb-2 group-hover:scale-110 transition-transform" />
          <h3 className="text-sm font-bold text-white">Resolve Cross-Doc Duplicates</h3>
          <p className="text-xs text-slate-400 mt-1">Review entity match candidates and merge aliases.</p>
        </div>

        <div
          onClick={() => navigate('/graph')}
          className="glass-card p-5 cursor-pointer hover:border-pink-500/50 transition-all border border-slate-800 group"
        >
          <Network className="w-6 h-6 text-pink-400 mb-2 group-hover:scale-110 transition-transform" />
          <h3 className="text-sm font-bold text-white">Explore Network Graph</h3>
          <p className="text-xs text-slate-400 mt-1">Cytoscape interactive multi-hop path analysis.</p>
        </div>
      </div>

      {/* Recent Documents Table */}
      <div className="glass-card p-6 border border-slate-800">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-white">Recent Documents</h2>
          <button
            onClick={() => navigate('/documents')}
            className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
          >
            View all <ArrowRight className="w-3 h-3" />
          </button>
        </div>

        {docsLoading ? (
          <div className="flex items-center justify-center p-8 text-slate-500">
            <Loader2 className="w-6 h-6 animate-spin mr-2 text-blue-500" />
            Loading documents...
          </div>
        ) : recentDocs && recentDocs.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-slate-500 uppercase border-b border-white/5">
                <tr>
                  <th className="pb-3 font-medium">Filename</th>
                  <th className="pb-3 font-medium">Type</th>
                  <th className="pb-3 font-medium">Status</th>
                  <th className="pb-3 font-medium">Size</th>
                  <th className="pb-3 font-medium">Pages</th>
                  <th className="pb-3 font-medium">Uploaded</th>
                  <th className="pb-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {recentDocs.map((doc) => {
                  const statusInfo = PROCESSING_STATUSES[doc.processing_status as keyof typeof PROCESSING_STATUSES];
                  return (
                    <tr key={doc.id} className="hover:bg-white/[0.02] transition-colors">
                      <td className="py-3 font-medium text-white max-w-[200px] truncate">
                        {doc.original_filename}
                      </td>
                      <td className="py-3">
                        <span className="badge badge-info">{doc.document_type}</span>
                      </td>
                      <td className="py-3">
                        <span className={`badge ${getProcessingStatusColor(doc.processing_status)}`}>
                          {statusInfo?.icon} {statusInfo?.label || doc.processing_status}
                        </span>
                      </td>
                      <td className="py-3 text-slate-400">{formatFileSize(doc.file_size)}</td>
                      <td className="py-3 text-slate-400">{doc.total_pages ?? '-'}</td>
                      <td className="py-3 text-slate-400">{formatDate(doc.created_at)}</td>
                      <td className="py-3 text-right">
                        <button
                          onClick={() => navigate(`/documents/${doc.id}`)}
                          className="text-blue-400 hover:text-blue-300 font-medium"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8 text-slate-500 text-xs">
            No documents uploaded yet. Go to Upload Evidence to add files.
          </div>
        )}
      </div>
    </div>
  );
}
