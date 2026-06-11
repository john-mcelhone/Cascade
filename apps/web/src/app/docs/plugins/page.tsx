import type { Metadata } from "next";
import Link from "next/link";
import {
  CodeBlock,
  CodeTabs,
  DocPage,
  ParamRow,
  ParamTable,
} from "@/components/docs";
import { Callout, Section } from "@/components/learn/content";

export const metadata: Metadata = { title: "Plugins" };

export default function PluginsPage() {
  return (
    <DocPage slug="plugins">
      <Section id="what" title="What a plugin is">
        <p>
          A plugin is a single Python file that adds a <strong>loss
          model</strong> — your lab’s correlation, a vendor’s proprietary
          fit, a published model Cascade doesn’t ship yet. Once installed,
          it appears in the loss-model picker next to the built-ins and runs
          inside the same mean-line solve.
        </p>
        <p>
          One rule is non-negotiable: <strong>plugins carry citations
          too</strong>. The same registry discipline that gates the built-in
          models applies — a correlation without a stated source is exactly
          the kind of quiet guesswork Cascade exists to eliminate.
        </p>
      </Section>

      <Section id="writing" title="Writing one">
        <p>
          Start from the shipped template (
          <code className="font-mono text-[13px]">cascade plugin template</code>)
          and implement one method:
        </p>
        <CodeBlock
          lang="python"
          title="my_loss_model.py"
          code={`from cascade.plugins import LossModel, LossContext


class MyLabRadialLoss(LossModel):
    """Passage-loss correlation from our 2024 rig campaign."""

    name = "MyLabRadial"
    applicable_machine_classes = ["radial_turbine"]
    description = "In-house correlation, 40-160 mm rotors"
    citation = "Smith, J. & Patel, R., 2024, J. Turbomach. 146(3), 031004"

    def loss_coefficient(self, context: LossContext) -> float:
        # Return a loss coefficient ζ ≥ 0. The context carries the
        # solved flow state: relative Mach, exit Mach, and more.
        return 0.04 + 0.025 * context.M_relative_max ** 2`}
        />
        <ParamTable title="The LossModel contract">
          <ParamRow name="name" type="str" required>
            Unique display name — what the picker and the result attribution
            show.
          </ParamRow>
          <ParamRow name="applicable_machine_classes" type="list[str]" required>
            <code className="font-mono text-[13px]">{`"radial_turbine"`}</code>,{" "}
            <code className="font-mono text-[13px]">{`"centrifugal_compressor"`}</code>,
            or both. The picker only offers your model where it applies.
          </ParamRow>
          <ParamRow name="citation" type="str" required>
            The published source. Enforced — an uncited model is rejected.
          </ParamRow>
          <ParamRow name="loss_coefficient(context)" type="→ float ≥ 0" required>
            The correlation itself, fed a{" "}
            <code className="font-mono text-[13px]">LossContext</code> with
            the solved flow state (relative and absolute Mach numbers among
            other fields).
          </ParamRow>
        </ParamTable>
      </Section>

      <Section id="installing" title="Installing and selecting">
        <CodeTabs
          tabs={[
            {
              label: "CLI",
              lang: "bash",
              code: `$ cascade plugin template > my_loss_model.py
$ cascade plugin install my_loss_model.py
# → prompts for trust confirmation, then stores under ~/.cascade/plugins
$ cascade plugin list
$ cascade plugin remove MyLabRadial`,
            },
            {
              label: "HTTP",
              lang: "http",
              code: `POST   /api/projects/{id}/loss-models/upload      # multipart file
GET    /api/projects/{id}/loss-models             # built-ins + project plugins
POST   /api/projects/{id}/loss-models/{name}/select
DELETE /api/projects/{id}/loss-models/{name}`,
            },
          ]}
        />
        <p>
          In the web app, the Flow path page has an upload card and a
          loss-model picker — uploaded models are scoped to the project, so
          an experimental correlation doesn’t leak into every design.
        </p>
        <Callout kind="warning" title="Plugins are executable code">
          A plugin runs with the API’s permissions. The CLI prompts before
          installing for exactly this reason (set{" "}
          <code className="font-mono text-[13px]">CASCADE_PLUGIN_INSTALL_YES=1</code>{" "}
          only in CI you control), and you should review any plugin file you
          didn’t write — same rule as any dependency.
        </Callout>
      </Section>

      <Section id="provenance" title="Provenance in results">
        <p>
          When a solve uses your model, the result says so — the loss-model
          name rides along with the candidate and the cycle attribution, so
          two explorations run under different correlations never get
          silently compared as equals. If you find your model and a built-in
          disagree, that disagreement is publishable information — consider{" "}
          <Link href="/docs/contributing" className="font-medium text-brand-text hover:underline">
            contributing
          </Link>{" "}
          a validation case.
        </p>
      </Section>
    </DocPage>
  );
}
