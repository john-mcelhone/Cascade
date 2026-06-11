import type { Metadata } from "next";
import Link from "next/link";
import { CodeBlock, DocPage, ParamRow, ParamTable } from "@/components/docs";
import { Callout, Section } from "@/components/learn/content";

export const metadata: Metadata = { title: "Optimization" };

export default function OptimizationPage() {
  return (
    <DocPage slug="optimization">
      <Section id="when" title="Exploration or optimization?">
        <p>
          <Link href="/docs/exploration" className="font-medium text-brand-text hover:underline">
            Design exploration
          </Link>{" "}
          shows you the whole space; optimization walks downhill to a point.
          Use exploration first — it tells you whether the space has one
          basin or many, and where the manufacturable region is. Then hand
          the promising basin to an optimizer to polish the answer. The
          optimizers are deliberately plain Python callables over{" "}
          <code className="font-mono text-[13px]">numpy</code> arrays, so any
          Cascade solver (or anything else) can be the objective.
        </p>
      </Section>

      <Section id="optimizers" title="The four optimizers">
        <ParamTable>
          <ParamRow name="OptimizeSLSQP" type="gradient-based, constrained">
            Sequential least-squares programming. The workhorse for smooth
            problems with bounds and nonlinear constraints. Options:{" "}
            <code className="font-mono text-[13px]">max_iter</code>,{" "}
            <code className="font-mono text-[13px]">ftol</code>.
          </ParamRow>
          <ParamRow name="OptimizeBOBYQA" type="derivative-free">
            Bound-constrained, no gradients needed — right when the objective
            is noisy or non-smooth.{" "}
            <strong>Honesty note:</strong> the implementation under this name
            is currently Powell’s method, not true BOBYQA — tracked as{" "}
            <code className="font-mono text-[13px]">KG-019</code> rather than
            silently relabeled.
          </ParamRow>
          <ParamRow name="OptimizeCMAES" type="evolutionary">
            Covariance-matrix-adaptation evolution strategy, self-contained
            implementation. For rugged or moderately multimodal landscapes.
            Options: <code className="font-mono text-[13px]">sigma</code>{" "}
            (initial step), <code className="font-mono text-[13px]">max_iter</code>,{" "}
            <code className="font-mono text-[13px]">seed</code>.
          </ParamRow>
          <ParamRow name="OptimizeNSGA2" type="multi-objective">
            NSGA-II for genuine trade-offs — efficiency vs. mass, range vs.
            margin. Returns the Pareto front, not one blended compromise.
            Options: <code className="font-mono text-[13px]">pop_size</code>,{" "}
            <code className="font-mono text-[13px]">n_gen</code>,{" "}
            <code className="font-mono text-[13px]">seed</code>.
          </ParamRow>
        </ParamTable>
        <Callout kind="note" title="What about NSGA-III and IPOPT?">
          Not shipped (<code className="font-mono text-[13px]">KG-020</code>,{" "}
          <code className="font-mono text-[13px]">KG-021</code>).{" "}
          <code className="font-mono text-[13px]">OptimizeNSGA3</code> exists
          as a name and deliberately raises instead of quietly running NSGA-II
          underneath — you find out at import time, not in a design review.
        </Callout>
      </Section>

      <Section id="single" title="Single-objective example">
        <CodeBlock
          lang="python"
          title="branin.py — the canonical benchmark (validation case OPT-1)"
          code={`import math
import numpy as np
from cascade.optimize import OptimizeSLSQP

def branin(x):
    x1, x2 = float(x[0]), float(x[1])
    return ((x2 - 5.1 / (4 * math.pi**2) * x1**2
             + 5 / math.pi * x1 - 6) ** 2
            + 10 * (1 - 1 / (8 * math.pi)) * math.cos(x1) + 10)

opt = OptimizeSLSQP(max_iter=80, ftol=1e-6)
res = opt.minimize(
    branin,
    x0=np.array([2.0, 4.0]),
    bounds=[(-5.0, 10.0), (0.0, 15.0)],
)
print(f"f* = {res.fun:.6f} at x = {res.x}")
print(f"{res.n_evals} evaluations, success = {res.success}")`}
        />
        <ParamTable title="OptimizationResult">
          <ParamRow name="x / fun" type="ndarray / float">
            The best design found and its objective value.
          </ParamRow>
          <ParamRow name="success / message" type="bool / str">
            Whether the optimizer believes it converged, and why it stopped.
          </ParamRow>
          <ParamRow name="n_evals / n_iter / history" type="int / int / list">
            The cost record: every (x, f) pair along the way, so you can plot
            convergence instead of trusting it.
          </ParamRow>
        </ParamTable>
      </Section>

      <Section id="multi" title="Multi-objective example">
        <p>
          Real design questions are trade-offs. NSGA-II returns the whole
          Pareto front — every design where improving one objective must cost
          the other:
        </p>
        <CodeBlock
          lang="python"
          title="pareto.py"
          code={`import numpy as np
from cascade.optimize import OptimizeNSGA2, hypervolume_2d

def two_objectives(x):
    f1 = float(x[0])
    g = 1.0 + 9.0 * float(np.sum(x[1:])) / (len(x) - 1)
    f2 = g * (1.0 - (f1 / g) ** 2)
    return np.array([f1, f2])

opt = OptimizeNSGA2(pop_size=100, n_gen=200, seed=42)
res = opt.minimize(two_objectives, bounds=[(0.0, 1.0)] * 30, n_obj=2)

print(f"Pareto front: {res.pareto_x.shape[0]} designs")
print(f"hypervolume = {hypervolume_2d(res.pareto_f, reference=(1.0, 1.0)):.4f}")`}
        />
        <p>
          <code className="font-mono text-[13px]">hypervolume_2d</code> gives
          you a single quality number for the front — useful for comparing
          runs or checking that more generations are still buying anything.
        </p>
      </Section>

      <Section id="objectives" title="Wiring a Cascade solver in as the objective">
        <CodeBlock
          lang="python"
          title="optimize_impeller.py"
          code={`import math
import numpy as np
from cascade.meanline import (
    CentrifugalCompressorMeanline, CentrifugalCompressorGeometry,
    AungierCentrifugal, RegimeOutOfValidity,
)
from cascade.optimize import OptimizeCMAES
from cascade.units import Port, Q, Composition

inlet = Port(
    pressure_total=Q(101.325, "kPa"), temperature_total=Q(288.15, "K"),
    mass_flow=Q(0.31, "kg/s"), composition=Composition.air(),
)
solver = CentrifugalCompressorMeanline()

def negative_eta(x):
    """Maximize η_tt over (outlet radius, blade height, backsweep)."""
    try:
        result = solver.solve(
            inlet=inlet, rpm=Q(70_000, "rpm"),
            geometry=CentrifugalCompressorGeometry(
                inducer_hub_radius=0.008, inducer_tip_radius=0.030,
                impeller_outlet_radius=float(x[0]),
                blade_height_outlet=float(x[1]),
                blade_count=15,
                beta_2_metal_rad=float(x[2]),
                tip_clearance=0.00015,
            ),
            loss_model=AungierCentrifugal(),
        )
        return -result.efficiency_total_to_total
    except RegimeOutOfValidity:
        return 1.0          # penalize out-of-validity instead of crashing

opt = OptimizeCMAES(sigma=0.3, max_iter=60, seed=7)
res = opt.minimize(
    negative_eta,
    x0=np.array([0.055, 0.0045, math.pi / 6]),
    bounds=[(0.04, 0.07), (0.003, 0.007), (0.3, 0.9)],
)
print(f"best η_tt = {-res.fun:.4f}")`}
        />
        <Callout kind="warning" title="Respect the refusals">
          When the solver raises{" "}
          <code className="font-mono text-[13px]">RegimeOutOfValidity</code>,
          that region of the design space is genuinely unknown to the loss
          model — penalize it (as above) rather than catching and returning a
          flattering guess. An optimizer will exploit any lie you tell it.
        </Callout>
      </Section>

      <Section id="validation" title="How good is it?">
        <p>
          Validation case OPT-1: SLSQP, Powell, and CMA-ES each find the
          Branin global minimum in under 100 evaluations. The deterministic
          seeds mean optimization runs are as reproducible as everything else
          — details in the{" "}
          <Link href="/docs/validation" className="font-medium text-brand-text hover:underline">
            validation report
          </Link>
          .
        </p>
      </Section>
    </DocPage>
  );
}
