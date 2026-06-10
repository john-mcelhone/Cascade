"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useTheme } from "next-themes";
import { useFrame } from "@react-three/fiber";
import {
  Environment,
  GizmoHelper,
  GizmoViewport,
  Grid,
  OrbitControls,
  PerspectiveCamera,
} from "@react-three/drei";
import * as THREE from "three";
import {
  Download,
  Box,
  Layers,
  Rotate3d,
  Scissors,
  Spline,
  Sun,
  Wand2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useQuery } from "@tanstack/react-query";
import { useFlowPathStore } from "@/lib/flowpath/store";
import {
  useGltfStream,
  type UseGltfStreamResult,
} from "@/lib/three/gltf-loader";
import {
  createProceduralImpeller,
  disposeGroup,
} from "@/lib/three/procedural-impeller";
import { toast } from "sonner";
import {
  cadExportAvailable,
  cadHealth,
  downloadUrl,
  geometryUrl,
  getMergedGeometry,
  type DownloadFormat,
  type MergedGeometry,
} from "@/lib/api/flowpath";
import { fmtNumber, cn } from "@/lib/utils";
import { CanvasErrorBoundary } from "@/components/three/canvas-error-boundary";
import { MeridionalView } from "@/components/flowpath/meridional-view";

// Three.js Canvas must be client-only — it touches `window`/`document`
// inside its constructor. Rendering an empty placeholder during SSR keeps
// the layout stable and prevents a flash of restructuring on hydration.
const Canvas = dynamic(
  () => import("@react-three/fiber").then((m) => m.Canvas),
  { ssr: false, loading: () => <CanvasFallback /> },
);

/**
 * Store-connected viewer for the Flow Path PD page: sources the picked
 * candidate from the flow-path Zustand store. Thin wrapper over the
 * prop-driven `ImpellerViewerView` (which the candidate detail page uses
 * directly — that page is self-sufficient from the URL and never assumes
 * a warm store).
 */
export function ImpellerViewer() {
  const pickedId = useFlowPathStore((s) => s.pickedCandidateId);
  const candidates = useFlowPathStore((s) => s.candidates);

  const pickedCandidate = useMemo(
    () => candidates.find((c) => c.id === pickedId) ?? null,
    [candidates, pickedId],
  );

  return (
    <ImpellerViewerView candidateId={pickedId} candidate={pickedCandidate} />
  );
}

interface ImpellerViewerViewProps {
  /** Candidate id driving the streamed glTF; null renders the empty state. */
  candidateId: string | null;
  /** Candidate record for the HUD + procedural placeholder silhouette. */
  candidate: import("@/lib/api/flowpath").ServerCandidate | null;
  /** Hide the bottom download strip (the detail page hosts its own). */
  hideDownloads?: boolean;
}

/**
 * Prop-driven 3D viewer (U8). Viewer *settings* (display mode, shading,
 * HUD) stay in the persisted store — they are user preferences shared
 * across surfaces — but the candidate itself arrives via props.
 *
 * The glTF stream lives HERE (not in the scene) so the host can render
 * honesty affordances: a stub badge when the server tags the mesh
 * `X-Cascade-Stub: true`, an error overlay when generation fails, and a
 * download gate while either is the case. The mesh loads progressively —
 * STANDARD LOD first (~200 ms server-side), upgraded to HIGH once the
 * first mesh is on screen; the existing crossfade makes the swap seamless.
 */
export function ImpellerViewerView({
  candidateId,
  candidate,
  hideDownloads = false,
}: ImpellerViewerViewProps) {
  const displayMode = useFlowPathStore((s) => s.displayMode);
  const shading = useFlowPathStore((s) => s.shading);
  const setDisplayMode = useFlowPathStore((s) => s.setDisplayMode);
  const setShading = useFlowPathStore((s) => s.setShading);
  const showHud = useFlowPathStore((s) => s.showHud);
  const setMeshStubbed = useFlowPathStore((s) => s.setMeshStubbed);
  const { resolvedTheme } = useTheme();

  const pickedId = candidateId;
  const pickedCandidate = candidate;

  // Progressive LOD: request "standard" on pick, swap the URL to "high"
  // once the standard mesh has rendered (skipped while stubbed).
  const baseUrl = pickedId ? geometryUrl(pickedId, "standard") : null;
  const highUrl = pickedId ? geometryUrl(pickedId, "high") : null;
  const [meshUrl, setMeshUrl] = useState<string | null>(baseUrl);
  useEffect(() => {
    setMeshUrl(baseUrl);
  }, [baseUrl]);

  const stream = useGltfStream(meshUrl);
  const { current, loading, error, crossfade } = stream;

  // Upgrade only AFTER the standard mesh's crossfade has finished: swapping
  // the URL mid-fade cancels the fade animation and leaves the PREVIOUS
  // candidate's mesh at full opacity under this candidate's HUD for the
  // whole high-LOD generation (~1 s) — the exact stale-mesh dishonesty
  // this viewer is built to prevent.
  useEffect(() => {
    if (
      current &&
      current.url === baseUrl &&
      !current.isStub &&
      highUrl &&
      crossfade >= 1
    ) {
      setMeshUrl(highUrl);
    }
  }, [current, baseUrl, highUrl, crossfade]);

  // Mirror the stub state into the store so download strips (including
  // the detail page's own strip) can refuse placeholder downloads.
  const isStub = current?.isStub ?? false;
  useEffect(() => {
    setMeshStubbed(isStub);
    return () => setMeshStubbed(false);
  }, [isStub, setMeshStubbed]);

  // Merged geometry — the same normative merge the server meshes from.
  // Feeds the HUD's r2/b2/U_tip and the meridional view, so the numbers
  // and contours describe the wheel on screen (the candidate params alone
  // don't carry rpm or the scaled geometry).
  const projectId = pickedCandidate?.project_id ?? null;
  const { data: mergedGeometry } = useQuery({
    queryKey: ["merged-geometry", pickedId, projectId],
    queryFn: () => getMergedGeometry(pickedId!, projectId!),
    enabled: Boolean(pickedId && projectId),
    staleTime: Infinity,
  });

  // 3D vs 2D meridional — the page is named "Flow path"; the r–z contour
  // is the view engineers actually judge one by.
  const [viewKind, setViewKind] = useState<"3d" | "meridional">("3d");
  const meridionalAvailable = Boolean(
    mergedGeometry && (mergedGeometry.meridional?.hub?.length ?? 0) > 1,
  );
  const showMeridional = viewKind === "meridional" && meridionalAvailable;

  return (
    <div className="flex h-full flex-col">
      <ViewerToolbar
        displayMode={displayMode}
        shading={shading}
        setDisplayMode={setDisplayMode}
        setShading={setShading}
        viewKind={viewKind}
        setViewKind={setViewKind}
        meridionalAvailable={meridionalAvailable}
      />
      <div className="relative flex-1 overflow-hidden">
        {showMeridional && mergedGeometry ? (
          <MeridionalView merged={mergedGeometry} />
        ) : (
          <CanvasErrorBoundary fallback={<CanvasFallback />}>
            <Canvas
              gl={{ antialias: true, alpha: true }}
              aria-label="Impeller 3D viewer canvas — drag to orbit, scroll to zoom."
              dpr={[1, 2]}
              className="bg-background"
            >
              <ImpellerScene
                stream={stream}
                displayMode={displayMode}
                shading={shading}
                theme={resolvedTheme}
                candidate={pickedCandidate}
              />
            </Canvas>
          </CanvasErrorBoundary>
        )}

        {showHud && pickedCandidate && (
          <Hud candidate={pickedCandidate} merged={mergedGeometry ?? null} />
        )}

        {!pickedId && <EmptyOverlay />}

        {pickedId && !showMeridional && isStub && (
          <StatusOverlay tone="warning">
            Placeholder geometry — the server mesh module is unavailable.
            The mean-line numbers are computed independently and are
            unaffected; downloads are disabled until real geometry is
            served.
          </StatusOverlay>
        )}

        {pickedId && !showMeridional && error && !loading && !isStub && (
          <StatusOverlay tone="error">
            Geometry generation failed for this candidate: {error.message}
          </StatusOverlay>
        )}

        <a
          aria-label="Canvas accessibility note"
          className="sr-only"
        >
          Three.js canvas showing the picked impeller. Use the controls
          above the canvas to swap render modes; the gizmo in the bottom
          right indicates orientation.
        </a>
      </div>
      <div className="border-t border-border-subtle bg-surface-subtle/30 px-2 py-1 text-[10px] text-text-muted">
        Preliminary geometry — canonical hub/shroud profiles, fixed blade
        thickness, no fillets or lean (KG-G-01…04, KG-G-09).
      </div>
      {!hideDownloads && <DownloadStrip pickedId={pickedId} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Scene
// ---------------------------------------------------------------------------

interface SceneProps {
  stream: UseGltfStreamResult;
  displayMode: "solid" | "wireframe" | "section";
  shading: "photoreal" | "linedrawing";
  theme: string | undefined;
  candidate: import("@/lib/api/flowpath").ServerCandidate | null;
}

function ImpellerScene({ stream, displayMode, shading, theme, candidate }: SceneProps) {
  const { current, previous, loading, crossfade } = stream;
  // The clipping plane is a long-lived THREE.Plane that we MUTATE in place
  // each frame (see useSectionPlaneRef below). We must not put its sweep
  // value in React state — doing so re-renders this whole subtree 60 ×/s
  // and (a) hammers the SceneObject material-update effect into fighting
  // the glTF crossfade, (b) makes the canvas flash on every candidate
  // change. Always use the ref + direct mutation pattern for live values
  // in R3F.
  const sectionPlaneRef = useSectionPlaneRef(displayMode);

  // Procedural placeholder — generated once per candidate while the real
  // glTF streams. We regenerate it whenever the rotor radius or blade
  // count from the candidate changes, so the silhouette stays plausible.
  const proceduralRef = useRef<THREE.Group | null>(null);
  useEffect(() => {
    proceduralRef.current?.parent?.remove(proceduralRef.current);
    if (proceduralRef.current) disposeGroup(proceduralRef.current);
    if (!candidate) {
      proceduralRef.current = null;
      return;
    }
    const rTip = (candidate.params.rotor_outlet_radius as number) ?? 0.03;
    const z = (candidate.params.blade_count as number) ?? 12;
    proceduralRef.current = createProceduralImpeller({
      rTip,
      bladeCount: Math.round(z),
    });
    // We deliberately only respawn the placeholder on candidate identity
    // change — re-running on every objective tweak would thrash the GPU.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candidate?.id]);

  const sectionPlanes = useMemo(() => {
    if (displayMode !== "section") return null;
    // The plane object is stable for the lifetime of the section mode;
    // useSectionPlaneRef mutates its `constant` field each frame. The
    // material samples the plane every frame from the render loop, so
    // mutation is visible to the renderer without React having to
    // re-render.
    return [sectionPlaneRef.current];
  }, [displayMode, sectionPlaneRef]);

  return (
    <>
      {/* The wheel is centimetre-scale (r_tip ≈ 0.03 m), so the default
          near plane (0.1 m) sits FARTHER than the closest allowed zoom —
          the whole mesh gets near-clipped to nothing the moment the user
          zooms inside 10 cm. Keep near ≪ minDistance − r_tip. */}
      <PerspectiveCamera
        makeDefault
        position={[0.15, 0.08, 0.2]}
        fov={42}
        near={0.001}
        far={10}
      />
      {/* makeDefault registers the controls in R3F state — GizmoHelper
          requires it: clicking a gizmo axis runs `'getTarget' in controls`
          / `'minPolarAngle' in controls` on `state.controls`, which throws
          a TypeError when no default controls are registered (null). */}
      <OrbitControls
        makeDefault
        enableDamping
        dampingFactor={0.08}
        target={[0, 0, 0]}
        minDistance={0.02}
        maxDistance={1.5}
      />
      <GizmoHelper alignment="bottom-right" margin={[60, 60]}>
        <GizmoViewport
          axisColors={["#ef4444", "#10b981", "#3b82f6"]}
          labelColor={theme === "dark" ? "#EEEFF1" : "#1A1C21"}
        />
      </GizmoHelper>

      <Grid
        args={[1, 1]}
        cellColor={theme === "dark" ? "#4A4F58" : "#DCDEE2"}
        sectionColor={theme === "dark" ? "#7A808A" : "#7A808A"}
        sectionThickness={1}
        cellThickness={0.6}
        infiniteGrid
        fadeDistance={0.6}
        fadeStrength={1.2}
      />

      {shading === "photoreal" ? (
        <Suspense fallback={null}>
          <Environment preset="studio" environmentIntensity={0.6} />
        </Suspense>
      ) : (
        <>
          <ambientLight intensity={0.6} />
          <directionalLight position={[1, 1, 1]} intensity={0.7} />
          <directionalLight position={[-1, 0.4, -0.6]} intensity={0.25} />
        </>
      )}

      {previous && (
        <SceneObject
          group={previous.scene}
          displayMode={displayMode}
          shading={shading}
          opacity={1 - crossfade * 0.6}
          clippingPlanes={sectionPlanes}
        />
      )}

      {loading && !current && proceduralRef.current && (
        <SceneObject
          group={proceduralRef.current}
          displayMode="wireframe"
          shading="linedrawing"
          opacity={0.6}
          clippingPlanes={sectionPlanes}
        />
      )}

      {current && (
        <SceneObject
          group={current.scene}
          displayMode={displayMode}
          shading={shading}
          opacity={crossfade}
          clippingPlanes={sectionPlanes}
        />
      )}

      {!current && !loading && proceduralRef.current && (
        <SceneObject
          group={proceduralRef.current}
          displayMode={displayMode}
          shading={shading}
          opacity={1}
          clippingPlanes={sectionPlanes}
        />
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Mesh wrapper — applies the display / shading mode + opacity to every
// material in a glTF scene. Re-runs whenever the controls change.
// ---------------------------------------------------------------------------

function SceneObject({
  group,
  displayMode,
  shading,
  opacity,
  clippingPlanes,
}: {
  group: THREE.Group;
  displayMode: "solid" | "wireframe" | "section";
  shading: "photoreal" | "linedrawing";
  opacity: number;
  clippingPlanes: THREE.Plane[] | null;
}) {
  useEffect(() => {
    group.traverse((obj) => {
      const mesh = obj as THREE.Mesh;
      if (!mesh.isMesh) return;
      const apply = (mat: THREE.Material) => {
        mat.transparent = opacity < 1;
        mat.opacity = opacity;
        mat.clippingPlanes = clippingPlanes ?? null;
        mat.needsUpdate = true;
        if ("wireframe" in mat) {
          (mat as THREE.MeshStandardMaterial).wireframe = displayMode === "wireframe";
        }
        if ("metalness" in mat) {
          const m = mat as THREE.MeshStandardMaterial;
          if (shading === "linedrawing") {
            m.metalness = 0.0;
            m.roughness = 1.0;
          } else {
            m.metalness = 0.55;
            m.roughness = 0.42;
          }
        }
      };
      const mat = mesh.material as THREE.Material | THREE.Material[];
      if (Array.isArray(mat)) mat.forEach(apply);
      else apply(mat);
    });
  }, [group, displayMode, shading, opacity, clippingPlanes]);

  return <primitive object={group} />;
}

// ---------------------------------------------------------------------------
// Section plane animation hook — a slow up/down sweep so the "Section"
// affordance reads as live without needing a slider in the toolbar.
// ---------------------------------------------------------------------------

/**
 * Returns a stable React ref to a `THREE.Plane` whose `constant` is animated
 * in-place every frame by `useFrame` when `displayMode === "section"`. The
 * plane object identity never changes for the lifetime of the component;
 * only its `constant` (and only while section mode is active). React is
 * never notified, which is exactly the point — animating a clipping plane
 * via setState causes O(refreshRate) re-renders of the entire scene tree
 * and crashes the glTF crossfade.
 */
function useSectionPlaneRef(
  displayMode: "solid" | "wireframe" | "section",
): React.MutableRefObject<THREE.Plane> {
  const planeRef = useRef<THREE.Plane>(
    new THREE.Plane(new THREE.Vector3(0, 1, 0), 0),
  );
  const timeRef = useRef(0);
  useFrame((_, delta) => {
    if (displayMode !== "section") {
      // Park the plane at zero so it has predictable state when section
      // mode is re-engaged later.
      timeRef.current = 0;
      planeRef.current.constant = 0;
      return;
    }
    timeRef.current += delta * 0.08;
    planeRef.current.constant = Math.sin(timeRef.current) * 0.04;
  });
  return planeRef;
}

// ---------------------------------------------------------------------------
// HUD overlay
// ---------------------------------------------------------------------------

function Hud({
  candidate,
  merged,
}: {
  candidate: import("@/lib/api/flowpath").ServerCandidate;
  merged: MergedGeometry | null;
}) {
  // r2 / b2 / U_tip come from the merged geometry — the same normative
  // merge the server meshes from — so the HUD describes the wheel on
  // screen. Until the merge arrives, show a placeholder rather than
  // fabricating values from keys the candidate doesn't carry.
  const r2 = merged?.geometry_params.impeller_outlet_radius ?? null;
  const b2 = merged?.geometry_params.blade_height_outlet ?? null;
  const rpm = merged?.meanline_rpm_rpm ?? null;
  const uTip =
    r2 !== null && rpm !== null ? (2 * Math.PI * rpm * r2) / 60 : null;
  return (
    <div
      className="absolute right-3 top-3 z-10 rounded-md border border-border-subtle bg-surface-raised/90 px-3 py-2 text-xs shadow-z2 backdrop-blur"
      role="status"
      aria-live="polite"
    >
      <div className="mb-1 text-[10px] uppercase tracking-wide text-text-muted">
        Picked candidate
      </div>
      <table className="w-full font-mono">
        <tbody>
          <HudRow label="η_tt" value={fmtNumber(candidate.objectives.eta_tt ?? 0, { decimals: 4 })} />
          <HudRow label="η_ts" value={fmtNumber(candidate.objectives.eta_ts ?? 0, { decimals: 4 })} />
          <HudRow label="M_rel" value={fmtNumber(candidate.objectives.M_rel ?? 0, { decimals: 3 })} />
          <HudRow
            label="r₂"
            value={r2 !== null ? `${fmtNumber(r2 * 1000, { decimals: 1 })} mm` : "—"}
          />
          <HudRow
            label="b₂"
            value={b2 !== null ? `${fmtNumber(b2 * 1000, { decimals: 2 })} mm` : "—"}
          />
          <HudRow
            label="U_tip"
            value={uTip !== null ? `${fmtNumber(uTip, { decimals: 0 })} m/s` : "—"}
          />
          <HudRow
            label="mass"
            value={`${fmtNumber(candidate.objectives.mass ?? 0, { decimals: 3 })} kg`}
          />
        </tbody>
      </table>
    </div>
  );
}

function HudRow({ label, value }: { label: string; value: string }) {
  return (
    <tr>
      <td className="pr-2 text-text-muted">{label}</td>
      <td className="text-right text-text">{value}</td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Top + bottom strips
// ---------------------------------------------------------------------------

interface ViewerToolbarProps {
  displayMode: "solid" | "wireframe" | "section";
  shading: "photoreal" | "linedrawing";
  setDisplayMode: (m: "solid" | "wireframe" | "section") => void;
  setShading: (s: "photoreal" | "linedrawing") => void;
  viewKind: "3d" | "meridional";
  setViewKind: (v: "3d" | "meridional") => void;
  meridionalAvailable: boolean;
}

function ViewerToolbar({
  displayMode,
  shading,
  setDisplayMode,
  setShading,
  viewKind,
  setViewKind,
  meridionalAvailable,
}: ViewerToolbarProps) {
  const meridionalActive = viewKind === "meridional" && meridionalAvailable;
  // This toolbar lives in a side pane that can be as narrow as ~280 px
  // regardless of viewport, so labels must not be viewport-gated and the
  // row must never squash: the view tabs keep their labels, the secondary
  // mode/shading toggles are icon-only (tooltips carry the labels), and
  // each group wraps as a unit if the pane gets really tight.
  return (
    <div className="flex flex-wrap items-center gap-x-1 gap-y-1 border-b border-border-subtle bg-surface-subtle/30 px-2 py-1.5">
      <div className="flex shrink-0 items-center gap-0.5" role="group" aria-label="View">
        <ToggleGroupItem
          label="3D"
          icon={Rotate3d}
          active={viewKind === "3d"}
          onClick={() => setViewKind("3d")}
        />
        <ToggleGroupItem
          label="Meridional"
          icon={Spline}
          active={meridionalActive}
          onClick={() => setViewKind("meridional")}
          disabled={!meridionalAvailable}
        />
      </div>

      <span className="mx-0.5 h-4 w-px shrink-0 bg-border-subtle" aria-hidden />

      <div className="flex shrink-0 items-center gap-0.5" role="group" aria-label="Display mode">
        <ToggleGroupItem
          label="Solid"
          icon={Box}
          iconOnly
          active={displayMode === "solid"}
          onClick={() => setDisplayMode("solid")}
          disabled={meridionalActive}
        />
        <ToggleGroupItem
          label="Wireframe"
          icon={Layers}
          iconOnly
          active={displayMode === "wireframe"}
          onClick={() => setDisplayMode("wireframe")}
          disabled={meridionalActive}
        />
        <ToggleGroupItem
          label="Section"
          icon={Scissors}
          iconOnly
          active={displayMode === "section"}
          onClick={() => setDisplayMode("section")}
          disabled={meridionalActive}
        />
      </div>

      <span className="mx-0.5 h-4 w-px shrink-0 bg-border-subtle" aria-hidden />

      <div className="flex shrink-0 items-center gap-0.5" role="group" aria-label="Shading">
        <ToggleGroupItem
          label="Photoreal"
          icon={Sun}
          iconOnly
          active={shading === "photoreal"}
          onClick={() => setShading("photoreal")}
          disabled={meridionalActive}
        />
        <ToggleGroupItem
          label="Line drawing"
          icon={Wand2}
          iconOnly
          active={shading === "linedrawing"}
          onClick={() => setShading("linedrawing")}
          disabled={meridionalActive}
        />
      </div>
    </div>
  );
}

function ToggleGroupItem({
  label,
  icon: Icon,
  active,
  onClick,
  disabled = false,
  iconOnly = false,
}: {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  active: boolean;
  onClick: () => void;
  disabled?: boolean;
  /** Render icon only; the tooltip and aria-label still carry the name. */
  iconOnly?: boolean;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={onClick}
          disabled={disabled}
          aria-pressed={active}
          aria-label={label}
          className={cn(
            "inline-flex h-6 shrink-0 items-center gap-1 whitespace-nowrap rounded-sm px-1.5 text-xs",
            active
              ? "bg-brand-surface text-brand-text"
              : "text-text-muted hover:bg-surface-subtle hover:text-text",
            disabled && "cursor-not-allowed opacity-40 hover:bg-transparent",
          )}
        >
          <Icon className="h-3 w-3 shrink-0" />
          {!iconOnly && <span>{label}</span>}
        </button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

/**
 * W-19: Tooltip shown on STEP/IGES buttons when pythonocc-core is absent.
 * Matches the AC2 wording: "CAD export requires the cascade[cad] extra."
 */
const CAD_UNAVAILABLE_TOOLTIP =
  "CAD export requires the cascade[cad] extra. " +
  "Install with: pip install 'cascade[cad]' or contact support.";

const STUB_DOWNLOAD_TOOLTIP =
  "Downloads disabled — the server is serving placeholder geometry, " +
  "not this candidate's impeller.";

export function DownloadStrip({ pickedId }: { pickedId: string | null }) {
  // W-19: Probe the /api/health/cad endpoint (richer than _cad/available)
  // so the UI can disable STEP/IGES buttons proactively and show the
  // OCCT version in the tooltip when available.
  const [cadAvailable, setCadAvailable] = useState<boolean | null>(null);
  useEffect(() => {
    const ctrl = new AbortController();
    cadHealth(ctrl.signal).then((h) => setCadAvailable(h.cad_available));
    return () => ctrl.abort();
  }, []);

  // While the viewer is showing a server stub, downloading would hand the
  // user an empty/placeholder file under the candidate's name — refuse.
  const meshStubbed = useFlowPathStore((s) => s.meshStubbed);
  const stubReason = meshStubbed ? STUB_DOWNLOAD_TOOLTIP : undefined;

  const cadTooltip =
    cadAvailable === false ? CAD_UNAVAILABLE_TOOLTIP : undefined;

  return (
    <div
      className="flex items-center gap-1 border-t border-border-subtle bg-surface-subtle/30 px-2 py-1.5"
      aria-label="Download options for the picked candidate"
    >
      <DownloadButton
        format="glb"
        pickedId={pickedId}
        label="glTF"
        disabled={meshStubbed}
        unavailableReason={stubReason}
      />
      <DownloadButton
        format="stl"
        pickedId={pickedId}
        label="STL"
        disabled={meshStubbed}
        unavailableReason={stubReason}
      />
      <DownloadButton
        format="step"
        pickedId={pickedId}
        label="STEP"
        disabled={cadAvailable !== true || meshStubbed}
        unavailableReason={stubReason ?? cadTooltip}
      />
      <DownloadButton
        format="iges"
        pickedId={pickedId}
        label="IGES"
        disabled={cadAvailable !== true || meshStubbed}
        unavailableReason={stubReason ?? cadTooltip}
      />
      <DownloadButton
        format="fluid.step"
        pickedId={pickedId}
        label="Fluid STEP"
        disabled={cadAvailable !== true || meshStubbed}
        unavailableReason={
          stubReason ??
          (cadAvailable === false ? CAD_UNAVAILABLE_TOOLTIP : undefined)
        }
        tooltip="Fluid passage volume with 8 named patches (FILE_DESCRIPTION; patch names in DESCRIPTION text, not PRODUCT_DEFINITION)"
      />
      <DownloadButton
        format="turbogrid.ndf"
        pickedId={pickedId}
        label="NDF"
        disabled={meshStubbed}
        unavailableReason={stubReason}
        tooltip="Hub, shroud, blade profiles in Ansys TurboGrid NDF format"
      />
      <span className="ml-auto text-[10px] text-text-muted">
        {pickedId ? "Streaming from /api/candidates" : "No candidate"}
      </span>
    </div>
  );
}

/** Whether this download format requires the cascade[cad] extra. */
const CAD_FORMATS: Set<DownloadFormat> = new Set(["step", "iges", "fluid.step"]);

function DownloadButton({
  format,
  pickedId,
  label,
  disabled,
  unavailableReason,
  tooltip,
}: {
  format: DownloadFormat;
  pickedId: string | null;
  label: string;
  disabled?: boolean;
  unavailableReason?: string;
  /** Informational tooltip shown even when the button is enabled. */
  tooltip?: string;
}) {
  const href = pickedId ? downloadUrl(pickedId, format) : "#";

  /**
   * W-19 AC3: When the user clicks a CAD export button that was NOT
   * proactively disabled (e.g. the health probe is still in-flight or the
   * server-side state changed), intercept the fetch, detect a 503, and show
   * a clear toast instead of silently failing or showing a broken download.
   */
  const handleCadClick = async (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (!CAD_FORMATS.has(format) || !pickedId) return;
    e.preventDefault();
    try {
      const resp = await fetch(href, { method: "HEAD" });
      if (resp.status === 503) {
        toast.error(
          "CAD export requires the cascade[cad] extra. " +
            "Run pip install 'cascade[cad]' or contact support.",
          { duration: 6000 },
        );
        return;
      }
      // Non-503: trigger the real download.
      window.location.href = href;
    } catch {
      // Network error — fall back to direct link navigation.
      window.location.href = href;
    }
  };

  if (!pickedId || disabled) {
    const button = (
      <Button
        variant="ghost"
        size="sm"
        disabled
        aria-label={`Download ${label}${unavailableReason ? ` (${unavailableReason})` : ""}`}
      >
        <Download className="h-3 w-3" />
        <span>{label}</span>
      </Button>
    );
    if (unavailableReason) {
      return (
        <Tooltip>
          <TooltipTrigger asChild>
            {/*
              shadcn TooltipTrigger requires a single child; wrap the disabled
              Button in a span so it receives pointer events for the hover.
            */}
            <span className="inline-block">{button}</span>
          </TooltipTrigger>
          <TooltipContent>{unavailableReason}</TooltipContent>
        </Tooltip>
      );
    }
    return button;
  }

  if (CAD_FORMATS.has(format)) {
    // Intercept CAD downloads to detect 503 and show the helpful toast.
    const btn = (
      <Button variant="ghost" size="sm" asChild>
        <a
          href={href}
          onClick={handleCadClick}
          aria-label={`Download ${label}${tooltip ? ` — ${tooltip}` : ""}`}
        >
          <Download className="h-3 w-3" />
          <span>{label}</span>
        </a>
      </Button>
    );
    if (tooltip) {
      return (
        <Tooltip>
          <TooltipTrigger asChild>{btn}</TooltipTrigger>
          <TooltipContent>{tooltip}</TooltipContent>
        </Tooltip>
      );
    }
    return btn;
  }

  const plainBtn = (
    <Button variant="ghost" size="sm" asChild>
      <a href={href} download aria-label={`Download ${label}${tooltip ? ` — ${tooltip}` : ""}`}>
        <Download className="h-3 w-3" />
        <span>{label}</span>
      </a>
    </Button>
  );
  if (tooltip) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>{plainBtn}</TooltipTrigger>
        <TooltipContent>{tooltip}</TooltipContent>
      </Tooltip>
    );
  }
  return plainBtn;
}

function CanvasFallback() {
  return (
    <div className="flex h-full items-center justify-center bg-surface-subtle/30 text-xs text-text-muted">
      Loading 3D viewer…
    </div>
  );
}

function EmptyOverlay() {
  return (
    <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
      <div className="pointer-events-auto max-w-xs rounded-md border border-dashed border-border-subtle bg-surface-default/70 p-3 text-center text-xs backdrop-blur">
        <p className="text-sm text-text">No candidate picked.</p>
        <p className="mt-1 text-text-muted">
          Click a point on the scatter to load that impeller geometry here.
        </p>
      </div>
    </div>
  );
}

/**
 * Honesty banner over the canvas: the viewer must never show a stub or a
 * stale mesh as if it were the picked candidate's geometry without saying
 * so (the silent-stub failure mode this replaces is the worst of both).
 */
function StatusOverlay({
  tone,
  children,
}: {
  tone: "warning" | "error";
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "absolute left-3 top-3 z-10 max-w-xs rounded-md border px-3 py-2 text-xs shadow-z2 backdrop-blur",
        tone === "warning"
          ? "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300"
          : "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300",
      )}
      role="status"
      aria-live="polite"
    >
      {children}
    </div>
  );
}
