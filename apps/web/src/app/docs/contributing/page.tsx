import type { Metadata } from "next";
import Link from "next/link";
import { CodeBlock, DocPage } from "@/components/docs";
import { Callout, Section } from "@/components/learn/content";

export const metadata: Metadata = { title: "Contributing" };

export default function ContributingPage() {
  return (
    <DocPage slug="contributing">
      <Section id="highest-leverage" title="The highest-leverage contribution is validation">
        <p>
          Cascade’s accuracy claims are only as tight as the published cases
          they’re tested against — and several gates are wide today simply
          because nobody has digitized the exact published geometry yet. If
          you have access to these references and an afternoon, you can
          tighten a tolerance the whole community relies on:
        </p>
        <ul className="ml-5 list-disc space-y-2">
          <li>
            <strong>NASA TN D-7508</strong> turbine deck → tightens RIT-1
            from ±5 pt toward ±2 pt (
            <code className="font-mono text-[13px]">KG-ML-04</code>).
          </li>
          <li>
            <strong>Wood 1963</strong> and the <strong>Sandia sCO₂</strong>{" "}
            turbine cases → currently no test files (
            <code className="font-mono text-[13px]">KG-ML-09</code>).
          </li>
          <li>
            <strong>Krain G/3, NASA CC3, VKI</strong> compressor cases → same
            (<code className="font-mono text-[13px]">KG-ML-10</code>).
          </li>
          <li>
            <strong>Childs 1993 §5.3</strong> rotor-dynamics worked example →
            straightforward to transcribe (
            <code className="font-mono text-[13px]">KG-RD-06</code>).
          </li>
        </ul>
        <p>
          Other welcome contributions: alloy property tables with sources for
          the{" "}
          <Link href="/docs/materials" className="font-medium text-brand-text hover:underline">
            materials database
          </Link>
          , and cited loss-model{" "}
          <Link href="/docs/plugins" className="font-medium text-brand-text hover:underline">
            plugins
          </Link>{" "}
          worth promoting to built-ins.
        </p>
      </Section>

      <Section id="gate" title="Run the gate before you open a PR">
        <CodeBlock
          lang="bash"
          title="terminal"
          code={`make ci
# = make test          unit tests (core + API)
# + make validation    the public validation suite
# + make test-web      web unit tests + typecheck
# + make web-build     production build (lint + compile)
# + make check-citations   every loss model must cite its source`}
        />
        <p>
          <code className="font-mono text-[13px]">make ci</code> is the same
          gate the maintainers run — there is no separate private CI that
          knows more than you do. (Public hosted CI is pending; the gate runs
          locally today.)
        </p>
      </Section>

      <Section id="rules" title="House rules">
        <ul className="ml-5 list-disc space-y-2">
          <li>
            <strong>Every loss model carries a published citation.</strong>{" "}
            <code className="font-mono text-[13px]">make check-citations</code>{" "}
            enforces it mechanically — an uncited correlation fails the
            build.
          </li>
          <li>
            <strong>Nothing unshipped in the present tense.</strong> If your
            PR defers something, give it a stable ID in{" "}
            <code className="font-mono text-[13px]">KNOWN_GAPS.md</code>{" "}
            (the file documents how to add one).
          </li>
          <li>
            <strong>Accuracy claims need a public case.</strong> A new solver
            or model lands with a validation test against a published
            reference, tolerances stated, caveats written down in{" "}
            <code className="font-mono text-[13px]">VALIDATION_REPORT.md</code>.
          </li>
        </ul>
        <Callout kind="note" title="When docs and code disagree">
          The code and the gap registry win. File an issue — a documentation
          page that overstates the product is treated as a bug, not a
          marketing choice.
        </Callout>
      </Section>

      <Section id="license" title="License">
        <p>
          Cascade is{" "}
          <span className="font-medium text-text">AGPL-3.0-or-later</span> —
          free to self-host, forever. It is developed and hosted by{" "}
          <a
            href="https://americanturbines.com/"
            target="_blank"
            rel="noreferrer"
            className="font-medium text-brand-text hover:underline"
          >
            American Turbines
          </a>
          . Contributions are licensed under the same terms.
        </p>
      </Section>
    </DocPage>
  );
}
