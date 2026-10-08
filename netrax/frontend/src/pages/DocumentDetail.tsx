import { useQuery } from '@tanstack/react-query';
import { useParams, useNavigate } from 'react-router-dom';
import {
  FileText, Loader2, Search, RefreshCcw, Clock,
  CheckCircle2, AlertTriangle, XCircle, FileSearch
} from 'lucide-react';
import { getDocument, getProcessingStatus, getDocumentPages, processDocument } from '../services/api';
import { formatDate, formatFileSize, getProcessingStatusColor } from '../utils';

export default function DocumentDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: doc, isLoading } = useQuery({
    queryKey: ['document', id],
    queryFn: () => getDocument(id!),
    enabled: !!id,
  });

  const { data: status } = useQuery({
    queryKey: ['document-status', id],
    queryFn: () => getProcessingStatus(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return s === 'PROCESSING' || s === 'TEXT_EXTRACTED' || s === 'ENTITY_EXTRACTION' ? 2000 : false;
    },
  });

  const { data: pages } = useQuery({
    queryKey: ['document-pages', id],
    queryFn: () => getDocumentPages(id!),
    enabled: !!id && (status?.status === 'READY_FOR_REVIEW' || status?.status === 'COMPLETED' || status?.status === 'TEXT_EXTRACTED'),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 animate-spin text-blue-400" />
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="text-center py-20 text-slate-500">
        <p>Document not found</p>
      </div>
    );
  }

  const isProcessing = ['PROCESSING', 'TEXT_EXTRACTED', 'ENTITY_EXTRACTION'].includes(
    status?.status || doc.processing_status
  );
  const isReady = status?.status === 'READY_FOR_REVIEW' || status?.status === 'COMPLETED';
  const isFailed = status?.status === 'FAILED';

  const pipelineSteps = [
    { key: 'UPLOADED', label: 'Uploaded', icon: FileText },
    { key: 'PROCESSING', label: 'Extracting Text', icon: Clock },
    { key: 'TEXT_EXTRACTED', label: 'Text Extracted', icon: CheckCircle2 },
    { key: 'ENTITY_EXTRACTION', label: 'Extracting Entities', icon: Search },
    { key: 'READY_FOR_REVIEW', label: 'Ready for Review', icon: AlertTriangle },
    { key: 'COMPLETED', label: 'Completed', icon: CheckCircle2 },
  ];

  const currentStep = status?.status || doc.processing_status;
  const currentIdx = pipelineSteps.findIndex((s) => s.key === currentStep);

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">{doc.original_filename}</h1>
          <p className="text-slate-400 text-sm mt-1">
            {doc.document_type} • {formatFileSize(doc.file_size)}
            {doc.source && ` • ${doc.source}`}
          </p>
        </div>
        <div className="flex gap-3">
          {isFailed && (
            <button
              className="btn-secondary"
              onClick={async () => {
                await processDocument(doc.id);
                window.location.reload();
              }}
            >
              <RefreshCcw className="w-4 h-4" /> Reprocess
            </button>
          )}
          {isReady && (
            <button
              className="btn-primary"
              onClick={() => navigate(`/review/${doc.id}`)}
            >
              <Search className="w-4 h-4" /> Review Entities
            </button>
          )}
        </div>
      </div>

      {/* Processing Pipeline */}
      <div className="glass-card p-6">
        <h2 className="text-sm font-semibold text-white uppercase tracking-wider mb-5">
          Processing Pipeline
        </h2>
        <div className="flex items-center gap-2">
          {pipelineSteps.map((step, idx) => {
            const isComplete = idx < currentIdx;
            const isCurrent = idx === currentIdx;
            const Icon = step.icon;

            return (
              <div key={step.key} className="flex items-center gap-2 flex-1">
                <div className={`flex items-center gap-2 flex-1 p-3 rounded-lg border transition-all
                  ${isComplete ? 'bg-emerald-500/10 border-emerald-500/20' :
                    isCurrent ? (isFailed ? 'bg-red-500/10 border-red-500/20' : 'bg-blue-500/10 border-blue-500/20 animate-pulse-glow') :
                    'bg-white/[0.02] border-white/5'
                  }`}>
                  {isCurrent && isProcessing ? (
                    <Loader2 className="w-4 h-4 text-blue-400 animate-spin flex-shrink-0" />
                  ) : isCurrent && isFailed ? (
                    <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                  ) : isComplete ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  ) : (
                    <Icon className="w-4 h-4 text-slate-600 flex-shrink-0" />
                  )}
                  <span className={`text-xs font-medium truncate
                    ${isComplete ? 'text-emerald-400' :
                      isCurrent ? (isFailed ? 'text-red-400' : 'text-blue-400') :
                      'text-slate-600'
                    }`}>
                    {step.label}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {isFailed && doc.processing_error && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
            <p className="text-red-400 text-sm font-medium">Processing Failed</p>
            <p className="text-red-300/70 text-xs mt-1">{doc.processing_error}</p>
          </div>
        )}
      </div>

      {/* Document Details */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="glass-card p-5">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
            File Information
          </h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-400">Filename</span>
              <span className="text-white">{doc.original_filename}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">MIME Type</span>
              <span className="text-white">{doc.mime_type}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">File Size</span>
              <span className="text-white">{formatFileSize(doc.file_size)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Pages</span>
              <span className="text-white">{doc.total_pages ?? '—'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">SHA-256</span>
              <span className="text-white font-mono text-xs truncate max-w-[200px]" title={doc.file_hash}>
                {doc.file_hash.slice(0, 16)}...
              </span>
            </div>
          </div>
        </div>

        <div className="glass-card p-5">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
            Metadata
          </h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-400">Document Type</span>
              <span className="text-white">{doc.document_type}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Source</span>
              <span className="text-white">{doc.source || '—'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Uploaded</span>
              <span className="text-white">{formatDate(doc.created_at)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Status</span>
              <span className={getProcessingStatusColor(currentStep)}>
                {currentStep}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Extracted Pages */}
      {pages && pages.length > 0 && (
        <div className="glass-card p-6">
          <h2 className="text-sm font-semibold text-white uppercase tracking-wider mb-4">
            Extracted Text ({pages.length} page{pages.length !== 1 ? 's' : ''})
          </h2>
          <div className="space-y-3">
            {pages.map((page) => (
              <details key={page.id} className="group">
                <summary className="flex items-center gap-3 p-3 rounded-lg bg-white/[0.02] border border-white/5 cursor-pointer hover:bg-white/[0.04] transition-colors">
                  <FileSearch className="w-4 h-4 text-slate-500" />
                  <span className="text-sm font-medium text-white">
                    Page {page.page_number}
                  </span>
                  {page.ocr_applied && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                      OCR
                    </span>
                  )}
                  <span className="text-xs text-slate-500 ml-auto">
                    {(page.cleaned_text || page.raw_text || '').length.toLocaleString()} chars
                  </span>
                </summary>
                <div className="mt-2 p-4 bg-black/30 rounded-lg border border-white/5 max-h-[400px] overflow-auto">
                  <pre className="text-sm text-slate-300 whitespace-pre-wrap font-mono leading-relaxed">
                    {page.cleaned_text || page.raw_text || 'No text extracted'}
                  </pre>
                </div>
              </details>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
