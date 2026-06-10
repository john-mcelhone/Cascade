"use client";

import * as React from "react";
import {
  AlertTriangle,
  Bug,
  ChevronDown,
  ChevronUp,
  ClipboardCopy,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { fmtNumber } from "@/lib/utils";
import { useCycleUiStore } from "./store";
import type { CycleFailure, CycleNode, CycleResult } from "@/lib/api/types";

interface ResultPanelProps {
  nodes: CycleNode[];
}

/* ---------------------------------------------------------------------------
 * U9 / ADAPT-045 — per-rotor efficiency attribution.
 *
 * The backend ships four dicts keyed by component name: the converged η
 * actually used, the mode actually used, the mode the user requested
 * (pre-fallback), and an explicit fallback flag. The block below renders a
 * row per rotor and, when live mean-line was requested but the solve fell
 * back to constant η (no geometry attached), a warning chip — icon + text,
 * never colour alone.
 *
 * Mirrored (plain JS) by src/__tests__/efficiency-sources.test.mjs.
 * ------------------------------------------------------------------------- */

/** Solver-convention mode → human label ("constant" is the lumped η path). */
const EFFICIENCY_MODE_LABELS: Record<string, string> = {
  constant: "isentropic",
  polytropic: "polytropic",
  live_meanline: "live mean-line",
};

interface EfficiencySourceRow {
  componentId: string;
  /** Converged η actually used; undefined when the payload lacks it. */
  eta?: number;
  /** Human label for the mode actually used. */
  modeLabel: string;
  /** Live mean-line was requested but the solve fell back to constant η. */
  fellBack: boolean;
}

function efficiencySourceRows(
  result: Pick<
    CycleResult,
    | "componentEfficiencies"
    | "efficiencyModes"
    | "requestedEfficiencyModes"
    | "efficiencyFallbacks"
  >,
): EfficiencySourceRow[] {
  const modes = result.efficiencyModes ?? {};
  const requested = result.requestedEfficiencyModes ?? {};
  const fallbacks = result.efficiencyFallbacks ?? {};
  return Object.keys(modes).map((name) => ({
    componentId: name,
    eta: result.componentEfficiencies?.[name],
    modeLabel: EFFICIENCY_MODE_LABELS[modes[name]] ?? modes[name],
    fellBack:
      fallbacks[name] === true ||
      (requested[name] === "live_meanline" && modes[name] !== "live_meanline"),
  }));
}

/** Show the block when live mean-line was requested OR a fallback occurred. */
function showEfficiencySources(
  result: Pick<
    CycleResult,
    "efficiencyModes" | "requestedEfficiencyModes" | "efficiencyFallbacks"
  >,
): boolean {
  return (
    Object.values(result.efficiencyModes ?? {}).includes("live_meanline") ||
    Object.values(result.requestedEfficiencyModes ?? {}).includes(
      "live_meanline",
    ) ||
    Object.values(result.efficiencyFallbacks ?? {}).some(Boolean)
  );
}

/**
 * Slide-up panel at the bottom of the canvas that shows the most recent
 * cycle-solve result. Collapsible. Has two distinct modes:
 *
 *   1. Converged — the historical headline-metrics + per-component table.
 *   2. Failed   — a friendly first-principles explanation of why the
 *                 cycle didn't solve, with concrete suggestions to try.
 *                 Bug-class failures also expose a "Copy bug log" button.
 */
export function ResultPanel({ nodes }: ResultPanelProps) {
  const open = useCycleUiStore((s) => s.resultPanelOpen);
  const setOpen = useCycleUiStore((s) => s.setResultPanelOpen);
  const result = useCycleUiStore((s) => s.run.result);
  const [collapsed, setCollapsed] = React.useState(false);

  if (!open || !result) return null;

  // When the backend couldn't solve the cycle, surface a friendly error
  // display instead of the headline-metrics layout.
  if (result.failure) {
    return (
      <FailurePanel
        failure={result.failure}
        collapsed={collapsed}
        onToggleCollapsed={() => setCollapsed((v) => !v)}
        onDismiss={() => setOpen(false)}
      />
    );
  }

  return (
    <div className="pointer-events-auto absolute inset-x-3 bottom-3 z-10 rounded-md border border-border-subtle bg-surface-raised shadow-z2">
      <div className="flex items-center justify-between border-b border-border-subtle px-3 py-2">
        <div className="flex items-center gap-2">
          <Badge variant="success">converged</Badge>
          <span className="text-sm font-medium">Cycle result</span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setCollapsed((v) => !v)}
            aria-label={collapsed ? "Expand" : "Collapse"}
          >
            {collapsed ? (
              <ChevronUp className="h-3.5 w-3.5" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" />
            )}
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setOpen(false)}
            aria-label="Dismiss result"
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {!collapsed && (
        <>
        <div className="grid grid-cols-1 gap-3 p-3 md:grid-cols-[1fr_2fr]">
          {/* Headline metrics */}
          <div className="grid grid-cols-3 gap-3">
            <Metric
              label="η_th"
              hint="Thermal efficiency"
              value={fmtNumber(result.thermalEfficiency, { decimals: 4 })}
            />
            <Metric
              label="η_e"
              hint="Electrical efficiency"
              value={fmtNumber(result.electricalEfficiency, { decimals: 4 })}
            />
            <Metric
              label="w_s"
              hint="Specific work"
              value={`${fmtNumber(result.specificWork, { decimals: 1 })} kJ/kg`}
            />
            <Metric
              label="ṁ_f"
              hint="Fuel mass flow"
              value={`${fmtNumber(result.fuelFlow, { sigFigs: 3 })} kg/s`}
            />
            <Metric
              label="W_s"
              hint="Net shaft work"
              value={`${fmtNumber(result.netShaftWork, { decimals: 1 })} kW`}
            />
            <Metric
              label="W_e"
              hint="Electrical output"
              value={`${fmtNumber(result.electricalOutput, { decimals: 1 })} kW`}
            />
          </div>

          {/* Per-component table */}
          <div className="overflow-x-auto rounded-sm border border-border-subtle">
            <table className="w-full text-xs">
              <thead className="bg-surface-subtle/60 text-text-muted">
                <tr>
                  <th className="px-2 py-1.5 text-left font-medium">Component</th>
                  <th className="px-2 py-1.5 text-right font-medium">W [kW]</th>
                  <th className="px-2 py-1.5 text-right font-medium">Tt [K]</th>
                  <th className="px-2 py-1.5 text-right font-medium">Pt [kPa]</th>
                  <th className="px-2 py-1.5 text-right font-medium">ṁ [kg/s]</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle font-mono">
                {result.components.length === 0 ? (
                  <tr>
                    <td
                      colSpan={5}
                      className="px-2 py-3 text-center text-text-muted"
                    >
                      Component-level breakdown not available from this run.
                    </td>
                  </tr>
                ) : (
                  result.components.map((c) => {
                    const node = nodes.find(
                      (n) =>
                        n.id === c.componentId || n.label === c.componentId,
                    );
                    // U7: in fuel-mass-flow mode the burner outlet Tt (the
                    // TIT) is back-derived from ṁ_fuel — label it so the
                    // user knows it's a solver output, not their input.
                    const titDerived =
                      node?.kind === "burner" &&
                      node.params?.spec_mode === "fuel_mass_flow";
                    return (
                      <tr key={c.componentId}>
                        <td className="px-2 py-1 font-sans">
                          {node?.label ?? c.componentId}
                          <span className="ml-1 text-text-muted">
                            {node && `(${node.kind})`}
                          </span>
                        </td>
                        <td className="px-2 py-1 text-right tabular-nums">
                          {fmtNumber(c.shaftWork, { decimals: 1 })}
                        </td>
                        <td className="px-2 py-1 text-right tabular-nums">
                          {fmtNumber(c.outletTemperature, { decimals: 0 })}
                          {titDerived && (
                            <span className="ml-1 font-sans text-[10px] text-text-muted">
                              (derived)
                            </span>
                          )}
                        </td>
                        <td className="px-2 py-1 text-right tabular-nums">
                          {fmtNumber(c.outletPressure, { decimals: 1 })}
                        </td>
                        <td className="px-2 py-1 text-right tabular-nums">
                          {fmtNumber(c.outletMassFlow, { decimals: 3 })}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* U9: per-rotor efficiency attribution — shown when live
            mean-line was requested or a fallback occurred. */}
        {showEfficiencySources(result) && (
          <div className="border-t border-border-subtle px-3 pb-3">
            <div className="mb-1.5 mt-2 text-xs font-medium uppercase tracking-wide text-text-muted">
              Efficiency sources
            </div>
            <div className="flex flex-col gap-1.5">
              {efficiencySourceRows(result).map((row) => {
                const node = nodes.find(
                  (n) =>
                    n.id === row.componentId || n.label === row.componentId,
                );
                return (
                  <div
                    key={row.componentId}
                    className="flex flex-wrap items-center gap-2 text-xs"
                  >
                    <span className="text-text">
                      {node?.label ?? row.componentId}
                      {node && (
                        <span className="ml-1 text-text-muted">
                          ({node.kind})
                        </span>
                      )}
                    </span>
                    <span className="font-mono tabular-nums text-text">
                      η ={" "}
                      {row.eta !== undefined
                        ? fmtNumber(row.eta, { decimals: 3 })
                        : "—"}
                    </span>
                    <span className="text-text-muted">({row.modeLabel})</span>
                    {row.fellBack && (
                      <span className="inline-flex items-center gap-1 rounded-sm border border-semantic-warning-border bg-semantic-warning-surface/40 px-1.5 py-0.5 text-[11px] text-semantic-warning-text">
                        <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                        Fell back to isentropic — no geometry attached
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
        </>
      )}
    </div>
  );
}

function Metric({
  label,
  hint,
  value,
}: {
  label: string;
  hint?: string;
  value: string;
}) {
  return (
    <div className="rounded-sm border border-border-subtle bg-surface px-2 py-1.5">
      <div
        title={hint}
        className="font-mono text-[10px] uppercase tracking-wide text-text-muted"
      >
        {label}
      </div>
      <div className="font-mono text-base tabular-nums text-text">{value}</div>
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * Failure mode — friendly first-principles explanation for design issues,
 * copy-the-log panel for software bugs.
 * ------------------------------------------------------------------------- */

function FailurePanel({
  failure,
  collapsed,
  onToggleCollapsed,
  onDismiss,
}: {
  failure: CycleFailure;
  collapsed: boolean;
  onToggleCollapsed: () => void;
  onDismiss: () => void;
}) {
  const isBug = failure.kind === "bug";
  const Icon = isBug ? Bug : AlertTriangle;
  // Distinct visual treatments so the user can tell at a glance whether
  // they should fix their design (amber) or report a bug to the dev (red).
  const borderClass = isBug
    ? "border-semantic-danger-border"
    : "border-semantic-warning-border";
  const bgClass = isBug
    ? "bg-semantic-danger-surface/40"
    : "bg-semantic-warning-surface/40";
  const iconClass = isBug
    ? "text-semantic-danger-text"
    : "text-semantic-warning-text";

  const copyBugLog = React.useCallback(async () => {
    if (!failure.bug_log) return;
    const text = [
      `Cascade cycle solver — bug report`,
      `Title: ${failure.title}`,
      ``,
      failure.bug_log,
    ].join("\n");
    try {
      await navigator.clipboard.writeText(text);
      toast.success("Bug log copied to clipboard.", {
        description:
          "Paste it into a message to the developer. The traceback alone is usually enough to reproduce.",
      });
    } catch (err) {
      toast.error("Couldn't copy", {
        description: (err as Error).message,
      });
    }
  }, [failure]);

  return (
    <div
      className={`pointer-events-auto absolute inset-x-3 bottom-3 z-10 rounded-md border ${borderClass} ${bgClass} shadow-z2`}
    >
      <div
        className={`flex items-center justify-between border-b ${borderClass} px-3 py-2`}
      >
        <div className="flex items-center gap-2">
          <Icon className={`h-4 w-4 ${iconClass}`} />
          <Badge variant={isBug ? "danger" : "warning"}>
            {isBug ? "software bug" : "cycle didn't solve"}
          </Badge>
          <span className="text-sm font-medium text-text">
            {failure.title}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onToggleCollapsed}
            aria-label={collapsed ? "Expand" : "Collapse"}
          >
            {collapsed ? (
              <ChevronUp className="h-3.5 w-3.5" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" />
            )}
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onDismiss}
            aria-label="Dismiss"
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {!collapsed && (
        <div className="flex flex-col gap-3 p-3">
          {/* Plain-english explanation */}
          <p className="text-sm leading-relaxed text-text">
            {failure.plain_english}
          </p>

          {/* Optional raw solver detail */}
          {failure.details && (
            <div className="rounded-sm border border-border-subtle bg-surface px-2.5 py-1.5 font-mono text-[11px] text-text-muted">
              {failure.details}
            </div>
          )}

          {/* Suggestions */}
          {failure.suggestions.length > 0 && (
            <div>
              <div className="mb-1.5 text-xs font-medium uppercase tracking-wide text-text-muted">
                {isBug ? "What to do" : "Things to try"}
              </div>
              <ul className="flex flex-col gap-1.5 text-sm text-text">
                {failure.suggestions.map((s, i) => (
                  <li
                    key={i}
                    className="flex gap-2 leading-relaxed"
                  >
                    <span
                      className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${
                        isBug
                          ? "bg-semantic-danger-text"
                          : "bg-semantic-warning-text"
                      }`}
                    />
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Bug log + copy button */}
          {isBug && failure.bug_log && (
            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <div className="text-xs font-medium uppercase tracking-wide text-text-muted">
                  Bug log
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="gap-1.5"
                  onClick={copyBugLog}
                >
                  <ClipboardCopy className="h-3 w-3" />
                  Copy bug log
                </Button>
              </div>
              <pre className="max-h-48 overflow-auto rounded-sm border border-border-subtle bg-surface p-2.5 font-mono text-[11px] leading-relaxed text-text-muted">
                {failure.bug_log}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
