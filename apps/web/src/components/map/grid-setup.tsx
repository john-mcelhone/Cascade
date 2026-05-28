"use client";

import { useId } from "react";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export type MapObjective = "pi_tt" | "eta_tt" | "eta_ts" | "power" | "max_M_rel";

export interface GridVariable {
  /** Variable label, e.g. "mass_flow". */
  name: string;
  /** Display unit suffix. */
  unit: string;
  min: number;
  max: number;
  points: number;
}

export interface GridConfig {
  variables: GridVariable[];
  objective: MapObjective;
}

export const OBJECTIVE_OPTIONS: Array<{ value: MapObjective; label: string }> = [
  { value: "pi_tt", label: "π_tt — total-to-total pressure ratio" },
  { value: "eta_tt", label: "η_tt — total-to-total efficiency" },
  { value: "eta_ts", label: "η_ts — total-to-static efficiency" },
  { value: "power", label: "Power [kW]" },
  { value: "max_M_rel", label: "max M_rel" },
];

interface GridSetupProps {
  config: GridConfig;
  onConfigChange: (next: GridConfig) => void;
}

/**
 * Left-rail grid configuration. Each variable row is a min/max/points triple.
 * Variables are fixed at v1 (mass_flow, rpm, tip_clearance) — the backend
 * doesn't yet permit arbitrary axes.
 */
export function GridSetup({ config, onConfigChange }: GridSetupProps) {
  const updateVar = (idx: number, patch: Partial<GridVariable>) => {
    const next = [...config.variables];
    next[idx] = { ...next[idx], ...patch };
    onConfigChange({ ...config, variables: next });
  };

  return (
    <div className="flex flex-col gap-4">
      <section>
        <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">
          Variables
        </h3>
        <div className="flex flex-col gap-2">
          {config.variables.map((v, i) => (
            <VariableRow
              key={v.name}
              variable={v}
              onChange={(patch) => updateVar(i, patch)}
            />
          ))}
        </div>
      </section>

      <section>
        <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">
          Objective
        </h3>
        <Select
          value={config.objective}
          onValueChange={(v) =>
            onConfigChange({ ...config, objective: v as MapObjective })
          }
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {OBJECTIVE_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </section>
    </div>
  );
}

function VariableRow({
  variable,
  onChange,
}: {
  variable: GridVariable;
  onChange: (patch: Partial<GridVariable>) => void;
}) {
  const minId = useId();
  const maxId = useId();
  const ptsId = useId();
  return (
    <div className="rounded-md border border-border-subtle bg-surface px-2 py-2">
      <div className="mb-1.5 flex items-baseline justify-between">
        <span className="font-mono text-sm text-text">{variable.name}</span>
        <span className="text-xs text-text-muted">{variable.unit}</span>
      </div>
      <div className="grid grid-cols-3 gap-1.5">
        <label htmlFor={minId} className="flex flex-col gap-0.5">
          <span className="text-[10px] uppercase tracking-wide text-text-muted">
            min
          </span>
          <Input
            id={minId}
            type="number"
            data-input="true"
            value={variable.min}
            step="any"
            onChange={(e) =>
              onChange({ min: Number(e.target.value) })
            }
          />
        </label>
        <label htmlFor={maxId} className="flex flex-col gap-0.5">
          <span className="text-[10px] uppercase tracking-wide text-text-muted">
            max
          </span>
          <Input
            id={maxId}
            type="number"
            data-input="true"
            value={variable.max}
            step="any"
            onChange={(e) =>
              onChange({ max: Number(e.target.value) })
            }
          />
        </label>
        <label htmlFor={ptsId} className="flex flex-col gap-0.5">
          <span className="text-[10px] uppercase tracking-wide text-text-muted">
            points
          </span>
          <Input
            id={ptsId}
            type="number"
            data-input="true"
            value={variable.points}
            min={2}
            max={50}
            onChange={(e) =>
              onChange({
                points: Math.max(2, Math.floor(Number(e.target.value))),
              })
            }
          />
        </label>
      </div>
    </div>
  );
}

/** Expand a GridConfig into the explicit value lists the backend wants. */
export function expandGrid(config: GridConfig): {
  rpms: number[];
  massFlows: number[];
} {
  const rpmVar = config.variables.find((v) => v.name === "rpm");
  const mVar = config.variables.find((v) => v.name === "mass_flow");
  return {
    rpms: rpmVar ? linspace(rpmVar.min, rpmVar.max, rpmVar.points) : [],
    massFlows: mVar ? linspace(mVar.min, mVar.max, mVar.points) : [],
  };
}

function linspace(lo: number, hi: number, n: number): number[] {
  if (n <= 1) return [lo];
  const out: number[] = [];
  for (let i = 0; i < n; i++) {
    out.push(lo + ((hi - lo) * i) / (n - 1));
  }
  return out;
}

export function defaultGridConfig(): GridConfig {
  return {
    variables: [
      { name: "mass_flow", unit: "kg/s", min: 0.1, max: 0.5, points: 9 },
      { name: "rpm", unit: "rpm", min: 60000, max: 108000, points: 5 },
      { name: "tip_clearance", unit: "mm", min: 0.15, max: 0.45, points: 3 },
    ],
    objective: "pi_tt",
  };
}
