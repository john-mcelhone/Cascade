import Link from "next/link";
import { ArrowRight, BookOpen, FileText, GraduationCap, Github } from "lucide-react";
import { Logo } from "@/components/shell/logo";
import { Button } from "@/components/ui/button";

/**
 * Cascade landing page. Marketing-light: just enough to orient a returning
 * engineer and route them into /projects. Voice follows the product's copy style
 * (the homepage hero exemplar).
 */
export default function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-text">
      <header className="flex h-topbar items-center justify-between border-b border-border-subtle px-5">
        <Logo />
        <nav className="hidden items-center gap-4 text-sm text-text-muted sm:flex">
          <Link href="/learn" className="hover:text-text">
            Learn
          </Link>
          <Link href="/docs" className="hover:text-text">
            Docs
          </Link>
          <Link href="/docs/validation" className="hover:text-text">
            Validation
          </Link>
          <Link href="/pricing" className="hover:text-text">
            Pricing
          </Link>
          <Link href="/projects">
            <Button size="sm">Open the workspace</Button>
          </Link>
        </nav>
      </header>

      <main className="flex flex-1 flex-col">
        <section className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-5 py-8 sm:py-8">
          <p className="text-sm font-medium uppercase tracking-wide text-brand-text">
            Cascade
          </p>
          <h1 className="max-w-3xl text-xl font-medium leading-tight tracking-tight text-text sm:text-2xl">
            Turbomachinery design, in the open.
          </h1>
          <p className="max-w-2xl text-md text-text-muted">
            Cascade is a web-native design environment for turbomachinery teams.
            Build a cycle. Run a meanline. Sweep ten thousand candidates against
            your constraints. Pick one. Ship it.
          </p>
          <p className="max-w-2xl text-md text-text-muted">
            Every loss model is cited. Every project is a folder of text files.
            Every run is reproducible. Sign in with your work email and
            you&apos;ll be running your first radial-turbine sweep in about four
            minutes.
          </p>
          <div className="flex flex-wrap items-center gap-2 pt-2">
            <Link href="/projects">
              <Button size="lg" className="gap-2">
                Open the workspace
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link href="/learn">
              <Button size="lg" variant="outline" className="gap-2">
                <GraduationCap className="h-4 w-4" />
                Start with Learn
              </Button>
            </Link>
            <Link href="/docs">
              <Button size="lg" variant="ghost" className="gap-2">
                <BookOpen className="h-4 w-4" />
                Read the docs
              </Button>
            </Link>
            <Link href="/docs/validation">
              <Button size="lg" variant="ghost" className="gap-2">
                <FileText className="h-4 w-4" />
                Validation report
              </Button>
            </Link>
          </div>

          <div className="mt-2 flex items-center gap-3 rounded-md border border-border-subtle bg-surface-1 px-4 py-3 text-sm text-text-muted">
            <GraduationCap className="h-4 w-4 shrink-0 text-brand-text" />
            <span>
              <strong className="text-text">New to turbines?</strong>{" "}
              The{" "}
              <Link href="/learn" className="text-brand-text hover:underline">
                Learn section
              </Link>{" "}
              teaches the principles from first cycles to rotor dynamics in ten short chapters
              with interactive widgets.
            </span>
          </div>
        </section>

        <section className="mx-auto w-full max-w-5xl px-5 pb-8">
          <div className="grid gap-4 sm:grid-cols-3">
            <ReasonCard
              title="You can see the math."
              body="Every loss correlation is a citation, an equation, a calibration scale, and the Python source. Aungier 2000, profile loss, Eq. 6.42 — with the DOI."
            />
            <ReasonCard
              title="Your project lives in git."
              body="A Cascade project is a folder of TOML files, scripts, and a lockfile. Diff it. Code-review it. Bisect a regression."
            />
            <ReasonCard
              title="Trust is published."
              body="Every solver ships with a public validation suite. We tell you what we get wrong and by how much."
            />
          </div>
        </section>

        <footer className="mt-auto border-t border-border-subtle">
          <div className="mx-auto flex w-full max-w-5xl flex-col items-center justify-between gap-3 px-5 py-4 text-sm text-text-muted sm:flex-row">
            <span>© 2026 American Turbines</span>
            <div className="flex items-center gap-4">
              <Link href="/pricing" className="hover:text-text">
                Pricing
              </Link>
              <Link href="/docs" className="hover:text-text">
                Docs
              </Link>
              <Link href="/docs/validation" className="hover:text-text">
                Validation
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
                <Github className="h-3 w-3" />
                Source
              </a>
            </div>
          </div>
        </footer>
      </main>
    </div>
  );
}

function ReasonCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-md border border-border-subtle bg-surface-raised p-4">
      <h3 className="text-md font-medium text-text">{title}</h3>
      <p className="mt-2 text-sm text-text-muted">{body}</p>
    </div>
  );
}
