import type { Metadata } from "next";
import Link from "next/link";
import { CodeBlock, DocPage, ParamRow, ParamTable } from "@/components/docs";
import { Callout, Section } from "@/components/learn/content";

export const metadata: Metadata = { title: "CLI reference" };

export default function CliPage() {
  return (
    <DocPage slug="cli">
      <Section id="overview" title="Overview">
        <p>
          Installing the package puts a{" "}
          <code className="font-mono text-[13px]">cascade</code> command on
          your path. It covers the workflows you’d want without a browser:
          demos, validation, parameter sweeps, result export, and plugin
          management.
        </p>
        <CodeBlock
          lang="bash"
          bare
          code={`$ cascade --help
$ cascade --version`}
        />
      </Section>

      <Section id="demo" title="cascade demo">
        <p>
          Runs the demo projects end-to-end — the same thing{" "}
          <code className="font-mono text-[13px]">make demo</code> calls. Good
          as a smoke test and as living example code:
        </p>
        <CodeBlock
          lang="bash"
          title="terminal"
          code={`$ cascade demo run                              # all three demos
$ cascade demo run --case microturbine_cycle
$ cascade demo run --case radial_turbine_design
$ cascade demo run --case rotor_dynamics
$ cascade demo run --energy-balance             # Capstone cycle with the
                                                # sensible-vs-absolute energy report`}
        />
      </Section>

      <Section id="validate" title="cascade validate">
        <p>
          Runs the public validation suite (
          <code className="font-mono text-[13px]">pytest -m validation</code>)
          — the pass-gates against published cases. If this passes, your
          install reproduces the claims in the{" "}
          <Link href="/docs/validation" className="font-medium text-brand-text hover:underline">
            validation report
          </Link>
          .
        </p>
        <CodeBlock lang="bash" bare code={`$ cascade validate`} />
      </Section>

      <Section id="citations" title="cascade citations">
        <p>
          Prints every loss model with its published citation — the registry
          that <code className="font-mono text-[13px]">make check-citations</code>{" "}
          enforces in CI.
        </p>
        <CodeBlock lang="bash" bare code={`$ cascade citations`} />
      </Section>

      <Section id="sweep" title="cascade sweep">
        <p>
          One-dimensional parameter sweep over a saved project’s cycle —
          the fastest way to answer “what does η do as pressure ratio goes
          from 2 to 6?”:
        </p>
        <CodeBlock
          lang="bash"
          title="terminal"
          code={`$ cascade sweep \\
    --project microturbine-30kw \\
    --param compressor.pressure_ratio \\
    --range 2.0:6.0:25 \\
    --output sweep.csv`}
        />
        <ParamTable title="Options">
          <ParamRow name="--project" type="slug" required>
            A project in your projects directory (
            <code className="font-mono text-[13px]">~/.cascade/projects</code>{" "}
            by default).
          </ParamRow>
          <ParamRow name="--param" type="component.field" required>
            Which parameter to sweep, addressed as{" "}
            <code className="font-mono text-[13px]">component_id.field</code>.
          </ParamRow>
          <ParamRow name="--range" type="start:end:n" required>
            Inclusive range and point count —{" "}
            <code className="font-mono text-[13px]">2.0:6.0:25</code> is 25
            evenly spaced points.
          </ParamRow>
          <ParamRow name="--output" type="file.csv" required>
            Destination CSV.
          </ParamRow>
        </ParamTable>
        <p>The CSV carries one row per point, with an honest tail:</p>
        <CodeBlock
          lang="text"
          bare
          code={`param_value, pressure_drop_Pa, thermal_efficiency, electrical_efficiency,
specific_work_kJ_per_kg, fuel_flow_kg_s, net_shaft_work_kW,
electrical_output_kW, status, reason`}
        />
        <Callout kind="note" title="status and reason columns">
          A point that refused or failed to converge is a row with a status
          and a reason, not a missing row. Sweeps tell you where the validity
          region ends — that’s half their value.
        </Callout>
      </Section>

      <Section id="export" title="cascade export">
        <p>Exports a project’s latest cycle result as a structured CSV:</p>
        <CodeBlock
          lang="bash"
          title="terminal"
          code={`$ cascade export --project microturbine-30kw --output result.csv`}
        />
        <p>
          The file has three sections —{" "}
          <code className="font-mono text-[13px]">[STATUS]</code> (converged?
          why not?), <code className="font-mono text-[13px]">[HEADLINE]</code>{" "}
          (efficiencies, powers, fuel flow), and one{" "}
          <code className="font-mono text-[13px]">[COMPONENT:*]</code> block
          per component with its inlet/outlet states.
        </p>
      </Section>

      <Section id="plugin" title="cascade plugin">
        <CodeBlock
          lang="bash"
          title="terminal"
          code={`$ cascade plugin template > my_loss_model.py   # start from the template
$ cascade plugin install my_loss_model.py      # prompts for trust confirmation
$ cascade plugin list                          # built-in + installed models
$ cascade plugin remove MyLossModel`}
        />
        <p>
          Install prompts for confirmation because a plugin is executable
          Python; set{" "}
          <code className="font-mono text-[13px]">CASCADE_PLUGIN_INSTALL_YES=1</code>{" "}
          to skip the prompt in CI. The plugin contract — including the
          mandatory citation — is documented in{" "}
          <Link href="/docs/plugins" className="font-medium text-brand-text hover:underline">
            Plugins
          </Link>
          .
        </p>
      </Section>

      <Section id="make" title="Make targets (repo workflows)">
        <p>
          Working from a clone, the Makefile is the front door. The full set:
        </p>
        <div className="overflow-x-auto scrollbar-subtle">
          <table className="w-full min-w-[480px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-border-subtle text-left">
                <th className="py-2 pr-4 text-xs font-medium uppercase tracking-wide text-text-muted">Target</th>
                <th className="py-2 text-xs font-medium uppercase tracking-wide text-text-muted">What it does</th>
              </tr>
            </thead>
            <tbody className="text-text-subtle">
              {[
                ["make setup", "One-time: install Python deps into .venv."],
                ["make run / stop / logs", "Start API (:8000) + web (:3000) in the background; stop them; tail .logs/."],
                ["make api / web", "Run either server in the foreground with reload."],
                ["make demo", "The three demo projects, end to end."],
                ["make test / test-web", "Python unit tests; web unit tests + typecheck."],
                ["make validation", "Public validation suite vs published cases (≈14 s)."],
                ["make check-citations", "Fail if any loss model ships uncited."],
                ["make spec-parity", "SPEC §2 parity gate — SDK/CLI coverage of the spec."],
                ["make ci", "The full gate: test + validation + test-web + web-build + citations. Run before every PR."],
                ["make lint / typecheck", "Ruff and mypy (strict) over the core."],
                ["make clean / clean-web", "Remove build artifacts and caches (clean-web fixes stale Next.js chunks)."],
              ].map(([target, desc]) => (
                <tr key={target} className="border-b border-border-subtle/60 last:border-b-0">
                  <td className="py-2 pr-4 font-mono text-xs text-text">{target}</td>
                  <td className="py-2">{desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </DocPage>
  );
}
