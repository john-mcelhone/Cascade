"use client";

import { useMemo } from "react";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { HelpCircle, Lock, Unlock } from "lucide-react";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useFlowPathStore } from "@/lib/flowpath/store";
import type { ParameterTabKey } from "@/lib/flowpath/store";
import {
  formatParameterValue,
  validateParameter,
  type ParameterDef,
  type ParameterKind,
} from "@/lib/flowpath/parameters";
import { cn } from "@/lib/utils";
import { LossModelPicker } from "./loss-model-picker";

/**
 * The five tabs that group parameters in the left pane. Each non-loss-model
 * tab maps to a single `ParameterKind`; the loss-model tab renders the
 * dedicated picker component. Tab state persists per-user via the flow-path
 * store.
 */
interface TabSpec {
  key: ParameterTabKey;
  label: string;
  /**
   * The ParameterKind this tab filters on. `null` for the loss-model tab,
   * which renders its own component instead of the table.
   */
  kind: ParameterKind | null;
  /** Optional subtitle shown to the right of the tab content header. */
  subtitle?: string;
}

const TABS: TabSpec[] = [
  { key: "boundary", label: "Boundary", kind: "boundary" },
  {
    key: "geometry",
    label: "Geometry",
    kind: "geometry",
    subtitle: "Min · Value · Max",
  },
  { key: "constraint", label: "Constraints", kind: "constraint" },
  { key: "exploration", label: "Exploration", kind: "exploration" },
  { key: "loss-model", label: "Losses", kind: null },
];

interface ParameterTableProps {
  projectId: string;
}

export function ParameterTable({ projectId }: ParameterTableProps) {
  const parameters = useFlowPathStore((s) => s.getParameters(projectId));
  const resetParameters = useFlowPathStore((s) => s.resetParameters);
  const activeTab = useFlowPathStore((s) => s.parameterTab);
  const setActiveTab = useFlowPathStore((s) => s.setParameterTab);

  // Pre-group once per parameters change. The table only renders one group
  // at a time but we still want stable counts for the tab labels.
  const grouped = useMemo(() => {
    const map: Record<ParameterKind, ParameterDef[]> = {
      boundary: [],
      geometry: [],
      constraint: [],
      exploration: [],
    };
    for (const p of parameters) map[p.kind].push(p);
    return map;
  }, [parameters]);

  // Roll up validity per tab so each tab pill can show a warning chip when
  // any of its parameters is failing — much faster than scanning rows.
  const tabValidity = useMemo(() => {
    const out: Record<ParameterTabKey, "ok" | "warn" | "error"> = {
      boundary: "ok",
      geometry: "ok",
      constraint: "ok",
      exploration: "ok",
      "loss-model": "ok",
    };
    for (const p of parameters) {
      const tabKey = p.kind as ParameterTabKey;
      const v = validateParameter(p);
      if (v === "error") out[tabKey] = "error";
      else if (v === "warn" && out[tabKey] !== "error") out[tabKey] = "warn";
    }
    return out;
  }, [parameters]);

  const active = TABS.find((t) => t.key === activeTab) ?? TABS[0];

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border-subtle px-3 py-2">
        <h3 className="text-xs font-medium uppercase tracking-wide text-text-muted">
          Parameters
        </h3>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => resetParameters(projectId)}
          aria-label="Reset parameter table to defaults"
          className="text-text-muted"
        >
          Reset
        </Button>
      </div>

      <TabBar
        active={activeTab}
        setActive={setActiveTab}
        counts={{
          boundary: grouped.boundary.length,
          geometry: grouped.geometry.length,
          constraint: grouped.constraint.length,
          exploration: grouped.exploration.length,
          "loss-model": 0, // The loss-model tab is qualitative, no count.
        }}
        validity={tabValidity}
      />

      <div className="flex-1 overflow-auto scrollbar-subtle px-3 py-3">
        {active.subtitle && (
          <div className="mb-1 flex items-baseline justify-end">
            <span className="font-mono text-[10px] text-text-muted">
              {active.subtitle}
            </span>
          </div>
        )}

        {active.kind === null ? (
          <LossModelPicker />
        ) : (
          <div className="rounded-sm border border-border-subtle bg-surface-default/60 overflow-hidden">
            <Table
              projectId={projectId}
              kind={active.kind}
              rows={grouped[active.kind]}
            />
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab bar
// ---------------------------------------------------------------------------

function TabBar({
  active,
  setActive,
  counts,
  validity,
}: {
  active: ParameterTabKey;
  setActive: (t: ParameterTabKey) => void;
  counts: Record<ParameterTabKey, number>;
  validity: Record<ParameterTabKey, "ok" | "warn" | "error">;
}) {
  // The pane this lives in can be resized down to ~320 px; tabs must never
  // squash or clip mid-label. Each tab is shrink-proof and the row wraps to
  // a second line when the pane gets too narrow for all five.
  return (
    <div
      role="tablist"
      aria-label="Parameter sections"
      className="flex flex-wrap items-center gap-0.5 border-b border-border-subtle bg-surface-subtle/30 px-1.5 py-1"
    >
      {TABS.map((tab) => {
        const isActive = tab.key === active;
        const count = counts[tab.key];
        const v = validity[tab.key];
        return (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={isActive}
            aria-controls={`parameter-pane-${tab.key}`}
            onClick={() => setActive(tab.key)}
            className={cn(
              "group inline-flex h-6 shrink-0 items-center gap-1 whitespace-nowrap rounded-sm px-1.5 text-xs transition-colors",
              isActive
                ? "bg-surface-default font-medium text-text shadow-z1"
                : "text-text-muted hover:bg-surface-default/60 hover:text-text",
            )}
          >
            <span>{tab.label}</span>
            {tab.kind !== null && (
              <span
                className={cn(
                  "tabular-nums text-[10px]",
                  isActive ? "text-text-muted" : "text-text-subtle",
                )}
              >
                {count}
              </span>
            )}
            {v === "warn" && (
              <span
                aria-label="One or more parameters outside its expected range"
                className="h-1.5 w-1.5 rounded-full bg-semantic-warning-default"
              />
            )}
            {v === "error" && (
              <span
                aria-label="One or more parameters failing validation"
                className="h-1.5 w-1.5 rounded-full bg-semantic-danger-default"
              />
            )}
          </button>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Table
// ---------------------------------------------------------------------------

interface TableProps {
  projectId: string;
  kind: ParameterKind;
  rows: ParameterDef[];
}

function Table({ projectId, kind, rows }: TableProps) {
  const setParameter = useFlowPathStore((s) => s.setParameter);

  const helper = createColumnHelper<ParameterDef>();

  const columns = useMemo(() => {
    const cols = [
      helper.display({
        id: "symbol",
        header: () => <span>Symbol</span>,
        cell: ({ row }) => (
          <span className="truncate font-mono text-xs text-text-muted">
            {row.original.symbol}
          </span>
        ),
      }),
    ];

    if (kind === "geometry") {
      cols.push(
        helper.display({
          id: "min",
          header: () => <span>Min</span>,
          cell: ({ row }) => (
            <NumberCell
              value={row.original.min ?? row.original.value}
              variant="input"
              onChange={(v) =>
                setParameter(projectId, row.original.id, { min: v })
              }
              disabled={row.original.frozen}
              ariaLabel={`Minimum value of ${row.original.symbol}`}
            />
          ),
        }),
      );
      cols.push(
        helper.display({
          id: "value",
          header: () => <span>Value</span>,
          cell: ({ row }) => (
            <NumberCell
              value={row.original.value}
              variant="input"
              onChange={(v) =>
                setParameter(projectId, row.original.id, { value: v })
              }
              disabled={row.original.frozen}
              ariaLabel={`Value of ${row.original.symbol}`}
            />
          ),
        }),
      );
      cols.push(
        helper.display({
          id: "max",
          header: () => <span>Max</span>,
          cell: ({ row }) => (
            <NumberCell
              value={row.original.max ?? row.original.value}
              variant="input"
              onChange={(v) =>
                setParameter(projectId, row.original.id, { max: v })
              }
              disabled={row.original.frozen}
              ariaLabel={`Maximum value of ${row.original.symbol}`}
            />
          ),
        }),
      );
    } else {
      cols.push(
        helper.display({
          id: "value",
          header: () => <span>Value</span>,
          cell: ({ row }) => (
            <NumberCell
              value={row.original.value}
              variant="input"
              onChange={(v) =>
                setParameter(projectId, row.original.id, { value: v })
              }
              disabled={row.original.frozen}
              ariaLabel={`Value of ${row.original.symbol}`}
            />
          ),
        }),
      );
    }

    cols.push(
      helper.display({
        id: "unit",
        header: () => <span>Unit</span>,
        cell: ({ row }) => (
          <span className="truncate text-xs text-text-muted">
            {row.original.unit || "—"}
          </span>
        ),
      }),
    );

    cols.push(
      helper.display({
        id: "validity",
        header: () => <span aria-label="Validity" />,
        cell: ({ row }) => <ValidityChip parameter={row.original} />,
      }),
    );

    cols.push(
      helper.display({
        id: "info",
        header: () => <span aria-label="Info" />,
        cell: ({ row }) => <InfoPopover parameter={row.original} />,
      }),
    );

    cols.push(
      helper.display({
        id: "freeze",
        header: () => <span aria-label="Freeze" />,
        cell: ({ row }) => (
          <FreezeToggle
            frozen={row.original.frozen}
            onToggle={() =>
              setParameter(projectId, row.original.id, {
                frozen: !row.original.frozen,
              })
            }
            symbol={row.original.symbol}
          />
        ),
      }),
    );

    return cols;
  }, [kind, projectId, setParameter, helper]);

  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  // Validity / info / freeze columns shrunk so the value cells get the
  // breathing room; this is the main reason the page reads cramped.
  const gridTemplate =
    kind === "geometry"
      ? "minmax(64px, 88px) repeat(3, minmax(0, 1fr)) 44px 18px 20px 20px"
      : "minmax(64px, 110px) minmax(0, 1fr) 48px 18px 20px 20px";

  return (
    <div role="table" className="w-full text-sm">
      <div
        role="row"
        className="grid h-6 items-center gap-1 border-b border-border-subtle bg-surface-subtle/60 px-2 text-[10px] uppercase tracking-wide text-text-muted"
        style={{ gridTemplateColumns: gridTemplate }}
      >
        {table.getHeaderGroups()[0]?.headers.map((header) => (
          <div key={header.id} role="columnheader" className="truncate">
            {flexRender(header.column.columnDef.header, header.getContext())}
          </div>
        ))}
      </div>
      {table.getRowModel().rows.length === 0 && (
        <div className="px-2 py-3 text-xs text-text-muted">
          No {kind} parameters configured.
        </div>
      )}
      {table.getRowModel().rows.map((row) => {
        const frozen = row.original.frozen;
        const validity = validateParameter(row.original);
        return (
          <div
            key={row.id}
            role="row"
            className={cn(
              "grid h-7 items-center gap-1 border-b border-border-subtle/60 px-2 text-sm last:border-b-0",
              frozen && "bg-surface-subtle/40 opacity-70",
              validity === "error" && "bg-semantic-danger-surface/40",
            )}
            style={{ gridTemplateColumns: gridTemplate }}
          >
            {row.getVisibleCells().map((cell) => (
              <div key={cell.id} role="cell" className="min-w-0 truncate">
                {flexRender(cell.column.columnDef.cell, cell.getContext())}
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Cells
// ---------------------------------------------------------------------------

function NumberCell({
  value,
  variant,
  onChange,
  disabled,
  ariaLabel,
}: {
  value: number;
  variant: "input" | "computed";
  onChange: (v: number) => void;
  disabled?: boolean;
  ariaLabel: string;
}) {
  return (
    <Input
      data-input={variant === "input" ? "true" : undefined}
      type="number"
      step="any"
      value={Number.isFinite(value) ? value : ""}
      onChange={(e) => {
        const parsed = parseFloat(e.target.value);
        if (Number.isFinite(parsed)) onChange(parsed);
      }}
      disabled={disabled}
      aria-label={ariaLabel}
      className={cn(
        "h-6 px-1.5 font-mono text-xs tabular-nums",
        variant === "input"
          ? "bg-surface-input"
          : "bg-surface-computed text-text-muted",
      )}
    />
  );
}

/**
 * Validity chip — only renders when the row is in `warn` or `error` state.
 * The previous always-on "ok" badge added clutter to every row of the table
 * for no information value (engineers read "the absence of a chip" as
 * passing, the same way they read "no warning lamp" in any other engineering
 * UI). Hiding the green badge frees up several pixels per row and makes
 * actual issues much more visible.
 */
function ValidityChip({ parameter }: { parameter: ParameterDef }) {
  const v = validateParameter(parameter);
  if (v === "ok") {
    return <span aria-label="Parameter passes validation" className="sr-only">ok</span>;
  }
  if (v === "warn") {
    return (
      <Badge
        variant="warning"
        className="h-4 px-1 text-[10px]"
        aria-label="Parameter outside range"
      >
        rng
      </Badge>
    );
  }
  return (
    <Badge
      variant="danger"
      className="h-4 px-1 text-[10px]"
      aria-label="Parameter fails validation"
    >
      err
    </Badge>
  );
}

function InfoPopover({ parameter }: { parameter: ParameterDef }) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`Show details for ${parameter.symbol}`}
          className="inline-flex h-5 w-5 items-center justify-center rounded-sm text-text-muted hover:bg-surface-subtle hover:text-text"
        >
          <HelpCircle className="h-3 w-3" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80">
        <div className="space-y-2">
          <div className="flex items-baseline justify-between">
            <span className="font-mono text-sm">{parameter.symbol}</span>
            <span className="text-xs text-text-muted">{parameter.unit || "—"}</span>
          </div>
          {parameter.description && (
            <p className="text-xs text-text">{parameter.description}</p>
          )}
          {parameter.regimeHint && (
            <div className="rounded-sm border border-border-subtle bg-surface-subtle/50 p-2 text-xs">
              <span className="block font-medium text-text-muted">
                Validity envelope
              </span>
              <span className="text-text-subtle">{parameter.regimeHint}</span>
            </div>
          )}
          <div className="grid grid-cols-3 gap-1 text-xs font-mono">
            <Cell label="value" value={formatParameterValue(parameter.value, parameter.unit)} />
            <Cell
              label="min"
              value={
                parameter.min === null
                  ? "—"
                  : formatParameterValue(parameter.min, parameter.unit)
              }
            />
            <Cell
              label="max"
              value={
                parameter.max === null
                  ? "—"
                  : formatParameterValue(parameter.max, parameter.unit)
              }
            />
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}

function Cell({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col rounded-sm bg-surface-subtle/40 px-1.5 py-1">
      <span className="text-[10px] uppercase tracking-wide text-text-muted">
        {label}
      </span>
      <span className="tabular-nums">{value}</span>
    </div>
  );
}

function FreezeToggle({
  frozen,
  onToggle,
  symbol,
}: {
  frozen: boolean;
  onToggle: () => void;
  symbol: string;
}) {
  return (
    <button
      type="button"
      aria-pressed={frozen}
      aria-label={
        frozen ? `Unfreeze ${symbol}` : `Freeze ${symbol} at current value`
      }
      onClick={onToggle}
      className={cn(
        "inline-flex h-5 w-5 items-center justify-center rounded-sm text-text-muted transition-colors",
        frozen ? "bg-brand-surface text-brand-text" : "hover:bg-surface-subtle",
      )}
    >
      {frozen ? <Lock className="h-3 w-3" /> : <Unlock className="h-3 w-3" />}
    </button>
  );
}
