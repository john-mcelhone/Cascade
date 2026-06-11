"use client";

import { useEffect, useState } from "react";
import { CodeBlock } from "./code-block";
import { cn } from "@/lib/utils";

export const DOCS_LANG_KEY = "cascade.docs.codeLang";
const DOCS_LANG_EVENT = "cascade:docs:codeLang";

export interface CodeTab {
  /** Tab label, e.g. "Python", "CLI", "HTTP". Also the sync key. */
  label: string;
  /** Highlighter language id. */
  lang: string;
  code: string;
  /** Optional filename shown next to the tabs. */
  title?: string;
}

export interface CodeTabsProps {
  tabs: CodeTab[];
  className?: string;
}

function readPreferred(): string | null {
  try {
    return window.localStorage.getItem(DOCS_LANG_KEY);
  } catch {
    return null;
  }
}

/**
 * Stripe-style language switcher. Picking "Python" on one block flips every
 * other CodeTabs on the page (and future pages — the choice persists in
 * localStorage) to its Python tab when it has one. Blocks without the
 * preferred label keep their own selection.
 */
export function CodeTabs({ tabs, className }: CodeTabsProps) {
  const [active, setActive] = useState(0);

  // Adopt the stored preference after mount (SSR renders tab 0).
  useEffect(() => {
    const apply = () => {
      const pref = readPreferred();
      if (!pref) return;
      const idx = tabs.findIndex((t) => t.label === pref);
      if (idx >= 0) setActive(idx);
    };
    apply();
    window.addEventListener(DOCS_LANG_EVENT, apply);
    window.addEventListener("storage", apply);
    return () => {
      window.removeEventListener(DOCS_LANG_EVENT, apply);
      window.removeEventListener("storage", apply);
    };
  }, [tabs]);

  const choose = (idx: number) => {
    setActive(idx);
    try {
      window.localStorage.setItem(DOCS_LANG_KEY, tabs[idx].label);
      window.dispatchEvent(new Event(DOCS_LANG_EVENT));
    } catch {
      /* private mode — selection stays local to this block */
    }
  };

  const tab = tabs[Math.min(active, tabs.length - 1)];

  return (
    <div
      className={cn(
        "w-full overflow-hidden rounded-md border border-border-subtle bg-surface-raised",
        className,
      )}
    >
      <div
        role="tablist"
        aria-label="Code language"
        className="flex items-center gap-0.5 border-b border-border-subtle bg-surface-subtle/60 px-1.5 pt-1.5"
      >
        {tabs.map((t, i) => {
          const selected = i === active;
          return (
            <button
              key={t.label}
              role="tab"
              aria-selected={selected}
              onClick={() => choose(i)}
              className={cn(
                "relative rounded-t-sm px-2.5 py-1.5 text-xs font-medium transition-colors duration-fast",
                selected
                  ? "bg-surface-raised text-text shadow-[inset_0_1px_0_rgb(var(--border-subtle)),inset_1px_0_0_rgb(var(--border-subtle)),inset_-1px_0_0_rgb(var(--border-subtle))]"
                  : "text-text-muted hover:text-text",
              )}
            >
              {t.label}
              {selected && (
                <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-brand" />
              )}
            </button>
          );
        })}
        {tab.title && (
          <span className="ml-auto truncate px-2 font-mono text-xs text-text-muted">
            {tab.title}
          </span>
        )}
      </div>
      <CodeBlock code={tab.code} lang={tab.lang} bare className="rounded-none border-0" />
    </div>
  );
}
