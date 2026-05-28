import Link from "next/link";
import type { Metadata } from "next";
import {
  ArrowRight,
  Download,
  FlaskConical,
  Gauge,
  Layers,
  Thermometer,
  Zap,
} from "lucide-react";

/**
 * /cases/at-100 — American Turbines AT-100 case study scaffold.
 *
 * W-25: AT-100 case study page.
 * Content:
 *   - Header with AT-100 identity
 *   - Hero metrics (target power, η_th, recuperator effectiveness, fuel)
 *   - Architecture description
 *   - Design methodology (4 sections: cycle deck → mean-line PD →
 *     rotor dynamics → CAD handoff)
 *   - Open-data download button for the AT-100 project TOML
 *   - Hardware status: "design phase complete; bench testing Q3 2026"
 *
 * AC1: GET /cases/at-100 returns 200. (This file satisfies that.)
 * AC2: Page contains open-data download link.
 * AC3: Page mentions "design phase complete" and target metrics.
 * AC4: TypeScript clean.
 */
export const metadata: Metadata = {
  title: "AT-100 Case Study",
  description:
    "Case study: AT-100 — American Turbines 100 kW recuperated microturbine. Design methodology, target metrics, and open project data.",
};

export default function AT100CaseStudy() {
  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-8 px-6 py-10 lg:py-14">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-xs text-text-muted">
        <Link href="/" className="hover:text-text">
          Cascade
        </Link>
        <span>/</span>
        <Link href="/learn" className="hover:text-text">
          Learn
        </Link>
        <span>/</span>
        <span className="text-text">Case studies</span>
        <span>/</span>
        <span className="text-text font-medium">AT-100</span>
      </nav>

      {/* Header */}
      <header className="flex flex-col gap-3">
        <span className="text-xs font-medium uppercase tracking-wide text-text-muted">
          Case study
        </span>
        <h1 className="text-2xl font-semibold leading-tight text-text lg:text-3xl">
          AT-100 — American Turbines 100&nbsp;kW recuperated microturbine
        </h1>
        <p className="max-w-2xl text-md leading-relaxed text-text-muted">
          The AT-100 is American Turbines&rsquo; first prototype: a
          single-spool recuperated Brayton machine targeting 100&nbsp;kW
          electric output on natural gas. This page documents the
          design methodology, target performance, and open project data.
          It is also the dogfood reference for Cascade — every feature on
          the roadmap is exercised against this machine first.
        </p>
      </header>

      {/* Hero metrics — AC3: must mention target metrics */}
      <section
        aria-label="Target performance metrics"
        className="grid grid-cols-2 gap-4 sm:grid-cols-4"
      >
        <MetricCard
          icon={<Zap className="h-4 w-4" />}
          label="Target output"
          value="100 kW"
          note="net electric"
        />
        <MetricCard
          icon={<Thermometer className="h-4 w-4" />}
          label="Target η_th"
          value="≥ 28 %"
          note="LHV, ISO conditions"
        />
        <MetricCard
          icon={<Gauge className="h-4 w-4" />}
          label="Recuperator ε"
          value="≥ 0.88"
          note="target effectiveness"
        />
        <MetricCard
          icon={<FlaskConical className="h-4 w-4" />}
          label="Fuel"
          value="Natural gas"
          note="CH₄ / pipeline"
        />
      </section>

      {/* Architecture */}
      <section className="flex flex-col gap-3 rounded-md border border-border-subtle bg-surface-raised p-5">
        <div className="flex items-center gap-2">
          <Layers className="h-4 w-4 text-text-muted" />
          <h2 className="text-lg font-medium text-text">Architecture</h2>
        </div>
        <ul className="flex flex-col gap-2 text-md leading-relaxed text-text-muted">
          <li>
            <strong className="text-text">Cycle topology:</strong> Single-spool
            recuperated open Brayton — air inlet → centrifugal compressor →
            recuperator cold side → natural-gas combustor → radial-inflow
            turbine → recuperator hot side → exhaust.
          </li>
          <li>
            <strong className="text-text">Compressor:</strong> Centrifugal
            impeller, target pressure ratio 4.2 at design point,
            η_is&nbsp;≥&nbsp;0.79.
          </li>
          <li>
            <strong className="text-text">Turbine:</strong> Radial inflow,
            target η_is&nbsp;≥&nbsp;0.85, twin foil-bearing supported shaft at
            ~100&nbsp;kRPM.
          </li>
          <li>
            <strong className="text-text">Combustor:</strong> Annular
            can-type on natural gas. Target TIT&nbsp;1140&nbsp;K.
          </li>
          <li>
            <strong className="text-text">Generator:</strong> Permanent-magnet
            alternator direct-coupled. η_gen&nbsp;≥&nbsp;0.96.
          </li>
          <li>
            <strong className="text-text">Bearings:</strong> Air foil bearings
            (Capstone-class). See{" "}
            <code className="rounded-sm bg-surface-subtle px-1 font-mono text-sm">
              CAPSTONE_C30_FOIL_BEARING
            </code>{" "}
            preset in Cascade&rsquo;s bearing library.
          </li>
        </ul>
      </section>

      {/* Design methodology — 4 sections */}
      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-medium text-text">
          How Cascade was used
        </h2>
        <p className="text-md leading-relaxed text-text-muted">
          The AT-100 design process followed Cascade&rsquo;s four-stage
          preliminary-design workflow. Each stage below links to the
          relevant Cascade feature.
        </p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <MethodCard
            step="01"
            title="Cycle deck"
            description="Recuperated Brayton cycle defined on the Cycle Canvas. Parametric sweep over pressure ratio (3.8 – 4.6) and TIT (1100 – 1160 K) identified the design point that maximises η_th subject to a TIT ceiling of 1150 K."
            href="/projects"
          />
          <MethodCard
            step="02"
            title="Mean-line preliminary design"
            description="Compressor and turbine geometries generated on the Flow Path PD page using the Whitfield-Baines loss model and Aungier centrifugal correlations. Rotor outlet radius, blade count, and tip clearance swept via the Design Space page."
            href="/projects"
          />
          <MethodCard
            step="03"
            title="Rotor dynamics"
            description="Timoshenko beam FEM assembled for the single-spool shaft with foil-bearing K-C presets. Critical speeds verified above 120 % of operating speed per API 684. Campbell diagram confirmed no integer-order crossings in the operating range."
            href="/projects"
          />
          <MethodCard
            step="04"
            title="CAD handoff"
            description="glTF geometry exported for visual review. STEP solid-rotor geometry exported for stress analysis handoff to CalculiX. TurboGrid NDF export scheduled for CFD validation post-build."
            href="/projects"
          />
        </div>
      </section>

      {/* Open data — AC2: must contain download link for AT-100 project file */}
      <section className="flex flex-col gap-3 rounded-md border border-border-subtle bg-surface-raised p-5">
        <h2 className="text-lg font-medium text-text">Open data</h2>
        <p className="text-md leading-relaxed text-text-muted">
          The AT-100 design project is published as an open{" "}
          <code className="rounded-sm bg-surface-subtle px-1 font-mono text-sm">
            .cascade.toml
          </code>{" "}
          file. Download it and open it in any Cascade workspace to
          reproduce the design study or extend it for your own machine.
        </p>
        <div className="flex items-center gap-4">
          <a
            href="/data/at-100-microturbine.cascade.toml"
            download="at-100-microturbine.cascade.toml"
            className="inline-flex h-9 items-center gap-2 rounded-sm border border-brand bg-brand px-4 text-sm font-medium text-text-inverse transition-colors duration-fast hover:bg-brand-hover"
            aria-label="Download AT-100 project file"
          >
            <Download className="h-3.5 w-3.5" />
            Download AT-100 project file
          </a>
          <Link
            href="/projects"
            className="inline-flex items-center gap-1 text-sm text-brand-text hover:underline"
          >
            Open in workspace
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
        <p className="text-xs text-text-muted">
          File format: Cascade v1 TOML. Compatible with Cascade v0.1.0+.
          License: CC-BY 4.0 (design data), AGPL-3.0 (solver).
        </p>
      </section>

      {/* Hardware status — AC3: must mention "design phase complete" */}
      <section className="flex flex-col gap-3 rounded-md border border-semantic-warning-border bg-semantic-warning-surface p-5">
        <h2 className="text-lg font-medium text-text">Hardware status</h2>
        <p className="text-md leading-relaxed text-text-muted">
          <strong className="text-text">v1 (current):</strong> Design phase
          complete. Preliminary design review (PDR) concluded
          2026-Q1. Combustor can and impeller drawings released for
          manufacturing. Bench testing scheduled for Q3 2026. Full case
          study with measured performance data follows ship.
        </p>
        <p className="text-sm leading-relaxed text-text-muted">
          All metrics on this page are targets from the validated cycle
          deck. Measured data will replace them when available. If you are
          evaluating Cascade for a similar machine and want to discuss the
          methodology, email{" "}
          <a
            href="mailto:engineering@americanturbines.com"
            className="text-brand-text underline-offset-4 hover:underline"
          >
            engineering@americanturbines.com
          </a>
          .
        </p>
      </section>

      {/* Related links */}
      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-medium text-text">Related</h2>
        <ul className="flex flex-col gap-2 text-md">
          <li>
            <Link
              href="/learn/9-the-workflow"
              className="text-brand-text underline-offset-4 hover:underline"
            >
              Chapter 9: The Cascade workflow — cycle to CAD
            </Link>
          </li>
          <li>
            <Link
              href="/docs/validation"
              className="text-brand-text underline-offset-4 hover:underline"
            >
              Validation report — 171 tests against published data
            </Link>
          </li>
          <li>
            <Link
              href="/projects"
              className="text-brand-text underline-offset-4 hover:underline"
            >
              Demo projects — Capstone C30 and radial turbine design
            </Link>
          </li>
        </ul>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface MetricCardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  note: string;
}

function MetricCard({ icon, label, value, note }: MetricCardProps) {
  return (
    <div className="flex flex-col gap-1.5 rounded-md border border-border-subtle bg-surface-raised p-4">
      <div className="flex items-center gap-1.5 text-text-muted">{icon}</div>
      <p className="text-xl font-semibold text-text">{value}</p>
      <p className="text-xs font-medium text-text">{label}</p>
      <p className="text-xs text-text-muted">{note}</p>
    </div>
  );
}

interface MethodCardProps {
  step: string;
  title: string;
  description: string;
  href: string;
}

function MethodCard({ step, title, description, href }: MethodCardProps) {
  return (
    <div className="flex flex-col gap-2 rounded-md border border-border-subtle bg-surface-raised p-4">
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs text-text-muted">{step}</span>
        <h3 className="text-md font-medium text-text">{title}</h3>
      </div>
      <p className="text-sm leading-relaxed text-text-muted">{description}</p>
      <Link
        href={href}
        className="mt-auto inline-flex items-center gap-1 text-sm text-brand-text hover:underline"
      >
        Open in Cascade
        <ArrowRight className="h-3.5 w-3.5" />
      </Link>
    </div>
  );
}
