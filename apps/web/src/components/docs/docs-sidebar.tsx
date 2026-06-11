"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo, useState } from "react";
import { BookOpen, Search, X } from "lucide-react";
import { DOC_GROUPS, docHref } from "@/lib/docs/manifest";
import { cn } from "@/lib/utils";

/**
 * Left rail for /docs. Grouped page list with a type-to-filter box; the
 * filter matches titles and descriptions so "SSE" finds the REST API page
 * even though it isn't in the title.
 */
export function DocsSidebar() {
  const pathname = usePathname() ?? "";
  const [query, setQuery] = useState("");

  const activeSlug = useMemo(() => {
    const m = pathname.match(/^\/docs(?:\/([^/]+))?/);
    return m ? (m[1] ?? "") : null;
  }, [pathname]);

  const q = query.trim().toLowerCase();
  const groups = useMemo(() => {
    if (q === "") return DOC_GROUPS;
    return DOC_GROUPS.map((g) => ({
      ...g,
      pages: g.pages.filter(
        (p) =>
          p.title.toLowerCase().includes(q) ||
          p.description.toLowerCase().includes(q),
      ),
    })).filter((g) => g.pages.length > 0);
  }, [q]);

  return (
    <aside className="hidden w-rail shrink-0 border-r border-border-subtle bg-surface lg:flex lg:flex-col">
      <div className="flex h-full flex-col overflow-y-auto scrollbar-subtle">
        <div className="flex items-center gap-2 border-b border-border-subtle px-4 py-3">
          <BookOpen className="h-4 w-4 text-brand" />
          <span className="text-sm font-medium text-text">Docs</span>
        </div>

        <div className="relative mx-3 mt-3">
          <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-muted" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter pages…"
            aria-label="Filter documentation pages"
            className="h-7 w-full rounded-sm border border-border-subtle bg-surface-raised pl-7 pr-7 text-sm text-text placeholder:text-text-muted focus:border-border-focus focus:outline-none"
          />
          {query !== "" && (
            <button
              type="button"
              onClick={() => setQuery("")}
              aria-label="Clear filter"
              className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-sm p-0.5 text-text-muted hover:text-text"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>

        <nav className="flex flex-col gap-4 px-2 py-3">
          {groups.length === 0 && (
            <p className="px-2 text-xs text-text-muted">
              No pages match “{query}”.
            </p>
          )}
          {groups.map((group) => (
            <div key={group.label} className="flex flex-col gap-0.5">
              <div className="px-2 pb-1 text-[11px] font-medium uppercase tracking-wide text-text-muted">
                {group.label}
              </div>
              {group.pages.map((page) => {
                const active = activeSlug === page.slug;
                return (
                  <Link
                    key={page.slug}
                    href={docHref(page.slug)}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex h-7 items-center rounded-sm px-2 text-sm transition-colors duration-fast",
                      active
                        ? "bg-brand-surface font-medium text-brand-text"
                        : "text-text hover:bg-surface-subtle",
                    )}
                  >
                    <span className="truncate">{page.title}</span>
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
      </div>
    </aside>
  );
}
