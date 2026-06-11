import type { Metadata } from "next";
import Link from "next/link";
import { DocPage, ParamRow, ParamTable } from "@/components/docs";
import { Callout, Section } from "@/components/learn/content";

export const metadata: Metadata = { title: "Known gaps" };

export default function KnownGapsPage() {
  return (
    <DocPage slug="known-gaps">
      <Section id="policy" title="The policy: nothing unshipped in the present tense">
        <p>
          Cascade keeps a public registry of everything it doesn’t do yet —{" "}
          <code className="font-mono text-[13px]">KNOWN_GAPS.md</code> in the
          repository root. Every gap has a <strong>stable ID</strong> (
          <code className="font-mono text-[13px]">KG-003</code>,{" "}
          <code className="font-mono text-[13px]">KG-ML-04</code>, …) that
          documentation, error messages, and release notes cite. The rule it
          enforces: nothing unshipped is ever described in the present tense.
          If a page says “Cascade does X,” X is in the code; if X is planned,
          you’ll see a KG-ID next to it.
        </p>
        <p>
          This sounds like bookkeeping. It’s actually the product’s main
          defense against the failure mode of engineering software marketing
          — capability claims that turn out to mean “on the roadmap.”
        </p>
      </Section>

      <Section id="reading" title="How to read a gap ID">
        <ParamTable>
          <ParamRow name="KG-0xx" type="numerical engine">
            Core solver gaps — e.g.{" "}
            <code className="font-mono text-[13px]">KG-003</code> map-based
            multi-spool matching,{" "}
            <code className="font-mono text-[13px]">KG-004</code>{" "}
            cooled-turbine modeling,{" "}
            <code className="font-mono text-[13px]">KG-007/008/009</code>{" "}
            native tilt-pad/thrust/foil bearing solvers,{" "}
            <code className="font-mono text-[13px]">KG-019/020/021</code>{" "}
            true BOBYQA / NSGA-III / IPOPT.
          </ParamRow>
          <ParamRow name="KG-ML-xx" type="mean-line">
            E.g. <code className="font-mono text-[13px]">KG-ML-02</code> the
            Eckardt calibration scale,{" "}
            <code className="font-mono text-[13px]">KG-ML-04</code> the
            approximate NASA TN D-7508 geometry,{" "}
            <code className="font-mono text-[13px]">KG-ML-07</code>{" "}
            perfect-gas-only mean-line.
          </ParamRow>
          <ParamRow name="KG-TFN-01 / KG-AXT-01" type="whole subsystems">
            The 1D thermal-fluid network solver and the axial mean-line —
            not implemented in v1, stated as such.
          </ParamRow>
          <ParamRow name="KG-RD-xx" type="rotor dynamics">
            Scope boundaries and validation gaps, e.g.{" "}
            <code className="font-mono text-[13px]">KG-RD-01</code> the RD-3
            proxy-shaft caveat.
          </ParamRow>
          <ParamRow name="KG-PLAT-xx" type="platform">
            <code className="font-mono text-[13px]">KG-PLAT-01</code>{" "}
            real-time collaboration,{" "}
            <code className="font-mono text-[13px]">KG-PLAT-03</code>{" "}
            candidate-fed maps,{" "}
            <code className="font-mono text-[13px]">KG-PLAT-04</code> the
            hosted instance.
          </ParamRow>
          <ParamRow name="KG-G-xx" type="geometry">
            E.g. <code className="font-mono text-[13px]">KG-G-08</code> —
            STEP/IGES behind the optional CAD extra.
          </ParamRow>
        </ParamTable>
      </Section>

      <Section id="big-picture" title="The big picture for v0.1">
        <p>
          Cascade v0.1 serves <strong>single-shaft radial machines in the
          microturbine class</strong>, well. The major deliberate
          deferrals:
        </p>
        <ul className="ml-5 list-disc space-y-2">
          <li>
            Axial machines — the 1–20 MW segment is the v1.1 trajectory.
          </li>
          <li>
            Real-gas mean-line (the cycle has real gas; sCO₂ mean-line
            validation waits on it).
          </li>
          <li>
            Multi-spool map matching, cooled turbines, native exotic-bearing
            solvers.
          </li>
          <li>
            Native CFD / full 3D FEA — out of scope <em>by design</em>;
            Cascade exports to the tools that do this well instead of
            shipping a worse version of them.
          </li>
          <li>
            Hosted multi-user deployment — AGPL self-host is first-class
            today; the hosted instance is roadmap.
          </li>
        </ul>
        <Callout kind="note" title="Where to read the full list">
          <code className="font-mono text-[13px]">KNOWN_GAPS.md</code> (every
          gap, rationale, target release) and{" "}
          <code className="font-mono text-[13px]">ROADMAP.md</code> in the
          repository root. When documentation and the gap registry disagree,
          the registry wins — file an issue.
        </Callout>
      </Section>

      <Section id="refusals" title="Gaps that refuse, not pretend">
        <p>
          Where a gap could be mistaken for a feature, the code raises:{" "}
          <code className="font-mono text-[13px]">OptimizeNSGA3</code> exists
          as a name and deliberately throws rather than quietly running
          NSGA-II; combustor temperatures that would need cooled-row modeling
          are refused with the KG-ID in the message. The gap registry isn’t a
          separate document that drifts — it’s wired into the failure
          surface. See{" "}
          <Link href="/docs/errors" className="font-medium text-brand-text hover:underline">
            Failures &amp; status codes
          </Link>
          .
        </p>
      </Section>
    </DocPage>
  );
}
