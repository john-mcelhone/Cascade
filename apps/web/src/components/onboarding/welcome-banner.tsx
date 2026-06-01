"use client";

import Link from "next/link";
import { GraduationCap, Sparkles, Plus, X, ArrowRight } from "lucide-react";
import { useUIStore } from "@/lib/stores/ui-store";
import { useMounted } from "@/lib/hooks/use-mounted";

/**
 * First-run welcome. Shows once on the Projects screen until dismissed, giving
 * newcomers three clear front doors instead of a cold empty grid. Honors the
 * experience level: in Expert mode we never show it (pros don't want a tour).
 */
export function WelcomeBanner() {
  const mounted = useMounted();
  const dismissed = useUIStore((s) => s.onboardingDismissed);
  const experience = useUIStore((s) => s.experience);
  const dismiss = useUIStore((s) => s.dismissOnboarding);

  // SSR-safe: render nothing until hydrated, then decide.
  if (!mounted || dismissed || experience === "expert") return null;

  return (
    <div className="animate-fade-in-up relative mb-6 overflow-hidden rounded-xl border border-brand/25 bg-surface-raised p-6 shadow-z2">
      <div
        aria-hidden
        className="aurora pointer-events-none absolute inset-0 opacity-70"
      />
      <button
        type="button"
        onClick={dismiss}
        aria-label="Dismiss welcome"
        className="absolute right-3 top-3 z-10 rounded-md p-1.5 text-text-muted transition-colors hover:bg-surface-subtle hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
      >
        <X className="h-4 w-4" />
      </button>

      <div className="relative flex flex-col gap-1">
        <span className="inline-flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-brand-text">
          <Sparkles className="h-3.5 w-3.5" />
          Welcome to Cascade
        </span>
        <h2 className="text-xl font-semibold tracking-tight text-text">
          Let&apos;s get you to your first result.
        </h2>
        <p className="mt-1 max-w-2xl text-sm leading-relaxed text-text-muted">
          Cascade takes you from a thermodynamic cycle to a validated rotor in
          one browser tab. Pick a starting point — you can change the amount of
          hand-holding any time from the experience dial in the top bar.
        </p>
      </div>

      <div className="relative mt-5 grid gap-3 sm:grid-cols-3">
        <WelcomeChoice
          href="/learn"
          Icon={GraduationCap}
          title="Learn the basics"
          body="Ten illustrated chapters, start to finish."
        />
        <WelcomeChoice
          href="/projects/new"
          Icon={Plus}
          title="Start from a template"
          body="Microturbine, sCO₂, or radial turbine."
          primary
        />
        <button
          type="button"
          onClick={dismiss}
          className="group flex flex-col items-start gap-1 rounded-lg border border-border-subtle bg-surface-raised/70 p-3.5 text-left transition-all hover:-translate-y-0.5 hover:shadow-z2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
        >
          <span className="text-sm font-medium text-text">
            I&apos;ll explore myself
          </span>
          <span className="text-xs leading-snug text-text-muted">
            Hide this and browse the projects below.
          </span>
        </button>
      </div>
    </div>
  );
}

function WelcomeChoice({
  href,
  Icon,
  title,
  body,
  primary = false,
}: {
  href: string;
  Icon: typeof GraduationCap;
  title: string;
  body: string;
  primary?: boolean;
}) {
  return (
    <Link
      href={href}
      className={`group flex flex-col items-start gap-1 rounded-lg border p-3.5 transition-all hover:-translate-y-0.5 hover:shadow-z2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus ${
        primary
          ? "border-brand/30 bg-brand-surface/60"
          : "border-border-subtle bg-surface-raised/70"
      }`}
    >
      <span
        className={`mb-1 flex h-8 w-8 items-center justify-center rounded-md ${
          primary
            ? "bg-brand-gradient text-text-inverse shadow-z1"
            : "border border-border-subtle bg-surface-subtle text-text-subtle"
        }`}
      >
        <Icon className="h-4 w-4" />
      </span>
      <span className="flex items-center gap-1 text-sm font-medium text-text">
        {title}
        <ArrowRight className="h-3.5 w-3.5 text-text-muted transition-transform group-hover:translate-x-0.5" />
      </span>
      <span className="text-xs leading-snug text-text-muted">{body}</span>
    </Link>
  );
}
