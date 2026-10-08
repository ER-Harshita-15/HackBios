import { useState, useCallback, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Upload, FileText, X, Loader2, CheckCircle2,
  AlertTriangle, Plus, FolderPlus, Info
} from 'lucide-react';
import { listCases, createCase, uploadDocument } from '../services/api';
import { DOCUMENT_TYPES } from '../types';
import { formatFileSize } from '../utils';

export default function DocumentUpload() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();

  const [dragOver, setDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [caseId, setCaseId] = useState(searchParams.get('caseId') || '');
  const [documentType, setDocumentType] = useState('FIR');
  const [description, setDescription] = useState('');
  const [source, setSource] = useState('');
  const [caseError, setCaseError] = useState(false);

  // Quick case creation state
  const [showNewCaseModal, setShowNewCaseModal] = useState(false);
  const [newCaseNumber, setNewCaseNumber] = useState('');
  const [newCaseTitle, setNewCaseTitle] = useState('');
  const [newCaseDesc, setNewCaseDesc] = useState('');

  const { data: casesData, isLoading: casesLoading } = useQuery({
    queryKey: ['cases'],
    queryFn: listCases,
  });

  // Auto-select case if available and not yet selected
  useEffect(() => {
    if (!caseId && casesData?.cases && casesData.cases.length > 0) {
      setCaseId(casesData.cases[0].id);
      setCaseError(false);
    }
  }, [casesData, caseId]);

  // Quick Case Creation Mutation
  const createCaseMutation = useMutation({
    mutationFn: async () => {
      const generatedNumber = newCaseNumber.trim() || `CASE-${new Date().getFullYear()}-${Math.floor(1000 + Math.random() * 9000)}`;
      const generatedTitle = newCaseTitle.trim() || 'General Investigation';
      return createCase({
        case_number: generatedNumber,
        title: generatedTitle,
        description: newCaseDesc.trim() || undefined,
        status: 'UNDER_INVESTIGATION',
      });
    },
    onSuccess: (newCase) => {
      queryClient.invalidateQueries({ queryKey: ['cases'] });
      setCaseId(newCase.id);
      setCaseError(false);
      setShowNewCaseModal(false);
      setNewCaseNumber('');
      setNewCaseTitle('');
      setNewCaseDesc('');
    },
  });

  // Document Upload Mutation
  const mutation = useMutation({
    mutationFn: async () => {
      if (!selectedFile) throw new Error('Please select a file to upload');
      if (!caseId) throw new Error('Please select or create an investigation case');

      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('case_id', caseId);
      formData.append('document_type', documentType);
      if (description) formData.append('description', description);
      if (source) formData.append('source', source);

      return uploadDocument(formData);
    },
    onSuccess: (doc) => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      navigate(`/documents/${doc.id}`);
    },
  });

  const validateAndSetFile = (file: File) => {
    const name = file.name.toLowerCase();
    const validExt = name.endsWith('.pdf') || name.endsWith('.txt') || name.endsWith('.csv');
    if (!validExt) {
      alert('Unsupported file type. Please upload PDF, TXT, or CSV files.');
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      alert('File too large. Maximum size is 50MB.');
      return;
    }

    // Auto-detect document type from filename hints
    if (name.includes('cdr') || name.includes('call')) {
      setDocumentType('CDR');
    } else if (name.includes('transaction') || name.includes('bank') || name.includes('financial')) {
      setDocumentType('FINANCIAL_RECORD');
    } else if (name.includes('fir') || name.includes('robbery') || name.includes('crime') || name.includes('police')) {
      setDocumentType('FIR');
    }

    setSelectedFile(file);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) validateAndSetFile(file);
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) validateAndSetFile(file);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!selectedFile) {
      alert('Please select or drop a file to upload.');
      return;
    }

    if (!caseId) {
      setCaseError(true);
      if (!casesData?.cases || casesData.cases.length === 0) {
        setShowNewCaseModal(true);
      }
      return;
    }

    setCaseError(false);
    mutation.mutate();
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-fade-in pb-12">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Upload Investigation Evidence</h1>
        <p className="text-slate-400 text-sm mt-1">
          Upload documents for automated processing, OCR, and traceable entity extraction.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Upload Zone */}
        <div
          className={`upload-zone ${dragOver ? 'drag-over' : ''} ${!selectedFile ? 'hover:border-blue-500/50' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => {
            if (!selectedFile) document.getElementById('file-input')?.click();
          }}
        >
          <input
            id="file-input"
            type="file"
            className="hidden"
            accept=".pdf,.txt,.csv"
            onChange={handleFileSelect}
          />

          {selectedFile ? (
            <div className="flex items-center gap-4 justify-between max-w-xl mx-auto p-3 rounded-xl bg-white/[0.04] border border-white/10">
              <div className="flex items-center gap-3 truncate">
                <div className="w-12 h-12 rounded-xl bg-blue-500/20 border border-blue-500/30 flex items-center justify-center shrink-0">
                  <FileText className="w-6 h-6 text-blue-400" />
                </div>
                <div className="text-left truncate">
                  <p className="text-white font-medium text-sm truncate">{selectedFile.name}</p>
                  <p className="text-slate-400 text-xs mt-0.5">{formatFileSize(selectedFile.size)}</p>
                </div>
              </div>
              <button
                type="button"
                className="p-2 rounded-lg hover:bg-white/10 text-slate-400 hover:text-white transition-colors shrink-0"
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedFile(null);
                  const fileInput = document.getElementById('file-input') as HTMLInputElement;
                  if (fileInput) fileInput.value = '';
                }}
                title="Remove file"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          ) : (
            <div className="py-2">
              <Upload className="w-12 h-12 text-blue-400/80 mx-auto mb-3" />
              <p className="text-white font-medium text-base">Drag & drop investigation document here</p>
              <p className="text-slate-500 text-sm mt-1">or click to browse your computer</p>
              <button
                type="button"
                className="btn-secondary mt-4 text-xs font-semibold px-4 py-2"
                onClick={() => document.getElementById('file-input')?.click()}
              >
                Browse Files
              </button>
              <p className="text-slate-600 text-xs mt-3">Supported formats: PDF, TXT, CSV (Up to 50MB)</p>
            </div>
          )}
        </div>

        {/* Metadata Form */}
        <div className="glass-card p-6 space-y-5">
          <div className="flex items-center justify-between border-b border-white/5 pb-3">
            <h3 className="text-sm font-semibold text-white uppercase tracking-wider">
              Document Information
            </h3>
            <span className="text-[11px] text-slate-500">* Required fields</span>
          </div>

          {/* Case Selection & Quick Add */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                Case *
                {caseError && <span className="text-red-400 normal-case font-normal">(Please select or create a case)</span>}
              </label>
              <button
                type="button"
                onClick={() => setShowNewCaseModal(true)}
                className="text-xs text-blue-400 hover:text-blue-300 font-medium flex items-center gap-1 transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                New Case
              </button>
            </div>

            <div className="relative">
              <select
                className={`nx-select ${caseError ? 'border-red-500/80 ring-1 ring-red-500/40' : ''}`}
                value={caseId}
                onChange={(e) => {
                  setCaseId(e.target.value);
                  if (e.target.value) setCaseError(false);
                }}
              >
                <option value="">-- Select an Investigation Case --</option>
                {casesData?.cases.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.case_number} — {c.title}
                  </option>
                ))}
              </select>
            </div>

            {/* Prompt to create case if none exist */}
            {casesData && casesData.cases.length === 0 && !casesLoading && (
              <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300 flex items-center justify-between mt-2">
                <div className="flex items-center gap-2">
                  <Info className="w-4 h-4 shrink-0" />
                  <span>No cases found in database. Create one to proceed with upload.</span>
                </div>
                <button
                  type="button"
                  onClick={() => setShowNewCaseModal(true)}
                  className="px-2.5 py-1 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 font-medium shrink-0"
                >
                  Create Case
                </button>
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-slate-400 uppercase tracking-wider block mb-1">
                Document Type *
              </label>
              <select
                className="nx-select"
                value={documentType}
                onChange={(e) => setDocumentType(e.target.value)}
              >
                {DOCUMENT_TYPES.map((dt) => (
                  <option key={dt.value} value={dt.value}>
                    {dt.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs font-medium text-slate-400 uppercase tracking-wider block mb-1">
                Source / Origin
              </label>
              <input
                className="nx-input"
                placeholder="e.g., Central Police Station, Bank Branch"
                value={source}
                onChange={(e) => setSource(e.target.value)}
              />
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-slate-400 uppercase tracking-wider block mb-1">
              Description / Investigator Notes
            </label>
            <textarea
              className="nx-input min-h-[80px] resize-none"
              placeholder="Brief context about this piece of evidence (suspects mentioned, incident summary)..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
        </div>

        {/* Validation or Mutation Error Display */}
        {caseError && (
          <div className="flex items-center gap-2 text-amber-400 text-sm bg-amber-500/10 border border-amber-500/20 rounded-lg p-3">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>Please select an investigation case above (or click <strong>+ New Case</strong> to create one) before uploading.</span>
          </div>
        )}

        {mutation.isError && (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg p-3">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>
              {(mutation.error as any)?.response?.data?.detail ||
               mutation.error.message ||
               'Upload failed. Please check backend connection and try again.'}
            </span>
          </div>
        )}

        {/* Success */}
        {mutation.isSuccess && (
          <div className="flex items-center gap-2 text-emerald-400 text-sm bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-3">
            <CheckCircle2 className="w-4 h-4" />
            Document uploaded successfully! Starting extraction pipeline...
          </div>
        )}

        {/* Submit Button */}
        <button
          type="submit"
          className="btn-primary w-full justify-center py-3.5 text-base font-semibold shadow-lg shadow-blue-500/20 transition-all cursor-pointer"
          disabled={!selectedFile || mutation.isPending}
        >
          {mutation.isPending ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Uploading & Processing Document...
            </>
          ) : (
            <>
              <Upload className="w-5 h-5" />
              Upload & Process Document
            </>
          )}
        </button>

        {!selectedFile && (
          <p className="text-center text-xs text-slate-500">
            Please choose or drag a document into the upload area above to enable processing.
          </p>
        )}
      </form>

      {/* Quick Create Case Modal */}
      {showNewCaseModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-card max-w-md w-full p-6 space-y-4 border border-blue-500/30 shadow-2xl animate-fade-in bg-[#111827]">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <div className="flex items-center gap-2">
                <FolderPlus className="w-5 h-5 text-blue-400" />
                <h3 className="font-bold text-white text-base">Create Investigation Case</h3>
              </div>
              <button
                type="button"
                onClick={() => setShowNewCaseModal(false)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-white/10 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-slate-400 uppercase tracking-wider block mb-1">
                  Case Title *
                </label>
                <input
                  className="nx-input"
                  placeholder="e.g., ATM Robbery & Money Trail"
                  value={newCaseTitle}
                  onChange={(e) => setNewCaseTitle(e.target.value)}
                  autoFocus
                />
              </div>

              <div>
                <label className="text-xs font-medium text-slate-400 uppercase tracking-wider block mb-1">
                  Case Number (Optional)
                </label>
                <input
                  className="nx-input"
                  placeholder={`e.g., CASE-${new Date().getFullYear()}-001`}
                  value={newCaseNumber}
                  onChange={(e) => setNewCaseNumber(e.target.value)}
                />
                <span className="text-[10px] text-slate-500">Leave blank to auto-generate</span>
              </div>

              <div>
                <label className="text-xs font-medium text-slate-400 uppercase tracking-wider block mb-1">
                  Description
                </label>
                <textarea
                  className="nx-input min-h-[60px] resize-none"
                  placeholder="Brief synopsis of the investigation..."
                  value={newCaseDesc}
                  onChange={(e) => setNewCaseDesc(e.target.value)}
                />
              </div>
            </div>

            {createCaseMutation.isError && (
              <div className="text-red-400 text-xs bg-red-500/10 p-2.5 rounded border border-red-500/20">
                {(createCaseMutation.error as any)?.response?.data?.detail || 'Failed to create case. Case number may already exist.'}
              </div>
            )}

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowNewCaseModal(false)}
                className="btn-secondary text-xs px-4 py-2"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => createCaseMutation.mutate()}
                disabled={createCaseMutation.isPending}
                className="btn-primary text-xs px-4 py-2"
              >
                {createCaseMutation.isPending ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Creating Case...
                  </>
                ) : (
                  'Create Case & Select'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
