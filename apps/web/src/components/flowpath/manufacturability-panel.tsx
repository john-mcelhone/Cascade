"use client";

/**
 * Manufacturability panel for the Flow Path PD page (ADAPT-032).
 *
 * Shows a summary chip ("4 / 7 manufacturability rules pass") plus an
 * expandable rule list with per-rule measured-vs-required figures. Each rule
 * has an "override" toggle that, when flipped, lets the user supply a
 * project-specific threshold; overrides persist on the project's
 * ``settings.manufacturability_overrides`` map via the
 * ``PUT /api/projects/{id}/manufacturability/overrides`` endpoint.
 *
 * Render policy:
 *   - No violations → small "ok" chip with a chevron to expand.
 *   - Any violations → warning / danger chip drawing attention.
 *   - Loading → muted chip with em-dashes.
 *
 * The panel lives in the header above the parameter table (left pane) so
 * the user sees it on every flow-path interaction.
 */

import { useMemo, useState } from "react";
import { AlertTriangle, Check, ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  useManufacturability,
  useSetManufacturabilityOverrides,
} from "@/lib/api/hooks";
import type {
  ManufacturabilityPass,
  ManufacturabilityReport,
  ManufacturabilityViolation,
} from "@/lib/api/types";
import { cn } from "@/lib/utils";

interface ManufacturabilityPanelProps {
  projectId: string;
}

export function ManufacturabilityPanel({ projectId }: ManufacturabilityPanelProps) {
  const { data, isLoading, isError } = useManufacturability(projectId);
  const [expanded, setExpanded] = useState(false);

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 text-xs text-text-subtle">
        <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
        <span>Checking manufacturability…</span>
      </div>
    );
  }
  if (isError || !data) {
    return (
      <div className="px-3 py-2 text-xs text-text-subtle">
        Manufacturability check unavailable.
      </div>
    );
  }

  const passCount = data.passes.length;
  const totalCount = data.rule_count;
  const violationCount = data.violations.length;
  const hasOverrides = Object.keys(data.overrides_used).length > 0;

  return (
    <div className="border-b border-border-subtle bg-surface-subtle/40">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        aria-controls="manufacturability-panel-body"
        className={cn(
          "flex w-full items-center justify-between gap-3 px-3 py-2 text-left",
          "hover:bg-surface-subtle focus:outline-none focus-visible:bg-surface-subtle",
        )}
      >
        <div className="flex items-center gap-2">
          {expanded ? (
            <ChevronDown className="h-3 w-3 text-text-subtle" aria-hidden />
          ) : (
            <ChevronRight className="h-3 w-3 text-text-subtle" aria-hidden />
          )}
          <span className="text-xs font-medium text-text">
            Manufacturability
          </span>
          <SummaryChip
            passCount={passCount}
            totalCount={totalCount}
            violationCount={violationCount}
          />
          {hasOverrides && (
            <Badge variant="info" className="text-[10px]">
              overrides
            </Badge>
          )}
        </div>
        <span className="text-[11px] text-text-subtle">
          {data.machine_class === "centrifugal_compressor" ? "Impeller" : "RIT rotor"}
        </span>
      </button>

      {expanded && (
        <div
          id="manufacturability-panel-body"
          className="border-t border-border-subtle px-3 py-2"
        >
          <RuleList projectId={projectId} report={data} />
        </div>
      )}
    </div>
  );
}

function SummaryChip({
  passCount,
  totalCount,
  violationCount,
}: {
  passCount: number;
  totalCount: number;
  violationCount: number;
}) {
  if (violationCount === 0) {
    return (
      <Badge variant="success" className="gap-1">
        <Check className="h-3 w-3" aria-hidden />
        {passCount}/{totalCount} pass
      </Badge>
    );
  }
  return (
    <Badge variant="warning" className="gap-1">
      <AlertTriangle className="h-3 w-3" aria-hidden />
      {violationCount} violation{violationCount === 1 ? "" : "s"}
    </Badge>
  );
}

interface RuleRowItem {
  rule_name: string;
  description: string;
  measured: number;
  threshold_min: number | null;
  threshold_max: number | null;
  units: string;
  citation: string;
  isViolation: boolean;
  severity?: "warning" | "error";
  direction?: "below_min" | "above_max";
}

function isViolation(
  row: ManufacturabilityViolation | ManufacturabilityPass,
): row is ManufacturabilityViolation {
  return "severity" in row;
}

function RuleList({
  projectId,
  report,
}: {
  projectId: string;
  report: ManufacturabilityReport;
}) {
  const items: RuleRowItem[] = useMemo(() => {
    const violations: RuleRowItem[] = report.violations.map((v) => ({
      rule_name: v.rule_name,
      description: v.description,
      measured: v.measured,
      threshold_min: v.threshold_min,
      threshold_max: v.threshold_max,
      units: v.units,
      citation: v.citation,
      isViolation: true,
      severity: v.severity,
      direction: v.direction,
    }));
    const passes: RuleRowItem[] = report.passes.map((p) => ({
      rule_name: p.rule_name,
      description: p.description,
      measured: p.measured,
      threshold_min: p.threshold_min,
      threshold_max: p.threshold_max,
      units: p.units,
      citation: p.citation,
      isViolation: false,
    }));
    return [...violations, ...passes];
  }, [report]);

  return (
    <ul className="space-y-2">
      {items.map((row) => (
        <RuleRow
          key={row.rule_name}
          row={row}
          projectId={projectId}
          report={report}
        />
      ))}
    </ul>
  );
}

function RuleRow({
  row,
  projectId,
  report,
}: {
  row: RuleRowItem;
  projectId: string;
  report: ManufacturabilityReport;
}) {
  const mutation = useSetManufacturabilityOverrides(projectId);
  const overrideValue = report.overrides_used[row.rule_name];
  const hasOverride = overrideValue !== undefined;
  const [draft, setDraft] = useState<string>(
    overrideValue !== undefined
      ? String(overrideValue)
      : row.threshold_min !== null
        ? String(row.threshold_min)
        : row.threshold_max !== null
          ? String(row.threshold_max)
          : "",
  );

  const onToggleOverride = (next: boolean) => {
    const nextOverrides = { ...report.overrides_used };
    if (next) {
      const parsed = Number(draft);
      if (!Number.isFinite(parsed)) return;
      nextOverrides[row.rule_name] = parsed;
    } else {
      delete nextOverrides[row.rule_name];
    }
    mutation.mutate(nextOverrides);
  };

  const onSubmitDraft = () => {
    if (!hasOverride) return;
    const parsed = Number(draft);
    if (!Number.isFinite(parsed)) return;
    const nextOverrides = {
      ...report.overrides_used,
      [row.rule_name]: parsed,
    };
    mutation.mutate(nextOverrides);
  };

  return (
    <li
      className={cn(
        "rounded-sm border px-2 py-1.5 text-xs",
        row.isViolation
          ? "border-semantic-warning-border bg-semantic-warning-surface/40"
          : "border-border-subtle bg-surface/50",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            {row.isViolation ? (
              <AlertTriangle
                className="h-3 w-3 text-semantic-warning-text"
                aria-hidden
              />
            ) : (
              <Check className="h-3 w-3 text-semantic-success-text" aria-hidden />
            )}
            <span className="font-medium text-text">{row.rule_name}</span>
            <span className="text-text-subtle">{row.description}</span>
          </div>
          <div className="mt-0.5 pl-4 text-[11px] text-text-subtle">
            <span className="tabular-nums">
              {formatMeasured(row.measured, row.units)}
            </span>
            <span className="mx-1">·</span>
            <span>
              {row.isViolation && row.direction === "below_min"
                ? "min "
                : row.isViolation && row.direction === "above_max"
                  ? "max "
                  : row.threshold_min !== null
                    ? "min "
                    : "max "}
              {formatThreshold(row, hasOverride)}
            </span>
            {row.citation && (
              <span className="ml-1 text-text-subtle">[{row.citation}]</span>
            )}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <label className="flex items-center gap-1 text-[11px] text-text-subtle">
            <Switch
              checked={hasOverride}
              onCheckedChange={onToggleOverride}
              aria-label={`Override rule ${row.rule_name}`}
            />
            override
          </label>
        </div>
      </div>
      {hasOverride && (
        <div className="mt-1.5 flex items-center gap-1.5 pl-4">
          <span className="text-[11px] text-text-subtle">threshold</span>
          <Input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={onSubmitDraft}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                (e.target as HTMLInputElement).blur();
              }
            }}
            className="h-6 w-24 text-[11px] tabular-nums"
            inputMode="decimal"
            aria-label={`Override threshold for ${row.rule_name}`}
          />
          <span className="text-[11px] text-text-subtle">{row.units}</span>
          {mutation.isPending && (
            <Loader2 className="h-3 w-3 animate-spin text-text-subtle" aria-hidden />
          )}
        </div>
      )}
    </li>
  );
}

function formatMeasured(value: number, units: string): string {
  if (!Number.isFinite(value)) return `— ${units}`;
  if (units === "m") {
    // Display millimetres for sub-cm values so the floor numbers read
    // naturally (0.30 mm rather than 3e-4 m).
    if (Math.abs(value) < 0.05) return `${(value * 1e3).toFixed(3)} mm`;
    return `${value.toFixed(4)} m`;
  }
  if (units === "deg") return `${value.toFixed(1)}°`;
  if (units === "-") return value.toFixed(3);
  return `${value.toFixed(3)} ${units}`;
}

function formatThreshold(row: RuleRowItem, hasOverride: boolean): string {
  // For violations we prefer to show the active boundary the measured value
  // missed; for passes show the binding side.
  let value: number | null = null;
  if (row.isViolation && row.direction === "below_min") {
    value = row.threshold_min;
  } else if (row.isViolation && row.direction === "above_max") {
    value = row.threshold_max;
  } else if (row.threshold_min !== null) {
    value = row.threshold_min;
  } else if (row.threshold_max !== null) {
    value = row.threshold_max;
  }
  if (value === null) return "—";
  const overrideMark = hasOverride ? "*" : "";
  return `${formatMeasured(value, row.units)}${overrideMark}`;
}
