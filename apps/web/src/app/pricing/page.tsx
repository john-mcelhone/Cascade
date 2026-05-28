import Link from "next/link";
import { Fragment } from "react";
import type { Metadata } from "next";
import { ArrowRight, Check, Github, Minus, Wrench } from "lucide-react";
import { Logo } from "@/components/shell/logo";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

/**
 * Static /pricing page (ADAPT-016). Three transparent tiers; honest about what's
 * shipping today vs. planned. Stripe checkout lands in Q4 2026 — until then every
 * CTA either routes to the workspace or to a mailto:. Matches the marketing-light
 * shell used by /. Linked from the landing nav and footer.
 */

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Cascade pricing — three transparent tiers. Free for solo engineers, Team for small groups, Enterprise for on-prem and SSO.",
};

type IncludedFeature = { text: string; note?: string; eta?: string };
type ExcludedFeature = { text: string; eta?: string };

interface Tier {
  name: string;
  price: string;
  cadence?: string;
  blurb: string;
  cta: { label: string; href: string };
  highlight?: boolean;
  badge?: string;
  included: IncludedFeature[];
  excluded?: ExcludedFeature[];
}

const TIERS: Tier[] = [
  {
    name: "Free",
    price: "$0",
    cadence: "/ user / month",
    blurb:
      "Everything you need to run a real design study on a single laptop, with no time limit.",
    cta: { label: "Open the workspace", href: "/projects" },
    included: [
      { text: "Full Flow Path PD page (centrifugal compressor + radial turbine)" },
      { text: "Full Cycle Canvas" },
      { text: "Local geometry (glTF) viewing" },
      { text: "Performance Map (single-machine sweep)" },
      { text: "Up to 3 projects" },
      { text: "Single user, no collaboration" },
    ],
    excluded: [
      { text: "Real-time collaboration", eta: "planned v1.1" },
      { text: "Materials database", eta: "planned v1.1" },
      { text: "API access" },
    ],
  },
  {
    name: "Team",
    price: "$129",
    cadence: "/ user / month, billed annually",
    blurb:
      "For small engineering teams shipping production hardware. Adds rotor dynamics, exports, and shared workspaces.",
    cta: {
      label: "Get Team",
      href:
        "mailto:sales@americanturbines.com" +
        "?subject=Cascade%20Team%20Tier%20Inquiry" +
        "&body=Hi%20American%20Turbines%2C%0A%0AI%27d%20like%20to%20start%20a%20Cascade%20Team%20subscription.%0A%0ATeam%20size%3A%20%5Byour%20answer%5D%0AUse%20case%3A%20%5Byour%20answer%5D%0ATimeline%3A%20%5Byour%20answer%5D%0A%0ABest%2C%0A%5Byour%20name%5D",
    },
    highlight: true,
    badge: "Most teams pick this",
    included: [
      { text: "Everything in Free" },
      { text: "Unlimited projects" },
      { text: "Rotor Dynamics page with API 617 compliance reports" },
      { text: "Export to glTF, STL, and STEP", note: "STEP requires cascade[cad] extra" },
      { text: "Team workspace — same files, separate sessions" },
      { text: "Real-time co-editing", eta: "Q4 2026" },
      {
        text: "Email support",
        note: "Slack workspace invite: email community@americanturbines.com",
      },
    ],
  },
  {
    name: "Enterprise",
    price: "Contact us",
    blurb:
      "For organisations that need to deploy on their own infrastructure, integrate with corporate SSO, or extend the loss-model library.",
    cta: {
      label: "Get Enterprise",
      href:
        "mailto:sales@americanturbines.com" +
        "?subject=Cascade%20Enterprise%20Inquiry" +
        "&body=Hi%20American%20Turbines%2C%0A%0AI%27d%20like%20to%20discuss%20a%20Cascade%20Enterprise%20subscription.%0A%0ATeam%20size%3A%20%5Byour%20answer%5D%0AUse%20case%3A%20%5Byour%20answer%5D%0ATimeline%3A%20%5Byour%20answer%5D%0AOn-prem%20required%3A%20%5Byes%20%2F%20no%5D%0A%0ABest%2C%0A%5Byour%20name%5D",
    },
    included: [
      { text: "Everything in Team" },
      { text: "On-prem deployment option" },
      { text: "SSO (SAML / OIDC)" },
      { text: "Custom loss-model plug-ins via Python API" },
      { text: "Dedicated solver capacity" },
      { text: "Phone support with 4-hour response SLA" },
      {
        text: "Commercial license exception to AGPL-3.0 copyleft requirements",
        note: "modify and self-host without source-publication obligation",
      },
      { text: "Annual contract; volume pricing" },
    ],
  },
];

// Side-by-side comparison row data. `true` = included, `false` = excluded,
// string = qualified inclusion.
type ComparisonRow = {
  feature: string;
  free: boolean | string;
  team: boolean | string;
  enterprise: boolean | string;
};

const COMPARISON: { group: string; rows: ComparisonRow[] }[] = [
  {
    group: "Design",
    rows: [
      { feature: "Flow Path PD (compressor + turbine)", free: true, team: true, enterprise: true },
      { feature: "Cycle Canvas", free: true, team: true, enterprise: true },
      { feature: "Analysis page (loss breakdown)", free: true, team: true, enterprise: true },
      { feature: "Performance Map", free: true, team: true, enterprise: true },
      { feature: "Rotor Dynamics + API 617 reports", free: false, team: true, enterprise: true },
      { feature: "Custom loss-model plug-ins", free: false, team: false, enterprise: true },
    ],
  },
  {
    group: "Projects & exports",
    rows: [
      { feature: "Projects", free: "Up to 3", team: "Unlimited", enterprise: "Unlimited" },
      { feature: "glTF / STL export", free: "View only", team: true, enterprise: true },
      { feature: "STEP export", free: false, team: "cascade[cad] extra", enterprise: "cascade[cad] extra" },
    ],
  },
  {
    group: "Collaboration & support",
    rows: [
      { feature: "Single-user", free: true, team: true, enterprise: true },
      { feature: "Team workspace (shared files)", free: false, team: true, enterprise: true },
      { feature: "Real-time co-editing", free: false, team: "Q4 2026", enterprise: "Q4 2026" },
      { feature: "SSO (SAML / OIDC)", free: false, team: false, enterprise: true },
      { feature: "On-prem deployment", free: false, team: false, enterprise: true },
      { feature: "Support channel", free: "Community", team: "Email + Slack", enterprise: "Phone + 4-hr SLA" },
    ],
  },
];

const FAQ: { q: string; a: React.ReactNode }[] = [
  {
    q: "Why is the Free tier this generous?",
    a: (
      <>
        Because we&rsquo;d rather you build a real radial-turbine wheel on the free
        plan, prove the workflow, and then upgrade when you need rotor dynamics
        and STEP export. The Flow Path PD and Cycle Canvas pages are the same
        code on every tier — there&rsquo;s no crippled solver.
      </>
    ),
  },
  {
    q: "Can I pay monthly on Team?",
    a: (
      <>
        Not yet. Stripe checkout lands in Q4 2026, with monthly billing at a 15%
        premium. Until then, Team is invoiced annually — email{" "}
        <a
          className="text-brand-text underline-offset-4 hover:underline"
          href="mailto:sales@americanturbines.com"
        >
          sales@americanturbines.com
        </a>
        .
      </>
    ),
  },
  {
    q: "What does “cascade[cad] extra” mean?",
    a: (
      <>
        STEP export depends on a CAD kernel (OpenCASCADE) that isn&rsquo;t
        installed by default to keep the base install slim. Run{" "}
        <code className="rounded-sm bg-surface-subtle px-1 font-mono">
          pip install &quot;cascade[cad]&quot;
        </code>{" "}
        once and it just works.
      </>
    ),
  },
  {
    q: "Do you offer academic pricing?",
    a: (
      <>
        Yes. Free is free for academic use, and Team is 70% off for accredited
        institutions and degree-seeking students. Email us from your{" "}
        <code className="font-mono">.edu</code> address.
      </>
    ),
  },
  {
    q: "Can I self-host?",
    a: (
      <>
        Self-hosting is an Enterprise feature. The entire Cascade codebase —
        solver core and web app — is licensed under{" "}
        <strong>AGPL-3.0</strong> (GNU Affero General Public License v3.0).
        In plain English: if you modify Cascade and run it as a service for
        others over a network, you must publish your modifications. If you use
        it internally for your own engineering work, no publishing requirement
        applies. Enterprise contracts include a{" "}
        <strong>commercial license exception to AGPL-3.0 copyleft
        requirements</strong>, so you can deploy and modify Cascade on your own
        infrastructure without the source-publication obligation. See our{" "}
        <Link href="/terms" className="text-brand-text underline-offset-4 hover:underline">
          Terms of Service
        </Link>{" "}
        or email{" "}
        <a
          href="mailto:sales@americanturbines.com"
          className="text-brand-text underline-offset-4 hover:underline"
        >
          sales@americanturbines.com
        </a>{" "}
        for Enterprise licensing details.
      </>
    ),
  },
  {
    q: "Will my project files be locked in?",
    a: (
      <>
        No. Cascade projects are folders of TOML files, scripts, and a lockfile
        — diffable, scriptable, git-trackable. The solver core runs without the
        web app. If you cancel, your projects keep working.
      </>
    ),
  },
];

export default function PricingPage() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-text">
      <header className="flex h-topbar items-center justify-between border-b border-border-subtle px-5">
        <Link href="/" aria-label="Cascade home">
          <Logo />
        </Link>
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
          <Link href="/pricing" className="font-medium text-text">
            Pricing
          </Link>
          <Link href="/projects">
            <Button size="sm">Open the workspace</Button>
          </Link>
        </nav>
      </header>

      <main className="flex flex-1 flex-col">
        <section className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-5 py-8">
          <p className="text-sm font-medium uppercase tracking-wide text-brand-text">
            Pricing
          </p>
          <h1 className="max-w-3xl text-xl font-medium leading-tight tracking-tight text-text sm:text-2xl">
            Engineering software priced like engineering software, not enterprise.
          </h1>
          <p className="max-w-2xl text-md text-text-muted">
            Three tiers. No per-seat solver-run quotas. No gated loss models. No
            sales call required to find out what it costs. Free is real work,
            not a 14-day trial.
          </p>
          <p className="max-w-2xl text-md text-text-muted">
            Stripe checkout lands in Q4 2026; until then, Team and Enterprise
            are invoiced directly. Every plan ships the same solver core.
          </p>
        </section>

        <section className="mx-auto w-full max-w-5xl px-5 pb-8">
          <div className="grid gap-4 sm:grid-cols-3">
            {TIERS.map((tier) => (
              <TierCard key={tier.name} tier={tier} />
            ))}
          </div>
        </section>

        <section className="mx-auto w-full max-w-5xl px-5 pb-8">
          <h2 className="mb-3 text-md font-medium text-text">
            What&rsquo;s in each tier
          </h2>
          <ComparisonTable />
        </section>

        <section className="mx-auto w-full max-w-5xl px-5 pb-8">
          <h2 className="mb-3 text-md font-medium text-text">
            Frequently asked
          </h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {FAQ.map((item) => (
              <div
                key={item.q}
                className="rounded-md border border-border-subtle bg-surface-raised p-4"
              >
                <h3 className="text-md font-medium text-text">{item.q}</h3>
                <p className="mt-2 text-sm text-text-muted">{item.a}</p>
              </div>
            ))}
          </div>
        </section>

        {/* W-24: Services / consulting line */}
        <section className="mx-auto w-full max-w-5xl px-5 pb-8">
          <div className="flex flex-col gap-3 rounded-md border border-border-subtle bg-surface-raised p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <Wrench className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" aria-hidden />
              <div>
                <h3 className="text-md font-medium text-text">
                  Need a full design review or consulting engagement?
                </h3>
                <p className="mt-1 text-sm text-text-muted">
                  American Turbines provides paid design services for customers
                  who need expert turbomachinery review beyond what the software
                  alone provides — cycle analysis, meanline trade studies, rotor-
                  dynamics assessment, and hardware-readiness reviews.
                </p>
              </div>
            </div>
            <div className="shrink-0">
              <a href="mailto:services@americanturbines.com?subject=Cascade%20Design%20Services%20Inquiry">
                <Button size="lg" variant="outline" className="whitespace-nowrap">
                  Email services
                </Button>
              </a>
            </div>
          </div>
        </section>

        {/* W-07: Stripe timeline note + Still deciding */}
        <section className="mx-auto w-full max-w-5xl px-5 pb-8">
          <p className="mb-4 text-center text-sm text-text-muted">
            Self-serve Stripe checkout: Q4 2026. Until then, email-based
            onboarding ensures the right tier and pricing fit for your team.
          </p>
          <div className="flex flex-col items-start gap-3 rounded-md border border-border-subtle bg-surface-raised p-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="text-md font-medium text-text">
                Still deciding?
              </h3>
              <p className="mt-1 text-sm text-text-muted">
                Open the workspace and run a sweep — no signup, no credit card.
                You&rsquo;ll know in four minutes whether Cascade fits your team.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link href="/projects">
                <Button size="lg" className="gap-2">
                  Open the workspace
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              <a href="mailto:sales@americanturbines.com?subject=Cascade%20pricing%20question">
                <Button size="lg" variant="outline">
                  Email sales
                </Button>
              </a>
            </div>
          </div>
        </section>

        <footer className="mt-auto border-t border-border-subtle">
          <div className="mx-auto flex w-full max-w-5xl flex-col items-center justify-between gap-3 px-5 py-4 text-sm text-text-muted sm:flex-row">
            <span>© 2026 American Turbines</span>
            <div className="flex flex-wrap items-center gap-4">
              <Link href="/pricing" className="font-medium text-text">
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

function TierCard({ tier }: { tier: Tier }) {
  const ctaIsMail = tier.cta.href.startsWith("mailto:");
  return (
    <div
      className={
        "flex flex-col rounded-md border bg-surface-raised p-4 " +
        (tier.highlight
          ? "border-brand/40 ring-1 ring-brand/30"
          : "border-border-subtle")
      }
    >
      <div className="flex items-baseline justify-between">
        <h3 className="text-md font-medium text-text">{tier.name}</h3>
        {tier.badge ? (
          <Badge variant="brand">{tier.badge}</Badge>
        ) : null}
      </div>
      <div className="mt-3 flex items-baseline gap-1">
        <span className="text-2xl font-medium tabular-nums text-text">
          {tier.price}
        </span>
        {tier.cadence ? (
          <span className="text-sm text-text-muted">{tier.cadence}</span>
        ) : null}
      </div>
      <p className="mt-2 text-sm text-text-muted">{tier.blurb}</p>

      <ul className="mt-4 flex flex-col gap-2 text-sm">
        {tier.included.map((feat) => (
          <li key={feat.text} className="flex gap-2">
            <Check
              className="mt-0.5 h-3.5 w-3.5 shrink-0 text-semantic-success"
              aria-hidden
            />
            <span className="text-text">
              {feat.text}
              {feat.note ? (
                <span className="ml-1 text-text-muted">— {feat.note}</span>
              ) : null}
              {feat.eta ? (
                <span className="ml-1 text-text-muted">({feat.eta})</span>
              ) : null}
            </span>
          </li>
        ))}
      </ul>

      {tier.excluded && tier.excluded.length > 0 ? (
        <ul className="mt-3 flex flex-col gap-2 border-t border-border-subtle pt-3 text-sm">
          {tier.excluded.map((feat) => (
            <li key={feat.text} className="flex gap-2 text-text-muted">
              <Minus
                className="mt-0.5 h-3.5 w-3.5 shrink-0"
                aria-hidden
              />
              <span>
                {feat.text}
                {feat.eta ? (
                  <span className="ml-1 text-text-muted">({feat.eta})</span>
                ) : null}
              </span>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="mt-auto pt-4">
        {ctaIsMail ? (
          <a href={tier.cta.href} className="block">
            <Button
              size="lg"
              variant={tier.highlight ? "default" : "outline"}
              className="w-full"
            >
              {tier.cta.label}
            </Button>
          </a>
        ) : (
          <Link href={tier.cta.href} className="block">
            <Button
              size="lg"
              variant={tier.highlight ? "default" : "outline"}
              className="w-full"
            >
              {tier.cta.label}
            </Button>
          </Link>
        )}
      </div>
    </div>
  );
}

function ComparisonTable() {
  return (
    <div className="overflow-x-auto rounded-md border border-border-subtle bg-surface-raised">
      <table className="w-full text-sm">
        <thead className="border-b border-border-subtle bg-surface-subtle text-left">
          <tr>
            <th className="px-3 py-2 font-medium text-text">Feature</th>
            <th className="px-3 py-2 font-medium text-text">Free</th>
            <th className="px-3 py-2 font-medium text-text">Team</th>
            <th className="px-3 py-2 font-medium text-text">Enterprise</th>
          </tr>
        </thead>
        <tbody>
          {COMPARISON.map((group) => (
            <Fragment key={group.group}>
              <tr>
                <th
                  scope="colgroup"
                  colSpan={4}
                  className="bg-surface-subtle/40 px-3 py-1.5 text-left text-xs font-medium uppercase tracking-wide text-text-muted"
                >
                  {group.group}
                </th>
              </tr>
              {group.rows.map((row) => (
                <tr
                  key={row.feature}
                  className="border-t border-border-subtle/60"
                >
                  <td className="px-3 py-2 text-text">{row.feature}</td>
                  <td className="px-3 py-2">{renderCell(row.free)}</td>
                  <td className="px-3 py-2">{renderCell(row.team)}</td>
                  <td className="px-3 py-2">{renderCell(row.enterprise)}</td>
                </tr>
              ))}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function renderCell(value: boolean | string) {
  if (value === true) {
    return (
      <span className="inline-flex items-center gap-1 text-semantic-success">
        <Check className="h-3.5 w-3.5" aria-hidden />
        <span className="sr-only">Included</span>
      </span>
    );
  }
  if (value === false) {
    return (
      <span className="inline-flex items-center gap-1 text-text-disabled">
        <Minus className="h-3.5 w-3.5" aria-hidden />
        <span className="sr-only">Not included</span>
      </span>
    );
  }
  return <span className="text-text-muted">{value}</span>;
}
