"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  BookOpen,
  Check,
  Clock,
  CircleDot,
} from "lucide-react";
import {
  CHAPTERS,
  LEARN_LAST_VISITED_KEY,
  LEARN_PROGRESS_KEY,
  type ChapterMeta,
} from "@/lib/learn/chapters";
import { cn } from "@/lib/utils";

/**
 * /learn landing page — "Learn the principles, then apply them."
 *
 * Hero, then a 2-column grid of chapter cards with progress state from
 * localStorage, then two short prose sections (curriculum philosophy +
 * quick-jump for experienced users). Static content with one client-side
 * read of progress.
 */
export default function LearnLanding() {
  const [progress, setProgress] = useState<Set<string>>(new Set());
  const [lastVisited, setLastVisited] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    try {
      const raw = window.localStorage.getItem(LEARN_PROGRESS_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          setProgress(
            new Set(parsed.filter((s): s is string => typeof s === "string")),
          );
        }
      }
      setLastVisited(window.localStorage.getItem(LEARN_LAST_VISITED_KEY));
    } catch {
      /* ignore */
    }
  }, []);

  const completedCount = mounted ? progress.size : 0;
  const startSlug = lastVisited ?? CHAPTERS[0].slug;

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-7 px-6 py-8 lg:py-12">
      {/* Hero */}
      <header className="flex flex-col gap-4">
        <span className="text-xs font-medium uppercase tracking-wide text-text-muted">
          Cascade · Learn
        </span>
        <h1 className="max-w-3xl text-xl font-medium leading-tight text-text lg:text-2xl">
          Learn the principles, then apply them.
        </h1>
        <p className="max-w-2xl text-md leading-relaxed text-text-muted">
          Ten chapters from &ldquo;what is a turbine&rdquo; to &ldquo;how
          we validate a design.&rdquo; Each chapter ends with a working
          widget and a deep-link into Cascade so you can immediately try
          what you just read about. No prior turbomachinery background
          required.
        </p>
        <div className="flex flex-wrap items-center gap-3 pt-1">
          <Link
            href={`/learn/${startSlug}`}
            className="inline-flex h-8 items-center gap-2 rounded-sm border border-brand bg-brand px-4 text-sm font-medium text-text-inverse transition-colors duration-fast hover:bg-brand-hover"
          >
            {lastVisited ? "Resume" : "Start with Chapter 1"}
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
          {mounted && (
            <div className="flex items-center gap-1.5 text-xs text-text-muted">
              <CircleDot className="h-3 w-3" />
              <span className="font-mono tabular-nums">
                {completedCount} of {CHAPTERS.length}
              </span>
              <span>complete</span>
            </div>
          )}
          <Link
            href="/learn/glossary"
            className="inline-flex items-center gap-1 text-sm text-brand-text hover:underline"
          >
            <BookOpen className="h-3.5 w-3.5" />
            Glossary
          </Link>
        </div>
      </header>

      {/* Chapter grid */}
      <section
        aria-label="Chapter list"
        className="grid grid-cols-1 gap-4 md:grid-cols-2"
      >
        {CHAPTERS.map((ch) => {
          const complete = mounted && progress.has(ch.slug);
          const current = mounted && lastVisited === ch.slug && !complete;
          return (
            <ChapterCard
              key={ch.slug}
              chapter={ch}
              complete={complete}
              current={current}
            />
          );
        })}
      </section>

      {/* Why these basics matter */}
      <section className="flex flex-col gap-3 rounded-md border border-border-subtle bg-surface-raised p-5">
        <h2 className="text-lg font-medium text-text">
          Why these basics matter
        </h2>
        <div className="grid grid-cols-1 gap-4 text-md leading-relaxed text-text-muted md:grid-cols-2">
          <p>
            Cascade is a real design tool. The buttons and sliders inside
            it correspond to real equations &mdash; the Euler turbine
            equation, the Whitfield-Baines loss correlations, the
            Timoshenko beam rotor model. Engineers who know what those
            equations <em>do</em> get useful designs out of Cascade in
            an afternoon. Engineers who don&rsquo;t fight the tool.
          </p>
          <p>
            We wrote this curriculum because the gap between
            &ldquo;reading a textbook on turbomachinery&rdquo; and
            &ldquo;sketching a real cycle in software&rdquo; is wider
            than it ought to be. By chapter five you know where
            efficiency goes. By chapter nine you&rsquo;ve walked through
            a complete microturbine design. By chapter ten you can read
            our validation report and decide whether you trust the tool
            on your problem.
          </p>
        </div>
      </section>

      {/* Quick jump */}
      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-medium text-text">
          Already comfortable?
        </h2>
        <p className="max-w-2xl text-md leading-relaxed text-text-muted">
          Jump straight into a workspace. The example projects are
          pre-configured with realistic boundary conditions so you can
          poke at every page without entering numbers first.
        </p>
        <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
          {QUICK_JUMPS.map((jump) => (
            <li key={jump.href}>
              <Link
                href={jump.href}
                className="group flex items-center justify-between gap-3 rounded-md border border-border-subtle bg-surface-raised px-4 py-3 transition-colors duration-fast hover:border-brand"
              >
                <div className="flex flex-col gap-0.5">
                  <span className="text-sm font-medium text-text group-hover:text-brand-text">
                    {jump.title}
                  </span>
                  <span className="text-xs text-text-muted">
                    {jump.subtitle}
                  </span>
                </div>
                <ArrowRight className="h-4 w-4 shrink-0 text-text-muted transition-colors duration-fast group-hover:text-brand" />
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function ChapterCard({
  chapter,
  complete,
  current,
}: {
  chapter: ChapterMeta;
  complete: boolean;
  current: boolean;
}) {
  const cta = complete ? "Re-read" : current ? "Continue" : "Start";
  const tier = chapter.difficulty;
  return (
    <Link
      href={`/learn/${chapter.slug}`}
      className={cn(
        "group flex flex-col gap-3 rounded-md border bg-surface-raised p-4 transition-colors duration-fast",
        current
          ? "border-brand"
          : "border-border-subtle hover:border-border-default",
      )}
    >
      <div className="flex items-start gap-3">
        <ChapterNumber n={chapter.number} complete={complete} />
        <div className="flex flex-1 flex-col gap-1">
          <h3 className="text-md font-medium leading-tight text-text">
            {chapter.title}
          </h3>
          <p className="text-sm leading-snug text-text-muted">
            {chapter.subtitle}
          </p>
        </div>
      </div>

      <div className="mt-auto flex items-center justify-between gap-2 pt-2 text-xs">
        <div className="flex items-center gap-1.5 text-text-muted">
          <span
            className={cn(
              "rounded-sm border px-1 py-px text-[10px] font-medium",
              tier === "Beginner" &&
                "border-semantic-success-border bg-semantic-success-surface text-semantic-success-text",
              tier === "Intermediate" &&
                "border-semantic-warning-border bg-semantic-warning-surface text-semantic-warning-text",
              tier === "Advanced" &&
                "border-semantic-danger-border bg-semantic-danger-surface text-semantic-danger-text",
            )}
          >
            {tier}
          </span>
          <span className="inline-flex items-center gap-1 tabular-nums">
            <Clock className="h-3 w-3" />
            {chapter.readMinutes} min
          </span>
        </div>
        <span className="inline-flex items-center gap-1 text-sm font-medium text-brand-text">
          {cta}
          <ArrowRight className="h-3 w-3 transition-transform duration-fast group-hover:translate-x-0.5" />
        </span>
      </div>
    </Link>
  );
}

function ChapterNumber({ n, complete }: { n: number; complete: boolean }) {
  return (
    <span
      aria-hidden
      className={cn(
        "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border font-mono text-sm tabular-nums",
        complete
          ? "border-semantic-success-border bg-semantic-success-surface text-semantic-success-text"
          : "border-border-default bg-surface text-text-muted",
      )}
    >
      {complete ? <Check className="h-4 w-4" strokeWidth={3} /> : n}
    </span>
  );
}

interface QuickJump {
  href: string;
  title: string;
  subtitle: string;
}

const QUICK_JUMPS: QuickJump[] = [
  {
    href: "/projects",
    title: "Browse projects",
    subtitle: "The microturbine, radial turbine, and rotor demos.",
  },
  {
    href: "/projects/new",
    title: "Start a fresh project",
    subtitle: "From a Brayton template or a blank canvas.",
  },
  {
    href: "/cases/at-100",
    title: "AT-100 case study",
    subtitle: "American Turbines 100 kW microturbine — design phase complete.",
  },
  {
    href: "/learn/glossary",
    title: "Glossary",
    subtitle: "Every term from the tutorial, A to Z, searchable.",
  },
  {
    href: "/docs/validation",
    title: "Validation report",
    subtitle: "171 tests, every source cited, regenerated each commit.",
  },
];
