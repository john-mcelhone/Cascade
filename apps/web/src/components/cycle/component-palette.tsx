"use client";

import * as React from "react";
import {
  ArrowDownRight,
  ArrowLeftRight,
  ArrowUpRight,
  Cog,
  Flame,
  GitBranch,
  GitMerge,
  LogIn,
  LogOut,
  Minus,
  Search,
  Snowflake,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import type { CycleNodeKind } from "@/lib/api/types";

/** Mime type used for cycle-component drag transfer. */
export const PALETTE_MIME = "application/x-cascade-cycle-component";

interface PaletteItem {
  kind: CycleNodeKind;
  name: string;
  blurb: string;
  Icon: React.ComponentType<{ className?: string }>;
}

interface PaletteCategory {
  label: string;
  items: PaletteItem[];
}

const CATEGORIES: PaletteCategory[] = [
  {
    label: "Sources",
    items: [
      {
        kind: "inlet",
        name: "Inlet",
        blurb: "Boundary source. Pt, Tt, ṁ.",
        Icon: LogIn,
      },
      {
        kind: "outlet",
        name: "Outlet",
        blurb: "Boundary sink. Exhausts to ambient.",
        Icon: LogOut,
      },
    ],
  },
  {
    label: "Rotors",
    items: [
      {
        kind: "compressor",
        name: "Compressor",
        blurb: "Pressure rise via shaft work.",
        Icon: ArrowUpRight,
      },
      {
        kind: "turbine",
        name: "Turbine",
        blurb: "Shaft work extraction.",
        Icon: ArrowDownRight,
      },
    ],
  },
  {
    label: "Heat",
    items: [
      {
        kind: "burner",
        name: "Combustor",
        blurb: "Heat addition at near-constant Pt.",
        Icon: Flame,
      },
      {
        kind: "recuperator",
        name: "Recuperator",
        blurb: "Counterflow gas-gas heat exchanger.",
        Icon: ArrowLeftRight,
      },
      {
        kind: "intercooler",
        name: "Intercooler",
        blurb: "Heat rejection between stages.",
        Icon: Snowflake,
      },
    ],
  },
  {
    label: "Flow",
    items: [
      {
        kind: "mixer",
        name: "Mixer",
        blurb: "Combine two streams.",
        Icon: GitMerge,
      },
      {
        kind: "splitter",
        name: "Splitter",
        blurb: "Divide one stream into two by mass-flow fraction.",
        Icon: GitBranch,
      },
      {
        kind: "duct",
        name: "Duct",
        blurb: "Constant-pressure-loss segment.",
        Icon: Minus,
      },
    ],
  },
  {
    label: "System",
    items: [
      {
        kind: "shaft",
        name: "Shaft",
        blurb: "Couples turbines to compressors at a common ω.",
        Icon: Cog,
      },
    ],
  },
];

interface ComponentPaletteProps {
  className?: string;
}

/**
 * Left-side palette of cycle components. Drag an item onto the canvas to
 * add a node at the drop position. Search filters by name and blurb.
 */
export function ComponentPalette({ className }: ComponentPaletteProps) {
  const [query, setQuery] = React.useState("");
  const lowered = query.trim().toLowerCase();
  const categories = lowered
    ? CATEGORIES.map((c) => ({
        ...c,
        items: c.items.filter(
          (it) =>
            it.name.toLowerCase().includes(lowered) ||
            it.blurb.toLowerCase().includes(lowered),
        ),
      })).filter((c) => c.items.length > 0)
    : CATEGORIES;

  return (
    <aside
      className={cn(
        "flex w-[240px] shrink-0 flex-col overflow-hidden border-r border-border-subtle bg-surface-subtle/40",
        className,
      )}
    >
      <div className="border-b border-border-subtle p-3">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-text-muted" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Find component"
            className="pl-7"
            aria-label="Filter components"
          />
        </div>
      </div>

      <div className="flex-1 overflow-auto scrollbar-subtle px-2 py-2">
        {categories.length === 0 && (
          <div className="px-2 py-4 text-sm text-text-muted">
            Nothing matches that query.
          </div>
        )}
        {categories.map((c) => (
          <div key={c.label} className="mb-3 last:mb-0">
            <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-text-muted">
              {c.label}
            </div>
            <ul className="flex flex-col gap-0.5">
              {c.items.map((it) => (
                <PaletteEntry key={it.kind} item={it} />
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="border-t border-border-subtle bg-surface/30 px-3 py-2 text-[11px] text-text-muted">
        Drag onto the canvas. Drop where you want it.
      </div>
    </aside>
  );
}

function PaletteEntry({ item }: { item: PaletteItem }) {
  const { Icon } = item;
  const onDragStart = (e: React.DragEvent<HTMLLIElement>) => {
    e.dataTransfer.setData(PALETTE_MIME, item.kind);
    e.dataTransfer.setData("text/plain", item.name);
    e.dataTransfer.effectAllowed = "copy";
  };
  return (
    <li
      draggable
      onDragStart={onDragStart}
      className={cn(
        "flex cursor-grab items-start gap-2 rounded-sm border border-transparent px-2 py-1.5 text-sm",
        "hover:border-border-subtle hover:bg-surface-raised",
        "active:cursor-grabbing",
      )}
      title={item.blurb}
    >
      <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-text-muted" />
      <div className="min-w-0 flex-1">
        <div className="font-medium text-text leading-tight">{item.name}</div>
        <div className="text-[11px] text-text-muted leading-tight">
          {item.blurb}
        </div>
      </div>
    </li>
  );
}
