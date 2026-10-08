/**
 * NETRA-X Utility Functions
 */

import { clsx, type ClassValue } from 'clsx';

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-IN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatConfidence(confidence: number): string {
  return `${Math.round(confidence * 100)}%`;
}

export function getEntityTypeColor(type: string): string {
  const colors: Record<string, string> = {
    PERSON: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
    PHONE: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
    LOCATION: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
    ORGANIZATION: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
    ACCOUNT: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
    VEHICLE: 'bg-orange-500/20 text-orange-300 border-orange-500/30',
    CASE: 'bg-rose-500/20 text-rose-300 border-rose-500/30',
    DATE: 'bg-teal-500/20 text-teal-300 border-teal-500/30',
    DEVICE: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30',
    EMAIL: 'bg-pink-500/20 text-pink-300 border-pink-500/30',
  };
  return colors[type] || 'bg-gray-500/20 text-gray-300 border-gray-500/30';
}

export function getVerificationColor(status: string): string {
  const colors: Record<string, string> = {
    UNVERIFIED: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
    VERIFIED: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
    REJECTED: 'bg-red-500/20 text-red-300 border-red-500/30',
    MODIFIED: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  };
  return colors[status] || 'bg-gray-500/20 text-gray-300 border-gray-500/30';
}

export function getProcessingStatusColor(status: string): string {
  const colors: Record<string, string> = {
    UPLOADED: 'text-slate-400',
    PROCESSING: 'text-blue-400',
    TEXT_EXTRACTED: 'text-indigo-400',
    ENTITY_EXTRACTION: 'text-purple-400',
    READY_FOR_REVIEW: 'text-amber-400',
    COMPLETED: 'text-emerald-400',
    FAILED: 'text-red-400',
  };
  return colors[status] || 'text-gray-400';
}

export function highlightText(text: string, start: number, end: number): string {
  if (start < 0 || end > text.length || start >= end) return text;
  return text.substring(0, start) +
    '<<HIGHLIGHT>>' + text.substring(start, end) + '<</HIGHLIGHT>>' +
    text.substring(end);
}
