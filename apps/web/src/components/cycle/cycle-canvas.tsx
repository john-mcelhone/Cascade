"use client";

import * as React from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
  type NodeMouseHandler,
  type OnConnect,
  type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { toast } from "sonner";
import { cycleNodeTypes, type CycleNodeData } from "./nodes";
import { ComponentPalette, PALETTE_MIME } from "./component-palette";
import { PropertiesPanel } from "./properties-panel";
import { RunButton } from "./run-button";
import { ResultPanel } from "./result-panel";
import { HsDiagram } from "./hs-diagram";
import {
  isValidConnection,
  type ConnectionEndpoint,
} from "./edge-validator";
import { useCycleUiStore } from "./store";
import { getApiClient } from "@/lib/api/client";
import type {
  CycleEdge,
  CycleNode,
  CycleNodeKind,
  CycleResult,
  Project,
} from "@/lib/api/types";

interface CycleCanvasProps {
  projectId: string;
  project?: Project;
  initialNodes: CycleNode[];
  initialEdges: CycleEdge[];
}

/**
 * Top-level Cycle Canvas — composes palette, React Flow, properties
 * panel, run button, result panel, and the h-s drawer. Owns autosave +
 * edge validation.
 */
export function CycleCanvas(props: CycleCanvasProps) {
  return (
    <ReactFlowProvider>
      <Inner {...props} />
    </ReactFlowProvider>
  );
}

function Inner({
  projectId,
  project,
  initialNodes,
  initialEdges,
}: CycleCanvasProps) {
  const api = getApiClient();
  const reactFlow = useReactFlow();
  const containerRef = React.useRef<HTMLDivElement | null>(null);

  // Convert domain nodes/edges → React Flow shapes.
  const [nodes, setNodes, onNodesChange] = useNodesState<
    Node<CycleNodeData>
  >(initialNodes.map(toRFNode));
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(
    initialEdges.map(toRFEdge),
  );

  const setSelected = useCycleUiStore((s) => s.setSelectedNode);
  const selectedNodeId = useCycleUiStore((s) => s.selectedNodeId);
  const result = useCycleUiStore((s) => s.run.result);

  // ---- Wrap nodes/edges change handlers to also persist position drags.
  const onNodesChangeWrapped = React.useCallback(
    (changes: NodeChange<Node<CycleNodeData>>[]) => {
      onNodesChange(changes);
      for (const ch of changes) {
        if (ch.type === "position" && ch.dragging === false && ch.position) {
          // commit position to backend (best-effort)
          void api
            .updateCycleComponent(projectId, ch.id, { position: ch.position })
            .catch(() => {
              /* tolerated; autosave best-effort */
            });
        }
        if (ch.type === "remove") {
          void api
            .deleteCycleComponent(projectId, ch.id)
            .catch(() => {
              /* tolerated */
            });
        }
      }
    },
    [api, projectId, onNodesChange],
  );

  const onEdgesChangeWrapped = React.useCallback(
    (changes: EdgeChange<Edge>[]) => {
      onEdgesChange(changes);
      for (const ch of changes) {
        if (ch.type === "remove") {
          void api.deleteCycleEdge(projectId, ch.id).catch(() => {
            /* tolerated */
          });
        }
      }
    },
    [api, projectId, onEdgesChange],
  );

  // ---- Connection validation
  const onConnect: OnConnect = React.useCallback(
    async (conn: Connection) => {
      const src = nodeKindFor(nodes, conn.source);
      const dst = nodeKindFor(nodes, conn.target);
      if (!src || !dst) return;
      const sourceEnd: ConnectionEndpoint = {
        nodeKind: src,
        portId: conn.sourceHandle ?? "out",
      };
      const targetEnd: ConnectionEndpoint = {
        nodeKind: dst,
        portId: conn.targetHandle ?? "in",
      };
      const valid = isValidConnection(sourceEnd, targetEnd);
      if (!valid.ok) {
        toast.error("Connection rejected", { description: valid.reason });
        return;
      }
      const newEdge: Edge = {
        ...conn,
        id: `e-${Math.random().toString(36).slice(2, 8)}`,
        source: conn.source!,
        target: conn.target!,
      };
      setEdges((e) => addEdge(newEdge, e));
      void api
        .addCycleEdge(projectId, {
          source: conn.source!,
          target: conn.target!,
          sourcePort: conn.sourceHandle ?? undefined,
          targetPort: conn.targetHandle ?? undefined,
        })
        .catch(() => {
          /* tolerated */
        });
    },
    [api, projectId, nodes, setEdges],
  );

  /** React Flow's `isValidConnection` predicate — pre-validates as the user
   *  drags so the edge never snaps in if it'd be rejected anyway. */
  const isConnectionValid = React.useCallback(
    (c: Connection | Edge): boolean => {
      const src = nodeKindFor(nodes, c.source ?? "");
      const dst = nodeKindFor(nodes, c.target ?? "");
      if (!src || !dst) return false;
      return isValidConnection(
        { nodeKind: src, portId: c.sourceHandle ?? "out" },
        { nodeKind: dst, portId: c.targetHandle ?? "in" },
      ).ok;
    },
    [nodes],
  );

  // ---- Drop from the palette
  const onDragOver = React.useCallback((e: React.DragEvent<HTMLDivElement>) => {
    if (e.dataTransfer.types.includes(PALETTE_MIME)) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
    }
  }, []);

  const onDrop = React.useCallback(
    async (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      const kindRaw = e.dataTransfer.getData(PALETTE_MIME);
      if (!kindRaw) return;
      const kind = kindRaw as CycleNodeKind;
      const bounds = containerRef.current?.getBoundingClientRect();
      const pos = reactFlow.screenToFlowPosition({
        x: e.clientX - (bounds?.left ?? 0),
        y: e.clientY - (bounds?.top ?? 0),
      });
      const label = nextLabelFor(nodes, kind);
      try {
        const created = await api.addCycleComponent(projectId, {
          kind,
          label,
          x: pos.x,
          y: pos.y,
        });
        setNodes((ns) => [...ns, toRFNode(created)]);
        // auto-select the new node
        setSelected(created.id);
      } catch (err) {
        toast.error("Could not add component", {
          description: (err as Error).message,
        });
      }
    },
    [api, projectId, nodes, reactFlow, setNodes, setSelected],
  );

  // ---- Selection plumbing
  const onNodeClick: NodeMouseHandler = React.useCallback(
    (_evt, node) => {
      setSelected(node.id);
    },
    [setSelected],
  );

  const onPaneClick = React.useCallback(() => {
    setSelected(undefined);
  }, [setSelected]);

  // ---- Properties-panel callbacks
  const onPatchComponent = React.useCallback(
    async (
      componentId: string,
      patch: {
        label?: string;
        params?: Record<string, number | string | boolean>;
      },
    ) => {
      const updated = await api.updateCycleComponent(projectId, componentId, patch);
      setNodes((ns) =>
        ns.map((n) => {
          if (n.id === componentId) {
            // Update the patched node from the server response AND clear
            // all solved-state chips — the cycle state is now stale until
            // the user re-runs.
            const fresh = toRFNode(updated);
            return { ...fresh, data: { ...fresh.data, solvedState: undefined } };
          }
          // W-11 AC3: editing ANY component clears solved state on ALL nodes.
          if (n.data.solvedState !== undefined) {
            return { ...n, data: { ...n.data, solvedState: undefined } };
          }
          return n;
        }),
      );
    },
    [api, projectId, setNodes],
  );

  const onDeleteComponent = React.useCallback(
    async (componentId: string) => {
      await api.deleteCycleComponent(projectId, componentId);
      setNodes((ns) => ns.filter((n) => n.id !== componentId));
      setEdges((es) =>
        es.filter((e) => e.source !== componentId && e.target !== componentId),
      );
      setSelected(undefined);
    },
    [api, projectId, setNodes, setEdges, setSelected],
  );

  // ---- React Flow init hook
  const onInit = React.useCallback((_inst: ReactFlowInstance<Node<CycleNodeData>, Edge>) => {
    // Could fit-view here, but the canvas already sizes from the
    // pre-seeded positions; leaving it as-is keeps user pans deterministic.
    void _inst;
  }, []);

  // Marshal selected node data + result for the panel.
  const selectedNode = React.useMemo(() => {
    const n = nodes.find((x) => x.id === selectedNodeId);
    if (!n) return undefined;
    return rfNodeToDomain(n);
  }, [nodes, selectedNodeId]);

  const selectedResult = React.useMemo(() => {
    if (!selectedNodeId || !result) return undefined;
    // The solver result uses the component *name* (e.g. "C1") as the
    // componentId key, while the React Flow node id is the backend component
    // *id* (e.g. "compressor").  Match by node label which equals the name.
    const selectedLabel = nodes.find((n) => n.id === selectedNodeId)?.data.label;
    const c = result.components.find(
      (x) => x.componentId === selectedNodeId || x.componentId === selectedLabel,
    );
    if (!c) return undefined;
    return {
      shaftWork: c.shaftWork,
      outletTemperature: c.outletTemperature,
      outletPressure: c.outletPressure,
      outletMassFlow: c.outletMassFlow,
    };
  }, [selectedNodeId, result, nodes]);

  // W-11: After a successful solve, push post-solve outlet-state chips to
  // every canvas node.  The `solvedState` field on `CycleNodeData` drives
  // a secondary chip row in `BaseNode` so the engineer can see T, P, ṁ at
  // each station without opening the result panel.
  //
  // We watch `result` from the store (not the `selectedResult` slice) so
  // ALL nodes update — not just the currently selected one.
  React.useEffect(() => {
    if (!result || result.failure) {
      // Failed solve or no solve yet: clear any stale solved state.
      setNodes((ns) =>
        ns.map((n) => {
          if (!n.data.solvedState) return n;
          return { ...n, data: { ...n.data, solvedState: undefined } };
        }),
      );
      return;
    }
    // Build a lookup map: componentId → outlet state.
    // The solver uses the component *name* (e.g. "C1") as the componentId key.
    // Nodes are identified by their React Flow id (e.g. "compressor") AND their
    // label (which equals the component name).  We index on both so the lookup
    // works regardless of whether ids happen to match names (mock vs real API).
    const stateByKey = new Map<
      string,
      { outletTemperature: number; outletPressure: number; outletMassFlow: number }
    >();
    for (const c of result.components) {
      const s = {
        outletTemperature: c.outletTemperature,
        outletPressure: c.outletPressure,
        outletMassFlow: c.outletMassFlow,
      };
      stateByKey.set(c.componentId, s);
    }
    setNodes((ns) =>
      ns.map((n) => {
        // Try matching by node id first (mock data), then by label (real API).
        const solved = stateByKey.get(n.id) ?? stateByKey.get(n.data.label);
        // If this component isn't in the solver result (e.g. Inlet, Shaft),
        // leave its solvedState cleared.
        const nextSolved = solved ?? undefined;
        if (n.data.solvedState === nextSolved) return n;
        return { ...n, data: { ...n.data, solvedState: nextSolved } };
      }),
    );
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result]);

  // Mark nodes as selected for visual feedback (React Flow already does
  // this via the `selected` prop on the node component).
  React.useEffect(() => {
    setNodes((ns) =>
      ns.map((n) => ({ ...n, selected: n.id === selectedNodeId })),
    );
  }, [selectedNodeId, setNodes]);

  return (
    <div className="flex h-full w-full">
      <ComponentPalette />

      <div className="relative flex flex-1 flex-col overflow-hidden">
        <div
          ref={containerRef}
          onDragOver={onDragOver}
          onDrop={onDrop}
          className="relative flex-1 bg-background"
        >
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChangeWrapped}
            onEdgesChange={onEdgesChangeWrapped}
            onConnect={onConnect}
            isValidConnection={isConnectionValid}
            nodeTypes={cycleNodeTypes}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            onInit={onInit}
            fitView
            fitViewOptions={{ padding: 0.2, maxZoom: 1.2 }}
            proOptions={{ hideAttribution: true }}
            defaultEdgeOptions={{
              animated: false,
              style: { stroke: "rgb(var(--brand-default) / 0.85)", strokeWidth: 1.5 },
            }}
          >
            <Background
              variant={BackgroundVariant.Dots}
              gap={8}
              size={1}
              color="rgb(var(--border-subtle) / 0.85)"
            />
            <Controls
              showInteractive={false}
              className="!rounded-sm !border !border-border-subtle !bg-surface-raised !shadow-z1"
            />
            <MiniMap
              pannable
              zoomable
              nodeStrokeWidth={2}
              maskColor="rgb(var(--background) / 0.6)"
              className="!rounded-sm !border !border-border-subtle !bg-surface-raised !shadow-z1"
              nodeColor={(n) => nodeMiniColor(n.type)}
            />
          </ReactFlow>

          <div className="pointer-events-none absolute inset-x-0 top-2 z-10 flex justify-end pr-3">
            <div className="pointer-events-auto">
              <RunButton projectId={projectId} />
            </div>
          </div>

          <ResultPanel
            nodes={nodes.map((n) => rfNodeToDomain(n))}
          />
        </div>

        <HsDiagram />
      </div>

      <PropertiesPanel
        node={selectedNode}
        project={project}
        result={selectedResult}
        onPatch={onPatchComponent}
        onDelete={onDeleteComponent}
      />
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * Helpers
 * ------------------------------------------------------------------------- */

function toRFNode(n: CycleNode): Node<CycleNodeData> {
  return {
    id: n.id,
    type: n.kind,
    position: { x: n.x, y: n.y },
    data: {
      kind: n.kind,
      label: n.label,
      ref: n.label,
      chips: n.chips,
      params: n.params,
    },
  };
}

function rfNodeToDomain(n: Node<CycleNodeData>): CycleNode {
  return {
    id: n.id,
    kind: n.data.kind,
    label: n.data.label,
    x: n.position.x,
    y: n.position.y,
    chips: n.data.chips,
    params: n.data.params,
  };
}

function toRFEdge(e: CycleEdge): Edge {
  return {
    id: e.id,
    source: e.source,
    target: e.target,
    sourceHandle: e.sourcePort,
    targetHandle: e.targetPort,
  };
}

function nodeKindFor(
  nodes: Node<CycleNodeData>[],
  id: string | null | undefined,
): CycleNodeKind | undefined {
  if (!id) return undefined;
  return nodes.find((n) => n.id === id)?.data.kind;
}

function nextLabelFor(nodes: Node<CycleNodeData>[], kind: CycleNodeKind): string {
  const prefix = labelPrefix(kind);
  let i = 1;
  const existing = new Set(
    nodes.filter((n) => n.data.kind === kind).map((n) => n.data.label),
  );
  while (existing.has(`${prefix}${i}`)) i++;
  return `${prefix}${i}`;
}

function labelPrefix(kind: CycleNodeKind): string {
  switch (kind) {
    case "compressor":
      return "C";
    case "turbine":
      return "T";
    case "burner":
      return "B";
    case "recuperator":
      return "REC";
    case "intercooler":
      return "IC";
    case "mixer":
      return "M";
    case "splitter":
      return "S";
    case "duct":
      return "D";
    case "inlet":
      return "IN";
    case "outlet":
      return "OUT";
    case "shaft":
      return "SH";
  }
}

function nodeMiniColor(kind: string | undefined): string {
  switch (kind) {
    case "compressor":
      return "rgb(31, 78, 121)";
    case "turbine":
      return "rgb(194, 91, 31)";
    case "burner":
      return "rgb(180, 113, 0)";
    case "recuperator":
      return "rgb(46, 135, 84)";
    case "shaft":
      return "rgb(122, 61, 168)";
    case "inlet":
      return "rgb(46, 135, 84)";
    case "outlet":
      return "rgb(122, 128, 138)";
    default:
      return "rgb(122, 128, 138)";
  }
}
