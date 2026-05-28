"use client";

import { useMemo, useState } from "react";
import {
  type ColumnDef,
  type SortingState,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { MapPoint } from "@/lib/api/types";
import { cn, fmtNumber } from "@/lib/utils";

interface MapTableProps {
  points: MapPoint[];
}

/** Results table: one row per grid point. Sortable on every column. */
export function MapTable({ points }: MapTableProps) {
  const [sorting, setSorting] = useState<SortingState>([
    { id: "rpm", desc: false },
  ]);

  const columns = useMemo<ColumnDef<MapPoint>[]>(
    () => [
      {
        accessorKey: "rpm",
        header: "rpm",
        cell: ({ getValue }) => (
          <span className="tabular-nums">
            {Number(getValue()).toLocaleString()}
          </span>
        ),
      },
      {
        accessorKey: "massFlow",
        header: "ṁ [kg/s]",
        cell: ({ getValue }) => (
          <span className="tabular-nums">
            {fmtNumber(getValue<number>(), { decimals: 4 })}
          </span>
        ),
      },
      {
        accessorKey: "pi_tt",
        header: "π_tt",
        cell: ({ getValue }) => (
          <span className="tabular-nums">
            {fmtNumber(getValue<number>(), { decimals: 3 })}
          </span>
        ),
      },
      {
        accessorKey: "eta_tt",
        header: "η_tt",
        cell: ({ getValue }) => (
          <span className="tabular-nums">
            {fmtNumber(getValue<number>(), { decimals: 3 })}
          </span>
        ),
      },
      {
        accessorKey: "status",
        header: "status",
        cell: ({ getValue }) => {
          const v = getValue<MapPoint["status"]>();
          return (
            <Badge
              variant={
                v === "ok"
                  ? "success"
                  : v === "surge"
                    ? "danger"
                    : v === "choke"
                      ? "info"
                      : "warning"
              }
            >
              {v}
            </Badge>
          );
        },
      },
    ],
    [],
  );

  const table = useReactTable({
    data: points,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  if (points.length === 0) {
    return (
      <p className="px-2 py-3 text-sm text-text-muted">
        No points yet. Run the map above to populate.
      </p>
    );
  }

  return (
    <div className="overflow-hidden rounded-md border border-border-subtle">
      <div className="max-h-[420px] overflow-auto scrollbar-subtle">
        <table className="w-full text-sm">
          <thead className="sticky top-0 border-b border-border-subtle bg-surface-subtle text-xs uppercase tracking-wide text-text-muted">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((h) => {
                  const sorted = h.column.getIsSorted();
                  return (
                    <th
                      key={h.id}
                      className={cn(
                        "px-3 py-1.5 text-left font-medium select-none",
                        h.column.getCanSort() && "cursor-pointer",
                      )}
                      onClick={h.column.getToggleSortingHandler()}
                    >
                      <span className="inline-flex items-center gap-1">
                        {flexRender(h.column.columnDef.header, h.getContext())}
                        {sorted === "asc" && (
                          <ChevronUp className="h-3 w-3" />
                        )}
                        {sorted === "desc" && (
                          <ChevronDown className="h-3 w-3" />
                        )}
                      </span>
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody className="font-mono">
            {table.getRowModel().rows.map((r) => (
              <tr
                key={r.id}
                className="border-b border-border-subtle/60 last:border-b-0 hover:bg-surface-subtle/40"
              >
                {r.getVisibleCells().map((c) => (
                  <td key={c.id} className="px-3 py-1">
                    {flexRender(c.column.columnDef.cell, c.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
