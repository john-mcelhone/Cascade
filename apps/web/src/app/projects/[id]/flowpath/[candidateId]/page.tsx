"use client";

/**
 * Candidate detail route (U8) — `/projects/[id]/flowpath/[candidateId]`.
 *
 * Self-sufficient from the URL: fetches the candidate, its merged geometry,
 * and the candidate-scoped manufacturability verdict by id; never assumes a
 * warm client store (paste the URL in a fresh tab and it renders the same).
 *
 * States:
 *  - unknown / restart-expired id (404) → designed not-found with a
 *    "re-run exploration" CTA (candidates are ephemeral; pins persist);
 *  - candidate from a non-latest exploration job → provenance label
 *    "from exploration job X" with a warning-tinted stale chip;
 *  - cross-project candidate → same designed not-found.
 *
 * Handoffs: "Send to cycle" writes the merged geometry (the normative
 * `build_cc_geometry` merge, serialized server-side) onto the project's
 * Compressor component; "Pin as active candidate" persists the pin +
 * params snapshot to the project TOML.
 */

import { use, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  Compass,
  Loader2,
  Pin,
  Send,
  Unlink,
  XOctagon,
} from "lucide-react";

import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  DownloadStrip,
  ImpellerViewerView,
} from "@/components/flowpath/impeller-viewer";
import { ManufacturabilityPanel } from "@/components/flowpath/manufacturability-panel";
import {
  detachComponentGeometry,
  fetchCandidateOutcome,
  FlowPathApiError,
  getMergedGeometry,
  getProjectSettings,
  getRawComponents,
  pinCandidate,
  sendCandidateToCycle,
  type MergedGeometry,
  type RawComponent,
  type ServerCandidate,
} from "@/lib/api/flowpath";
import { useProjectDisplayName, useRuns } from "@/lib/api/hooks";
import {
  candidateStatusChip,
  classifyCandidateDetail,
  handoffDisabledReason,
  objectiveDisplay,
  type CandidateDetailState,
} from "@/lib/flowpath/candidate-detail";
import { useFlowPathStore } from "@/lib/flowpath/store";
import { cn } from "@/lib/utils";

interface PageProps {
  params: Promise<{ id: string; candidateId: string }>;
}

export default function CandidateDetailPage({ params }: PageProps) {
  const { id, candidateId } = use(params);
  const projectName = useProjectDisplayName(id);
  const setPicked = useFlowPathStore((s) => s.setPicked);
  const queryClient = useQueryClient();
  const router = useRouter();

  // ---- Data: everything keyed off the URL ---------------------------------

  const candidateQuery = useQuery({
    queryKey: ["candidate-outcome", candidateId],
    queryFn: () => fetchCandidateOutcome(candidateId),
    staleTime: 5_000,
  });
  const outcome = candidateQuery.data ?? null;

  // Latest finished exploration for the provenance / stale classification.
  const { data: runs } = useRuns(id);
  const latestExploreJobId = useMemo(() => {
    const explore = (runs ?? []).find(
      (r) => r.kind === "explore" && r.status === "succeeded",
    );
    return explore?.id ?? null;
  }, [runs]);

  const state: CandidateDetailState = classifyCandidateDetail({
    outcome,
    routeProjectId: id,
    latestExploreJobId,
  });
  const candidate: ServerCandidate | null =
    (state === "ok" || state === "stale") && outcome?.kind === "ok"
      ? outcome.candidate
      : null;
  const isValid = candidate?.status === "VALID";
  // MANUFACTURABILITY_FAILED solved fine and its merged geometry is
  // well-defined — show it (the user needs to SEE the un-millable
  // passage); only handoff and exports stay VALID-gated.
  const geometryWellDefined =
    isValid || candidate?.status === "MANUFACTURABILITY_FAILED";

  const mergedQuery = useQuery({
    queryKey: ["candidate-merged-geometry", candidateId, id],
    queryFn: () => getMergedGeometry(candidateId, id),
    enabled: Boolean(candidate) && geometryWellDefined,
    retry: false,
  });

  const componentsQuery = useQuery({
    queryKey: ["raw-components", id],
    queryFn: () => getRawComponents(id),
  });
  const compressor: RawComponent | null = useMemo(
    () =>
      componentsQuery.data?.find((c) => c.kind === "Compressor") ?? null,
    [componentsQuery.data],
  );
  const hasCompressor: boolean | null = componentsQuery.data
    ? Boolean(compressor)
    : null;
  const existingGeometry = compressor?.params?.geometry_params as
    | Record<string, unknown>
    | undefined;
  const hasExistingGeometry = Boolean(
    existingGeometry && Object.keys(existingGeometry).length > 0,
  );

  const settingsQuery = useQuery({
    queryKey: ["project-settings", id],
    queryFn: () => getProjectSettings(id),
  });
  const isPinned =
    settingsQuery.data?.active_candidate_id === candidateId;

  // ---- URL arrival side effects -------------------------------------------

  // Arriving by URL sets the picked candidate so back-navigation to the
  // flow-path scatter highlights this dot.
  useEffect(() => {
    // Identity gate: a cached/stale candidate object from a previous route
    // must not mark the *current* URL's id as picked.
    if (candidate && candidate.id === candidateId) setPicked(candidateId);
  }, [candidate, candidateId, setPicked]);

  // Accessibility: focus moves to the page heading on navigation.
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  // ---- Handoff mutations ---------------------------------------------------

  const [align, setAlign] = useState(true);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const invalidateGeometryConsumers = () => {
    queryClient.invalidateQueries({ queryKey: ["raw-components", id] });
    queryClient.invalidateQueries({ queryKey: ["project", id, "cycle"] });
    queryClient.invalidateQueries({ queryKey: ["project", id] });
  };

  const sendMutation = useMutation({
    mutationFn: () => sendCandidateToCycle(candidateId, id, align),
    onSuccess: () => {
      invalidateGeometryConsumers();
      toast.success("Compressor geometry updated — open Cycle", {
        action: {
          label: "Open Cycle",
          onClick: () => router.push(`/projects/${id}/cycle`),
        },
      });
    },
    onError: (err) => {
      toast.error(
        err instanceof FlowPathApiError
          ? err.message
          : `Send to cycle failed: ${(err as Error).message}`,
      );
    },
  });

  const pinMutation = useMutation({
    mutationFn: () => pinCandidate(candidateId, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project-settings", id] });
      queryClient.invalidateQueries({
        predicate: (q) =>
          q.queryKey[0] === "project" &&
          q.queryKey[1] === id &&
          q.queryKey[2] === "manufacturability",
      });
      toast.success(
        "Pinned as active candidate — the pin persists across restarts.",
      );
    },
    onError: (err) => {
      toast.error(
        err instanceof FlowPathApiError
          ? err.message
          : `Pin failed: ${(err as Error).message}`,
      );
    },
  });

  const detachMutation = useMutation({
    mutationFn: async () => {
      // Capture at call time: the components query may have refetched (or
      // errored) since the button rendered. A missing compressor surfaces
      // as a descriptive mutation error toast, not a TypeError.
      const compressorId = compressor?.id;
      if (!compressorId) {
        throw new Error(
          "No cycle Compressor component found — nothing to detach geometry from.",
        );
      }
      return detachComponentGeometry(id, compressorId);
    },
    onSuccess: () => {
      invalidateGeometryConsumers();
      toast.success(
        "Geometry detached — the cycle falls back to constant-η.",
      );
    },
    onError: (err) => {
      toast.error(`Detach failed: ${(err as Error).message}`);
    },
  });

  const disabledReason = handoffDisabledReason({
    candidate,
    hasCompressor,
  });

  const onSendClick = () => {
    if (disabledReason || sendMutation.isPending) return;
    if (hasExistingGeometry) {
      setConfirmOpen(true);
      return;
    }
    sendMutation.mutate();
  };

  // ---- Render ---------------------------------------------------------------

  const shortId = candidateId.slice(0, 8);

  if (state === "expired" || state === "cross-project") {
    return (
      <NotFoundState
        projectId={id}
        projectName={projectName}
        candidateId={candidateId}
        crossProject={state === "cross-project"}
      />
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header — mirrors PageHeader's chrome, but the h1 is focusable so
          focus can move to the page heading on navigation (a11y per the
          design notes). */}
      <div className="flex flex-col gap-2 border-b border-border-subtle bg-surface px-5 py-4">
        <Breadcrumb
          items={[
            { label: "Projects", href: "/projects" },
            { label: projectName, href: `/projects/${id}` },
            { label: "Flow path", href: `/projects/${id}/flowpath` },
            { label: shortId },
          ]}
        />
        <div className="flex flex-wrap items-center gap-2">
          <h1
            ref={headingRef}
            tabIndex={-1}
            className="font-mono text-lg font-semibold leading-tight tracking-tight text-text outline-none"
          >
            Candidate {shortId}
          </h1>
          {candidate && <StatusChip status={candidate.status} />}
          {isPinned && (
            <Badge variant="brand" className="gap-1">
              <Pin className="h-3 w-3" aria-hidden />
              pinned
            </Badge>
          )}
        </div>
        {candidate && !isValid && candidate.error_message && (
          <p className="mt-1 text-xs text-text-muted" role="note">
            {candidate.error_message}
          </p>
        )}
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Main: scrollable detail sheet */}
        <main className="relative min-w-0 flex-1 overflow-y-auto">
          {/* Sticky handoff actions */}
          <div className="sticky top-0 z-10 flex flex-wrap items-center gap-3 border-b border-border-subtle bg-surface/95 px-5 py-2 backdrop-blur">
            <SendToCycleButton
              disabledReason={disabledReason}
              pending={sendMutation.isPending}
              onClick={onSendClick}
            />
            <label className="flex items-center gap-1.5 text-xs text-text-muted">
              <input
                type="checkbox"
                checked={align}
                onChange={(e) => setAlign(e.target.checked)}
                disabled={Boolean(disabledReason)}
                className="h-3.5 w-3.5 accent-current"
                aria-describedby="align-help"
              />
              Align cycle design point
              <Tooltip>
                <TooltipTrigger asChild>
                  <span
                    id="align-help"
                    className="cursor-help text-text-subtle underline decoration-dotted"
                  >
                    ?
                  </span>
                </TooltipTrigger>
                <TooltipContent className="max-w-xs">
                  Also sets the cycle compressor&apos;s pressure ratio and the
                  inlet mass flow to this candidate&apos;s design point.
                  Without alignment the co-simulation runs the geometry deep
                  off-design and a mean-line refusal is the expected outcome.
                </TooltipContent>
              </Tooltip>
            </label>
            <Button
              variant="outline"
              size="sm"
              className="gap-1"
              disabled={!candidate || pinMutation.isPending || isPinned}
              onClick={() => pinMutation.mutate()}
              aria-label="Pin as active candidate"
            >
              {pinMutation.isPending ? (
                <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
              ) : (
                <Pin className="h-3 w-3" aria-hidden />
              )}
              {isPinned ? "Pinned" : "Pin"}
            </Button>
            {hasExistingGeometry && compressor && (
              <Button
                variant="ghost"
                size="sm"
                className="ml-auto gap-1 text-text-muted"
                disabled={detachMutation.isPending}
                onClick={() => detachMutation.mutate()}
                aria-label="Detach geometry from the cycle Compressor"
              >
                <Unlink className="h-3 w-3" aria-hidden />
                Detach geometry
              </Button>
            )}
          </div>

          {state === "loading" || !outcome ? (
            <LoadingSheet />
          ) : state === "error" ? (
            <ErrorSheet
              message={
                outcome.kind === "error" ? outcome.message : "Unknown error"
              }
            />
          ) : candidate ? (
            <div className="space-y-5 px-5 py-4">
              <ProvenanceSection
                candidate={candidate}
                stale={state === "stale"}
              />
              <ObjectivesSection candidate={candidate} />
              {geometryWellDefined ? (
                <MergedParamsSection
                  merged={mergedQuery.data ?? null}
                  loading={mergedQuery.isLoading}
                />
              ) : (
                <SuppressedSection
                  title="Merged geometry"
                  reason="Geometry is not shown for a candidate whose design point refused — no trustworthy parameter set exists."
                />
              )}
              <section aria-label="Manufacturability">
                <SectionHeading>Manufacturability</SectionHeading>
                <div className="overflow-hidden rounded-md border border-border-subtle">
                  <ManufacturabilityPanel
                    projectId={id}
                    candidateId={candidateId}
                    defaultExpanded
                  />
                </div>
              </section>
              {isValid ? (
                <section aria-label="Exports">
                  <SectionHeading>Exports</SectionHeading>
                  <div className="overflow-hidden rounded-md border border-border-subtle">
                    <DownloadStrip pickedId={candidateId} />
                  </div>
                </section>
              ) : (
                <SuppressedSection
                  title="Exports"
                  reason="Exports are disabled for non-VALID candidates."
                />
              )}
            </div>
          ) : null}
        </main>

        {/* Right pane: 3D viewer column (mirrors the flow-path layout) */}
        <aside
          className="hidden w-[360px] shrink-0 border-l border-border-subtle lg:block"
          aria-label="Impeller 3D viewer"
        >
          {geometryWellDefined || !candidate ? (
            <ImpellerViewerView
              candidateId={candidate ? candidateId : null}
              candidate={candidate}
              hideDownloads
            />
          ) : (
            <div className="flex h-full items-center justify-center p-4 text-center text-xs text-text-muted">
              <div>
                <AlertTriangle
                  className="mx-auto mb-2 h-4 w-4 text-semantic-warning-text"
                  aria-hidden
                />
                Geometry preview suppressed — this candidate&apos;s design
                point refused ({candidate.status}).
              </div>
            </div>
          )}
        </aside>
      </div>

      {/* Overwrite confirmation */}
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Overwrite existing compressor geometry?</DialogTitle>
            <DialogDescription>
              The cycle Compressor already carries a geometry set
              {compressor ? ` (component "${compressor.name}")` : ""}. Sending
              this candidate replaces it wholesale — the previous geometry is
              not recoverable from the cycle page.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                // Double-submit guard: a second click before the dialog
                // closes must not fire a second send.
                if (sendMutation.isPending) return;
                setConfirmOpen(false);
                sendMutation.mutate();
              }}
            >
              Replace geometry
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * Sections
 * ------------------------------------------------------------------------- */

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-1.5 text-xs font-medium uppercase tracking-wide text-text-muted">
      {children}
    </h2>
  );
}

function ProvenanceSection({
  candidate,
  stale,
}: {
  candidate: ServerCandidate;
  stale: boolean;
}) {
  return (
    <section aria-label="Provenance">
      <SectionHeading>Provenance</SectionHeading>
      <div className="rounded-md border border-border-subtle">
        <table className="w-full text-xs">
          <tbody>
            <DenseRow label="Candidate id">
              <span className="font-mono">{candidate.id}</span>
            </DenseRow>
            <DenseRow label="Exploration">
              <span className="inline-flex flex-wrap items-center gap-2">
                <span className="font-mono">
                  from exploration job {candidate.job_id}
                </span>
                {stale && (
                  <Badge variant="warning" className="gap-1">
                    <AlertTriangle className="h-3 w-3" aria-hidden />
                    stale — a newer exploration exists
                  </Badge>
                )}
              </span>
            </DenseRow>
            <DenseRow label="Sample index">
              <span className="font-mono tabular-nums">
                #{candidate.index}
              </span>
            </DenseRow>
          </tbody>
        </table>
      </div>
      <p className="mt-1 text-[11px] text-text-subtle">
        Exploration candidates are held in memory and expire on server
        restart. Pin the candidate to persist its parameters with the
        project.
      </p>
    </section>
  );
}

const OBJECTIVE_ROWS: Array<{ key: string; label: string; unit: string }> = [
  { key: "eta_tt", label: "η_tt", unit: "–" },
  { key: "eta_ts", label: "η_ts", unit: "–" },
  { key: "power", label: "power", unit: "kW" },
  { key: "mass", label: "mass", unit: "kg" },
  { key: "M_rel", label: "M_rel", unit: "–" },
];

function ObjectivesSection({ candidate }: { candidate: ServerCandidate }) {
  return (
    <section aria-label="Objectives and constraints">
      <SectionHeading>Objectives &amp; constraints</SectionHeading>
      <div className="rounded-md border border-border-subtle">
        <table className="w-full text-xs">
          <tbody>
            {OBJECTIVE_ROWS.map(({ key, label, unit }) => {
              const d = objectiveDisplay(
                key,
                candidate.objectives[key],
                candidate.status,
                key === "power" || key === "mass" ? 3 : 4,
              );
              return (
                <DenseRow key={key} label={label} unit={unit}>
                  {d.sentinel ? (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span
                          className="cursor-help font-mono text-text-muted"
                          aria-label={`${label}: no value — sentinel`}
                        >
                          —
                        </span>
                      </TooltipTrigger>
                      <TooltipContent className="max-w-xs">
                        No real value exists — the solver wrote a sentinel
                        because this point&apos;s evaluation refused
                        ({candidate.status}).
                      </TooltipContent>
                    </Tooltip>
                  ) : (
                    <span className="font-mono tabular-nums">{d.text}</span>
                  )}
                </DenseRow>
              );
            })}
            {Object.entries(candidate.constraints ?? {}).map(([k, ok]) => (
              <DenseRow key={k} label={k} unit="constraint">
                <span
                  className={cn(
                    "inline-flex items-center gap-1 font-mono",
                    ok
                      ? "text-semantic-success-text"
                      : "text-semantic-danger-text",
                  )}
                >
                  {ok ? (
                    <Check className="h-3 w-3" aria-hidden />
                  ) : (
                    <XOctagon className="h-3 w-3" aria-hidden />
                  )}
                  {ok ? "pass" : "fail"}
                </span>
              </DenseRow>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/** Geometry field formatting: lengths in mm, angles in deg, ratios plain. */
const GEOM_LENGTH_KEYS = new Set([
  "inducer_hub_radius",
  "inducer_tip_radius",
  "impeller_outlet_radius",
  "blade_height_outlet",
  "tip_clearance",
  "chord_meridional",
]);
const GEOM_ANGLE_KEYS = new Set([
  "beta_2_metal_rad",
  "inducer_tip_blade_metal_rad",
]);

function fmtGeomValue(key: string, v: number): { text: string; unit: string } {
  if (key === "blade_count") {
    return { text: String(Math.round(v)), unit: "–" };
  }
  if (GEOM_ANGLE_KEYS.has(key)) {
    return { text: ((v * 180) / Math.PI).toFixed(1), unit: "deg" };
  }
  if (GEOM_LENGTH_KEYS.has(key)) {
    return { text: (v * 1e3).toFixed(3), unit: "mm" };
  }
  return { text: v.toFixed(4), unit: "–" };
}

function MergedParamsSection({
  merged,
  loading,
}: {
  merged: MergedGeometry | null;
  loading: boolean;
}) {
  return (
    <section aria-label="Merged geometry">
      <SectionHeading>
        Merged geometry — the parameter set actually used
      </SectionHeading>
      {loading ? (
        <div className="flex items-center gap-2 rounded-md border border-border-subtle px-3 py-2 text-xs text-text-muted">
          <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
          Resolving merged geometry…
        </div>
      ) : !merged ? (
        <div className="rounded-md border border-border-subtle px-3 py-2 text-xs text-text-muted">
          Merged geometry unavailable.
        </div>
      ) : (
        <>
          <div className="rounded-md border border-border-subtle">
            <table className="w-full text-xs">
              <tbody>
                {Object.entries(merged.geometry_params).map(([k, v]) => {
                  const f = fmtGeomValue(k, v);
                  const sampled = merged.sampled_keys.includes(k);
                  return (
                    <DenseRow
                      key={k}
                      label={k}
                      unit={f.unit}
                      labelMono
                      trailing={
                        sampled ? (
                          <Badge variant="brand" className="text-[10px]">
                            sampled
                          </Badge>
                        ) : (
                          <span className="text-[10px] text-text-subtle">
                            derived
                          </span>
                        )
                      }
                    >
                      <span className="font-mono tabular-nums">{f.text}</span>
                    </DenseRow>
                  );
                })}
                <DenseRow label="meanline_rpm_rpm" unit="rpm" labelMono>
                  <span className="font-mono tabular-nums">
                    {merged.meanline_rpm_rpm.toFixed(0)}
                  </span>
                </DenseRow>
                <DenseRow label="mass_flow (design pt)" unit="kg/s" labelMono>
                  <span className="font-mono tabular-nums">
                    {Number(
                      merged.operating_point.mass_flow_kg_per_s ?? 0,
                    ).toFixed(4)}
                  </span>
                </DenseRow>
              </tbody>
            </table>
          </div>
          <p className="mt-1 text-[11px] text-text-subtle">
            Sampled values come from the Sobol&apos; sweep; derived values are
            r₂-scaled from the Eckardt Rotor A reference to keep the design
            point physically consistent. &quot;Send to cycle&quot; writes
            exactly this set.
          </p>
        </>
      )}
    </section>
  );
}

function SuppressedSection({
  title,
  reason,
}: {
  title: string;
  reason: string;
}) {
  return (
    <section aria-label={title}>
      <SectionHeading>{title}</SectionHeading>
      <div className="flex items-center gap-2 rounded-md border border-dashed border-border-subtle px-3 py-2 text-xs text-text-muted">
        <AlertTriangle
          className="h-3 w-3 shrink-0 text-semantic-warning-text"
          aria-hidden
        />
        {reason}
      </div>
    </section>
  );
}

/** 24 px dense table row: label · value · unit (· trailing). */
function DenseRow({
  label,
  unit,
  labelMono = false,
  trailing,
  children,
}: {
  label: string;
  unit?: string;
  labelMono?: boolean;
  trailing?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <tr className="h-6 border-b border-border-subtle/60 last:border-b-0">
      <td
        className={cn(
          "w-56 px-2.5 text-text-muted",
          labelMono && "font-mono",
        )}
      >
        {label}
      </td>
      <td className="px-2.5 text-right">{children}</td>
      <td className="w-16 px-2.5 text-left text-text-subtle">{unit ?? ""}</td>
      {trailing !== undefined && (
        <td className="w-20 px-2.5 text-right">{trailing}</td>
      )}
    </tr>
  );
}

/* ---------------------------------------------------------------------------
 * Status chip, action buttons, page-level states
 * ------------------------------------------------------------------------- */

function StatusChip({ status }: { status: string }) {
  const chip = candidateStatusChip(status);
  const Icon =
    chip.icon === "check"
      ? Check
      : chip.icon === "x-octagon"
        ? XOctagon
        : AlertTriangle;
  return (
    <Badge variant={chip.variant} className="gap-1">
      <Icon className="h-3 w-3" aria-hidden />
      {chip.label}
    </Badge>
  );
}

function SendToCycleButton({
  disabledReason,
  pending,
  onClick,
}: {
  disabledReason: string | null;
  pending: boolean;
  onClick: () => void;
}) {
  const button = (
    <Button
      size="sm"
      className="gap-1"
      disabled={Boolean(disabledReason) || pending}
      onClick={onClick}
      aria-label={
        disabledReason
          ? `Send to cycle (disabled: ${disabledReason})`
          : "Send geometry to cycle"
      }
    >
      {pending ? (
        <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
      ) : (
        <Send className="h-3 w-3" aria-hidden />
      )}
      {pending ? "Sending…" : "Send to cycle"}
    </Button>
  );
  if (disabledReason) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-block">{button}</span>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs">{disabledReason}</TooltipContent>
      </Tooltip>
    );
  }
  return button;
}

function LoadingSheet() {
  return (
    <div className="flex h-64 items-center justify-center gap-2 text-xs text-text-muted">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      Loading candidate…
    </div>
  );
}

function ErrorSheet({ message }: { message: string }) {
  return (
    <div className="px-5 py-8 text-center text-xs text-text-muted">
      <p className="mb-1 text-sm text-text">
        Couldn&apos;t reach the Cascade API.
      </p>
      <p className="font-mono">{message}</p>
    </div>
  );
}

/**
 * Designed not-found / expired state. Candidates are ephemeral — the
 * in-memory index dies with the server — so an unknown id and a
 * restart-expired id share this state, with re-running the exploration as
 * the first-class way back.
 */
function NotFoundState({
  projectId,
  projectName,
  candidateId,
  crossProject,
}: {
  projectId: string;
  projectName: string;
  candidateId: string;
  crossProject: boolean;
}) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    headingRef.current?.focus();
  }, []);
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border-subtle bg-surface px-5 py-4">
        <Breadcrumb
          items={[
            { label: "Projects", href: "/projects" },
            { label: projectName, href: `/projects/${projectId}` },
            { label: "Flow path", href: `/projects/${projectId}/flowpath` },
            { label: candidateId.slice(0, 8) },
          ]}
        />
      </div>
      <div className="flex flex-1 items-center justify-center px-5">
        <div className="max-w-md rounded-md border border-dashed border-border-subtle bg-surface-subtle/30 p-6 text-center">
          <Compass
            className="mx-auto mb-3 h-6 w-6 text-text-subtle"
            aria-hidden
          />
          <h1
            ref={headingRef}
            tabIndex={-1}
            className="mb-1 text-sm font-semibold text-text outline-none"
          >
            {crossProject
              ? "Candidate not found in this project"
              : "Candidate not found"}
          </h1>
          <p className="mb-1 text-xs text-text-muted">
            {crossProject ? (
              <>
                <span className="font-mono">{candidateId.slice(0, 12)}…</span>{" "}
                belongs to a different project, so it isn&apos;t shown here.
              </>
            ) : (
              <>
                Exploration candidates live in memory and expire when the
                server restarts —{" "}
                <span className="font-mono">{candidateId.slice(0, 12)}…</span>{" "}
                is unknown or has expired.
              </>
            )}
          </p>
          <p className="mb-4 text-xs text-text-subtle">
            Pinned candidates persist with the project; everything else is
            one exploration away.
          </p>
          <div className="flex items-center justify-center gap-2">
            <Button asChild size="sm">
              <Link href={`/projects/${projectId}/flowpath`}>
                Re-run exploration
              </Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link href={`/projects/${projectId}/flowpath`}>
                <ArrowLeft className="h-3 w-3" aria-hidden />
                Back to Flow path
              </Link>
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
