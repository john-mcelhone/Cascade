"use client";

import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { BearingDef, BearingTableRow } from "./rotor-sketch";

interface BearingEditorProps {
  bearing: BearingDef;
  onChange: (next: BearingDef) => void;
}

/**
 * 2×2 K/C bearing editor (ADAPT-024).
 *
 * Tab 1 ("Linear") accepts eight numeric inputs: K_yy, K_zz, K_yz, K_zy on
 * one row, and C_yy, C_zz, C_yz, C_zy on another. The cross-coupling
 * terms accept any sign (oil-whirl asymmetry — Childs 1993 §4.7); the
 * direct terms must be > 0 (K) or ≥ 0 (C) per API 684 §2.4.
 *
 * Tab 2 ("Tabulated vs RPM") lets the user maintain a small table of
 * (rpm, K_yy, K_zz, ..., C_zy) rows for variable-speed analysis. The
 * backend interpolates between rows via cascade.rotor.TabulatedBearing.
 *
 * Validation runs on every input via react-hook-form + zod; the
 * `onChange` callback only fires when the form passes.
 */
export function BearingEditor({ bearing, onChange }: BearingEditorProps) {
  return (
    <TooltipProvider delayDuration={200}>
      <div className="rounded-md border border-border-subtle bg-surface px-3 py-3">
        <div className="mb-2 flex items-baseline justify-between">
          <span className="font-mono text-sm text-text">
            {bearing.label ?? bearing.id}
          </span>
          <span className="text-xs text-text-muted">API 684 §2.3 K · C</span>
        </div>
        <Tabs defaultValue="linear">
          <TabsList>
            <TabsTrigger value="linear">Linear</TabsTrigger>
            <TabsTrigger value="tabulated">Tabulated vs RPM</TabsTrigger>
          </TabsList>
          <TabsContent value="linear">
            <LinearTab bearing={bearing} onChange={onChange} />
          </TabsContent>
          <TabsContent value="tabulated">
            <TabulatedTab bearing={bearing} onChange={onChange} />
          </TabsContent>
        </Tabs>
      </div>
    </TooltipProvider>
  );
}

/* -------------------------------------------------------------------------- */
/* Tab 1 — Linear K · C                                                       */
/* -------------------------------------------------------------------------- */

const linearSchema = z.object({
  K_yy: z.coerce
    .number()
    .positive("K_yy must be > 0 (API 684 §2.4)")
    .max(1e10, "K_yy must be ≤ 1e10 N/m (SPEC §15)"),
  K_zz: z.coerce
    .number()
    .positive("K_zz must be > 0 (API 684 §2.4)")
    .max(1e10, "K_zz must be ≤ 1e10 N/m (SPEC §15)"),
  K_yz: z.coerce.number().min(-1e10).max(1e10),
  K_zy: z.coerce.number().min(-1e10).max(1e10),
  C_yy: z.coerce
    .number()
    .min(0, "C_yy must be ≥ 0 (passive bearing)")
    .max(1e7),
  C_zz: z.coerce
    .number()
    .min(0, "C_zz must be ≥ 0 (passive bearing)")
    .max(1e7),
  C_yz: z.coerce.number().min(-1e7).max(1e7),
  C_zy: z.coerce.number().min(-1e7).max(1e7),
  axialPosition: z.coerce.number(),
});

type LinearForm = z.infer<typeof linearSchema>;

function LinearTab({ bearing, onChange }: BearingEditorProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
    watch,
  } = useForm<LinearForm>({
    resolver: zodResolver(linearSchema),
    defaultValues: {
      K_yy: bearing.K_yy,
      K_zz: bearing.K_zz,
      K_yz: bearing.K_yz,
      K_zy: bearing.K_zy,
      C_yy: bearing.C_yy,
      C_zz: bearing.C_zz,
      C_yz: bearing.C_yz,
      C_zy: bearing.C_zy,
      axialPosition: bearing.axialPosition,
    },
    mode: "onChange",
  });

  // Reset the form when the parent picks a different bearing.
  useEffect(() => {
    reset({
      K_yy: bearing.K_yy,
      K_zz: bearing.K_zz,
      K_yz: bearing.K_yz,
      K_zy: bearing.K_zy,
      C_yy: bearing.C_yy,
      C_zz: bearing.C_zz,
      C_yz: bearing.C_yz,
      C_zy: bearing.C_zy,
      axialPosition: bearing.axialPosition,
    });
  }, [bearing.id, bearing, reset]);

  // Auto-commit on every valid change. We use react-hook-form's handleSubmit
  // wrapper as a validator and watch the form to trigger commits.
  const live = watch();
  useEffect(() => {
    const r = linearSchema.safeParse(live);
    if (r.success) {
      const next: BearingDef = {
        ...bearing,
        K_yy: r.data.K_yy,
        K_zz: r.data.K_zz,
        K_yz: r.data.K_yz,
        K_zy: r.data.K_zy,
        C_yy: r.data.C_yy,
        C_zz: r.data.C_zz,
        C_yz: r.data.C_yz,
        C_zy: r.data.C_zy,
        axialPosition: r.data.axialPosition,
        stiffness: 0.5 * (r.data.K_yy + r.data.K_zz),
        damping: 0.5 * (r.data.C_yy + r.data.C_zz),
      };
      // Only fire if anything actually changed (cheap shallow compare).
      const changed =
        next.K_yy !== bearing.K_yy ||
        next.K_zz !== bearing.K_zz ||
        next.K_yz !== bearing.K_yz ||
        next.K_zy !== bearing.K_zy ||
        next.C_yy !== bearing.C_yy ||
        next.C_zz !== bearing.C_zz ||
        next.C_yz !== bearing.C_yz ||
        next.C_zy !== bearing.C_zy ||
        next.axialPosition !== bearing.axialPosition;
      if (changed) onChange(next);
    }
  }, [live, bearing, onChange]);

  // Touch handleSubmit so the linter doesn't complain it's unused.
  void handleSubmit;

  return (
    <div className="flex flex-col gap-3">
      <p className="text-[11px] text-text-muted">
        Direct stiffness K_yy / K_zz must be {">"} 0; cross-coupling K_yz /
        K_zy may be any sign.
      </p>

      <div className="grid grid-cols-2 gap-2">
        <NumericField
          label="K_yy [N/m]"
          tip="Horizontal radial direct stiffness (API 684 §2.3)."
          {...register("K_yy")}
          error={errors.K_yy?.message}
        />
        <NumericField
          label="K_zz [N/m]"
          tip="Vertical radial direct stiffness (API 684 §2.3)."
          {...register("K_zz")}
          error={errors.K_zz?.message}
        />
        <NumericField
          label="K_yz [N/m]"
          tip="Cross-coupled horizontal→vertical stiffness. Negative is allowed (oil-whirl asymmetry, Childs §4.7)."
          {...register("K_yz")}
          error={errors.K_yz?.message}
        />
        <NumericField
          label="K_zy [N/m]"
          tip="Cross-coupled vertical→horizontal stiffness."
          {...register("K_zy")}
          error={errors.K_zy?.message}
        />
      </div>

      <div className="grid grid-cols-2 gap-2">
        <NumericField
          label="C_yy [N·s/m]"
          tip="Horizontal direct damping; must be ≥ 0 for a passive bearing."
          {...register("C_yy")}
          error={errors.C_yy?.message}
        />
        <NumericField
          label="C_zz [N·s/m]"
          tip="Vertical direct damping."
          {...register("C_zz")}
          error={errors.C_zz?.message}
        />
        <NumericField
          label="C_yz [N·s/m]"
          tip="Cross-coupled damping; sign unconstrained."
          {...register("C_yz")}
          error={errors.C_yz?.message}
        />
        <NumericField
          label="C_zy [N·s/m]"
          tip="Cross-coupled damping."
          {...register("C_zy")}
          error={errors.C_zy?.message}
        />
      </div>

      <NumericField
        label="axial [mm]"
        tip="Axial position from the rotor nose."
        {...register("axialPosition")}
        error={errors.axialPosition?.message}
      />
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Tab 2 — Tabulated K · C vs RPM                                             */
/* -------------------------------------------------------------------------- */

const tabRowSchema = z.object({
  rpm: z.coerce.number().min(0),
  K_yy: z.coerce.number().positive(),
  K_zz: z.coerce.number().positive(),
  K_yz: z.coerce.number(),
  K_zy: z.coerce.number(),
  C_yy: z.coerce.number().min(0),
  C_zz: z.coerce.number().min(0),
  C_yz: z.coerce.number(),
  C_zy: z.coerce.number(),
});

const SEED_TABLE_ROW = (rpm: number, k: number, c: number): BearingTableRow => ({
  rpm,
  K_yy: k,
  K_zz: k,
  K_yz: 0,
  K_zy: 0,
  C_yy: c,
  C_zz: c,
  C_yz: 0,
  C_zy: 0,
});

function TabulatedTab({ bearing, onChange }: BearingEditorProps) {
  const [rows, setRows] = useState<BearingTableRow[]>(
    bearing.table && bearing.table.length >= 2
      ? bearing.table
      : [
          SEED_TABLE_ROW(0, bearing.K_yy || 5e7, bearing.C_yy || 1e3),
          SEED_TABLE_ROW(60000, bearing.K_yy * 1.5 || 7.5e7, bearing.C_yy || 1e3),
        ],
  );

  // Refresh local rows whenever the bearing identity changes.
  useEffect(() => {
    setRows(
      bearing.table && bearing.table.length >= 2
        ? bearing.table
        : [
            SEED_TABLE_ROW(0, bearing.K_yy || 5e7, bearing.C_yy || 1e3),
            SEED_TABLE_ROW(
              60000,
              bearing.K_yy * 1.5 || 7.5e7,
              bearing.C_yy || 1e3,
            ),
          ],
    );
  }, [bearing.id, bearing.K_yy, bearing.C_yy, bearing.table]);

  const commit = (next: BearingTableRow[]) => {
    setRows(next);
    const allValid = next.every((r) => tabRowSchema.safeParse(r).success);
    if (allValid && next.length >= 2) {
      onChange({ ...bearing, table: next });
    } else if (next.length < 2) {
      // Need at least 2 rows for interpolation.
      onChange({ ...bearing, table: undefined });
    }
  };

  const update = (i: number, k: keyof BearingTableRow, v: number) => {
    const next = rows.map((r, j) => (i === j ? { ...r, [k]: v } : r));
    commit(next);
  };
  const addRow = () => {
    const lastRow = rows[rows.length - 1];
    const nextRpm = (lastRow?.rpm ?? 0) + 10000;
    commit([
      ...rows,
      SEED_TABLE_ROW(nextRpm, lastRow?.K_yy ?? 5e7, lastRow?.C_yy ?? 1e3),
    ]);
  };
  const removeRow = (i: number) => {
    commit(rows.filter((_, j) => j !== i));
  };

  const columns = useMemo<ColumnDef<BearingTableRow>[]>(
    () => [
      tabCol("rpm", "RPM"),
      tabCol("K_yy", "K_yy"),
      tabCol("K_zz", "K_zz"),
      tabCol("K_yz", "K_yz"),
      tabCol("K_zy", "K_zy"),
      tabCol("C_yy", "C_yy"),
      tabCol("C_zz", "C_zz"),
      tabCol("C_yz", "C_yz"),
      tabCol("C_zy", "C_zy"),
      {
        id: "actions",
        header: "",
        cell: ({ row }) => (
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={() => removeRow(row.index)}
            aria-label="Remove row"
            disabled={rows.length <= 2}
          >
            <Trash2 className="h-3 w-3" />
          </Button>
        ),
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [rows.length],
  );

  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
    meta: { update },
  });

  return (
    <div className="flex flex-col gap-2">
      <p className="text-[11px] text-text-muted">
        Tabulated K · C vs spin speed for variable-speed runs. Linearly
        interpolated by the backend (cascade.rotor.TabulatedBearing). Need at
        least two rows.
      </p>
      <div className="overflow-x-auto rounded-sm border border-border-subtle">
        <table className="w-full text-[11px] tabular-nums">
          <thead className="bg-surface-subtle text-[10px] uppercase tracking-wide text-text-muted">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((h) => (
                  <th key={h.id} className="px-1.5 py-1 text-left">
                    {flexRender(h.column.columnDef.header, h.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((r) => (
              <tr key={r.id} className="border-t border-border-subtle">
                {r.getVisibleCells().map((c) => (
                  <td key={c.id} className="px-1 py-0.5">
                    {flexRender(c.column.columnDef.cell, c.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Button
        variant="outline"
        size="sm"
        className="self-start gap-1"
        onClick={addRow}
      >
        <Plus className="h-3 w-3" /> Add row
      </Button>
    </div>
  );
}

function tabCol(
  key: Exclude<keyof BearingTableRow, "rpm"> | "rpm",
  label: string,
): ColumnDef<BearingTableRow> {
  return {
    accessorKey: key,
    header: label,
    cell: ({ row, table }) => {
      const v = row.getValue<number>(key);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const meta = table.options.meta as any;
      return (
        <input
          type="number"
          step="any"
          data-input="true"
          className="h-6 w-20 rounded-sm border border-border-subtle bg-surface-input px-1 text-[11px] tabular-nums focus:outline-none focus:ring-1 focus:ring-border-focus"
          value={Number.isFinite(v) ? v : 0}
          onChange={(e) => meta?.update?.(row.index, key, Number(e.target.value))}
        />
      );
    },
  };
}

/* -------------------------------------------------------------------------- */
/* Shared numeric field                                                       */
/* -------------------------------------------------------------------------- */

type RegisterReturn = ReturnType<ReturnType<typeof useForm>["register"]>;

interface NumericFieldProps extends Omit<RegisterReturn, "ref"> {
  label: string;
  tip?: string;
  error?: string;
  ref?: RegisterReturn["ref"];
}

const NumericField = ({ label, tip, error, ...rest }: NumericFieldProps) => {
  return (
    <label className="flex flex-col gap-0.5">
      <span className="flex items-baseline justify-between text-[10px] uppercase tracking-wide text-text-muted">
        <span>{label}</span>
        {tip && (
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="cursor-help normal-case text-text-muted/70">
                ?
              </span>
            </TooltipTrigger>
            <TooltipContent side="left" className="max-w-xs text-xs">
              {tip}
            </TooltipContent>
          </Tooltip>
        )}
      </span>
      <Input
        type="number"
        data-input="true"
        step="any"
        // react-hook-form's register() spreads ref, onChange, onBlur, name.
        // We forward them as-is.
        {...rest}
        className={
          error
            ? "border-semantic-danger-border focus-visible:ring-semantic-danger-border"
            : undefined
        }
      />
      {error && (
        <span className="text-[10px] text-semantic-danger-text">{error}</span>
      )}
    </label>
  );
};
