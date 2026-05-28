"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useFlowPathStore } from "@/lib/flowpath/store";
import { cn } from "@/lib/utils";

interface FlowPathLayoutProps {
  left: React.ReactNode;
  centre: React.ReactNode;
  right: React.ReactNode;
}

/**
 * Three-pane resizable layout: parameter table (left) · scatter (centre) ·
 * 3D viewer (right). Mouse drag on the two dividers resizes the outer
 * panes; the centre pane absorbs the difference. Pane widths persist via
 * the flowpath Zustand store (`layout.leftWidth`, `layout.rightWidth`).
 *
 * Minimum widths keep all three panes usable on a 1440 px laptop screen.
 */
const MIN_LEFT = 320;
const MIN_RIGHT = 280;
const MIN_CENTRE = 320;

export function FlowPathLayout({ left, centre, right }: FlowPathLayoutProps) {
  const layout = useFlowPathStore((s) => s.layout);
  const setLayout = useFlowPathStore((s) => s.setLayout);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const [drag, setDrag] = useState<null | "left" | "right">(null);

  const onMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!drag || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const xRel = e.clientX - rect.left;
      const width = rect.width;
      if (drag === "left") {
        const next = Math.max(MIN_LEFT, Math.min(xRel, width - layout.rightWidth - MIN_CENTRE));
        setLayout({ leftWidth: next });
      } else {
        const next = Math.max(MIN_RIGHT, Math.min(width - xRel, width - layout.leftWidth - MIN_CENTRE));
        setLayout({ rightWidth: next });
      }
    },
    [drag, layout.leftWidth, layout.rightWidth, setLayout],
  );

  const onMouseUp = useCallback(() => setDrag(null), []);

  useEffect(() => {
    if (!drag) return;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, [drag, onMouseMove, onMouseUp]);

  return (
    <div
      ref={containerRef}
      className="grid h-full w-full overflow-hidden"
      style={{
        gridTemplateColumns: `${layout.leftWidth}px 4px minmax(0, 1fr) 4px ${layout.rightWidth}px`,
      }}
    >
      <div className="min-h-0 min-w-0 overflow-auto scrollbar-subtle border-r border-border-subtle bg-surface-subtle/30">
        {left}
      </div>
      <Divider
        orientation="left"
        active={drag === "left"}
        onMouseDown={() => setDrag("left")}
      />
      <div className="min-h-0 min-w-0 overflow-hidden bg-background">{centre}</div>
      <Divider
        orientation="right"
        active={drag === "right"}
        onMouseDown={() => setDrag("right")}
      />
      <div className="min-h-0 min-w-0 overflow-hidden border-l border-border-subtle bg-surface-subtle/40">
        {right}
      </div>
    </div>
  );
}

function Divider({
  orientation,
  active,
  onMouseDown,
}: {
  orientation: "left" | "right";
  active: boolean;
  onMouseDown: () => void;
}) {
  return (
    <button
      type="button"
      aria-label={`Resize ${orientation === "left" ? "parameter" : "viewer"} pane`}
      onMouseDown={onMouseDown}
      className={cn(
        "group relative h-full w-1 cursor-col-resize touch-none select-none",
        "outline-none",
      )}
    >
      <span
        aria-hidden
        className={cn(
          "absolute inset-y-0 left-1/2 w-px -translate-x-1/2 transition-colors duration-fast",
          active
            ? "bg-brand"
            : "bg-border-subtle group-hover:bg-border-strong group-focus-visible:bg-brand",
        )}
      />
    </button>
  );
}
