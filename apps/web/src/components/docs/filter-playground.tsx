"use client";

import { useMemo, useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import {
  buildKnownFields,
  candidatePasses,
  parseFilter,
} from "@/lib/flowpath/filter-dsl";
import { cn } from "@/lib/utils";

/**
 * Live playground for the design-space filter DSL. Runs the exact same
 * parser the Flow path page uses (`@/lib/flowpath/filter-dsl`), so what
 * passes here passes there. The sample pool is a small, fixed set of
 * realistic candidates — enough to see terms include and exclude rows.
 */

interface SampleCandidate {
  id: string;
  objectives: Record<string, number>;
  params: Record<string, number>;
}

const SAMPLES: SampleCandidate[] = [
  {
    id: "cand-012",
    objectives: { eta_tt: 0.871, pressure_ratio: 4.12, M_rel: 1.08, power_W: 31200 },
    params: { rotor_outlet_radius: 0.041, blade_count: 14, tip_clearance: 0.00018 },
  },
  {
    id: "cand-047",
    objectives: { eta_tt: 0.843, pressure_ratio: 3.88, M_rel: 0.97, power_W: 29400 },
    params: { rotor_outlet_radius: 0.038, blade_count: 12, tip_clearance: 0.00025 },
  },
  {
    id: "cand-103",
    objectives: { eta_tt: 0.892, pressure_ratio: 4.31, M_rel: 1.24, power_W: 32800 },
    params: { rotor_outlet_radius: 0.044, blade_count: 16, tip_clearance: 0.00012 },
  },
  {
    id: "cand-156",
    objectives: { eta_tt: 0.815, pressure_ratio: 3.52, M_rel: 0.89, power_W: 27100 },
    params: { rotor_outlet_radius: 0.034, blade_count: 11, tip_clearance: 0.00034 },
  },
  {
    id: "cand-201",
    objectives: { eta_tt: 0.866, pressure_ratio: 4.05, M_rel: 1.15, power_W: 30600 },
    params: { rotor_outlet_radius: 0.040, blade_count: 15, tip_clearance: 0.00020 },
  },
];

const PRESETS = [
  "eta_tt > 0.85",
  "eta_tt > 0.85 AND M_rel < 1.2",
  "blade_count >= 14 AND power_W >= 30000",
];

const COLUMNS: Array<{ key: string; label: string; digits: number }> = [
  { key: "eta_tt", label: "eta_tt", digits: 3 },
  { key: "pressure_ratio", label: "pressure_ratio", digits: 2 },
  { key: "M_rel", label: "M_rel", digits: 2 },
  { key: "power_W", label: "power_W", digits: 0 },
  { key: "blade_count", label: "blade_count", digits: 0 },
];

export function FilterPlayground({ className }: { className?: string }) {
  const [raw, setRaw] = useState(PRESETS[1]);
  const knownFields = useMemo(() => buildKnownFields(SAMPLES), []);
  const parsed = useMemo(() => parseFilter(raw, knownFields), [raw, knownFields]);

  const results = useMemo(() => {
    if (!parsed.ok) return SAMPLES.map((c) => ({ candidate: c, pass: false }));
    return SAMPLES.map((c) => ({
      candidate: c,
      pass: candidatePasses(c, parsed.terms),
    }));
  }, [parsed]);

  const passCount = parsed.ok ? results.filter((r) => r.pass).length : 0;

  return (
    <figure
      className={cn(
        "w-full overflow-hidden rounded-md border border-border-subtle bg-surface-raised",
        className,
      )}
    >
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border-subtle bg-surface-subtle/60 px-3 py-2">
        <div className="flex items-baseline gap-2">
          <span className="text-xs font-medium uppercase tracking-wide text-text-muted">
            Playground
          </span>
          <span className="text-sm font-medium text-text">Filter DSL</span>
        </div>
        <span className="text-xs text-text-muted">
          Same parser the Flow path page runs
        </span>
      </header>

      <div className="flex flex-col gap-3 p-3">
        <input
          type="text"
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
          spellCheck={false}
          aria-label="Filter expression"
          className={cn(
            "h-9 w-full rounded-sm border bg-surface-input px-3 font-mono text-[13px] text-text focus:outline-none",
            parsed.ok
              ? "border-border-subtle focus:border-border-focus"
              : "border-semantic-danger-border",
          )}
          placeholder="eta_tt > 0.85 AND M_rel < 1.2"
        />

        <div className="flex flex-wrap items-center gap-1.5">
          {PRESETS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setRaw(p)}
              className="rounded-sm border border-border-subtle bg-surface px-1.5 py-0.5 font-mono text-[11px] text-text-muted transition-colors duration-fast hover:border-border-default hover:text-text"
            >
              {p}
            </button>
          ))}
        </div>

        {parsed.ok ? (
          <p className="text-xs text-text-muted">
            {parsed.terms.length === 0
              ? "Empty filter — every candidate passes."
              : `${parsed.terms.length} term${parsed.terms.length === 1 ? "" : "s"} · ${passCount} of ${SAMPLES.length} sample candidates pass.`}
          </p>
        ) : (
          <p className="flex items-center gap-1.5 text-xs text-semantic-danger-text">
            <XCircle className="h-3.5 w-3.5 shrink-0" />
            {parsed.error}
          </p>
        )}

        <div className="overflow-x-auto scrollbar-subtle">
          <table className="w-full min-w-[480px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-border-subtle text-left">
                <th className="py-1.5 pr-3 text-xs font-medium uppercase tracking-wide text-text-muted">
                  Candidate
                </th>
                {COLUMNS.map((c) => (
                  <th
                    key={c.key}
                    className="py-1.5 pr-3 text-right font-mono text-xs font-medium text-text-muted"
                  >
                    {c.label}
                  </th>
                ))}
                <th className="py-1.5 text-right text-xs font-medium uppercase tracking-wide text-text-muted">
                  Passes
                </th>
              </tr>
            </thead>
            <tbody>
              {results.map(({ candidate, pass }) => (
                <tr
                  key={candidate.id}
                  className={cn(
                    "border-b border-border-subtle/60 transition-colors duration-fast last:border-b-0",
                    parsed.ok && !pass && "opacity-45",
                  )}
                >
                  <td className="py-1.5 pr-3 font-mono text-xs text-text">
                    {candidate.id}
                  </td>
                  {COLUMNS.map((c) => {
                    const v =
                      candidate.objectives[c.key] ?? candidate.params[c.key];
                    return (
                      <td
                        key={c.key}
                        className="py-1.5 pr-3 text-right font-mono text-xs tabular-nums text-text-subtle"
                      >
                        {v.toFixed(c.digits)}
                      </td>
                    );
                  })}
                  <td className="py-1.5 text-right">
                    {parsed.ok && pass ? (
                      <CheckCircle2 className="ml-auto h-3.5 w-3.5 text-semantic-success" />
                    ) : (
                      <XCircle className="ml-auto h-3.5 w-3.5 text-text-disabled" />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </figure>
  );
}
