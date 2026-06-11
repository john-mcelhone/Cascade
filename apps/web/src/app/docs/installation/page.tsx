import type { Metadata } from "next";
import Link from "next/link";
import { CodeBlock, CodeTabs, DocPage, ParamRow, ParamTable } from "@/components/docs";
import { Callout, Section } from "@/components/learn/content";

export const metadata: Metadata = { title: "Installation" };

export default function InstallationPage() {
  return (
    <DocPage slug="installation">
      <Section id="requirements" title="Requirements">
        <p>
          Cascade is two things that install together: a Python numerical core
          (the <code className="font-mono text-[13px]">cascade</code> package)
          and a web workspace (Next.js) that talks to it through a local API.
          You need:
        </p>
        <ParamTable>
          <ParamRow name="Python" type="≥ 3.12" required>
            The numerical core targets Python 3.12. Everything — solvers,
            units, geometry — is plain Python on numpy, scipy, pint, and
            CoolProp.
          </ParamRow>
          <ParamRow name="Node.js" type="18+">
            Only needed for the web workspace. If you script Cascade from
            Python alone, you can skip the web app entirely.
          </ParamRow>
          <ParamRow name="make + git">
            The repo drives everything through a Makefile, and projects are
            designed to live in git.
          </ParamRow>
        </ParamTable>
        <Callout kind="note">
          Cascade v0.1.0 is a <strong>pre-release</strong> and is not yet on
          PyPI — you install from a clone of the repository. AGPL self-hosting
          is free and stays first-class.
        </Callout>
      </Section>

      <Section id="install" title="Install and run">
        <p>
          One command sets up a virtualenv with every Python dependency; a
          second starts both servers in the background:
        </p>
        <CodeBlock
          lang="bash"
          title="terminal"
          code={`git clone <your-fork-or-clone-url> Cascade
cd Cascade
make setup       # one-time: install Python deps in .venv
make run         # start API (:8000) + web (:3000); logs in .logs/`}
        />
        <p>
          Then open{" "}
          <Link
            href="/projects/microturbine-30kw/cycle"
            className="font-medium text-brand-text hover:underline"
          >
            http://localhost:3000/projects/microturbine-30kw/cycle
          </Link>{" "}
          — three demo projects are seeded on first startup. When you’re done:
        </p>
        <CodeBlock
          lang="bash"
          title="terminal"
          code={`make stop        # stop the background API + web servers
make logs        # tail .logs/api.log and .logs/web.log while running`}
        />
        <p>
          Prefer foreground processes with auto-reload while developing? Use{" "}
          <code className="font-mono text-[13px]">make api</code> and{" "}
          <code className="font-mono text-[13px]">make web</code> in two
          terminals.
        </p>
      </Section>

      <Section id="verify" title="Verify the install">
        <p>
          Cascade ships its acceptance gate with the code, so you can prove
          your install works the same way the maintainers do:
        </p>
        <CodeTabs
          tabs={[
            {
              label: "CLI",
              lang: "bash",
              code: `make demo        # run the three demo projects end-to-end
make test        # unit tests (core + API)
make validation  # the public validation suite vs published cases (~14 s)`,
            },
            {
              label: "Python",
              lang: "python",
              code: `# A ten-second smoke test from the repo root:
from cascade import Q, Port, Composition

inlet = Port(
    pressure_total=Q(101.325, "kPa"),
    temperature_total=Q(288.15, "K"),
    mass_flow=Q(1.0, "kg/s"),
    composition=Composition.air(),
)
print(inlet.pressure_total.to("Pa"))  # 101325.0 pascal`,
            },
          ]}
        />
        <p>
          <code className="font-mono text-[13px]">make validation</code> runs
          the pass-gate subset of the validation suite against published cases
          — the same numbers reported in the{" "}
          <Link href="/docs/validation" className="font-medium text-brand-text hover:underline">
            validation report
          </Link>
          . If it passes on your machine, your install reproduces the public
          claims.
        </p>
      </Section>

      <Section id="extras" title="Optional extras">
        <ParamTable title="pip extras">
          <ParamRow name="cascade[cad]" type="pythonocc-core ≥ 7.7.0">
            STEP and IGES export (plus fluid-volume STEP) via OpenCASCADE.
            Intentionally optional — it’s roughly 200 MB of compiled C++.
            Conda is the more reliable install channel; pip wheels are missing
            on some Python/OS combinations. Without it, GLB, STL, OBJ, and
            TurboGrid NDF export all still work.
          </ParamRow>
          <ParamRow name="cascade[api]" type="FastAPI, uvicorn, …">
            The web API server dependencies.{" "}
            <code className="font-mono text-[13px]">make setup</code> installs
            these for you — you only need this extra for a manual pip install.
          </ParamRow>
          <ParamRow name="cascade[dev]" type="pytest, ruff, mypy, hypothesis">
            The development toolchain, for running the test suite and the lint
            gate.
          </ParamRow>
        </ParamTable>
        <Callout kind="note" title="CoolProp and Python 3.13">
          The real-gas CoolProp dependency installs only on Python &lt; 3.13
          (no upstream wheels yet). On 3.13+, the NASA 9-coefficient
          polynomial fluid model still covers air and combustion products.
        </Callout>
      </Section>

      <Section id="configuration" title="Configuration">
        <p>
          Cascade needs almost no configuration. Two environment variables
          exist:
        </p>
        <ParamTable title="Environment variables">
          <ParamRow
            name="CASCADE_PROJECTS_DIR"
            type="path"
            defaultValue="~/.cascade"
          >
            Where project TOML files live, under{" "}
            <code className="font-mono text-[13px]">projects/</code>. Point it
            at a git repository to version your designs — see{" "}
            <Link href="/docs/projects" className="font-medium text-brand-text hover:underline">
              Projects
            </Link>
            .
          </ParamRow>
          <ParamRow
            name="NEXT_PUBLIC_API_URL"
            type="URL"
            defaultValue="http://localhost:8000"
          >
            Where the web app finds the API. Only relevant if you run the API
            on a different host or port.
          </ParamRow>
        </ParamTable>
      </Section>

      <Section id="troubleshooting" title="If something breaks">
        <ul className="ml-5 list-disc space-y-2 text-md">
          <li>
            <strong>Web build acting strange after an update?</strong>{" "}
            <code className="font-mono text-[13px]">make clean-web</code>{" "}
            removes the Next.js build caches (fixes stale vendor-chunk
            errors).
          </li>
          <li>
            <strong>Want a truly fresh start?</strong>{" "}
            <code className="font-mono text-[13px]">make clean</code> removes
            build artifacts, caches, the virtualenv, and logs. Your projects
            in <code className="font-mono text-[13px]">~/.cascade</code> are
            untouched.
          </li>
          <li>
            <strong>STEP/IGES export returns an error?</strong> Check{" "}
            <code className="font-mono text-[13px]">GET /api/health/cad</code>{" "}
            — it reports whether the optional CAD stack is importable, and
            which OpenCASCADE version it found.
          </li>
        </ul>
      </Section>
    </DocPage>
  );
}
