import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  LayoutDashboard, Upload, FileText, Shield,
  FolderOpen, Activity, Scan, GitMerge, Users,
  Share2, Network
} from 'lucide-react';
import Dashboard from './pages/Dashboard';
import Cases from './pages/Cases';
import DocumentUpload from './pages/DocumentUpload';
import Documents from './pages/Documents';
import DocumentDetail from './pages/DocumentDetail';
import EntityReview from './pages/EntityReview';
import EntityResolution from './pages/EntityResolution';
import CanonicalEntities from './pages/CanonicalEntities';
import Relationships from './pages/Relationships';
import KnowledgeGraph from './pages/KnowledgeGraph';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 10000,
    },
  },
});

function Sidebar() {
  const phase1Links = [
    { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/cases', icon: FolderOpen, label: 'Cases' },
    { to: '/upload', icon: Upload, label: 'Upload Evidence' },
    { to: '/documents', icon: FileText, label: 'Documents' },
    { to: '/review', icon: Shield, label: 'Entity Verification' },
  ];

  const phase2Links = [
    { to: '/resolution', icon: GitMerge, label: 'Entity Resolution' },
    { to: '/canonical', icon: Users, label: 'Canonical Entities' },
    { to: '/relationships', icon: Share2, label: 'Relationships' },
    { to: '/graph', icon: Network, label: 'Knowledge Graph' },
  ];

  return (
    <aside className="sidebar w-64 h-screen shrink-0 sticky top-0 flex flex-col z-30 select-none overflow-y-auto">
      {/* Logo */}
      <div className="p-6 border-b border-white/5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 via-indigo-600 to-pink-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
            <Scan className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold bg-gradient-to-r from-blue-400 via-indigo-400 to-pink-400 bg-clip-text text-transparent">
              NETRA-X
            </h1>
            <p className="text-[10px] text-slate-500 font-medium tracking-wider uppercase">
              Phase 1 & 2 Active
            </p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-6">
        <div>
          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider px-3 mb-2">
            Phase 1: Ingestion & Extraction
          </div>
          <div className="space-y-1">
            {phase1Links.map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `sidebar-link ${isActive ? 'active' : ''}`
                }
              >
                <Icon className="w-[18px] h-[18px]" />
                {label}
              </NavLink>
            ))}
          </div>
        </div>

        <div>
          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider px-3 mb-2">
            Phase 2: Graph & Intelligence
          </div>
          <div className="space-y-1">
            {phase2Links.map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `sidebar-link ${isActive ? 'active' : ''}`
                }
              >
                <Icon className="w-[18px] h-[18px]" />
                {label}
              </NavLink>
            ))}
          </div>
        </div>
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-white/5">
        <div className="text-[11px] text-slate-600 space-y-1">
          <div className="flex items-center gap-1.5">
            <Activity className="w-3 h-3 text-emerald-500" />
            <span>Postgres & Graph Engine Online</span>
          </div>
          <p className="text-[10px] text-slate-700">
            ⚠️ Synthetic Demo Data Only
          </p>
        </div>
      </div>
    </aside>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="flex min-h-screen w-full bg-[#0a0e1a]">
          <Sidebar />
          <main className="flex-1 min-w-0 p-8">
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/cases" element={<Cases />} />
              <Route path="/upload" element={<DocumentUpload />} />
              <Route path="/documents" element={<Documents />} />
              <Route path="/documents/:id" element={<DocumentDetail />} />
              <Route path="/review" element={<EntityReview />} />
              <Route path="/review/:documentId" element={<EntityReview />} />
              {/* Phase 2 Routes */}
              <Route path="/resolution" element={<EntityResolution />} />
              <Route path="/canonical" element={<CanonicalEntities />} />
              <Route path="/relationships" element={<Relationships />} />
              <Route path="/graph" element={<KnowledgeGraph />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
