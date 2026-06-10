import Link from "next/link";
import {
  ArrowRight,
  GraduationCap,
  Github,
  Network,
  Wind,
  Grid3x3,
  Cog,
  GitBranch,
  ShieldCheck,
  Sigma,
} from "lucide-react";
import { Logo, CascadeMark } from "@/components/shell/logo";
import { Button } from "@/components/ui/button";

/**
 * Cascade landing page — the front door for both audiences: a curious
 * newcomer who has never sized a turbine, and a veteran who wants to be
 * running a sweep in four minutes. Console language: blueprint grid, flat
 * panels, mono readouts, no gradients.
 */
export default function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-text">
      <header className="sticky top-0 z-40 flex h-topbar items-center justify-between border-b border-border-subtle bg-surface px-5">
        <Logo />
        <nav className="flex items-center gap-1">
          <Link
            href="/learn"
            className="micro-label hidden rounded-sm px-2.5 py-2 transition-colors hover:bg-surface-subtle hover:text-text sm:block"
          >
            Learn
          </Link>
          <Link
            href="/docs"
            className="micro-label hidden rounded-sm px-2.5 py-2 transition-colors hover:bg-surface-subtle hover:text-text sm:block"
          >
            Docs
          </Link>
          <Link
            href="/docs/validation"
            className="micro-label hidden rounded-sm px-2.5 py-2 transition-colors hover:bg-surface-subtle hover:text-text md:block"
          >
            Validation
          </Link>
          <Link href="/projects" className="ml-2">
            <Button size="sm" className="h-7 gap-1.5 px-3">
              Open workspace
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
        </nav>
      </header>

      <main className="flex flex-1 flex-col">
        {/* ───────────────────────── Hero ───────────────────────── */}
        <section className="relative overflow-hidden border-b border-border-subtle">
          <div
            aria-hidden
            className="bg-blueprint pointer-events-none absolute inset-0 -z-10 [mask-image:radial-gradient(ellipse_at_top_left,black,transparent_75%)]"
          />

          <div className="mx-auto w-full max-w-6xl px-5 py-14 sm:py-20">
            <div className="grid items-center gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,28rem)]">
              <div className="flex flex-col gap-6">
                <div className="animate-fade-in-up inline-flex items-center gap-3">
                  <span className="inline-flex items-center gap-2 rounded-sm border border-border-subtle bg-surface px-2.5 py-1">
                    <span
                      className="led led-pulse bg-semantic-success"
                      aria-hidden
                    />
                    <span className="micro-label !text-text-subtle">
                      v0.1.0 — Validation public
                    </span>
                  </span>
                  <Link
                    href="/docs/validation"
                    className="micro-label hidden underline-offset-4 hover:text-text hover:underline sm:block"
                  >
                    Read the report
                  </Link>
                </div>

                <h1
                  className="animate-fade-in-up max-w-2xl text-2xl font-semibold leading-[1.06] tracking-tight sm:text-3xl"
                  style={{ animationDelay: "60ms" }}
                >
                  Turbomachinery design,
                  <br className="hidden sm:block" />{" "}
                  <span className="text-brand">in the open.</span>
                </h1>

                <p
                  className="animate-fade-in-up max-w-xl text-md leading-relaxed text-text-muted"
                  style={{ animationDelay: "120ms" }}
                >
                  Build a cycle. Run a meanline. Sweep thousands of candidate
                  geometries against your constraints. Pick one. Ship it —
                  every loss model cited, every project a folder of text
                  files, every run reproducible.
                </p>

                <div
                  className="animate-fade-in-up flex flex-wrap items-center gap-3 pt-1"
                  style={{ animationDelay: "180ms" }}
                >
                  <Link href="/projects">
                    <Button size="xl" className="gap-2">
                      Open the workspace
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </Link>
                  <Link href="/learn">
                    <Button size="xl" variant="outline" className="gap-2">
                      <GraduationCap className="h-4 w-4" />
                      Start with Learn
                    </Button>
                  </Link>
                </div>

                <p
                  className="animate-fade-in-up text-sm text-text-muted"
                  style={{ animationDelay: "220ms" }}
                >
                  First radial-turbine sweep in about four minutes.
                </p>
              </div>

              <SolverConsole />
            </div>

            {/* Spec readout — hairline-segmented instrument strip. */}
            <dl
              className="animate-fade-in-up mt-12 grid grid-cols-2 overflow-hidden rounded-sm border border-border-subtle bg-surface sm:grid-cols-4"
              style={{ animationDelay: "300ms" }}
            >
              <Stat value="<200 ms" label="Recuperated Brayton solve" />
              <Stat value="2 000+" label="Candidates per sweep" />
              <Stat value="100 %" label="Loss models cited, CI-enforced" />
              <Stat value="AGPL-3.0" label="Free to self-host, forever" />
            </dl>
          </div>
        </section>

        {/* ─────────────────── Two ways in (audiences) ─────────────────── */}
        <section className="mx-auto w-full max-w-6xl px-5 py-14">
          <div className="mb-6">
            <p className="micro-label mb-2">Two ways in</p>
            <h2 className="text-xl font-semibold tracking-tight">
              Cascade meets you where you are — and grows as you do.
            </h2>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <AudienceCard
              eyebrow="New to turbines"
              title="Learn the principles, hands-on."
              body="Ten short illustrated chapters take you from your first Brayton cycle to rotor dynamics, with interactive widgets you can poke at. Switch the app to Guided mode and it coaches you through every step."
              cta="Open the Learn track"
              href="/learn"
              Icon={GraduationCap}
            />
            <AudienceCard
              eyebrow="Seasoned engineer"
              title="Skip the tour. Start sweeping."
              body="Jump straight into the workspace with a microturbine, sCO₂, or radial-turbine template pre-loaded. Switch to Expert mode for maximum density, keyboard-first, every control on screen at once."
              cta="Open the workspace"
              href="/projects"
              Icon={Wind}
              primary
            />
          </div>
        </section>

        {/* ─────────────────────── Why Cascade ─────────────────────── */}
        <section className="border-y border-border-subtle bg-surface">
          <div className="mx-auto w-full max-w-6xl px-5 py-14">
            <div className="grid gap-4 sm:grid-cols-3">
              <ReasonCard
                Icon={Sigma}
                title="You can see the math."
                body="Every loss correlation is a citation, an equation, a calibration scale, and the Python source. Aungier 2000, profile loss, Eq. 6.42 — with the DOI."
              />
              <ReasonCard
                Icon={GitBranch}
                title="Your project lives in git."
                body="A Cascade project is a folder of TOML files, scripts, and a lockfile. Diff it. Code-review it. Bisect a regression."
              />
              <ReasonCard
                Icon={ShieldCheck}
                title="Trust is published."
                body="Every solver ships with a public validation suite. We tell you what we get wrong and by how much."
              />
            </div>
          </div>
        </section>

        {/* ───────────────────── Workflow strip ───────────────────── */}
        <section className="mx-auto w-full max-w-6xl px-5 py-14">
          <div className="mb-6">
            <p className="micro-label mb-2">Pipeline</p>
            <h2 className="text-xl font-semibold tracking-tight">
              The whole hero workflow, in one browser tab.
            </h2>
            <p className="mt-1 text-sm text-text-muted">
              The path legacy desktop tools take a week to wire up.
            </p>
          </div>
          <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <WorkflowStep
              n={1}
              Icon={Network}
              title="Cycle"
              body="Drag components, connect flows, converge a recuperated Brayton in under 200 ms."
            />
            <WorkflowStep
              n={2}
              Icon={Wind}
              title="Flow path"
              body="Drop into preliminary design with the cycle's exit conditions pre-loaded."
            />
            <WorkflowStep
              n={3}
              Icon={Grid3x3}
              title="Explore + Map"
              body="Sweep 2,000 candidates, then build a performance map with explicit surge & choke."
            />
            <WorkflowStep
              n={4}
              Icon={Cog}
              title="Rotor"
              body="Import the impeller as a lumped disk and run lateral: Bode, Campbell, margins."
            />
          </ol>
        </section>

        <footer className="mt-auto border-t border-border-subtle bg-surface">
          <div className="mx-auto flex w-full max-w-6xl flex-col items-center justify-between gap-3 px-5 py-5 text-xs text-text-muted sm:flex-row">
            <div className="flex items-center gap-2">
              <CascadeMark />
              <span className="font-mono">© 2026 American Turbines</span>
            </div>
            <div className="flex flex-wrap items-center justify-center gap-4">
              <Link href="/docs" className="hover:text-text">
                Docs
              </Link>
              <Link href="/docs/validation" className="hover:text-text">
                Validation
              </Link>
              <Link href="/changelog" className="hover:text-text">
                Changelog
              </Link>
              <Link href="/terms" className="hover:text-text">
                Terms
              </Link>
              <Link href="/privacy" className="hover:text-text">
                Privacy
              </Link>
              <a
                href="mailto:services@americanturbines.com"
                className="hover:text-text"
              >
                Services
              </a>
              <a
                href="https://github.com/americanturbines/cascade"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 hover:text-text"
              >
                <Github className="h-3.5 w-3.5" />
                Source
              </a>
            </div>
          </div>
        </footer>
      </main>
    </div>
  );
}

/* ANSI-shadow logotype — the boot banner. 56 columns of pure nostalgia. */
const ASCII_BANNER = ` ██████╗ █████╗ ███████╗ ██████╗ █████╗ ██████╗ ███████╗
██╔════╝██╔══██╗██╔════╝██╔════╝██╔══██╗██╔══██╗██╔════╝
██║     ███████║███████╗██║     ███████║██║  ██║█████╗
██║     ██╔══██║╚════██║██║     ██╔══██║██║  ██║██╔══╝
╚██████╗██║  ██║███████║╚██████╗██║  ██║██████╔╝███████╗
 ╚═════╝╚═╝  ╚═╝╚══════╝ ╚═════╝╚═╝  ╚═╝╚═════╝ ╚══════╝`;

/**
 * Decorative boot-screen console for the hero — an honest day in Cascade
 * compressed into one terminal session: solve, sweep, map. Static markup,
 * CSS-only animation; numbers mirror the demo project.
 */
function SolverConsole() {
  return (
    <div
      className="animate-fade-in-up hidden overflow-hidden rounded-sm border border-border-subtle bg-surface shadow-z2 md:block"
      style={{ animationDelay: "150ms" }}
      aria-hidden
    >
      <div className="flex items-center justify-between border-b border-border-subtle bg-surface-subtle px-3 py-1.5">
        <span className="micro-label">Solver console</span>
        <span className="flex items-center gap-2">
          <span className="led led-pulse bg-semantic-success" />
          <span className="font-mono text-[10px] text-text-muted">
            tty1 · local
          </span>
        </span>
      </div>

      <div className="select-none overflow-x-auto p-4 scrollbar-subtle">
        <pre className="font-mono text-[9px] leading-[12px] text-brand sm:text-[10px] sm:leading-[13px]">
          {ASCII_BANNER}
        </pre>
        <pre className="mt-1.5 font-mono text-[10px] leading-[14px] text-text-muted">
          {" web-native turbomachinery design · v0.1.0"}
        </pre>

        <pre className="mt-4 font-mono text-[11px] leading-[17px]">
          <span className="text-brand">{"› "}</span>
          <span className="text-text">{"cascade solve cycle microturbine-30kw"}</span>
          {"\n"}
          <span className="text-text-muted">{"  iter 12 · residual 3.2e-09   "}</span>
          <span className="text-accent">{"█▇▅▃▂▁"}</span>
          {"\n"}
          <span className="text-semantic-success">{"  ✓ converged 182 ms"}</span>
          <span className="text-text-muted">{" · η_e 0.274 · w_net 30.2 kW"}</span>
          {"\n\n"}
          <span className="text-brand">{"› "}</span>
          <span className="text-text">{"cascade sweep --candidates 2000 --seed 42"}</span>
          {"\n"}
          <span className="text-semantic-success">{"  ✓ 1 847 solved"}</span>
          <span className="text-text-muted">{" · 219 valid · best η_tt 0.881"}</span>
          {"\n\n"}
          <span className="text-brand">{"› "}</span>
          <span className="text-text">{"cascade map --speedlines 5"}</span>
          {"\n"}
          <span className="text-text-muted">{"  π_tt ┤          ╭───"}</span>
          <span className="text-accent">{"●"}</span>
          <span className="text-text-muted">{"─╮    108 krpm\n"}</span>
          <span className="text-text-muted">{"       │      ╭───╯    ╰──╮\n"}</span>
          <span className="text-text-muted">{"       │   ╭──╯  96 krpm  ╰─╮\n"}</span>
          <span className="text-text-muted">{"       └───┬───────┬───────┬───  ṁ [kg/s]\n"}</span>
          <span className="text-semantic-success">{"  ✓ 45 points"}</span>
          <span className="text-text-muted">{" · surge & choke explicit · 0 ambiguous codes"}</span>
          {"\n\n"}
          <span className="text-brand">{"› "}</span>
          <span className="animate-led-pulse text-accent">{"█"}</span>
        </pre>
      </div>
    </div>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="flex flex-col gap-1 border-border-subtle px-4 py-3 [&:not(:first-child)]:border-l max-sm:[&:nth-child(odd)]:border-l-0 max-sm:[&:nth-child(n+3)]:border-t">
      <dt className="order-2 text-xs leading-snug text-text-muted">{label}</dt>
      <dd className="order-1 font-mono text-lg font-medium tabular-nums text-brand-text">
        {value}
      </dd>
    </div>
  );
}

function AudienceCard({
  eyebrow,
  title,
  body,
  cta,
  href,
  Icon,
  primary = false,
}: {
  eyebrow: string;
  title: string;
  body: string;
  cta: string;
  href: string;
  Icon: typeof Wind;
  primary?: boolean;
}) {
  return (
    <Link href={href} className="group block focus-visible:outline-none">
      <div
        className={`relative flex h-full flex-col overflow-hidden rounded-sm border transition-colors duration-fast group-focus-visible:ring-2 group-focus-visible:ring-border-focus ${
          primary
            ? "border-brand/40 bg-surface-raised group-hover:border-brand"
            : "border-border-subtle bg-surface-raised group-hover:border-border-strong"
        }`}
      >
        {/* Panel header strip */}
        <div
          className={`flex items-center justify-between border-b px-4 py-2 ${
            primary
              ? "border-brand/40 bg-brand-surface"
              : "border-border-subtle bg-surface-subtle"
          }`}
        >
          <span
            className={`micro-label ${primary ? "!text-brand-text" : ""}`}
          >
            {eyebrow}
          </span>
          <Icon
            className={`h-4 w-4 ${primary ? "text-brand" : "text-text-muted"}`}
          />
        </div>
        <div className="flex flex-1 flex-col gap-2 p-4">
          <h3 className="text-lg font-semibold tracking-tight">{title}</h3>
          <p className="text-sm leading-relaxed text-text-muted">{body}</p>
          <span className="mt-auto inline-flex items-center gap-1.5 pt-2 text-sm font-medium text-brand-text">
            {cta}
            <ArrowRight className="h-4 w-4 transition-transform duration-base group-hover:translate-x-0.5" />
          </span>
        </div>
      </div>
    </Link>
  );
}

function ReasonCard({
  Icon,
  title,
  body,
}: {
  Icon: typeof Sigma;
  title: string;
  body: string;
}) {
  return (
    <div className="rounded-sm border border-border-subtle bg-surface-raised p-4">
      <span className="mb-3 flex h-8 w-8 items-center justify-center rounded-sm border border-brand/40 bg-brand-surface text-brand">
        <Icon className="h-4 w-4" />
      </span>
      <h3 className="text-md font-semibold tracking-tight">{title}</h3>
      <p className="mt-1.5 text-sm leading-relaxed text-text-muted">{body}</p>
    </div>
  );
}

function WorkflowStep({
  n,
  Icon,
  title,
  body,
}: {
  n: number;
  Icon: typeof Network;
  title: string;
  body: string;
}) {
  return (
    <li className="relative flex flex-col gap-2 rounded-sm border border-border-subtle bg-surface-raised p-4">
      <div className="flex items-center justify-between">
        <span className="flex h-7 w-7 items-center justify-center rounded-sm border border-border-subtle bg-surface-subtle text-text-subtle">
          <Icon className="h-4 w-4" />
        </span>
        <span className="font-mono text-xs text-brand-text">
          {String(n).padStart(2, "0")} / 04
        </span>
      </div>
      <h3 className="text-md font-semibold tracking-tight">{title}</h3>
      <p className="text-sm leading-relaxed text-text-muted">{body}</p>
    </li>
  );
}
