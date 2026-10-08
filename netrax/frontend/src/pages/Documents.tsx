import { useQuery } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { FileText, Loader2, Search } from 'lucide-react';
import { listDocuments } from '../services/api';
import { formatDate, formatFileSize, getProcessingStatusColor } from '../utils';
import { PROCESSING_STATUSES } from '../types';

export default function Documents() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const caseId = searchParams.get('case') || undefined;

  const { data, isLoading } = useQuery({
    queryKey: ['documents', caseId],
    queryFn: () => listDocuments(caseId),
    refetchInterval: 5000,
  });

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Documents</h1>
          <p className="text-slate-400 text-sm mt-1">
            {caseId ? 'Documents for selected case' : 'All investigation documents'}
          </p>
        </div>
        <button
          className="btn-primary"
          onClick={() => navigate('/upload')}
        >
          Upload New
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-6 h-6 animate-spin text-blue-400" />
        </div>
      ) : data?.documents && data.documents.length > 0 ? (
        <div className="glass-card overflow-hidden">
          <table className="nx-table">
            <thead>
              <tr>
                <th>Document</th>
                <th>Type</th>
                <th>Size</th>
                <th>Pages</th>
                <th>Status</th>
                <th>Uploaded</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.documents.map((doc) => {
                const statusInfo = PROCESSING_STATUSES[doc.processing_status as keyof typeof PROCESSING_STATUSES];
                return (
                  <tr
                    key={doc.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/documents/${doc.id}`)}
                  >
                    <td>
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-slate-500" />
                        <div>
                          <p className="font-medium text-white text-sm">
                            {doc.original_filename}
                          </p>
                          {doc.source && (
                            <p className="text-[11px] text-slate-500">{doc.source}</p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className="text-xs px-2 py-0.5 rounded bg-white/5 text-slate-300 border border-white/5">
                        {doc.document_type}
                      </span>
                    </td>
                    <td className="text-slate-400 text-sm">{formatFileSize(doc.file_size)}</td>
                    <td className="text-slate-400 text-sm">{doc.total_pages ?? '—'}</td>
                    <td>
                      <span className={`flex items-center gap-1.5 text-xs font-medium ${getProcessingStatusColor(doc.processing_status)}`}>
                        <span>{statusInfo?.icon || '•'}</span>
                        {statusInfo?.label || doc.processing_status}
                      </span>
                    </td>
                    <td className="text-slate-500 text-xs">{formatDate(doc.created_at)}</td>
                    <td>
                      {(doc.processing_status === 'READY_FOR_REVIEW' || doc.processing_status === 'COMPLETED') && (
                        <button
                          className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                          onClick={(e) => { e.stopPropagation(); navigate(`/review/${doc.id}`); }}
                        >
                          <Search className="w-3 h-3" /> Review
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-center py-20 text-slate-500">
          <FileText className="w-12 h-12 mx-auto mb-4 text-slate-700" />
          <p className="text-lg">No documents found</p>
          <p className="text-sm mt-1">Upload investigation evidence to begin processing.</p>
        </div>
      )}
    </div>
  );
}
