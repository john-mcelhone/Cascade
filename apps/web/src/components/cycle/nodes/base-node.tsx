"use client";

import * as React from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { PORTS, type PortKind } from "../edge-validator";
import type { CycleNodeKind } from "@/lib/api/types";

export interface CycleNodeData extends Record<string, unknown> {
  kind: CycleNodeKind;
  label: string;
  /** Two-character family code (e.g. "C1", "T1") — appears next to label. */
  ref?: string;
  chips: Array<{ symbol: string; value: string }>;
  validationError?: string;
  /**
   * Full parameter bag for the component. Mirrors the Python dataclass in
   * `src/cascade/cycle/components.py`. Persisted as the canonical source of
   * truth — the chips above are derived display values.
   */
  params?: Record<string, number | string | boolean>;
  /**
   * Post-solve outlet thermodynamic state chips (W-11).
   * Populated after a successful cycle solve; cleared when the user edits
   * any component parameter (signals the state is stale).
   *
   * Three chips: T_out [K], P_out [bar], ṁ [kg/s].
   * undefined = not yet solved (pre-solve or after a failed solve).
   */
  solvedState?: {
    outletTemperature: number;
    outletPressure: number;
    outletMassFlow: number;
  };
}

/** Maps port kind → color class, so flow and shaft handles look different. */
const PORT_CLASS: Record<PortKind, string> = {
  flow:
    "!bg-brand !border-brand-pressed dark:!bg-brand dark:!border-brand-hover",
  shaft:
    "!bg-semantic-warning !border-semantic-warning dark:!bg-semantic-warning",
  heat:
    "!bg-semantic-danger !border-semantic-danger dark:!bg-semantic-danger",
};

interface BaseNodeProps extends NodeProps {
  /** Icon to render in the header. */
  icon: React.ReactNode;
  /** Human-readable family label (e.g. "Compressor"). */
  family: string;
  /** Optional accent class on the header (used by source/outlet nodes). */
  accent?: string;
  /** Data for the node (typed). */
  data: CycleNodeData;
}

/**
 * Shared shell for every cycle node: bold header, tabular chips, typed
 * handles laid out by the port catalogue. Keeps every component visually
 * consistent so a Compressor and a Burner read as the same product.
 */
export function BaseNode({
  icon,
  family,
  data,
  selected,
  accent,
  id,
}: BaseNodeProps) {
  const ports = PORTS[data.kind];
  const hasError = Boolean(data.validationError);

  const borderClass = hasError
    ? "border-semantic-danger"
    : selected
      ? "border-brand"
      : "border-border-default";
  const fillClass = hasError
    ? "bg-semantic-danger-surface/40"
    : selected
      ? "bg-brand-surface/40"
      : "bg-surface-raised";

  return (
    <div
      className={cn(
        "group min-w-[180px] select-none rounded-sm border shadow-z1 transition-colors duration-fast",
        "hover:border-brand-hover",
        borderClass,
        fillClass,
      )}
      data-cycle-node-id={id}
    >
      {/* Header */}
      <div
        className={cn(
          "flex items-center gap-2 border-b border-border-subtle px-2 py-1.5",
          accent,
        )}
      >
        <span className="flex h-4 w-4 items-center justify-center text-text-muted transition-transform duration-fast group-hover:scale-110">
          {icon}
        </span>
        <span className="text-sm font-semibold text-text leading-none">
          {family}
        </span>
        {data.ref && (
          <span className="font-mono text-xs text-text-muted leading-none">
            {data.ref}
          </span>
        )}
        {hasError && (
          <Tooltip>
            <TooltipTrigger asChild>
              <span
                aria-label="Validation error"
                className="ml-auto inline-flex h-3 w-3 items-center justify-center rounded-full bg-semantic-danger text-[10px] font-bold text-text-inverse"
              >
                !
              </span>
            </TooltipTrigger>
            <TooltipContent className="border-semantic-danger-border bg-semantic-danger-surface text-semantic-danger-text">
              {data.validationError}
            </TooltipContent>
          </Tooltip>
        )}
      </div>

      {/* Design-input chips */}
      {data.chips.length > 0 && (
        <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 px-2 py-1.5 font-mono text-[11px] leading-tight">
          {data.chips.map((c) => (
            <div key={c.symbol} className="flex items-baseline gap-1">
              <span className="text-text-muted">{c.symbol}</span>
              <span className="tabular-nums text-text">{c.value}</span>
            </div>
          ))}
        </div>
      )}
      {data.chips.length === 0 && !data.solvedState && (
        <div className="px-2 py-1.5 text-[10px] text-text-muted">
          (no parameters)
        </div>
      )}

      {/* Post-solve outlet state chips (W-11) */}
      {data.solvedState && (
        <div className="border-t border-brand/20 bg-brand-surface/20 px-2 py-1 font-mono text-[10px] leading-tight">
          <div className="mb-0.5 text-[9px] font-semibold uppercase tracking-wide text-brand-text/60">
            outlet state
          </div>
          <div className="grid grid-cols-3 gap-x-1.5 gap-y-0.5">
            <div className="flex flex-col items-start">
              <span className="text-text-muted">T&#8320;</span>
              <span className="tabular-nums text-text">
                {data.solvedState.outletTemperature.toFixed(0)}&nbsp;K
              </span>
            </div>
            <div className="flex flex-col items-start">
              <span className="text-text-muted">P&#8320;</span>
              <span className="tabular-nums text-text">
                {(data.solvedState.outletPressure / 100).toFixed(2)}&nbsp;bar
              </span>
            </div>
            <div className="flex flex-col items-start">
              <span className="text-text-muted">ṁ</span>
              <span className="tabular-nums text-text">
                {data.solvedState.outletMassFlow.toFixed(3)}&nbsp;kg/s
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Input handles — flow ports on the left, shaft ports at the bottom */}
      {ports.inputs
        .filter((p) => p.kind !== "shaft")
        .map((p, i, arr) => {
          const top = portOffset(i, arr.length);
          return (
            <Handle
              key={`in-${p.id}`}
              id={p.id}
              type="target"
              position={Position.Left}
              className={cn("!h-2 !w-2 !rounded-full", PORT_CLASS[p.kind])}
              style={{ top: `${top}%` }}
              title={`${p.label} (${p.kind})`}
            />
          );
        })}
      {ports.inputs
        .filter((p) => p.kind === "shaft")
        .map((p, i, arr) => {
          const left = portOffset(i, arr.length);
          return (
            <Handle
              key={`in-${p.id}`}
              id={p.id}
              type="target"
              position={Position.Bottom}
              className={cn("!h-2 !w-2 !rounded-full", PORT_CLASS[p.kind])}
              style={{ left: `${left}%` }}
              title={`${p.label} (${p.kind})`}
            />
          );
        })}

      {/* Output handles — flow ports on the right, shaft ports at the bottom */}
      {ports.outputs
        .filter((p) => p.kind !== "shaft")
        .map((p, i, arr) => {
          const top = portOffset(i, arr.length);
          return (
            <Handle
              key={`out-${p.id}`}
              id={p.id}
              type="source"
              position={Position.Right}
              className={cn("!h-2 !w-2 !rounded-full", PORT_CLASS[p.kind])}
              style={{ top: `${top}%` }}
              title={`${p.label} (${p.kind})`}
            />
          );
        })}
      {ports.outputs
        .filter((p) => p.kind === "shaft")
        .map((p, i, arr) => {
          const left = portOffset(i, arr.length);
          return (
            <Handle
              key={`out-${p.id}`}
              id={p.id}
              type="source"
              position={Position.Bottom}
              className={cn("!h-2 !w-2 !rounded-full", PORT_CLASS[p.kind])}
              style={{ left: `${left}%` }}
              title={`${p.label} (${p.kind})`}
            />
          );
        })}
    </div>
  );
}

/** Returns 1-based percent offset so 1 handle sits at 50 %, 2 at 33/67, etc. */
function portOffset(idx: number, count: number): number {
  return ((idx + 1) / (count + 1)) * 100;
}
