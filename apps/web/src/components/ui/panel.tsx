"use client";

import * as React from "react";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Panel — the editor-style container used across workspaces. A slim header
 * strip (title, optional meta and tools) over a body. Pass `collapsible` to
 * make the header a disclosure toggle, like a properties-editor section.
 */
export function Panel({
  title,
  meta,
  actions,
  collapsible = false,
  defaultOpen = true,
  className,
  bodyClassName,
  children,
}: {
  title: React.ReactNode;
  /** Quiet text right after the title (a count, a unit, a source). */
  meta?: React.ReactNode;
  /** Tools on the right edge of the header. */
  actions?: React.ReactNode;
  collapsible?: boolean;
  defaultOpen?: boolean;
  className?: string;
  bodyClassName?: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = React.useState(defaultOpen);
  const bodyId = React.useId();
  const expanded = !collapsible || open;

  const heading = (
    <>
      {collapsible && (
        <ChevronRight
          aria-hidden
          className={cn(
            "h-3.5 w-3.5 shrink-0 text-text-muted transition-transform duration-fast",
            open && "rotate-90",
          )}
        />
      )}
      <span className="truncate text-[13px] font-semibold text-text">
        {title}
      </span>
      {meta && (
        <span className="truncate text-xs font-normal text-text-muted">
          {meta}
        </span>
      )}
    </>
  );

  return (
    <section
      className={cn(
        "overflow-hidden rounded-md border border-border-subtle bg-surface",
        className,
      )}
    >
      <header
        className={cn(
          "flex h-9 items-center gap-2 px-3",
          expanded && "border-b border-border-subtle",
        )}
      >
        {collapsible ? (
          <button
            type="button"
            aria-expanded={open}
            aria-controls={bodyId}
            onClick={() => setOpen((o) => !o)}
            className="-ml-1 flex min-w-0 flex-1 items-center gap-1.5 rounded-sm px-1 py-0.5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
          >
            {heading}
          </button>
        ) : (
          <h2 className="flex min-w-0 flex-1 items-baseline gap-2">
            {heading}
          </h2>
        )}
        {actions && (
          <div className="flex shrink-0 items-center gap-1">{actions}</div>
        )}
      </header>
      {expanded && (
        <div id={bodyId} className={bodyClassName}>
          {children}
        </div>
      )}
    </section>
  );
}

/** A label/value row for property lists inside a panel. */
export function PropertyRow({
  label,
  children,
  mono = false,
}: {
  label: React.ReactNode;
  children: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 px-3 py-1.5 text-sm">
      <span className="shrink-0 text-text-muted">{label}</span>
      <span
        className={cn(
          "min-w-0 truncate text-right text-text",
          mono && "font-mono text-xs",
        )}
      >
        {children}
      </span>
    </div>
  );
}
