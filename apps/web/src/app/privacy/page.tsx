import Link from "next/link";
import { AlertTriangle, Github } from "lucide-react";
import { Logo } from "@/components/shell/logo";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description:
    "Cascade Privacy Policy — how American Turbines collects, uses, and protects your data.",
};

/**
 * /privacy — Privacy Policy for Cascade.
 *
 * v1 boilerplate for procurement review. Plain-English engineering audience.
 * Contact: privacy@americanturbines.com
 *
 * IMPORTANT: This is v1 under active counsel review. Final GDPR/CCPA
 * compliance language and DPA terms will follow legal review.
 */
export default function PrivacyPage() {
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
        </nav>
      </header>

      <main className="flex flex-1 flex-col">
        <div className="mx-auto w-full max-w-3xl px-5 py-8">
          {/* v1 counsel-review banner */}
          <div className="mb-6 flex items-start gap-3 rounded-md border border-amber-500/40 bg-amber-500/10 p-4 text-sm">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" aria-hidden />
            <p className="text-text-muted">
              <strong className="text-text">v1 — under review by counsel.</strong>{" "}
              This document is a working draft. Final GDPR/CCPA compliance
              language, data processing agreements, and sub-processor disclosures
              will follow legal review. Last updated: 2026-05-26.
            </p>
          </div>

          <h1 className="mb-1 text-xl font-medium text-text">Privacy Policy</h1>
          <p className="mb-8 text-sm text-text-muted">
            Effective date: 2026-05-26 &nbsp;·&nbsp; American Turbines, Inc.
          </p>

          <Section title="1. Who we are">
            <p>
              American Turbines, Inc. (&ldquo;American Turbines,&rdquo;
              &ldquo;we,&rdquo; &ldquo;us,&rdquo; &ldquo;our&rdquo;) operates
              the Cascade turbomachinery design environment (the
              &ldquo;Service&rdquo;). This Privacy Policy explains what data we
              collect when you use the Service, how we use it, and your rights
              over that data.
            </p>
            <p>
              Questions? Email{" "}
              <a
                href="mailto:privacy@americanturbines.com"
                className="text-brand-text underline-offset-4 hover:underline"
              >
                privacy@americanturbines.com
              </a>
              .
            </p>
          </Section>

          <Section title="2. What data we collect">
            <p>
              <strong>Account data:</strong> If you create an account, we collect
              your email address and any display name you provide. No payment
              information is handled directly by Cascade — payments are processed
              by Stripe (see Section 6).
            </p>
            <p>
              <strong>Project files:</strong> Your Cascade project files (TOML
              files, scripts, lockfiles) are stored in your own infrastructure
              or, for cloud-hosted accounts, on our servers. We treat project
              files as confidential engineering data and do not read, analyze,
              or share them except to operate the Service for you.
            </p>
            <p>
              <strong>Usage telemetry:</strong> We collect anonymized usage
              events (e.g., which pages are visited, which solver features are
              used, session duration) to understand how engineers use Cascade and
              improve the product. Telemetry does not include your project data,
              solver inputs, or design parameters. You can opt out of telemetry
              in your account settings.
            </p>
            <p>
              <strong>Support communications:</strong> If you contact us via
              email or Slack, we retain those communications to resolve your
              issue and improve the Service.
            </p>
            <p>
              <strong>Log data:</strong> Our servers record standard web server
              logs: IP addresses, browser type, pages visited, timestamps, and
              HTTP status codes. Logs are retained for 90 days and used
              exclusively for security and operations.
            </p>
          </Section>

          <Section title="3. How we use your data">
            <p>We use the data we collect to:</p>
            <ul className="list-disc pl-5 space-y-1">
              <li>Provide, operate, and improve the Service.</li>
              <li>Send you transactional emails (account confirmation, password reset, billing).</li>
              <li>Respond to support requests and resolve incidents.</li>
              <li>
                Understand aggregate usage patterns to prioritize product
                development (using anonymized telemetry only).
              </li>
              <li>Comply with applicable law or respond to lawful legal process.</li>
            </ul>
            <p>
              We do <strong>not</strong> sell your personal data. We do not use
              your project files or design data to train machine-learning models.
            </p>
          </Section>

          <Section title="4. Your rights">
            <p>You have the right to:</p>
            <ul className="list-disc pl-5 space-y-1">
              <li>
                <strong>Access:</strong> Request a copy of the personal data we
                hold about you.
              </li>
              <li>
                <strong>Correction:</strong> Ask us to correct inaccurate data.
              </li>
              <li>
                <strong>Deletion:</strong> Request deletion of your account and
                associated personal data. Project files hosted on our servers will
                be deleted within 30 days of an account deletion request. Note:
                project files stored in your own infrastructure are not affected.
              </li>
              <li>
                <strong>Export:</strong> Export your project files at any time
                directly from the workspace — projects are plain TOML directories.
                No lock-in.
              </li>
              <li>
                <strong>Opt-out of telemetry:</strong> Disable anonymized usage
                telemetry in your account settings at any time.
              </li>
            </ul>
            <p>
              To exercise any of these rights, email{" "}
              <a
                href="mailto:privacy@americanturbines.com"
                className="text-brand-text underline-offset-4 hover:underline"
              >
                privacy@americanturbines.com
              </a>
              . We will respond within 30 days.
            </p>
          </Section>

          <Section title="5. Data retention">
            <p>
              We retain account data for the life of your account and for up to
              90 days after deletion. Usage telemetry is retained in anonymized
              aggregate form indefinitely. Server logs are retained for 90 days.
              Support communications are retained for 3 years.
            </p>
          </Section>

          <Section title="6. Third-party processors">
            <p>
              We use a limited set of third-party sub-processors to operate the
              Service:
            </p>
            <ul className="list-disc pl-5 space-y-1">
              <li>
                <strong>Stripe</strong> — payment processing for Team and
                Enterprise subscriptions. Stripe handles all payment card data.
                We never see or store payment card numbers. Stripe&rsquo;s
                privacy policy:{" "}
                <a
                  href="https://stripe.com/privacy"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-brand-text underline-offset-4 hover:underline"
                >
                  stripe.com/privacy
                </a>
                .
              </li>
              <li>
                <strong>Cloud hosting provider</strong> — server infrastructure
                for the web app and API. Data is hosted in the United States.
                Enterprise customers requiring EU or specific-region hosting
                should contact us.
              </li>
            </ul>
            <p>
              We do not share personal data with third parties for their own
              marketing or advertising purposes.
            </p>
          </Section>

          <Section title="7. Security">
            <p>
              We implement reasonable technical and organizational measures to
              protect your data, including TLS encryption in transit, encrypted
              storage for project files, and access controls limiting who at
              American Turbines can access user data.
            </p>
            <p>
              No system is perfectly secure. If you believe your account has been
              compromised, contact{" "}
              <a
                href="mailto:security@americanturbines.com"
                className="text-brand-text underline-offset-4 hover:underline"
              >
                security@americanturbines.com
              </a>{" "}
              immediately.
            </p>
          </Section>

          <Section title="8. International transfers">
            <p>
              Cascade is operated from the United States. If you access the Service
              from outside the US, your data may be transferred to and processed in
              the US. For Enterprise customers in the EU/EEA, we can provide a Data
              Processing Agreement (DPA) covering Standard Contractual Clauses.
              Contact{" "}
              <a
                href="mailto:privacy@americanturbines.com"
                className="text-brand-text underline-offset-4 hover:underline"
              >
                privacy@americanturbines.com
              </a>
              .
            </p>
          </Section>

          <Section title="9. Changes to this policy">
            <p>
              We may update this Privacy Policy from time to time. We will post
              the updated policy at{" "}
              <Link
                href="/privacy"
                className="text-brand-text underline-offset-4 hover:underline"
              >
                cascade.app/privacy
              </Link>{" "}
              and, for material changes affecting Team and Enterprise subscribers,
              provide 14 days&rsquo; notice by email before changes take effect.
            </p>
          </Section>

          <Section title="10. Contact">
            <p>
              Privacy questions or data requests:{" "}
              <a
                href="mailto:privacy@americanturbines.com"
                className="text-brand-text underline-offset-4 hover:underline"
              >
                privacy@americanturbines.com
              </a>
            </p>
            <p className="text-text-muted">
              American Turbines, Inc. &nbsp;·&nbsp; privacy@americanturbines.com
            </p>
          </Section>
        </div>
      </main>

      <footer className="mt-auto border-t border-border-subtle">
        <div className="mx-auto flex w-full max-w-5xl flex-col items-center justify-between gap-3 px-5 py-4 text-sm text-text-muted sm:flex-row">
          <span>© 2026 American Turbines</span>
          <div className="flex items-center gap-4">
            <Link href="/terms" className="hover:text-text">
              Terms
            </Link>
            <Link href="/privacy" className="font-medium text-text">
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
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-8">
      <h2 className="mb-3 text-md font-medium text-text">{title}</h2>
      <div className="space-y-3 text-sm text-text-muted leading-relaxed">
        {children}
      </div>
    </section>
  );
}
