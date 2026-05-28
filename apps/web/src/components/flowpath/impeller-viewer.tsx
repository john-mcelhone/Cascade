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
import { Download, Box, Layers, Scissors, Sun, Wand2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useFlowPathStore } from "@/lib/flowpath/store";
import { useGltfStream } from "@/lib/three/gltf-loader";
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
  type DownloadFormat,
} from "@/lib/api/flowpath";
import { fmtNumber, cn } from "@/lib/utils";
import { CanvasErrorBoundary } from "@/components/three/canvas-error-boundary";

// Three.js Canvas must be client-only — it touches `window`/`document`
// inside its constructor. Rendering an empty placeholder during SSR keeps
// the layout stable and prevents a flash of restructuring on hydration.
const Canvas = dynamic(
  () => import("@react-three/fiber").then((m) => m.Canvas),
  { ssr: false, loading: () => <CanvasFallback /> },
);

/**
 * The pane currently sources its state entirely from the flow-path Zustand
 * store, so it takes no props.
 */
export function ImpellerViewer() {
  const pickedId = useFlowPathStore((s) => s.pickedCandidateId);
  const candidates = useFlowPathStore((s) => s.candidates);
  const displayMode = useFlowPathStore((s) => s.displayMode);
  const shading = useFlowPathStore((s) => s.shading);
  const setDisplayMode = useFlowPathStore((s) => s.setDisplayMode);
  const setShading = useFlowPathStore((s) => s.setShading);
  const showHud = useFlowPathStore((s) => s.showHud);
  const { resolvedTheme } = useTheme();

  const pickedCandidate = useMemo(
    () => candidates.find((c) => c.id === pickedId) ?? null,
    [candidates, pickedId],
  );

  const url = pickedId ? geometryUrl(pickedId, "standard") : null;

  return (
    <div className="flex h-full flex-col">
      <ViewerToolbar
        displayMode={displayMode}
        shading={shading}
        setDisplayMode={setDisplayMode}
        setShading={setShading}
      />
      <div className="relative flex-1 overflow-hidden">
        <CanvasErrorBoundary fallback={<CanvasFallback />}>
          <Canvas
            gl={{ antialias: true, alpha: true }}
            aria-label="Impeller 3D viewer canvas — drag to orbit, scroll to zoom."
            dpr={[1, 2]}
            className="bg-background"
          >
            <ImpellerScene
              url={url}
              displayMode={displayMode}
              shading={shading}
              theme={resolvedTheme}
              candidate={pickedCandidate}
            />
          </Canvas>
        </CanvasErrorBoundary>

        {showHud && pickedCandidate && (
          <Hud candidate={pickedCandidate} />
        )}

        {!pickedId && <EmptyOverlay />}

        <a
          aria-label="Canvas accessibility note"
          className="sr-only"
        >
          Three.js canvas showing the picked impeller. Use the controls
          above the canvas to swap render modes; the gizmo in the bottom
          right indicates orientation.
        </a>
      </div>
      <DownloadStrip pickedId={pickedId} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Scene
// ---------------------------------------------------------------------------

interface SceneProps {
  url: string | null;
  displayMode: "solid" | "wireframe" | "section";
  shading: "photoreal" | "linedrawing";
  theme: string | undefined;
  candidate: import("@/lib/api/flowpath").ServerCandidate | null;
}

function ImpellerScene({ url, displayMode, shading, theme, candidate }: SceneProps) {
  const { current, previous, loading, crossfade } = useGltfStream(url);
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
      <PerspectiveCamera makeDefault position={[0.15, 0.08, 0.2]} fov={42} />
      <OrbitControls
        enableDamping
        dampingFactor={0.08}
        target={[0, 0, 0]}
        minDistance={0.05}
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

      {loading && proceduralRef.current && (
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
}: {
  candidate: import("@/lib/api/flowpath").ServerCandidate;
}) {
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
            label="U_tip"
            value={`${fmtNumber(
              ((candidate.params.rotor_outlet_radius as number) ?? 0) *
                2 *
                Math.PI *
                ((candidate.params.omega_design as number) ?? 96000) /
                60,
              { decimals: 0 },
            )} m/s`}
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
}

function ViewerToolbar({
  displayMode,
  shading,
  setDisplayMode,
  setShading,
}: ViewerToolbarProps) {
  return (
    <div className="flex items-center gap-1 border-b border-border-subtle bg-surface-subtle/30 px-2 py-1.5">
      <ToggleGroupItem
        label="Solid"
        icon={Box}
        active={displayMode === "solid"}
        onClick={() => setDisplayMode("solid")}
      />
      <ToggleGroupItem
        label="Wireframe"
        icon={Layers}
        active={displayMode === "wireframe"}
        onClick={() => setDisplayMode("wireframe")}
      />
      <ToggleGroupItem
        label="Section"
        icon={Scissors}
        active={displayMode === "section"}
        onClick={() => setDisplayMode("section")}
      />

      <span className="mx-1 h-4 w-px bg-border-subtle" aria-hidden />

      <ToggleGroupItem
        label="Photoreal"
        icon={Sun}
        active={shading === "photoreal"}
        onClick={() => setShading("photoreal")}
      />
      <ToggleGroupItem
        label="Line drawing"
        icon={Wand2}
        active={shading === "linedrawing"}
        onClick={() => setShading("linedrawing")}
      />
    </div>
  );
}

function ToggleGroupItem({
  label,
  icon: Icon,
  active,
  onClick,
}: {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={onClick}
          aria-pressed={active}
          aria-label={label}
          className={cn(
            "inline-flex h-6 items-center gap-1 rounded-sm px-1.5 text-xs",
            active
              ? "bg-brand-surface text-brand-text"
              : "text-text-muted hover:bg-surface-subtle hover:text-text",
          )}
        >
          <Icon className="h-3 w-3" />
          <span className="hidden md:inline">{label}</span>
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

function DownloadStrip({ pickedId }: { pickedId: string | null }) {
  // W-19: Probe the /api/health/cad endpoint (richer than _cad/available)
  // so the UI can disable STEP/IGES buttons proactively and show the
  // OCCT version in the tooltip when available.
  const [cadAvailable, setCadAvailable] = useState<boolean | null>(null);
  useEffect(() => {
    const ctrl = new AbortController();
    cadHealth(ctrl.signal).then((h) => setCadAvailable(h.cad_available));
    return () => ctrl.abort();
  }, []);

  const cadTooltip =
    cadAvailable === false ? CAD_UNAVAILABLE_TOOLTIP : undefined;

  return (
    <div
      className="flex items-center gap-1 border-t border-border-subtle bg-surface-subtle/30 px-2 py-1.5"
      aria-label="Download options for the picked candidate"
    >
      <DownloadButton format="glb" pickedId={pickedId} label="glTF" />
      <DownloadButton format="stl" pickedId={pickedId} label="STL" />
      <DownloadButton
        format="step"
        pickedId={pickedId}
        label="STEP"
        disabled={cadAvailable !== true}
        unavailableReason={cadTooltip}
      />
      <DownloadButton
        format="iges"
        pickedId={pickedId}
        label="IGES"
        disabled={cadAvailable !== true}
        unavailableReason={cadTooltip}
      />
      <DownloadButton
        format="fluid.step"
        pickedId={pickedId}
        label="Fluid STEP"
        disabled={cadAvailable !== true}
        unavailableReason={cadAvailable === false ? CAD_UNAVAILABLE_TOOLTIP : undefined}
        tooltip="Fluid passage volume with 8 named patches (FILE_DESCRIPTION; patch names in DESCRIPTION text, not PRODUCT_DEFINITION)"
      />
      <DownloadButton
        format="turbogrid.ndf"
        pickedId={pickedId}
        label="NDF"
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
