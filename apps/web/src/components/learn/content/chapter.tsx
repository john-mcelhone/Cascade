"use client";

import { useEffect, useRef } from "react";
import { Clock } from "lucide-react";
import {
  LEARN_LAST_VISITED_KEY,
  LEARN_PROGRESS_KEY,
  type Difficulty,
} from "@/lib/learn/chapters";
import { cn } from "@/lib/utils";

const DIFFICULTY_TONE: Record<Difficulty, string> = {
  Beginner:
    "border-semantic-success-border bg-semantic-success-surface text-semantic-success-text",
  Intermediate:
    "border-semantic-warning-border bg-semantic-warning-surface text-semantic-warning-text",
  Advanced:
    "border-semantic-danger-border bg-semantic-danger-surface text-semantic-danger-text",
};

export interface ChapterProps {
  /** Chapter slug — used to mark progress. */
  slug: string;
  /** Display number, shown as `1.` prefix in the hero. */
  number: number;
  /** Chapter title (the H1). */
  title: string;
  /** One-line subtitle below the title. */
  subtitle?: string;
  /** Reading difficulty chip. */
  difficulty: Difficulty;
  /** Estimated reading time, in whole minutes. */
  readMinutes: number;
  /** Optional author note shown in a small caption block. */
  authorNote?: React.ReactNode;
  children: React.ReactNode;
}

/**
 * Hero header + max-w-3xl prose column. Drops a sentinel at the bottom of
 * the body that flips the slug to "complete" once it's intersected (i.e.
 * the user has scrolled past 90% of the chapter).
 *
 * Progress events are dispatched on the window so the sidebar can refresh
 * without a polling loop.
 */
export function Chapter({
  slug,
  number,
  title,
  subtitle,
  difficulty,
  readMinutes,
  authorNote,
  children,
}: ChapterProps) {
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  // Mark last-visited on mount.
  useEffect(() => {
    try {
      window.localStorage.setItem(LEARN_LAST_VISITED_KEY, slug);
      window.dispatchEvent(new Event("cascade:learn:progress"));
    } catch {
      /* ignore */
    }
  }, [slug]);

  // Mark complete once the sentinel scrolls into view.
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            try {
              const raw = window.localStorage.getItem(LEARN_PROGRESS_KEY);
              const set = new Set<string>(
                raw ? (JSON.parse(raw) as string[]) : [],
              );
              if (!set.has(slug)) {
                set.add(slug);
                window.localStorage.setItem(
                  LEARN_PROGRESS_KEY,
                  JSON.stringify(Array.from(set)),
                );
                window.dispatchEvent(new Event("cascade:learn:progress"));
              }
            } catch {
              /* ignore */
            }
          }
        }
      },
      { threshold: 0, rootMargin: "0px 0px -10% 0px" },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [slug]);

  return (
    <article className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-6 py-8 lg:py-12">
      <header className="flex flex-col gap-3">
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <span
            className={cn(
              "rounded-sm border px-1.5 py-px font-medium",
              DIFFICULTY_TONE[difficulty],
            )}
          >
            {difficulty}
          </span>
          <span className="inline-flex items-center gap-1 tabular-nums">
            <Clock className="h-3 w-3" />
            {readMinutes} min read
          </span>
          <span className="font-mono">Chapter {number}</span>
        </div>
        <h1 className="text-xl font-medium leading-tight text-text">
          {title}
        </h1>
        {subtitle && (
          <p className="max-w-2xl text-md text-text-muted">{subtitle}</p>
        )}
        {authorNote && (
          <p className="rounded-md border border-border-subtle bg-surface-subtle/60 px-3 py-2 text-sm text-text-muted">
            {authorNote}
          </p>
        )}
      </header>

      <div className="flex flex-col gap-5 text-md leading-relaxed text-text">
        {children}
      </div>

      <div ref={sentinelRef} aria-hidden data-chapter-complete-sentinel />
    </article>
  );
}
