import Link from "next/link";
import { AlertTriangle, Github } from "lucide-react";
import { Logo } from "@/components/shell/logo";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms of Service",
  description:
    "Cascade Terms of Service — governing terms for use of American Turbines' Cascade turbomachinery design environment.",
};

/**
 * /terms — Terms of Service for Cascade.
 *
 * v1 boilerplate for procurement review. Plain-English engineering audience.
 * Governing law: Delaware (standard US SaaS default).
 * Contact: legal@americanturbines.com
 *
 * IMPORTANT: This is v1 under active counsel review. Substantive terms,
 * liability limits, and indemnification language will be updated after
 * legal review. Do not rely on this draft as final legal advice.
 */
export default function TermsPage() {
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
              This document is a working draft. Substantive updates — including
              final indemnification, dispute-resolution, and liability-cap
              language — will follow legal review. Last updated: 2026-05-26.
            </p>
          </div>

          <h1 className="mb-1 text-xl font-medium text-text">Terms of Service</h1>
          <p className="mb-8 text-sm text-text-muted">
            Effective date: 2026-05-26 &nbsp;·&nbsp; American Turbines, Inc.
          </p>

          <Section title="1. Acceptance of terms">
            <p>
              By accessing or using Cascade (the &ldquo;Service&rdquo;), you agree
              to be bound by these Terms of Service (&ldquo;Terms&rdquo;). If you
              are using the Service on behalf of an organization, you represent
              that you have authority to bind that organization to these Terms.
            </p>
            <p>
              If you do not agree to these Terms, do not use the Service.
            </p>
          </Section>

          <Section title="2. Description of service">
            <p>
              Cascade is a web-native turbomachinery design environment for
              preliminary design of turbines, compressors, and turbomachinery
              systems. The Service provides cycle simulation, mean-line
              aerodynamic analysis, performance mapping, rotor-dynamics
              calculations, and related tooling.
            </p>
            <p>
              Cascade is a <strong>preliminary-design tool</strong>. It produces
              engineering estimates useful for design-space exploration and
              trade studies. It is not a certified analysis tool for final design
              validation, and output should not be used as the sole basis for
              safety-critical hardware decisions without independent validation
              by a qualified engineer.
            </p>
          </Section>

          <Section title="3. User responsibilities">
            <p>You agree to:</p>
            <ul className="list-disc pl-5 space-y-1">
              <li>
                Use the Service only for lawful purposes and in accordance with
                these Terms.
              </li>
              <li>
                Apply <strong>independent engineering judgment</strong> to all
                output produced by the Service. Cascade is a design-aid, not a
                substitute for qualified engineering review.
              </li>
              <li>
                Validate all design outputs against applicable industry standards,
                regulatory requirements, and test data before committing to
                manufacturing or field deployment.
              </li>
              <li>
                Not attempt to reverse-engineer, decompile, or circumvent the
                Service beyond what is permitted under the applicable open-source
                license (see Section 7).
              </li>
              <li>
                Keep your account credentials confidential and notify American
                Turbines promptly of any unauthorized use.
              </li>
            </ul>
          </Section>

          <Section title="4. Limitation of liability and warranty disclaimer">
            <div className="rounded-md border border-border-default bg-surface-subtle p-4 text-sm space-y-3">
              <p>
                <strong>THE SERVICE IS PROVIDED &ldquo;AS IS&rdquo; AND
                &ldquo;AS AVAILABLE&rdquo; WITHOUT WARRANTY OF ANY KIND,
                EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO WARRANTIES
                OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE,
                TITLE, OR NON-INFRINGEMENT.</strong>
              </p>
              <p>
                American Turbines does not warrant that: (a) the Service will
                meet your specific engineering or business requirements; (b) the
                Service will be uninterrupted, timely, secure, or error-free;
                (c) the results obtained from using the Service will be accurate
                or reliable; or (d) any errors in the Service will be corrected.
              </p>
              <p>
                <strong>
                  CASCADE IS NOT CERTIFIED FOR, AND MUST NOT BE USED AS THE
                  SOLE BASIS FOR, FLIGHT-SAFETY-CRITICAL APPLICATIONS,
                  MANNED AIRCRAFT DESIGN, OR ANY APPLICATION WHERE FAILURE
                  COULD RESULT IN LOSS OF LIFE WITHOUT INDEPENDENT VALIDATION
                  BY A QUALIFIED ENGINEER AND COMPLIANCE WITH ALL APPLICABLE
                  AIRWORTHINESS OR SAFETY STANDARDS.
                </strong>
              </p>
              <p>
                TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, IN NO
                EVENT SHALL AMERICAN TURBINES BE LIABLE FOR ANY INDIRECT,
                INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
                (INCLUDING LOSS OF PROFITS, DATA, BUSINESS INTERRUPTION, OR
                COST OF SUBSTITUTE GOODS OR SERVICES) ARISING OUT OF OR IN
                CONNECTION WITH YOUR USE OF THE SERVICE, EVEN IF AMERICAN
                TURBINES HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.
                AMERICAN TURBINES&rsquo; TOTAL CUMULATIVE LIABILITY SHALL NOT
                EXCEED THE FEES PAID BY YOU TO AMERICAN TURBINES IN THE TWELVE
                MONTHS PRECEDING THE CLAIM.
              </p>
            </div>
            <p className="mt-3 text-sm text-text-muted">
              Some jurisdictions do not allow the exclusion of implied warranties
              or limitation of liability; in such jurisdictions the above
              limitations apply to the maximum extent permitted by law.
            </p>
          </Section>

          <Section title="5. Intellectual property">
            <p>
              <strong>Your project data:</strong> You own your project files,
              design inputs, and results. Cascade projects are stored as TOML
              text files that you control. American Turbines does not claim
              ownership over the engineering content you create using the Service.
            </p>
            <p>
              <strong>The software:</strong> Cascade is licensed under the GNU
              Affero General Public License v3.0 (AGPL-3.0). The source code is
              available at{" "}
              <a
                href="https://github.com/americanturbines/cascade"
                target="_blank"
                rel="noopener noreferrer"
                className="text-brand-text underline-offset-4 hover:underline"
              >
                github.com/americanturbines/cascade
              </a>
              . American Turbines retains copyright over the Cascade codebase.
              The Cascade Python SDK is dual-licensed MIT for permissive downstream use.
            </p>
            <p>
              <strong>AGPL-3.0 in plain English:</strong> If you run the Service
              on your own servers and provide access to users over a network, and
              you have modified the Cascade source code, you must publish those
              modifications under AGPL-3.0. If you use Cascade internally for
              your own engineering work without providing network access to
              others, no source-publishing requirement applies to you. Enterprise
              contracts include a commercial license exception to these copyleft
              requirements — see Section 7 or contact us for details.
            </p>
            <p>
              &ldquo;Cascade,&rdquo; the Cascade logo, and &ldquo;American
              Turbines&rdquo; are trademarks of American Turbines, Inc. You may
              not use them without prior written permission.
            </p>
          </Section>

          <Section title="6. Termination">
            <p>
              Either party may terminate your use of the Service at any time.
              American Turbines may suspend or terminate your access if you
              violate these Terms or if required by law. Upon termination, your
              right to use the Service ceases, but your existing project files
              (which are stored locally or in your own infrastructure) remain
              accessible to you.
            </p>
            <p>
              Sections 3 (User responsibilities), 4 (Limitation of liability),
              5 (Intellectual property), 8 (Governing law), and 9 (Dispute
              resolution) survive termination.
            </p>
          </Section>

          <Section title="7. License tiers and commercial use">
            <p>
              <strong>Free and Team tiers</strong> are governed by AGPL-3.0.
              Use the Service for internal engineering work; publish modifications
              if you host a modified version for others.
            </p>
            <p>
              <strong>Enterprise contracts</strong> include a commercial license
              exception to AGPL-3.0 copyleft requirements. Under an Enterprise
              contract, you may deploy Cascade on your own infrastructure, modify
              the source, and provide access to your organization&rsquo;s users
              without the AGPL-3.0 network-use source-publication obligation.
              Enterprise terms are negotiated individually; contact{" "}
              <a
                href="mailto:sales@americanturbines.com"
                className="text-brand-text underline-offset-4 hover:underline"
              >
                sales@americanturbines.com
              </a>
              .
            </p>
          </Section>

          <Section title="8. Governing law">
            <p>
              These Terms are governed by the laws of the State of Delaware,
              United States, without regard to conflict-of-law principles. This
              is the standard SaaS governing law choice; if your organization
              requires a different jurisdiction, Enterprise contracts can be
              negotiated accordingly.
            </p>
          </Section>

          <Section title="9. Dispute resolution">
            <p>
              Any dispute arising out of or relating to these Terms shall first
              be addressed through good-faith negotiation. If unresolved after
              30 days, disputes shall be submitted to binding arbitration under
              the rules of the American Arbitration Association, with proceedings
              conducted in Delaware. Either party may seek injunctive relief in
              any court of competent jurisdiction.
            </p>
          </Section>

          <Section title="10. Changes to these terms">
            <p>
              American Turbines may update these Terms from time to time. We will
              post the updated Terms at{" "}
              <Link href="/terms" className="text-brand-text underline-offset-4 hover:underline">
                cascade.app/terms
              </Link>{" "}
              and, for material changes, notify active Team and Enterprise
              subscribers via email at least 14 days before the changes take
              effect. Continued use of the Service after the effective date
              constitutes acceptance of the updated Terms.
            </p>
          </Section>

          <Section title="11. Contact">
            <p>
              Questions about these Terms? Contact:{" "}
              <a
                href="mailto:legal@americanturbines.com"
                className="text-brand-text underline-offset-4 hover:underline"
              >
                legal@americanturbines.com
              </a>
            </p>
            <p className="text-text-muted">
              American Turbines, Inc. &nbsp;·&nbsp; legal@americanturbines.com
            </p>
          </Section>
        </div>
      </main>

      <footer className="mt-auto border-t border-border-subtle">
        <div className="mx-auto flex w-full max-w-5xl flex-col items-center justify-between gap-3 px-5 py-4 text-sm text-text-muted sm:flex-row">
          <span>© 2026 American Turbines</span>
          <div className="flex items-center gap-4">
            <Link href="/terms" className="font-medium text-text">
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
