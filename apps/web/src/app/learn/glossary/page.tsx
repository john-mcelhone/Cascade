"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Search, X, BookOpen, ArrowRight } from "lucide-react";
import {
  GLOSSARY,
  GLOSSARY_COUNT,
  GLOSSARY_LETTERS,
  type GlossaryEntry,
} from "@/lib/learn/glossary";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * /learn/glossary — A-Z searchable glossary of turbomachinery terms.
 *
 * Layout:
 *   - Hero with count + search.
 *   - Sticky A-Z navigation strip.
 *   - Letter-grouped entries, each rendered as a small card with chapter
 *     hot-link and optional Cascade feature link.
 *
 * Search filters live across term + definition + chapter slug. The
 * letter strip greys out letters with no surviving entries.
 */
export default function GlossaryPage() {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => filterEntries(GLOSSARY, query), [query]);

  // Group by letter, preserving the canonical A-Z order.
  const grouped = useMemo(() => {
    const map = new Map<string, GlossaryEntry[]>();
    for (const e of filtered) {
      const arr = map.get(e.letter) ?? [];
      arr.push(e);
      map.set(e.letter, arr);
    }
    return GLOSSARY_LETTERS.map((l) => ({
      letter: l,
      entries: map.get(l) ?? [],
    })).filter((g) => g.entries.length > 0);
  }, [filtered]);

  const matched = filtered.length;

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 px-6 py-8 lg:py-12">
      <header className="flex flex-col gap-3">
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <BookOpen className="h-3.5 w-3.5" />
          <span className="font-medium uppercase tracking-wide">
            Cascade · Learn · Glossary
          </span>
        </div>
        <h1 className="text-xl font-medium text-text">Glossary</h1>
        <p className="max-w-2xl text-md leading-relaxed text-text-muted">
          Every turbomachinery term used in the tutorial &mdash; with a
          definition, the chapter where it&rsquo;s introduced, and a
          link to the relevant Cascade feature.{" "}
          <span className="font-mono tabular-nums">
            {GLOSSARY_COUNT} entries.
          </span>
        </p>
      </header>

      {/* Search box */}
      <div className="relative">
        <Search
          className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-muted"
          aria-hidden
        />
        <Input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={`Search ${GLOSSARY_COUNT} terms...`}
          aria-label="Search glossary"
          className="pl-8 pr-9"
        />
        {query.length > 0 && (
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={() => setQuery("")}
            className="absolute right-1 top-1/2 -translate-y-1/2"
            aria-label="Clear search"
          >
            <X className="h-3 w-3" />
          </Button>
        )}
      </div>

      {/* A-Z navigation strip */}
      <nav
        aria-label="Glossary letter navigation"
        className="sticky top-0 z-10 -mx-2 flex flex-wrap items-center gap-1 rounded-md border border-border-subtle bg-surface/95 px-2 py-1.5 backdrop-blur"
      >
        {GLOSSARY_LETTERS.map((l) => {
          const has = grouped.some((g) => g.letter === l);
          return (
            <a
              key={l}
              href={has ? `#letter-${l}` : undefined}
              aria-disabled={!has}
              className={cn(
                "inline-flex h-6 w-6 items-center justify-center rounded-sm font-mono text-xs tabular-nums",
                has
                  ? "text-text hover:bg-brand-surface hover:text-brand-text"
                  : "text-text-disabled",
              )}
            >
              {l}
            </a>
          );
        })}
        <span className="ml-auto font-mono text-xs tabular-nums text-text-muted">
          {matched === GLOSSARY_COUNT
            ? `${matched} entries`
            : `${matched} of ${GLOSSARY_COUNT}`}
        </span>
      </nav>

      {/* Entries */}
      {grouped.length === 0 ? (
        <div className="rounded-md border border-border-subtle bg-surface-subtle/40 px-4 py-6 text-sm text-text-muted">
          No entries match &ldquo;{query}&rdquo;. Try a shorter query, or{" "}
          <button
            type="button"
            className="text-brand-text hover:underline"
            onClick={() => setQuery("")}
          >
            clear the search
          </button>
          .
        </div>
      ) : (
        <div className="flex flex-col gap-5">
          {grouped.map((g) => (
            <section
              key={g.letter}
              id={`letter-${g.letter}`}
              className="flex flex-col gap-2 scroll-mt-16"
            >
              <h2 className="flex items-baseline gap-2 text-lg font-medium text-text">
                <span className="font-mono">{g.letter}</span>
                <span className="text-xs font-normal text-text-muted">
                  {g.entries.length}
                </span>
              </h2>
              <ul className="grid grid-cols-1 gap-2">
                {g.entries.map((e) => (
                  <Entry key={e.term} entry={e} query={query} />
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}

      {/* Footer */}
      <footer className="mt-4 flex flex-col gap-2 border-t border-border-subtle pt-4 text-sm text-text-muted">
        <p>
          Missing a term? The glossary lives at{" "}
          <code className="rounded-sm bg-surface-subtle px-1 font-mono text-xs">
            src/lib/learn/glossary.ts
          </code>{" "}
          and accepts pull requests.
        </p>
      </footer>
    </div>
  );
}

function Entry({ entry, query }: { entry: GlossaryEntry; query: string }) {
  const chapterNum = entry.chapter?.split("-")[0];
  return (
    <li
      id={`term-${slugify(entry.term)}`}
      className="flex flex-col gap-1.5 rounded-md border border-border-subtle bg-surface-raised p-3"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-mono text-sm font-medium text-text">
          <Highlight text={entry.term} query={query} />
        </span>
        <div className="flex items-center gap-2 text-xs text-text-muted">
          {entry.chapter && (
            <Link
              href={`/learn/${entry.chapter}`}
              className="rounded-sm border border-border-subtle bg-surface-subtle px-1.5 py-px text-[10px] font-medium text-text-muted transition-colors duration-fast hover:border-brand hover:text-brand-text"
            >
              Ch. {chapterNum}
            </Link>
          )}
        </div>
      </div>
      <p className="text-sm leading-relaxed text-text-muted">
        <Highlight text={entry.definition} query={query} />
      </p>
      {entry.pageHref && (
        <Link
          href={entry.pageHref}
          className="mt-1 inline-flex w-fit items-center gap-1 text-xs font-medium text-brand-text hover:underline"
        >
          {entry.pageLabel ?? "Open in Cascade"}
          <ArrowRight className="h-3 w-3" />
        </Link>
      )}
    </li>
  );
}

function Highlight({ text, query }: { text: string; query: string }) {
  if (query.length < 2) return <>{text}</>;
  const q = query.toLowerCase();
  const lower = text.toLowerCase();
  const idx = lower.indexOf(q);
  if (idx < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="rounded-sm bg-semantic-warning-surface px-0.5 text-text">
        {text.slice(idx, idx + query.length)}
      </mark>
      {text.slice(idx + query.length)}
    </>
  );
}

function filterEntries(
  entries: GlossaryEntry[],
  query: string,
): GlossaryEntry[] {
  const q = query.trim().toLowerCase();
  if (q.length === 0) return entries;
  return entries.filter((e) => {
    const hay = `${e.term} ${e.definition} ${e.chapter ?? ""}`.toLowerCase();
    return hay.includes(q);
  });
}

function slugify(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}
