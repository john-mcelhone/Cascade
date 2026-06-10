"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useTheme } from "next-themes";
import { ArrowUpRight } from "lucide-react";
import type {
  Layout,
  PlotMouseEvent,
  PlotSelectionEvent,
} from "plotly.js";

// `plotly.js`'s `Data` union does not include all of `customdata` / colorbar
// shapes we want to use across the scatter and parallel-coords specs;
// relax it locally so the spec stays readable. Runtime is unchanged.
type Data = Record<string, unknown>;
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useFlowPathStore } from "@/lib/flowpath/store";
import type { ServerCandidate } from "@/lib/api/flowpath";
import { fmtNumber } from "@/lib/utils";
import { useFlowPathParameterAxes } from "./scatter-utils";
import {
  parseFilter,
  candidatePasses,
  buildKnownFields,
} from "@/lib/flowpath/filter-dsl";

// Plotly is heavy + DOM-dependent. Load it on the client only.
const Plot = dynamic(
  async () => {
    const factory = (await import("react-plotly.js/factory")).default;
    const plotly = await import("plotly.js-dist-min");
    return factory(plotly.default ?? plotly);
  },
  { ssr: false, loading: () => <ScatterSkeleton /> },
);

const FAILURE_STATUSES = new Set([
  "INVALID_GEOMETRY",
  "REGIME_OUT_OF_VALIDITY",
  // Solved fine, but a standard 5-axis machining cell cannot produce the
  // geometry — plotted at its REAL objectives so the cost of the lost
  // design is visible, greyed out like every other refusal.
  "MANUFACTURABILITY_FAILED",
  "STALL_SURGE",
  "CHOKED",
  "FAILED",
  "DIVERGED",
]);

interface DesignScatterProps {
  projectId: string;
}

/**
 * Centre pane: the design-space scatter, axes selectors, brushing, and
 * the parallel-coordinates strip below. Reads candidates and axis state
 * from `useFlowPathStore`.
 */
export function DesignScatter({ projectId }: DesignScatterProps) {
  const candidates = useFlowPathStore((s) => s.candidates);
  const scatterX = useFlowPathStore((s) => s.scatterX);
  const scatterY = useFlowPathStore((s) => s.scatterY);
  const scatterColor = useFlowPathStore((s) => s.scatterColor);
  const setScatterAxes = useFlowPathStore((s) => s.setScatterAxes);
  const setPicked = useFlowPathStore((s) => s.setPicked);
  const pickedId = useFlowPathStore((s) => s.pickedCandidateId);
  const brushed = useFlowPathStore((s) => s.brushedCandidateIds);
  const setBrushed = useFlowPathStore((s) => s.setBrushed);
  const scatterFilter = useFlowPathStore((s) => s.scatterFilter);
  const setScatterFilter = useFlowPathStore((s) => s.setScatterFilter);
  const { resolvedTheme } = useTheme();
  const axes = useFlowPathParameterAxes(projectId);

  // Build the known field set for filter validation.
  const knownFields = useMemo(() => buildKnownFields(candidates), [candidates]);

  // Parse the filter expression. Re-parses only when the expression or the
  // known-field set changes (knownFields changes when the first candidates
  // arrive, then stabilises).
  const filterResult = useMemo(
    () => parseFilter(scatterFilter, candidates.length > 0 ? knownFields : null),
    [scatterFilter, knownFields, candidates.length],
  );

  // Plotly is gentler with a stable revision number than data replacement.
  const revisionRef = useRef(0);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    revisionRef.current += 1;
    setRevision(revisionRef.current);
  }, [candidates.length, scatterX, scatterY, scatterColor, resolvedTheme, scatterFilter]);

  const { valid, failed } = useMemo(() => {
    const v: ServerCandidate[] = [];
    const f: ServerCandidate[] = [];
    for (const c of candidates) {
      if (FAILURE_STATUSES.has(c.status)) f.push(c);
      else v.push(c);
    }
    return { valid: v, failed: f };
  }, [candidates]);

  const valueOf = (c: ServerCandidate, key: string): number => {
    if (key in c.objectives) return c.objectives[key];
    if (key in c.params) return c.params[key];
    return Number.NaN;
  };

  const colors = useMemo(() => valid.map((c) => valueOf(c, scatterColor)), [
    valid,
    scatterColor,
  ]);

  // Per-candidate opacity: 1.0 if passes filter (or no filter), 0.3 if not.
  // Greying out rather than removing keeps the distribution context visible.
  const opacities = useMemo(() => {
    if (!filterResult.ok || filterResult.terms.length === 0) {
      return valid.map(() => 1);
    }
    return valid.map((c) =>
      candidatePasses(c, filterResult.terms) ? 1 : 0.3,
    );
  }, [valid, filterResult]);
  const pickedIdx = useMemo(
    () => valid.findIndex((c) => c.id === pickedId),
    [valid, pickedId],
  );

  const themed = isDark(resolvedTheme);
  const colorscale: Array<[number, string]> = themed
    ? [
        [0, "#3F8B96"], // brand-hover
        [0.5, "#7BA82E"], // chart-9 olive
        [1, "#C25B1F"], // chart-2 sienna
      ]
    : [
        [0, "#1F555E"], // brand-pressed
        [0.5, "#2E8754"], // success-default
        [1, "#B47100"], // warning-default
      ];

  const data: Data[] = [
    {
      type: "scattergl",
      mode: "markers",
      name: "Candidates",
      x: valid.map((c) => valueOf(c, scatterX)),
      y: valid.map((c) => valueOf(c, scatterY)),
      customdata: valid.map((c) => c.id),
      text: valid.map((c) =>
        [
          c.id,
          `η_tt = ${fmtNumber(c.objectives.eta_tt ?? 0, { decimals: 4 })}`,
          `η_ts = ${fmtNumber(c.objectives.eta_ts ?? 0, { decimals: 4 })}`,
          `M_rel = ${fmtNumber(c.objectives.M_rel ?? 0, { decimals: 3 })}`,
          `mass = ${fmtNumber(c.objectives.mass ?? 0, { decimals: 3 })} kg`,
        ].join("<br />"),
      ),
      hovertemplate: "%{text}<extra></extra>",
      marker: {
        size: 6,
        color: colors,
        opacity: opacities,
        colorscale,
        colorbar: {
          title: { text: prettyAxis(scatterColor), side: "right" } as never,
          thickness: 8,
          x: 1.02,
          xpad: 0,
          tickfont: { color: themed ? "#C1C5CB" : "#4A4F58", size: 9 },
        } as never,
        line: { width: 0 },
      },
    },
    failed.length > 0 && {
      type: "scattergl",
      mode: "markers",
      name: "Failed",
      x: failed.map((c) => valueOf(c, scatterX)),
      y: failed.map((c) => valueOf(c, scatterY)),
      customdata: failed.map((c) => c.id),
      text: failed.map((c) => {
        const detail = c.error_message
          ? `<br />${c.error_message.slice(0, 140)}`
          : "";
        return `${c.id}<br />status: ${c.status}${detail}`;
      }),
      hovertemplate: "%{text}<extra></extra>",
      marker: {
        size: 5,
        color: themed ? "#7A808A" : "#C1C5CB",
        symbol: "x",
        line: { width: 1, color: themed ? "#C1C5CB" : "#7A808A" },
      },
    },
    pickedIdx >= 0 && {
      type: "scattergl",
      mode: "markers",
      name: "Picked",
      x: [valueOf(valid[pickedIdx]!, scatterX)],
      y: [valueOf(valid[pickedIdx]!, scatterY)],
      hoverinfo: "skip",
      marker: {
        size: 14,
        color: "rgba(0,0,0,0)",
        line: { color: themed ? "#5BA5B0" : "#1F555E", width: 2 },
      },
      showlegend: false,
    },
  ].filter(Boolean) as Data[];

  const layout: Partial<Layout> = {
    autosize: true,
    margin: { t: 24, l: 56, r: 80, b: 40 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: themed ? "#1a1c21" : "#ffffff",
    font: {
      family: "Inter, system-ui, sans-serif",
      color: themed ? "#EEEFF1" : "#1A1C21",
      size: 11,
    },
    xaxis: {
      title: { text: prettyAxis(scatterX), font: { size: 11 } },
      gridcolor: themed ? "#2C3038" : "#EEEFF1",
      zerolinecolor: themed ? "#4A4F58" : "#DCDEE2",
      automargin: true,
    },
    yaxis: {
      title: { text: prettyAxis(scatterY), font: { size: 11 } },
      gridcolor: themed ? "#2C3038" : "#EEEFF1",
      zerolinecolor: themed ? "#4A4F58" : "#DCDEE2",
      automargin: true,
    },
    showlegend: failed.length > 0,
    legend: {
      orientation: "h",
      y: -0.18,
      x: 0,
      font: { size: 10 },
      bgcolor: "rgba(0,0,0,0)",
    },
    dragmode: "select",
    hoverlabel: {
      bgcolor: themed ? "#2C3038" : "#FFFFFF",
      bordercolor: themed ? "#4A4F58" : "#DCDEE2",
      font: { color: themed ? "#EEEFF1" : "#1A1C21", size: 11 },
    },
  };

  const onClick = (e: PlotMouseEvent) => {
    const point = e.points?.[0];
    if (!point) return;
    const id = point.customdata as unknown as string | undefined;
    if (id) setPicked(id);
  };

  const onSelected = (e: PlotSelectionEvent | undefined) => {
    if (!e || !e.points || e.points.length === 0) {
      setBrushed(null);
      return;
    }
    const ids: string[] = [];
    for (const p of e.points) {
      const id = (p as { customdata?: string }).customdata;
      if (id) ids.push(id);
    }
    setBrushed(ids.length > 0 ? ids : null);
  };

  return (
    <div className="flex h-full flex-col">
      <ScatterTopBar
        projectId={projectId}
        axes={axes}
        x={scatterX}
        y={scatterY}
        color={scatterColor}
        setAxes={setScatterAxes}
        filter={scatterFilter}
        setFilter={setScatterFilter}
        filterResult={filterResult}
        candidates={candidates}
        valid={valid}
        brushed={brushed}
        picked={pickedId}
      />

      <div className="relative flex-1">
        {candidates.length === 0 ? (
          <ScatterEmpty />
        ) : (
          <Plot
            data={data}
            layout={layout}
            revision={revision}
            useResizeHandler
            style={{ width: "100%", height: "100%" }}
            config={{
              displaylogo: false,
              responsive: true,
              modeBarButtonsToRemove: [
                "lasso2d",
                "zoom3d",
                "pan3d",
                "orbitRotation",
                "tableRotation",
                "resetCameraDefault3d",
                "resetCameraLastSave3d",
                "hoverClosest3d",
              ],
            }}
            onClick={onClick}
            onSelected={onSelected as never}
            onDeselect={() => setBrushed(null)}
          />
        )}
      </div>

      <ParallelCoordinatesDisclosure
        valid={valid}
        axes={axes}
        themed={themed}
        revision={revision}
      />
    </div>
  );
}

/**
 * Collapsible parallel-coordinates strip. Collapsed by default so the scatter
 * gets the full vertical real estate (engineers spend 95% of their time in
 * the scatter; the PCP is for the rare "what does this region of the design
 * space look like across all dims?" inspection). The toggle state persists
 * via the flow-path store so the user's preference survives navigation.
 */
function ParallelCoordinatesDisclosure({
  valid,
  axes,
  themed,
  revision,
}: PCoordsProps) {
  const open = useFlowPathStore((s) => s.showParallelCoords);
  const setOpen = useFlowPathStore((s) => s.setShowParallelCoords);
  return (
    <div className="shrink-0 border-t border-border-subtle bg-surface-subtle/20">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-controls="parallel-coords-panel"
        className="flex w-full items-center justify-between px-3 py-1.5 text-[11px] text-text-muted hover:text-text"
      >
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden>{open ? "▾" : "▸"}</span>
          <span className="uppercase tracking-wide">Parallel coordinates</span>
          <span className="text-text-subtle">
            ({valid.length} {valid.length === 1 ? "candidate" : "candidates"})
          </span>
        </span>
        <span className="text-text-subtle">
          {open ? "Hide" : "Show"}
        </span>
      </button>
      {open && (
        <div id="parallel-coords-panel">
          <ParallelCoordinates
            valid={valid}
            axes={axes}
            themed={themed}
            revision={revision}
          />
        </div>
      )}
    </div>
  );
}

function isDark(theme: string | undefined): boolean {
  if (typeof window === "undefined") return false;
  if (theme === "dark") return true;
  if (theme === "light") return false;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}

interface ScatterTopBarProps {
  projectId: string;
  axes: ReturnType<typeof useFlowPathParameterAxes>;
  x: string;
  y: string;
  color: string;
  setAxes: (axes: Partial<{ x: string; y: string; color: string }>) => void;
  filter: string;
  setFilter: (v: string) => void;
  filterResult: ReturnType<typeof parseFilter>;
  candidates: ServerCandidate[];
  valid: ServerCandidate[];
  brushed: string[] | null;
  picked: string | null;
}

function ScatterTopBar({
  projectId,
  axes,
  x,
  y,
  color,
  setAxes,
  filter,
  setFilter,
  filterResult,
  candidates,
  valid,
  brushed,
  picked,
}: ScatterTopBarProps) {
  const objectiveKey = "eta_tt";
  const sortBy = (cs: ServerCandidate[]) =>
    [...cs].sort(
      (a, b) =>
        (b.objectives[objectiveKey] ?? -Infinity) -
        (a.objectives[objectiveKey] ?? -Infinity),
    );

  const bestSpace = sortBy(valid)[0] ?? null;
  const bestFilter = brushed
    ? sortBy(valid.filter((c) => brushed.includes(c.id)))[0] ?? null
    : null;
  const pickedCand = picked ? valid.find((c) => c.id === picked) ?? null : null;

  // Count candidates that pass the active filter (for the stats badge).
  const filterTerms =
    filterResult.ok && filterResult.terms.length > 0
      ? filterResult.terms
      : null;
  const passCount = filterTerms
    ? valid.filter((c) => candidatePasses(c, filterTerms)).length
    : null;

  return (
    <div className="flex flex-col gap-2 border-b border-border-subtle px-3 py-2">
      {/* Axis selectors row */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <AxisSelect label="X" value={x} options={axes} onChange={(v) => setAxes({ x: v })} />
        <AxisSelect label="Y" value={y} options={axes} onChange={(v) => setAxes({ y: v })} />
        <AxisSelect
          label="Colour"
          value={color}
          options={axes.filter((a) => a.kind === "objective")}
          onChange={(v) => setAxes({ color: v })}
        />
        <span className="ml-auto text-text-muted">
          {candidates.length} candidates · {valid.length} valid
          {brushed && <> · {brushed.length} brushed</>}
        </span>
        {/* U8: explicit, focusable navigation affordance — a single click
            on the scatter keeps the preview in place; THIS is how you open
            the deep-linkable candidate detail route. Never a raw Plotly
            canvas handler. */}
        {picked && (
          <Button
            asChild
            variant="outline"
            size="sm"
            className="h-6 gap-1 px-2 text-xs"
          >
            <Link
              href={`/projects/${encodeURIComponent(projectId)}/flowpath/${encodeURIComponent(picked)}`}
              aria-label={`Open detail page for candidate ${picked}`}
              data-testid="open-candidate-detail"
            >
              Open detail
              <ArrowUpRight className="h-3 w-3" aria-hidden />
            </Link>
          </Button>
        )}
      </div>

      {/* Filter row (W-09) */}
      <FilterRow
        value={filter}
        onChange={setFilter}
        filterResult={filterResult}
        passCount={passCount}
        totalValid={valid.length}
      />

      {/* Best-in-space / best-in-filter / picked */}
      <div className="grid grid-cols-3 gap-2">
        <BestCard label="Best in space" candidate={bestSpace} variant="brand" />
        <BestCard label="Best in filter" candidate={bestFilter} variant="success" />
        <BestCard label="Picked" candidate={pickedCand} variant="info" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Filter row (W-09)
// ---------------------------------------------------------------------------

interface FilterRowProps {
  value: string;
  onChange: (v: string) => void;
  filterResult: ReturnType<typeof parseFilter>;
  passCount: number | null;
  totalValid: number;
}

/**
 * Single-line filter input accepting mini-DSL expressions.
 *
 * Valid:   eta_tt > 0.85 AND N < 60000
 * Invalid: foo > bar  → shows tooltip error, chart stays intact.
 *
 * Greyed-out candidates (30% opacity) are NOT removed from the chart so the
 * full distribution context stays visible.
 */
function FilterRow({
  value,
  onChange,
  filterResult,
  passCount,
  totalValid,
}: FilterRowProps) {
  const hasError = !filterResult.ok;
  const hasActiveFilter =
    filterResult.ok && filterResult.terms.length > 0;

  return (
    <div className="relative flex items-center gap-2">
      {/* Input */}
      <div className="relative flex-1">
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Filter: eta_tt > 0.85 AND M_rel < 1.2"
          aria-label="Design space filter expression"
          data-testid="scatter-filter-input"
          spellCheck={false}
          className={[
            "h-7 w-full rounded border bg-surface-subtle px-2.5 font-mono text-xs text-text",
            "placeholder:text-text-muted focus:outline-none focus:ring-1",
            hasError
              ? "border-destructive-default focus:ring-destructive-default"
              : "border-border-subtle focus:ring-brand-default",
          ].join(" ")}
        />

        {/* Inline error tooltip */}
        {hasError && (
          <div
            role="tooltip"
            className="absolute left-0 top-full z-20 mt-1 max-w-xs rounded border border-destructive-default bg-surface px-2.5 py-1.5 text-[11px] text-destructive-default shadow-md"
          >
            {filterResult.error}
          </div>
        )}
      </div>

      {/* Stats badge */}
      {hasActiveFilter && passCount !== null && (
        <span className="shrink-0 text-[11px] text-text-muted" data-testid="filter-pass-count">
          {passCount}/{totalValid} pass
        </span>
      )}

      {/* Clear button */}
      {value !== "" && (
        <button
          type="button"
          onClick={() => onChange("")}
          aria-label="Clear filter"
          className="shrink-0 rounded px-1.5 py-0.5 text-[11px] text-text-muted hover:bg-surface-subtle hover:text-text"
        >
          Clear
        </button>
      )}
    </div>
  );
}

function AxisSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: ReturnType<typeof useFlowPathParameterAxes>;
  onChange: (v: string) => void;
}) {
  return (
    <label className="flex items-center gap-1.5">
      <span className="text-text-muted">{label}</span>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="h-6 w-44 text-xs" aria-label={`${label} axis`}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((axis) => (
            <SelectItem key={axis.key} value={axis.key}>
              <span className="font-mono">{axis.label}</span>
              <span className="ml-2 text-[10px] text-text-muted">{axis.unit}</span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </label>
  );
}

function BestCard({
  label,
  candidate,
  variant,
}: {
  label: string;
  candidate: ServerCandidate | null;
  variant: "brand" | "success" | "info";
}) {
  return (
    <Card className="p-2 text-xs">
      <div className="mb-1 flex items-center justify-between">
        <span className="uppercase tracking-wide text-text-muted">{label}</span>
        <Badge variant={variant}>{candidate ? "ok" : "—"}</Badge>
      </div>
      <div className="font-mono text-text">
        {candidate ? (
          <>
            <div className="truncate text-[10px] text-text-muted">{candidate.id}</div>
            <div>η_tt {fmtNumber(candidate.objectives.eta_tt ?? 0, { decimals: 4 })}</div>
            <div className="text-text-muted">
              M_rel {fmtNumber(candidate.objectives.M_rel ?? 0, { decimals: 2 })}
            </div>
          </>
        ) : (
          <span className="text-text-muted">none yet</span>
        )}
      </div>
    </Card>
  );
}

function ScatterSkeleton() {
  return (
    <div className="flex h-full w-full items-center justify-center bg-surface-subtle/30 text-xs text-text-muted">
      Loading Plotly bundle…
    </div>
  );
}

function ScatterEmpty() {
  return (
    <div className="flex h-full w-full items-center justify-center text-xs text-text-muted">
      <div className="max-w-sm rounded-md border border-dashed border-border-subtle bg-surface-subtle/30 p-4 text-center">
        <p className="mb-2 text-sm text-text">No candidates yet.</p>
        <p>Click <span className="font-mono">Explore design space</span> to start a Sobol&apos; sweep — points stream in as they evaluate.</p>
      </div>
    </div>
  );
}

interface PCoordsProps {
  valid: ServerCandidate[];
  axes: ReturnType<typeof useFlowPathParameterAxes>;
  themed: boolean;
  revision: number;
}

function ParallelCoordinates({ valid, axes, themed, revision }: PCoordsProps) {
  const dims = useMemo(() => {
    if (valid.length === 0) return [];
    const keys = axes
      .filter(
        (a) =>
          a.kind === "objective" ||
          a.key === "rotor_outlet_radius" ||
          a.key === "blade_count" ||
          a.key === "tip_clearance",
      )
      .slice(0, 6);
    return keys.map((axis) => {
      const values = valid.map((c) =>
        axis.kind === "objective"
          ? c.objectives[axis.key]
          : c.params[axis.key],
      );
      return {
        label: axis.label,
        values,
      };
    });
  }, [valid, axes]);

  if (valid.length === 0) {
    return (
      <div className="h-[200px] shrink-0 border-t border-border-subtle bg-surface-subtle/20" />
    );
  }

  const data: Data[] = [
    {
      type: "parcoords",
      line: {
        color: valid.map((c) => c.objectives.eta_tt ?? 0),
        colorscale: themed
          ? [
              [0, "#3F8B96"],
              [1, "#C25B1F"],
            ]
          : [
              [0, "#1F555E"],
              [1, "#B47100"],
            ],
        showscale: false,
      },
      dimensions: dims,
    },
  ];

  const layout: Partial<Layout> = {
    autosize: true,
    margin: { t: 28, l: 32, r: 32, b: 28 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: {
      family: "Inter, system-ui, sans-serif",
      color: themed ? "#EEEFF1" : "#1A1C21",
      size: 10,
    },
  };

  return (
    <div
      className="h-[200px] shrink-0 border-t border-border-subtle bg-surface-subtle/20"
      aria-label="Parallel coordinates plot"
    >
      <Plot
        data={data}
        layout={layout}
        revision={revision}
        useResizeHandler
        style={{ width: "100%", height: "100%" }}
        config={{ displaylogo: false, responsive: true }}
      />
    </div>
  );
}

function prettyAxis(key: string): string {
  const map: Record<string, string> = {
    eta_tt: "η_tt",
    eta_ts: "η_ts",
    M_rel: "M_rel",
    mass: "mass [kg]",
    power: "power [kW]",
    rotor_outlet_radius: "r_tip,2 [m]",
    blade_count: "Z",
    tip_clearance: "τ [m]",
    outlet_blade_angle: "β_2,rel [deg]",
  };
  return map[key] ?? key;
}
