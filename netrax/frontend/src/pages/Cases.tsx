import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { FolderOpen, Plus, X, Loader2, FileText } from 'lucide-react';
import { listCases, createCase } from '../services/api';
import { formatDate } from '../utils';
import { useNavigate } from 'react-router-dom';

export default function Cases() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ case_number: '', title: '', description: '' });

  const { data, isLoading } = useQuery({
    queryKey: ['cases'],
    queryFn: listCases,
  });

  const mutation = useMutation({
    mutationFn: createCase,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cases'] });
      setShowCreate(false);
      setForm({ case_number: '', title: '', description: '' });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.case_number || !form.title) return;
    mutation.mutate(form);
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Cases</h1>
          <p className="text-slate-400 text-sm mt-1">Manage investigation cases</p>
        </div>
        <button className="btn-primary" onClick={() => setShowCreate(true)}>
          <Plus className="w-4 h-4" /> Create Case
        </button>
      </div>

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
          onClick={() => setShowCreate(false)}>
          <div className="glass-card p-6 w-full max-w-md animate-slide-up"
            onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold text-white">Create New Case</h2>
              <button onClick={() => setShowCreate(false)}
                className="text-slate-400 hover:text-white transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                  Case Number
                </label>
                <input
                  className="nx-input mt-1"
                  placeholder="e.g., CASE-001"
                  value={form.case_number}
                  onChange={(e) => setForm({ ...form, case_number: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                  Title
                </label>
                <input
                  className="nx-input mt-1"
                  placeholder="e.g., Operation Nightwatch"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                  Description
                </label>
                <textarea
                  className="nx-input mt-1 min-h-[80px] resize-none"
                  placeholder="Case description..."
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                />
              </div>
              {mutation.isError && (
                <p className="text-red-400 text-sm">
                  {(mutation.error as any)?.response?.data?.detail || 'Failed to create case'}
                </p>
              )}
              <div className="flex gap-3 pt-2">
                <button type="submit" className="btn-primary flex-1" disabled={mutation.isPending}>
                  {mutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                  Create Case
                </button>
                <button type="button" className="btn-secondary" onClick={() => setShowCreate(false)}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Cases List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-6 h-6 animate-spin text-blue-400" />
        </div>
      ) : data?.cases && data.cases.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.cases.map((c) => (
            <div
              key={c.id}
              className="glass-card p-5 cursor-pointer group"
              onClick={() => navigate(`/documents?case=${c.id}`)}
            >
              <div className="flex items-start justify-between mb-3">
                <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center group-hover:bg-blue-500/20 transition-colors">
                  <FolderOpen className="w-5 h-5 text-blue-400" />
                </div>
                <span className="text-[10px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  {c.status}
                </span>
              </div>
              <h3 className="font-semibold text-white text-sm">{c.case_number}</h3>
              <p className="text-white/80 text-sm mt-1">{c.title}</p>
              {c.description && (
                <p className="text-slate-500 text-xs mt-2 line-clamp-2">{c.description}</p>
              )}
              <div className="flex items-center justify-between mt-4 pt-3 border-t border-white/5">
                <div className="flex items-center gap-1.5 text-xs text-slate-500">
                  <FileText className="w-3.5 h-3.5" />
                  {c.document_count} documents
                </div>
                <span className="text-[11px] text-slate-600">{formatDate(c.created_at)}</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-20 text-slate-500">
          <FolderOpen className="w-12 h-12 mx-auto mb-4 text-slate-700" />
          <p className="text-lg">No cases yet</p>
          <p className="text-sm mt-1">Create your first investigation case to get started.</p>
          <button className="btn-primary mt-4" onClick={() => setShowCreate(true)}>
            <Plus className="w-4 h-4" /> Create Case
          </button>
        </div>
      )}
    </div>
  );
}
