"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

interface TocEntry {
  id: string;
  title: string;
}

/**
 * Right-rail floating ToC that highlights the section currently in the
 * viewport. Discovers entries by querying `[data-learn-section]` on mount
 * so chapters don't have to register sections explicitly.
 *
 * Renders nothing on screens below `lg` — the chapter rail collapses too.
 */
export function ReadingToc({ className }: { className?: string }) {
  const [entries, setEntries] = useState<TocEntry[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);

  useEffect(() => {
    const nodes = Array.from(
      document.querySelectorAll<HTMLElement>("[data-learn-section]"),
    );
    const found: TocEntry[] = nodes
      .map((n) => ({
        id: n.id,
        title: n.dataset.learnSectionTitle ?? n.id,
      }))
      .filter((e) => e.id);
    setEntries(found);

    if (found.length === 0) return;

    const obs = new IntersectionObserver(
      (records) => {
        // Pick the topmost section currently in view (smallest top > 0 wins;
        // otherwise the last one above the fold).
        const visible = records
          .filter((r) => r.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible.length > 0) {
          setActiveId(visible[0].target.id);
        }
      },
      { rootMargin: "-15% 0px -65% 0px", threshold: 0 },
    );
    nodes.forEach((n) => obs.observe(n));
    return () => obs.disconnect();
  }, []);

  if (entries.length === 0) return null;

  return (
    <aside
      aria-label="On this page"
      className={cn(
        "hidden xl:block",
        "sticky top-6 ml-6 h-[calc(100vh-3rem)] w-56 shrink-0 overflow-y-auto py-4 text-sm scrollbar-subtle",
        className,
      )}
    >
      <div className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">
        On this page
      </div>
      <ul className="flex flex-col gap-1 border-l border-border-subtle">
        {entries.map((e) => {
          const active = activeId === e.id;
          return (
            <li key={e.id}>
              <a
                href={`#${e.id}`}
                className={cn(
                  "block -ml-px border-l-2 pl-3 py-1 text-sm leading-snug transition-colors duration-fast",
                  active
                    ? "border-brand text-brand-text font-medium"
                    : "border-transparent text-text-muted hover:text-text",
                )}
              >
                {e.title}
              </a>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
