import type { Metadata } from "next";
import Link from "next/link";
import { CodeBlock, DocPage, ParamRow, ParamTable } from "@/components/docs";
import { Callout, Section } from "@/components/learn/content";

export const metadata: Metadata = { title: "Python scripting" };

export default function PythonApiPage() {
  return (
    <DocPage slug="python-api">
      <Section id="philosophy" title="The package is the product">
        <p>
          There is no separate “scripting SDK” bolted onto Cascade — the{" "}
          <code className="font-mono text-[13px]">cascade</code> Python
          package <em>is</em> the numerical core, and the web app is a client
          of it. Anything the UI computes, you can compute in a script, a
          notebook, or a CI pipeline, with the same solvers and the same
          refusal behavior. (Coverage isn’t 100% symmetrical yet —{" "}
          <code className="font-mono text-[13px]">make spec-parity</code>{" "}
          tracks the uncovered surface.)
        </p>
        <CodeBlock
          lang="python"
          bare
          code={`from cascade import Q, Port, Composition   # the types everything shares

from cascade.cycle      import solve_simple_brayton, solve_recuperated_brayton
from cascade.meanline   import RadialTurbineMeanline, CentrifugalCompressorMeanline
from cascade.explore    import SobolSampler, ParameterRange
from cascade.perf_map   import PerformanceMap
from cascade.rotor      import build_rotor_model, run_lateral_analysis
from cascade.optimize   import OptimizeSLSQP, OptimizeNSGA2
from cascade.thermo     import NasaMixture, CoolPropFluid
from cascade.materials  import MaterialDB
from cascade.geometry   import impeller_mesh, export_stl
from cascade.project    import load_project, save_project`}
        />
      </Section>

      <Section id="core-types" title="The three types everything shares">
        <ParamTable>
          <ParamRow name="Q(value, unit)" type="→ Quantity">
            Constructs a pint quantity:{" "}
            <code className="font-mono text-[13px]">{`Q(101.325, "kPa")`}</code>.
            Every physical number in Cascade is one of these — see{" "}
            <Link href="/docs/units" className="font-medium text-brand-text hover:underline">
              Units &amp; quantities
            </Link>
            .
          </ParamRow>
          <ParamRow name="Port" type="frozen dataclass">
            The canonical thermodynamic state at every component boundary:
            total pressure, total temperature, signed mass flow, composition,
            plus optional swirl and velocity fields. Validates dimensions on
            construction and refuses NaN/±Inf.
          </ParamRow>
          <ParamRow name="Composition" type="mass fractions">
            <code className="font-mono text-[13px]">Composition.air()</code>{" "}
            for standard dry air,{" "}
            <code className="font-mono text-[13px]">Composition.pure(Species.SCO2)</code>{" "}
            for a single species, or explicit mass fractions over the
            15-species catalog (N₂, O₂, Ar, CO₂, H₂O, CO, H₂, OH, NO, NO₂,
            CH₄, C₁₂H₂₃, soot, He, sCO₂).
          </ParamRow>
        </ParamTable>
      </Section>

      <Section id="modules" title="Module map">
        <p>
          Each solver area has its own guide with worked examples — this is
          the index:
        </p>
        <ParamTable>
          <ParamRow name="cascade.cycle" type="0D thermodynamics">
            <code className="font-mono text-[13px]">solve_simple_brayton</code>,{" "}
            <code className="font-mono text-[13px]">solve_recuperated_brayton</code>,{" "}
            <code className="font-mono text-[13px]">solve_multi_shaft_brayton</code>{" "}
            over component specs. →{" "}
            <Link href="/docs/cycle" className="font-medium text-brand-text hover:underline">Cycle design</Link>
          </ParamRow>
          <ParamRow name="cascade.meanline" type="1D machines">
            Radial turbine and centrifugal compressor solvers, geometry
            dataclasses, cited loss models, slip correlations. →{" "}
            <Link href="/docs/meanline" className="font-medium text-brand-text hover:underline">Mean-line design</Link>
          </ParamRow>
          <ParamRow name="cascade.explore" type="design space">
            <code className="font-mono text-[13px]">SobolSampler</code>,{" "}
            <code className="font-mono text-[13px]">ParameterRange</code>,{" "}
            <code className="font-mono text-[13px]">DesignSpace.filter()</code>{" "}
            and Pareto fronts. →{" "}
            <Link href="/docs/exploration" className="font-medium text-brand-text hover:underline">Design exploration</Link>
          </ParamRow>
          <ParamRow name="cascade.perf_map" type="maps">
            Grid generation over any evaluator, surge/choke detection,
            CSV/JSON/HDF5 export. →{" "}
            <Link href="/docs/performance-maps" className="font-medium text-brand-text hover:underline">Performance maps</Link>
          </ParamRow>
          <ParamRow name="cascade.rotor" type="rotor dynamics">
            Beam-FEM assembly, bearings, and the five analyses. →{" "}
            <Link href="/docs/rotor-dynamics" className="font-medium text-brand-text hover:underline">Rotor dynamics</Link>
          </ParamRow>
          <ParamRow name="cascade.optimize" type="optimizers">
            SLSQP, BOBYQA-named-Powell, CMA-ES, NSGA-II. →{" "}
            <Link href="/docs/optimization" className="font-medium text-brand-text hover:underline">Optimization</Link>
          </ParamRow>
          <ParamRow name="cascade.project" type="persistence">
            Load, save, and round-trip the TOML project format. →{" "}
            <Link href="/docs/projects" className="font-medium text-brand-text hover:underline">Projects</Link>
          </ParamRow>
          <ParamRow name="cascade.plugins" type="extensions">
            Custom loss models with mandatory citations. →{" "}
            <Link href="/docs/plugins" className="font-medium text-brand-text hover:underline">Plugins</Link>
          </ParamRow>
        </ParamTable>
      </Section>

      <Section id="thermo" title="Fluid properties directly">
        <p>
          The fluid models the cycle solver uses are callable on their own —
          handy for sanity checks and sizing spreadsheet replacements:
        </p>
        <CodeBlock
          lang="python"
          title="properties.py"
          code={`from cascade.thermo import NasaMixture, CoolPropFluid
from cascade.units import Composition, Species

air = Composition.air()
fluid = NasaMixture()                 # NASA 9-coefficient polynomials

h  = fluid.h(T=1200, p=1e5, composition=air)    # enthalpy [J/kg]
cp = fluid.cp(T=1200, composition=air)          # [J/(kg*K)]
s  = fluid.s(T=1200, p=1e5, composition=air)    # entropy [J/(kg*K)]
g  = fluid.gamma(T=1200, composition=air)       # cp/cv

# Pure real fluids ride on CoolProp:
sco2 = CoolPropFluid(fluid_name="sCO2")
h2 = sco2.h(T=500, p=2e7, composition=Composition.pure(Species.SCO2))`}
        />
        <p>
          Validity is enforced here too: temperatures outside 200–6000 K
          raise{" "}
          <code className="font-mono text-[13px]">RegimeOutOfValidity</code>{" "}
          — the polynomial fits have edges, and the edges are honored.
        </p>
      </Section>

      <Section id="materials" title="Materials and manufacturability">
        <CodeBlock
          lang="python"
          title="materials_and_rules.py"
          code={`from cascade.materials import MaterialDB

inco = MaterialDB.get("INCONEL_718")
print(inco.E(T=900))         # Young's modulus at 900 K [Pa]
print(inco.sigma_y(T=900))   # yield strength [Pa]
print(inco.alpha(T=900))     # thermal expansion [1/K]

# The same 5-axis rules the explorer applies, callable directly:
from cascade.manufacturability import check_impeller

report = check_impeller(geometry=geom)          # a CentrifugalCompressorGeometry
if report.has_violations:
    for v in report.violations:
        print(v.rule.name, "—", v.message)`}
        />
        <p>
          Ten alloys ship with temperature-dependent property tables and
          sources: Inconel 625/718/738, MAR-M 247, Ti-6Al-4V, AISI 4340,
          17-4PH, A286, Haynes 282, and 316L. See{" "}
          <Link href="/docs/materials" className="font-medium text-brand-text hover:underline">
            Materials database
          </Link>
          .
        </p>
      </Section>

      <Section id="geometry" title="Meshes and export">
        <CodeBlock
          lang="python"
          title="export_impeller.py"
          code={`from cascade.geometry import impeller_mesh, MeshLOD, export_stl, export_glb

mesh = impeller_mesh(
    geometry=geom,                # the geometry you designed above
    lod=MeshLOD.EXPORT,           # PREVIEW ~3k → EXPORT ~83k vertices
    with_splitter=True,
    with_back_face=True,
)
export_stl(mesh, "impeller.stl")
export_glb(mesh, "impeller.glb")
# export_step / export_iges need the optional cascade[cad] extra`}
        />
        <p>
          Full format details and the CAD extra live in{" "}
          <Link href="/docs/export" className="font-medium text-brand-text hover:underline">
            Geometry export
          </Link>
          .
        </p>
      </Section>

      <Section id="patterns" title="A pattern worth copying">
        <p>
          Because everything is plain Python, the loop “explore broadly, then
          verify the finalist end-to-end” is a single script:
        </p>
        <CodeBlock
          lang="python"
          title="screen_and_verify.py"
          code={`# 1. Sample geometries deterministically
candidates = SobolSampler(parameter_ranges=ranges,
                          n_samples=512, seed=42).generate()

# 2. Solve each one, keeping the survivors
survivors = []
for c in candidates:
    try:
        r = solver.solve(inlet=inlet, rpm=Q(70_000, "rpm"),
                         geometry=build_geometry(c),
                         loss_model=AungierCentrifugal())
        if r.efficiency_total_to_total > 0.85:
            survivors.append((c, r))
    except RegimeOutOfValidity:
        continue                       # honestly out of bounds — skip

# 3. Check the best survivor against the machining rules
best_c, best_r = max(survivors, key=lambda cr: cr[1].efficiency_total_to_total)
report = check_impeller(geometry=build_geometry(best_c))
print(f"η_tt = {best_r.efficiency_total_to_total:.4f}, "
      f"manufacturable = {not report.has_violations}")`}
        />
        <Callout kind="note" title="Reproducibility is a feature, use it">
          Commit the script next to the project TOML. Seeded sampling +
          versioned projects + cited models means a colleague can re-derive
          your shortlist from scratch — which is what a design review should
          be able to do.
        </Callout>
      </Section>
    </DocPage>
  );
}
