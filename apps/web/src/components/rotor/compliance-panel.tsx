"use client";

import { CheckCircle2, ExternalLink, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import type { RotorComplianceReport } from "@/lib/api/types";

interface CompliancePanelProps {
  compliance?: RotorComplianceReport;
}

/**
 * API 617 / 684 compliance panel (ADAPT-025).
 *
 * Renders one card per critical-speed crossing reported by the eigensolver.
 * For each crossing we show: the rpm, the whirl direction, the
 * amplification factor, the actual vs required separation margin, a
 * pass/fail chip, and a popover with the API 684 §2.7.1.7 citation text.
 *
 * Sorted closest-to-operating-speed first (so the most safety-relevant
 * crossing is at the top). Crossings outside the operating envelope are
 * tagged but still listed.
 */
export function CompliancePanel({ compliance }: CompliancePanelProps) {
  if (!compliance) {
    return (
      <Card>
        <CardHeader className="p-3 pb-1">
          <CardTitle className="text-sm font-medium uppercase tracking-wide text-text-muted">
            API 684 compliance
          </CardTitle>
        </CardHeader>
        <CardContent className="p-3 pt-0 text-xs text-text-muted">
          Run a lateral analysis to populate the compliance report.
        </CardContent>
      </Card>
    );
  }

  if (compliance.criticals.length === 0) {
    return (
      <Card>
        <CardHeader className="p-3 pb-1">
          <CardTitle className="text-sm font-medium uppercase tracking-wide text-text-muted">
            API 684 compliance
          </CardTitle>
        </CardHeader>
        <CardContent className="p-3 pt-0 text-xs text-text-muted">
          No critical-speed crossings found in the {formatRpm(
            compliance.speed_range_rpm[0],
          )}
          {" – "}
          {formatRpm(compliance.speed_range_rpm[1])} rpm envelope.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="p-3 pb-1">
        <div className="flex items-baseline justify-between">
          <CardTitle className="text-sm font-medium uppercase tracking-wide text-text-muted">
            API 684 compliance
          </CardTitle>
          <span className="text-[11px] text-text-muted">
            Operating speed{" "}
            <span className="font-mono tabular-nums text-text">
              {formatRpm(compliance.operating_speed_rpm)} rpm
            </span>
          </span>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-2 p-3 pt-1">
        {compliance.criticals.map((c, i) => (
          <CriticalRow key={`${c.mode_id}-${i}`} critical={c} />
        ))}
      </CardContent>
    </Card>
  );
}

function CriticalRow({
  critical: c,
}: {
  critical: RotorComplianceReport["criticals"][number];
}) {
  return (
    <div className="flex flex-col gap-1 rounded-sm border border-border-subtle bg-surface px-3 py-2">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-sm tabular-nums">
            {formatRpm(c.rpm)} rpm
          </span>
          <span className="text-[11px] text-text-muted">
            mode {c.mode_id + 1} ·{" "}
            <span className="uppercase">{c.whirl}</span>
          </span>
          {!c.in_operating_envelope && (
            <Badge variant="outline" className="text-[10px]">
              outside MCS envelope
            </Badge>
          )}
        </div>
        {c.passes ? (
          <Badge variant="success" className="gap-1">
            <CheckCircle2 className="h-3 w-3" /> pass
          </Badge>
        ) : (
          <Badge variant="danger" className="gap-1">
            <XCircle className="h-3 w-3" /> fail
          </Badge>
        )}
      </div>

      <div className="grid grid-cols-3 gap-x-3 gap-y-0.5 text-[11px]">
        <Cell label="AF">
          {c.amplification_factor.toFixed(2)}
        </Cell>
        <Cell label="Actual SM">
          <span className="font-mono tabular-nums">
            {c.separation_margin_pct.toFixed(1)}%
          </span>
        </Cell>
        <Cell label="Required SM">
          <span className="font-mono tabular-nums">
            {c.required_margin_pct.toFixed(1)}%
          </span>
        </Cell>
      </div>

      <div className="flex items-baseline justify-between text-[10px] text-text-muted">
        <Popover>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="inline-flex items-center gap-1 text-brand-text underline-offset-2 hover:underline"
            >
              <ExternalLink className="h-3 w-3" />
              {c.api_clause}
            </button>
          </PopoverTrigger>
          <PopoverContent
            className="max-w-sm text-xs leading-relaxed"
            side="top"
            align="end"
          >
            <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-text-muted">
              {c.api_clause}
            </p>
            <p className="text-text">{c.api_citation}</p>
          </PopoverContent>
        </Popover>
      </div>
    </div>
  );
}

function Cell({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-baseline justify-between">
      <span className="text-text-muted/80">{label}</span>
      {children}
    </div>
  );
}

function formatRpm(v: number): string {
  return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
}
