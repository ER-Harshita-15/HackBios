import { useEffect, useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import cytoscape from 'cytoscape';
import {
  Network, RefreshCw, ZoomIn, ZoomOut, Maximize2,
  Route, Download, X
} from 'lucide-react';
import {
  listCases, getGraph, buildGraph, findGraphPath,
  getCrossCaseConnections
} from '../services/api';

export default function KnowledgeGraph() {
  const queryClient = useQueryClient();
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);

  const [selectedCaseId, setSelectedCaseId] = useState<string>('');
  const [selectedLayout, setSelectedLayout] = useState<string>('cose');
  const [selectedNode, setSelectedNode] = useState<any | null>(null);
  const [pathSource, setPathSource] = useState<string>('');
  const [pathTarget, setPathTarget] = useState<string>('');
  const [showPathModal, setShowPathModal] = useState<boolean>(false);
  const [showCrossCase, setShowCrossCase] = useState<boolean>(false);
  const [crossCaseData, setCrossCaseData] = useState<any[]>([]);

  // Fetch Cases
  const { data: casesData } = useQuery({
    queryKey: ['cases'],
    queryFn: listCases,
  });

  // Set default case if not selected
  useEffect(() => {
    if (!selectedCaseId && casesData?.cases && casesData.cases.length > 0) {
      setSelectedCaseId(casesData.cases[0].id);
    }
  }, [casesData, selectedCaseId]);

  // Fetch Graph
  const { data: graphData, isLoading: isGraphLoading, refetch: refetchGraph } = useQuery({
    queryKey: ['graph', selectedCaseId],
    queryFn: () => (selectedCaseId ? getGraph(selectedCaseId) : null),
    enabled: !!selectedCaseId,
  });

  // Build Graph Mutation
  const buildMutation = useMutation({
    mutationFn: (caseId: string) => buildGraph(caseId, true),
    onSuccess: () => {
      refetchGraph();
      queryClient.invalidateQueries({ queryKey: ['graph'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
    },
  });

  // Shortest Path Mutation
  const pathMutation = useMutation({
    mutationFn: () => findGraphPath({
      source_entity_id: pathSource,
      target_entity_id: pathTarget,
      max_depth: 5,
    }),
    onSuccess: (data) => {
      if (data.found && cyRef.current) {
        const nodeIds = data.path.map((n) => n.id);
        // Highlight in Cytoscape
        cyRef.current.elements().removeClass('highlighted');
        nodeIds.forEach((id) => {
          cyRef.current?.$(`#${id}`).addClass('highlighted');
        });
        data.edges.forEach((e) => {
          cyRef.current?.$(`#${e.id}`).addClass('highlighted');
        });
      } else {
        alert('No path found between these entities within 5 hops.');
      }
    },
  });

  // Cross-case query
  const checkCrossCase = async () => {
    if (!selectedCaseId) return;
    try {
      const res = await getCrossCaseConnections(selectedCaseId);
      setCrossCaseData(res);
      setShowCrossCase(true);
    } catch (e) {
      console.error(e);
    }
  };

  // Initialize and update Cytoscape
  useEffect(() => {
    if (!containerRef.current) return;

    if (!graphData || !graphData.nodes || graphData.nodes.length === 0) {
      if (cyRef.current) {
        cyRef.current.destroy();
        cyRef.current = null;
      }
      return;
    }

    const elements: cytoscape.ElementDefinition[] = [];

    // Nodes
    graphData.nodes.forEach((n) => {
      elements.push({
        group: 'nodes',
        data: {
          id: n.id,
          label: n.label,
          type: n.entity_type,
          color: n.properties?.color || '#3b82f6',
          shape: n.properties?.shape || 'ellipse',
        },
      });
    });

    // Edges
    graphData.edges.forEach((e) => {
      elements.push({
        group: 'edges',
        data: {
          id: e.id,
          source: e.source,
          target: e.target,
          label: e.relationship_type,
        },
      });
    });

    if (cyRef.current) {
      cyRef.current.destroy();
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements: elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': 'data(color)',
            'label': 'data(label)',
            'color': '#f8fafc',
            'font-size': '11px',
            'font-family': 'Inter, sans-serif',
            'font-weight': 'bold',
            'text-valign': 'bottom',
            'text-margin-y': 6,
            'text-background-color': '#0f172a',
            'text-background-opacity': 0.8,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
            'width': 36,
            'height': 36,
            'border-width': 2,
            'border-color': '#ffffff30',
          },
        },
        {
          selector: 'edge',
          style: {
            'width': 2,
            'line-color': '#334155',
            'target-arrow-color': '#334155',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'label': 'data(label)',
            'font-size': '9px',
            'color': '#94a3b8',
            'text-background-color': '#0b0f19',
            'text-background-opacity': 0.85,
            'text-background-padding': '2px',
          },
        },
        {
          selector: '.highlighted',
          style: {
            'background-color': '#ec4899',
            'line-color': '#ec4899',
            'target-arrow-color': '#ec4899',
            'border-color': '#f43f5e',
            'border-width': 4,
            'width': 44,
            'height': 44,
          },
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 4,
            'border-color': '#38bdf8',
            'border-opacity': 1,
          },
        },
      ],
      layout: {
        name: selectedLayout,
        animate: false,
        padding: 50,
      } as any,
    });

    cy.on('tap', 'node', (evt) => {
      const node = evt.target;
      setSelectedNode(node.data());
    });

    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        setSelectedNode(null);
      }
    });

    cyRef.current = cy;

    return () => {
      if (cyRef.current) {
        cyRef.current.destroy();
        cyRef.current = null;
      }
    };
  }, [graphData, selectedLayout]);

  const handleExportPNG = () => {
    if (!cyRef.current) return;
    const png64 = cyRef.current.png({ full: true, bg: '#0a0e1a' });
    const a = document.createElement('a');
    a.href = png64;
    a.download = `knowledge_graph_${selectedCaseId.slice(0, 8)}.png`;
    a.click();
  };

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Network className="w-6 h-6 text-pink-400" />
            Knowledge Graph
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Interactive multi-relational intelligence graph connecting persons, phones, accounts, vehicles, and FIR records.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Case Picker */}
          <select
            value={selectedCaseId}
            onChange={(e) => setSelectedCaseId(e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-white focus:outline-none focus:border-pink-500"
          >
            {casesData?.cases.map((c) => (
              <option key={c.id} value={c.id}>
                {c.case_number} — {c.title}
              </option>
            ))}
          </select>

          <button
            onClick={() => selectedCaseId && buildMutation.mutate(selectedCaseId)}
            disabled={buildMutation.isPending || !selectedCaseId}
            className="btn-primary text-xs flex items-center gap-1.5"
            title="Rebuild and synchronize knowledge graph projection"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${buildMutation.isPending ? 'animate-spin' : ''}`} />
            {buildMutation.isPending ? 'Syncing...' : 'Build Graph'}
          </button>

          <button
            onClick={() => setShowPathModal(true)}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold flex items-center gap-1.5 border border-slate-700"
          >
            <Route className="w-3.5 h-3.5 text-pink-400" />
            Shortest Path
          </button>

          <button
            onClick={checkCrossCase}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold flex items-center gap-1.5 border border-slate-700"
          >
            Cross-Case Links
          </button>

          <button
            onClick={handleExportPNG}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700"
            title="Export as PNG"
          >
            <Download className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Canvas Area */}
      <div className="relative glass-card border border-slate-800 rounded-xl overflow-hidden h-[680px]">
        {/* Graph Controls Overlay */}
        <div className="absolute top-4 left-4 z-10 flex items-center gap-2 bg-slate-900/90 backdrop-blur-md p-1.5 rounded-lg border border-slate-700/80 shadow-xl">
          <button
            onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 1.2)}
            className="p-1.5 rounded hover:bg-slate-800 text-slate-300 hover:text-white"
            title="Zoom In"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 0.8)}
            className="p-1.5 rounded hover:bg-slate-800 text-slate-300 hover:text-white"
            title="Zoom Out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={() => cyRef.current?.fit(undefined, 40)}
            className="p-1.5 rounded hover:bg-slate-800 text-slate-300 hover:text-white"
            title="Fit View"
          >
            <Maximize2 className="w-4 h-4" />
          </button>

          <div className="w-px h-4 bg-slate-700 mx-1" />

          {/* Layout Selector */}
          <select
            value={selectedLayout}
            onChange={(e) => setSelectedLayout(e.target.value)}
            className="bg-transparent text-xs text-slate-300 focus:outline-none pr-2"
          >
            <option value="cose" className="bg-slate-900">CoSE Layout</option>
            <option value="concentric" className="bg-slate-900">Concentric</option>
            <option value="circle" className="bg-slate-900">Circle</option>
            <option value="breadthfirst" className="bg-slate-900">Hierarchical</option>
            <option value="grid" className="bg-slate-900">Grid</option>
          </select>
        </div>

        {/* Legend Overlay */}
        <div className="absolute bottom-4 left-4 z-10 flex flex-wrap items-center gap-3 bg-slate-900/90 backdrop-blur-md px-3 py-2 rounded-lg border border-slate-700/80 shadow-xl text-[11px] text-slate-300">
          <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[#3b82f6]" /> Person</div>
          <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded bg-[#10b981]" /> Phone</div>
          <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded bg-[#ef4444]" /> Account</div>
          <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded bg-[#06b6d4]" /> Vehicle</div>
          <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-[#8b5cf6]" /> Organization</div>
          <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rotate-45 bg-[#f59e0b]" /> Location</div>
        </div>

        {/* Cytoscape Container */}
        <div ref={containerRef} className="w-full h-full" />

        {/* Empty state overlay */}
        {(!graphData || !graphData.nodes || graphData.nodes.length === 0) && !isGraphLoading && (
          <div className="absolute inset-0 flex flex-col items-center justify-center p-8 text-center text-slate-400 pointer-events-none">
            <Network className="w-14 h-14 text-slate-600 mb-3" />
            <h3 className="text-base font-semibold text-slate-300">No Graph Data Built Yet</h3>
            <p className="text-xs text-slate-500 max-w-sm mt-1">
              Click &quot;Build Graph&quot; to compile verified canonical entities and evidence-backed relationships into the graph canvas.
            </p>
          </div>
        )}

        {/* Node Detail Sidebar Drawer */}
        {selectedNode && (
          <div className="absolute top-4 right-4 z-20 w-80 bg-slate-900/95 backdrop-blur-md p-4 rounded-xl border border-slate-700 shadow-2xl space-y-3 animate-slide-up">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-900/50 text-blue-300">
                  {selectedNode.type}
                </span>
                <h4 className="text-base font-bold text-white mt-1">
                  {selectedNode.label}
                </h4>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-slate-400 hover:text-white p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="text-xs text-slate-400 space-y-1.5 border-t border-slate-800 pt-2 font-mono">
              <div>ID: <span className="text-slate-300">{selectedNode.id}</span></div>
            </div>

            <div className="pt-2 flex gap-2">
              <button
                onClick={() => {
                  setPathSource(selectedNode.id);
                  setShowPathModal(true);
                }}
                className="flex-1 py-1.5 rounded-lg bg-pink-600 hover:bg-pink-500 text-white text-xs font-semibold"
              >
                Set as Path Source
              </button>
              <button
                onClick={() => {
                  setPathTarget(selectedNode.id);
                  setShowPathModal(true);
                }}
                className="flex-1 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold"
              >
                Set as Path Target
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Shortest Path Modal */}
      {showPathModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="glass-card max-w-md w-full p-6 space-y-4 animate-slide-up border border-slate-700">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Route className="w-5 h-5 text-pink-400" />
              Find Connective Path (BFS)
            </h3>
            <p className="text-xs text-slate-300 leading-relaxed">
              Finds the shortest trail of evidence-backed relationships linking two entities across documents.
            </p>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-slate-300">Source Entity ID</label>
                <input
                  type="text"
                  value={pathSource}
                  onChange={(e) => setPathSource(e.target.value)}
                  placeholder="Select a node or paste UUID"
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-xs text-white font-mono mt-1"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-slate-300">Target Entity ID</label>
                <input
                  type="text"
                  value={pathTarget}
                  onChange={(e) => setPathTarget(e.target.value)}
                  placeholder="Select a node or paste UUID"
                  className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-xs text-white font-mono mt-1"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowPathModal(false)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  pathMutation.mutate();
                  setShowPathModal(false);
                }}
                disabled={!pathSource || !pathTarget || pathMutation.isPending}
                className="btn-primary text-xs"
              >
                {pathMutation.isPending ? 'Tracing Path...' : 'Find Path'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Cross-case modal */}
      {showCrossCase && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="glass-card max-w-lg w-full p-6 space-y-4 animate-slide-up border border-slate-700 max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                Cross-Case Linkages
              </h3>
              <button
                onClick={() => setShowCrossCase(false)}
                className="text-slate-400 hover:text-white p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <p className="text-xs text-slate-300">
              Entities in this case that also appear in other ongoing or historic investigations:
            </p>

            {crossCaseData.length === 0 ? (
              <div className="p-6 text-center text-slate-400 text-xs">
                No cross-case overlaps identified for this case.
              </div>
            ) : (
              <div className="space-y-2">
                {crossCaseData.map((item, idx) => (
                  <div key={idx} className="p-3 rounded-lg bg-slate-900 border border-slate-800 text-xs space-y-1">
                    <div className="font-bold text-white">{item.entity_name} ({item.entity_type})</div>
                    <div className="text-slate-400">Connected to Case: <span className="text-pink-300 font-mono">{item.connected_case_number}</span></div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
