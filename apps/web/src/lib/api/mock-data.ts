/**
 * Deterministic seed data for the Cascade mock backend.
 * No randomness; same output on every render so the UI is reviewable and
 * screenshots are reproducible.
 */

import type {
  Candidate,
  CycleGraph,
  MapPoint,
  MapResult,
  Project,
  RotorShape,
  RunRecord,
} from "./types";

const ISO_NOW = "2026-05-26T08:00:00.000Z";

export const PROJECTS: Project[] = [
  {
    id: "microturbine-30kw",
    name: "Microturbine 30 kW",
    description:
      "Recuperated single-shaft Brayton cycle, air working fluid, 96k rpm radial-turbine + centrifugal-compressor pair.",
    template: "microturbine",
    status: "converged",
    createdAt: "2026-04-12T15:30:00.000Z",
    updatedAt: ISO_NOW,
    workingFluid: "air",
    headline: { label: "η_e", value: 0.2741, unit: "" },
    sparkline: [0.241, 0.252, 0.258, 0.262, 0.267, 0.272, 0.2741],
  },
  {
    id: "sco2-test-loop",
    name: "sCO2 Test Loop",
    description:
      "Recompression supercritical-CO2 Brayton cycle, 600 kW test loop, 50k rpm radial compressor.",
    template: "sco2-loop",
    status: "in-progress",
    createdAt: "2026-05-02T11:00:00.000Z",
    updatedAt: ISO_NOW,
    workingFluid: "co2",
    headline: { label: "η_th", value: 0.4172, unit: "" },
    sparkline: [0.391, 0.398, 0.404, 0.409, 0.413, 0.416, 0.4172],
  },
  {
    id: "aero-demonstrator",
    name: "Aero Demonstrator",
    description:
      "Two-stage axial demonstrator for high-altitude propulsion, sized against the Pratt JT8D legacy core.",
    template: "aero-axial",
    status: "design",
    createdAt: "2026-05-20T08:00:00.000Z",
    updatedAt: ISO_NOW,
    workingFluid: "air",
    headline: { label: "PR", value: 6.4, unit: "" },
    sparkline: [3.9, 4.6, 5.1, 5.4, 5.8, 6.1, 6.4],
  },
];

export const CYCLES: Record<string, CycleGraph> = {
  "microturbine-30kw": {
    nodes: [
      {
        id: "inlet",
        kind: "inlet",
        label: "Atmosphere",
        x: 40,
        y: 200,
        chips: [
          { symbol: "Pt", value: "101.3 kPa" },
          { symbol: "Tt", value: "288 K" },
        ],
        params: {
          pressure_total_kPa: 101.3,
          temperature_total_K: 288,
          mass_flow_kg_s: 0.22,
        },
      },
      {
        id: "C1",
        kind: "compressor",
        label: "C1",
        x: 240,
        y: 200,
        chips: [
          { symbol: "PR", value: "4.0" },
          { symbol: "η", value: "0.78" },
        ],
        params: { pressure_ratio: 4.0, efficiency_isentropic: 0.78 },
      },
      {
        id: "REC",
        kind: "recuperator",
        label: "Recuperator",
        x: 440,
        y: 80,
        chips: [
          { symbol: "ε", value: "0.83" },
          { symbol: "ΔP_c", value: "3.0 %" },
        ],
        params: {
          effectiveness: 0.83,
          cold_pressure_drop_fraction: 0.03,
          hot_pressure_drop_fraction: 0.03,
        },
      },
      {
        id: "B1",
        kind: "burner",
        label: "Combustor",
        x: 640,
        y: 80,
        chips: [
          { symbol: "T₃", value: "1223 K" },
          { symbol: "ΔP", value: "3.0 %" },
        ],
        params: {
          outlet_temperature_K: 1223,
          pressure_drop_fraction: 0.03,
          combustion_efficiency: 0.99,
        },
      },
      {
        id: "T1",
        kind: "turbine",
        label: "T1",
        x: 840,
        y: 200,
        chips: [
          { symbol: "PR", value: "4.0" },
          { symbol: "η", value: "0.83" },
        ],
        params: { pressure_ratio: 4.0, efficiency_isentropic: 0.83 },
      },
      {
        id: "SHAFT",
        kind: "shaft",
        label: "Shaft",
        x: 540,
        y: 360,
        chips: [
          { symbol: "ω", value: "96 krpm" },
          { symbol: "η_m", value: "0.98" },
        ],
        params: { speed_krpm: 96, mechanical_efficiency: 0.98 },
      },
      {
        id: "out",
        kind: "outlet",
        label: "Exhaust",
        x: 1040,
        y: 320,
        chips: [],
        params: {},
      },
    ],
    edges: [
      { id: "e1", source: "inlet", target: "C1" },
      { id: "e2", source: "C1", target: "REC", targetPort: "cold_in" },
      { id: "e3", source: "REC", sourcePort: "cold_out", target: "B1" },
      { id: "e4", source: "B1", target: "T1" },
      { id: "e5", source: "T1", target: "REC", targetPort: "hot_in" },
      { id: "e6", source: "REC", sourcePort: "hot_out", target: "out" },
      {
        id: "e7",
        source: "T1",
        sourcePort: "shaft",
        target: "SHAFT",
        targetPort: "in",
      },
      {
        id: "e8",
        source: "SHAFT",
        sourcePort: "out",
        target: "C1",
        targetPort: "shaft",
      },
    ],
    result: {
      thermalEfficiency: 0.291,
      electricalEfficiency: 0.2741,
      specificWork: 142.7,
      fuelFlow: 0.0079,
      netShaftWork: 31.4,
      electricalOutput: 30.1,
      components: [
        {
          componentId: "C1",
          shaftWork: -47.2,
          outletTemperature: 451,
          outletPressure: 405.2,
          outletMassFlow: 0.22,
        },
        {
          componentId: "REC",
          shaftWork: 0,
          outletTemperature: 821,
          outletPressure: 393.0,
          outletMassFlow: 0.22,
        },
        {
          componentId: "B1",
          shaftWork: 0,
          outletTemperature: 1223,
          outletPressure: 381.2,
          outletMassFlow: 0.227,
        },
        {
          componentId: "T1",
          shaftWork: 78.6,
          outletTemperature: 873,
          outletPressure: 102.5,
          outletMassFlow: 0.227,
        },
      ],
      states: [
        { label: "1", temperature: 288, entropy: 6.83, pressure: 101.3 },
        { label: "2", temperature: 451, entropy: 6.92, pressure: 405.2 },
        { label: "3", temperature: 821, entropy: 7.50, pressure: 393.0 },
        { label: "4", temperature: 1223, entropy: 7.92, pressure: 381.2 },
        { label: "5", temperature: 873, entropy: 8.00, pressure: 102.5 },
        { label: "6", temperature: 523, entropy: 7.62, pressure: 99.4 },
      ],
    },
  },
  "sco2-test-loop": {
    nodes: [
      { id: "src", kind: "inlet", label: "Cooler exit", x: 40, y: 160, chips: [] },
      {
        id: "C1",
        kind: "compressor",
        label: "Main C",
        x: 220,
        y: 160,
        chips: [{ symbol: "PR", value: "3.0" }],
      },
      {
        id: "HX",
        kind: "recuperator",
        label: "HTR",
        x: 400,
        y: 160,
        chips: [{ symbol: "ε", value: "0.95" }],
      },
      {
        id: "T1",
        kind: "turbine",
        label: "T1",
        x: 600,
        y: 160,
        chips: [{ symbol: "η", value: "0.88" }],
      },
      { id: "out", kind: "outlet", label: "To cooler", x: 780, y: 160, chips: [] },
    ],
    edges: [
      { id: "e1", source: "src", target: "C1" },
      { id: "e2", source: "C1", target: "HX" },
      { id: "e3", source: "HX", target: "T1" },
      { id: "e4", source: "T1", target: "out" },
    ],
    result: {
      thermalEfficiency: 0.4172,
      electricalEfficiency: 0.3851,
      specificWork: 217.9,
      fuelFlow: 0,
      netShaftWork: 612,
      electricalOutput: 565,
      components: [],
      states: [],
    },
  },
  "aero-demonstrator": {
    nodes: [
      { id: "in", kind: "inlet", label: "Inlet", x: 40, y: 160, chips: [] },
      {
        id: "LPC",
        kind: "compressor",
        label: "LPC",
        x: 200,
        y: 160,
        chips: [{ symbol: "PR", value: "2.0" }],
      },
      {
        id: "HPC",
        kind: "compressor",
        label: "HPC",
        x: 360,
        y: 160,
        chips: [{ symbol: "PR", value: "3.2" }],
      },
      {
        id: "B",
        kind: "burner",
        label: "Combustor",
        x: 520,
        y: 160,
        chips: [{ symbol: "T₄", value: "1450 K" }],
      },
      {
        id: "HPT",
        kind: "turbine",
        label: "HPT",
        x: 680,
        y: 160,
        chips: [{ symbol: "η", value: "0.86" }],
      },
      {
        id: "LPT",
        kind: "turbine",
        label: "LPT",
        x: 840,
        y: 160,
        chips: [{ symbol: "η", value: "0.88" }],
      },
      { id: "out", kind: "outlet", label: "Nozzle", x: 1000, y: 160, chips: [] },
    ],
    edges: [
      { id: "e1", source: "in", target: "LPC" },
      { id: "e2", source: "LPC", target: "HPC" },
      { id: "e3", source: "HPC", target: "B" },
      { id: "e4", source: "B", target: "HPT" },
      { id: "e5", source: "HPT", target: "LPT" },
      { id: "e6", source: "LPT", target: "out" },
    ],
  },
};

/** A deterministic Halton(2,3) sample for the design space scatter. */
function halton(i: number, base: number): number {
  let f = 1;
  let r = 0;
  let k = i;
  while (k > 0) {
    f /= base;
    r += f * (k % base);
    k = Math.floor(k / base);
  }
  return r;
}

function buildCandidates(): Candidate[] {
  const cs: Candidate[] = [];
  for (let i = 1; i <= 240; i++) {
    const a = halton(i, 2);
    const b = halton(i, 3);
    const eta_tt = 0.7 + 0.18 * (1 - Math.pow(a - 0.55, 2) * 3) - 0.06 * b;
    const eta_ts = eta_tt - 0.045;
    const max_m_rel = 0.4 + 0.9 * a;
    const mass = 0.18 + 0.08 * b;
    let status: Candidate["status"] = "ok";
    if (max_m_rel > 1.05) status = "regime-violation";
    if (a < 0.05) status = "invalid-geometry";
    if (b > 0.96 && a > 0.7) status = "diverged";
    cs.push({
      id: `cand-${i.toString().padStart(4, "0")}`,
      index: i,
      status,
      eta_tt: Math.max(0.4, Math.min(eta_tt, 0.89)),
      eta_ts: Math.max(0.35, Math.min(eta_ts, 0.85)),
      max_m_rel,
      mass,
      params: {
        rotor_outlet_radius_tip: 18 + 24 * a,
        blade_count: Math.round(7 + 8 * b),
        relative_flow_angle: -50 + 20 * b,
        tip_clearance: 0.15 + 0.3 * a,
      },
    });
  }
  return cs;
}

export const CANDIDATES: Record<string, Candidate[]> = {
  "microturbine-30kw": buildCandidates(),
  "sco2-test-loop": buildCandidates().slice(0, 140),
  "aero-demonstrator": [],
};

function buildMap(): MapResult {
  const rpmList = [60000, 72000, 84000, 96000, 108000];
  const points: MapPoint[] = [];
  for (const rpm of rpmList) {
    const speedFrac = rpm / 96000;
    const mDotMin = 0.12 * speedFrac;
    const mDotMax = 0.32 * speedFrac;
    const N = 9;
    for (let j = 0; j < N; j++) {
      const t = j / (N - 1);
      const mDot = mDotMin + t * (mDotMax - mDotMin);
      const pi = 1.5 + 3.5 * speedFrac - 4 * Math.pow(t - 0.55, 2);
      const eta = 0.75 + 0.1 * speedFrac - 0.2 * Math.pow(t - 0.55, 2);
      let status: MapPoint["status"] = "ok";
      if (t < 0.06) status = "surge";
      if (t > 0.93) status = "choke";
      points.push({
        rpm,
        massFlow: mDot,
        pi_tt: Math.max(1.05, pi),
        eta_tt: Math.max(0.55, eta),
        status,
      });
    }
  }
  return { rpmList, points };
}

export const MAPS: Record<string, MapResult> = {
  "microturbine-30kw": buildMap(),
  "sco2-test-loop": buildMap(),
  "aero-demonstrator": { rpmList: [], points: [] },
};

export const ROTOR_SHAPES: Record<string, RotorShape> = {
  "microturbine-30kw": {
    totalLength: 280,
    sections: [
      { axialStart: 0, axialEnd: 18, radius: 8, kind: "shaft", label: "Nose" },
      {
        axialStart: 18,
        axialEnd: 38,
        radius: 16,
        kind: "disk",
        label: "Compressor wheel",
      },
      { axialStart: 38, axialEnd: 90, radius: 8, kind: "shaft" },
      { axialStart: 90, axialEnd: 96, radius: 14, kind: "bearing", label: "B1" },
      { axialStart: 96, axialEnd: 180, radius: 8, kind: "shaft" },
      { axialStart: 180, axialEnd: 186, radius: 14, kind: "bearing", label: "B2" },
      { axialStart: 186, axialEnd: 240, radius: 8, kind: "shaft" },
      {
        axialStart: 240,
        axialEnd: 264,
        radius: 17,
        kind: "disk",
        label: "Turbine wheel",
      },
      { axialStart: 264, axialEnd: 280, radius: 8, kind: "shaft" },
    ],
  },
  "sco2-test-loop": {
    totalLength: 240,
    sections: [
      { axialStart: 0, axialEnd: 10, radius: 9, kind: "shaft" },
      { axialStart: 10, axialEnd: 36, radius: 18, kind: "disk", label: "Compressor" },
      { axialStart: 36, axialEnd: 90, radius: 9, kind: "shaft" },
      { axialStart: 90, axialEnd: 96, radius: 16, kind: "bearing", label: "B1" },
      { axialStart: 96, axialEnd: 160, radius: 9, kind: "shaft" },
      { axialStart: 160, axialEnd: 166, radius: 16, kind: "bearing", label: "B2" },
      { axialStart: 166, axialEnd: 210, radius: 9, kind: "shaft" },
      { axialStart: 210, axialEnd: 230, radius: 18, kind: "disk", label: "Turbine" },
      { axialStart: 230, axialEnd: 240, radius: 9, kind: "shaft" },
    ],
  },
  "aero-demonstrator": {
    totalLength: 400,
    sections: [{ axialStart: 0, axialEnd: 400, radius: 12, kind: "shaft" }],
  },
};

export const RUNS: Record<string, RunRecord[]> = {
  "microturbine-30kw": [
    {
      id: "run-1042",
      kind: "cycle",
      status: "succeeded",
      startedAt: "2026-05-26T07:42:11.000Z",
      finishedAt: "2026-05-26T07:42:11.371Z",
      durationMs: 371,
      summary: "Converged. η_e = 0.274.",
    },
    {
      id: "run-1041",
      kind: "explore",
      status: "succeeded",
      startedAt: "2026-05-26T07:30:00.000Z",
      finishedAt: "2026-05-26T07:30:08.840Z",
      durationMs: 8840,
      summary: "240 candidates; 219 passed regime; best η_tt = 0.881.",
    },
    {
      id: "run-1040",
      kind: "analysis",
      status: "succeeded",
      startedAt: "2026-05-25T22:14:00.000Z",
      finishedAt: "2026-05-25T22:14:00.198Z",
      durationMs: 198,
      summary: "Mean-line analysis on cand-0193. η_tt = 0.879.",
    },
    {
      id: "run-1039",
      kind: "map",
      status: "succeeded",
      startedAt: "2026-05-25T21:00:00.000Z",
      finishedAt: "2026-05-25T21:00:04.121Z",
      durationMs: 4121,
      summary: "5 speedlines × 9 mass-flow points. No diverged points.",
    },
    {
      id: "run-1038",
      kind: "explore",
      status: "failed",
      startedAt: "2026-05-25T19:00:00.000Z",
      finishedAt: "2026-05-25T19:00:02.000Z",
      durationMs: 2000,
      summary: "Aborted: blade_count range invalid (min > max).",
    },
  ],
  "sco2-test-loop": [
    {
      id: "run-877",
      kind: "cycle",
      status: "succeeded",
      startedAt: "2026-05-26T06:00:00.000Z",
      finishedAt: "2026-05-26T06:00:00.412Z",
      durationMs: 412,
      summary: "Converged. η_th = 0.417.",
    },
  ],
  "aero-demonstrator": [],
};

export { ISO_NOW };
