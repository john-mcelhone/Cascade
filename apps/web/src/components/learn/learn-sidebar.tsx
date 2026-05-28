"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Check, BookOpen, Bookmark } from "lucide-react";
import {
  CHAPTERS,
  LEARN_LAST_VISITED_KEY,
  LEARN_PROGRESS_KEY,
  getChapter,
  type ChapterMeta,
  type Difficulty,
} from "@/lib/learn/chapters";
import { cn } from "@/lib/utils";

const DIFFICULTY_TONE: Record<Difficulty, string> = {
  Beginner: "border-semantic-success-border bg-semantic-success-surface text-semantic-success-text",
  Intermediate: "border-semantic-warning-border bg-semantic-warning-surface text-semantic-warning-text",
  Advanced: "border-semantic-danger-border bg-semantic-danger-surface text-semantic-danger-text",
};

function readProgress(): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = window.localStorage.getItem(LEARN_PROGRESS_KEY);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return new Set(parsed.filter((s): s is string => typeof s === "string"));
    }
  } catch {
    /* ignore — corrupt storage */
  }
  return new Set();
}

function readLastVisited(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(LEARN_LAST_VISITED_KEY);
  } catch {
    return null;
  }
}

/**
 * The left rail for `/learn`. Lists the 10 chapters with progress chips,
 * reading time, difficulty, and a "Resume" pin at the top.
 *
 * Progress state lives in localStorage under `cascade.learn.progress` as a
 * JSON array of slugs. Chapters mark themselves complete via a sentinel
 * element rendered at the bottom of `<Chapter>`; we listen for the custom
 * `cascade:learn:complete` event so the sidebar can re-read storage without
 * a polling loop.
 */
export function LearnSidebar() {
  const pathname = usePathname() ?? "";
  const [progress, setProgress] = useState<Set<string>>(() => new Set());
  const [lastVisited, setLastVisited] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setProgress(readProgress());
    setLastVisited(readLastVisited());

    const onChange = () => {
      setProgress(readProgress());
      setLastVisited(readLastVisited());
    };
    window.addEventListener("cascade:learn:progress", onChange);
    window.addEventListener("storage", onChange);
    return () => {
      window.removeEventListener("cascade:learn:progress", onChange);
      window.removeEventListener("storage", onChange);
    };
  }, []);

  const activeSlug = pathname.match(/^\/learn\/([^/]+)/)?.[1] ?? null;
  const resumeChapter: ChapterMeta | null =
    lastVisited && lastVisited !== activeSlug ? getChapter(lastVisited) : null;

  return (
    <aside className="hidden w-rail shrink-0 border-r border-border-subtle bg-surface lg:flex lg:flex-col">
      <div className="flex h-full flex-col overflow-y-auto scrollbar-subtle">
        <div className="flex items-center gap-2 border-b border-border-subtle px-4 py-3">
          <BookOpen className="h-4 w-4 text-brand" />
          <span className="text-sm font-medium text-text">Learn</span>
        </div>

        {mounted && resumeChapter && (
          <Link
            href={`/learn/${resumeChapter.slug}`}
            className="mx-3 mt-3 flex flex-col gap-1 rounded-md border border-brand/30 bg-brand-surface px-3 py-2 text-xs transition-colors duration-fast hover:border-brand"
          >
            <div className="flex items-center gap-1.5 text-brand-text">
              <Bookmark className="h-3 w-3" />
              <span className="font-medium">Resume</span>
            </div>
            <span className="text-text">
              {resumeChapter.number}. {resumeChapter.title}
            </span>
          </Link>
        )}

        <nav className="flex flex-col gap-0.5 px-2 py-3">
          {CHAPTERS.map((ch) => {
            const active = activeSlug === ch.slug;
            const complete = mounted && progress.has(ch.slug);
            return (
              <Link
                key={ch.slug}
                href={`/learn/${ch.slug}`}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "group flex flex-col gap-1 rounded-sm px-2 py-1.5 text-sm transition-colors duration-fast",
                  active
                    ? "bg-brand-surface text-brand-text"
                    : "text-text hover:bg-surface-subtle",
                )}
              >
                <div className="flex items-start gap-2">
                  <ProgressChip complete={complete} active={active} />
                  <div className="flex-1 min-w-0">
                    <div
                      className={cn(
                        "flex items-baseline gap-1.5 truncate text-sm leading-tight",
                        active && "font-medium",
                      )}
                    >
                      <span className="font-mono text-xs text-text-muted">
                        {ch.number}.
                      </span>
                      <span className="truncate">{ch.title}</span>
                    </div>
                    <div className="mt-0.5 flex items-center gap-1.5 text-xs text-text-muted">
                      <span
                        className={cn(
                          "rounded-sm border px-1 py-px text-[10px] font-medium leading-tight",
                          DIFFICULTY_TONE[ch.difficulty],
                        )}
                      >
                        {ch.difficulty}
                      </span>
                      <span className="tabular-nums">{ch.readMinutes} min</span>
                    </div>
                  </div>
                </div>
              </Link>
            );
          })}
        </nav>

        <div className="mx-2 my-2 h-px bg-border-subtle" />
        <Link
          href="/learn/glossary"
          aria-current={activeSlug === "glossary" ? "page" : undefined}
          className={cn(
            "mx-2 mb-3 flex h-7 items-center gap-2 rounded-sm px-2 text-sm transition-colors duration-fast",
            activeSlug === "glossary"
              ? "bg-brand-surface text-brand-text font-medium"
              : "text-text-muted hover:bg-surface-subtle hover:text-text",
          )}
        >
          <BookOpen className="h-3.5 w-3.5" />
          <span>Glossary</span>
        </Link>
      </div>
    </aside>
  );
}

function ProgressChip({
  complete,
  active,
}: {
  complete: boolean;
  active: boolean;
}) {
  return (
    <span
      aria-hidden
      className={cn(
        "mt-1 flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full border transition-colors duration-fast",
        complete
          ? "border-semantic-success-border bg-semantic-success text-text-inverse"
          : active
            ? "border-brand bg-surface-raised"
            : "border-border-default bg-surface",
      )}
    >
      {complete && <Check className="h-2 w-2" strokeWidth={3} />}
    </span>
  );
}
