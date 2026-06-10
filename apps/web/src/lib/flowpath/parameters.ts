/**
 * Flow Path PD parameter definitions.
 *
 * Each parameter belongs to a section, carries a unit, an active value,
 * an optional min/max sweep range (for geometry), an optional constraint
 * expression, and a frozen flag. The parameter store (see store.ts) holds
 * these as state.
 *
 * Naming conventions:
 *  - `id` is a stable machine handle (snake_case ASCII).
 *  - `symbol` is the human-readable Unicode notation rendered in the UI.
 *  - `unit` is the canonical unit string; downstream code converts to SI.
 *  - `regimeHint` is a short note that explains the validity envelope.
 */

export type ParameterKind = "boundary" | "geometry" | "constraint" | "exploration";

export interface ParameterDef {
  id: string;
  symbol: string;
  unit: string;
  kind: ParameterKind;
  /** Display group label (e.g. "Inlet", "Operating point"). Optional. */
  group?: string;
  /** Active scalar value (the centre column for geometry rows). */
  value: number;
  /** Geometry sweep bounds — `null` for non-geometry rows. */
  min: number | null;
  max: number | null;
  /** Step (used for live-preview slider granularity). */
  step?: number;
  /** True when the parameter is locked out of the sweep. */
  frozen: boolean;
  /** Short description shown in the (?) popover. */
  description?: string;
  /** Regime / validity hint (rendered in the popover). */
  regimeHint?: string;
  /** Constraint comparator + RHS (e.g. ≤ 1.05) — only set for `constraint` rows. */
  constraint?: { op: "le" | "ge" | "eq"; rhs: number };
}

/**
 * Initial parameter set for the microturbine-30kw project.
 *
 * Boundary conditions match the cycle in `apps/web/src/lib/api/mock-data.ts`
 * (Pt_in = 101.3 kPa, Tt_in = 288.15 K, ṁ = 0.27 kg/s, ω = 96 000 rpm).
 * Geometry ranges are aligned with `apps/api/routers/explore.py`
 * `_default_parameter_ranges`.
 */
export const DEFAULT_PARAMETERS: ParameterDef[] = [
  // ---- Boundary conditions ------------------------------------------------
  {
    id: "Pt_in",
    symbol: "Pt_in",
    unit: "kPa",
    kind: "boundary",
    group: "Inlet",
    value: 101.3,
    min: null,
    max: null,
    frozen: false,
    description: "Total inlet pressure.",
    regimeHint: "Standard sea-level ambient; loss models valid for 50–500 kPa.",
  },
  {
    id: "Tt_in",
    symbol: "Tt_in",
    unit: "K",
    kind: "boundary",
    group: "Inlet",
    value: 288.15,
    min: null,
    max: null,
    frozen: false,
    description: "Total inlet temperature.",
    regimeHint: "Cold-air ISA conditions.",
  },
  {
    id: "m_dot",
    symbol: "ṁ",
    unit: "kg/s",
    kind: "boundary",
    group: "Operating point",
    value: 0.27,
    min: null,
    max: null,
    frozen: false,
    description: "Design-point mass flow rate.",
    regimeHint: "Choose to size the inducer; Whitfield-Baines valid 0.05–5 kg/s.",
  },
  {
    id: "omega_design",
    symbol: "ω_design",
    unit: "rpm",
    kind: "boundary",
    group: "Operating point",
    value: 96000,
    min: null,
    max: null,
    frozen: false,
    description: "Design-point shaft speed.",
    regimeHint: "Microturbine class typically 60–120 krpm.",
  },

  // ---- Geometry parameters -------------------------------------------------
  {
    id: "rotor_outlet_radius",
    symbol: "r_tip_2",
    unit: "mm",
    kind: "geometry",
    group: "Wheel",
    value: 30,
    min: 20,
    max: 45,
    step: 0.5,
    frozen: false,
    description: "Rotor outlet tip radius.",
    regimeHint: "Constrained by max tip speed (≤ 550 m/s for Ti alloys).",
  },
  {
    id: "blade_count",
    symbol: "Z",
    unit: "",
    kind: "geometry",
    group: "Wheel",
    value: 14,
    min: 10,
    max: 18,
    step: 1,
    frozen: false,
    description: "Number of main (full) blades.",
    regimeHint: "Wiesner slip-factor model valid Z = 8–24.",
  },
  {
    id: "tip_clearance",
    symbol: "τ",
    unit: "mm",
    kind: "geometry",
    group: "Tip",
    value: 0.3,
    min: 0.25,
    max: 0.5,
    step: 0.01,
    frozen: false,
    description: "Axial tip clearance.",
    regimeHint:
      "Whitfield-Baines tip-clearance loss valid τ/h ≤ 0.05. Floor " +
      "0.25 mm = manufacturable cold clearance (Boyce §3.4); below it " +
      "candidates fail the 5-axis manufacturability gate.",
  },
  {
    id: "outlet_blade_angle",
    symbol: "β_2,rel",
    unit: "deg",
    kind: "geometry",
    group: "Blade",
    value: -55,
    min: -65,
    max: -45,
    step: 0.5,
    frozen: false,
    description: "Outlet relative flow angle (backswept).",
    regimeHint: "Stable centrifugal compressor maps require β_2 ≤ −40°.",
  },

  // ---- Constraints ---------------------------------------------------------
  {
    id: "max_M_rel",
    symbol: "max M_rel",
    unit: "",
    kind: "constraint",
    value: 1.05,
    min: null,
    max: null,
    frozen: false,
    description: "Cap on the maximum relative Mach number.",
    regimeHint: "Whitfield-Baines validated to M_rel ≤ 1.2.",
    constraint: { op: "le", rhs: 1.05 },
  },
  {
    id: "max_tip_speed",
    symbol: "max U_tip",
    unit: "m/s",
    kind: "constraint",
    value: 550,
    min: null,
    max: null,
    frozen: false,
    description: "Cap on outlet tip speed.",
    regimeHint: "Mechanical-stress limit for Ti-6Al-4V; Inconel pushes to 650.",
    constraint: { op: "le", rhs: 550 },
  },

  // ---- Exploration setup ---------------------------------------------------
  {
    id: "n_samples",
    symbol: "n_samples",
    unit: "",
    kind: "exploration",
    value: 800,
    min: null,
    max: null,
    frozen: false,
    description: "Number of Sobol' samples to evaluate.",
    regimeHint: "Sobol' converges in O(N^-1); 256–2048 is the usable band.",
  },
  {
    id: "seed",
    symbol: "seed",
    unit: "",
    kind: "exploration",
    value: 2026,
    min: null,
    max: null,
    frozen: false,
    description: "Sobol' sequence seed.",
    regimeHint: "Set to make exploration runs reproducible.",
  },
  {
    id: "parallelism",
    symbol: "n_workers",
    unit: "",
    kind: "exploration",
    value: 8,
    min: null,
    max: null,
    frozen: false,
    description: "Worker processes for candidate evaluation.",
    regimeHint: "Cascade's evaluator is embarrassingly parallel.",
  },
];

/** Map UI parameter ids → backend Sobol parameter names (apps/api/routers/explore.py). */
export const BACKEND_PARAMETER_MAP: Record<string, { name: string; toBackend: (v: number) => number }> = {
  rotor_outlet_radius: { name: "rotor_outlet_radius", toBackend: (mm) => mm / 1000 },
  blade_count: { name: "blade_count", toBackend: (v) => v },
  tip_clearance: { name: "tip_clearance", toBackend: (mm) => mm / 1000 },
};

/**
 * Validate a parameter value against its sweep range. Returns the
 * resolved validity (used to colour the cell border).
 */
export function validateParameter(p: ParameterDef): "ok" | "warn" | "error" {
  if (!Number.isFinite(p.value)) return "error";
  if (p.min != null && p.value < p.min) return "warn";
  if (p.max != null && p.value > p.max) return "warn";
  if (p.kind === "geometry" && p.min != null && p.max != null && p.min >= p.max) {
    return "error";
  }
  if (p.kind === "exploration" && p.id === "n_samples" && (p.value < 50 || p.value > 8192)) {
    return "warn";
  }
  return "ok";
}

/**
 * Pretty-print a number for the parameter table — tight formatting that
 * preserves engineering intent without abbreviating to exponential.
 */
export function formatParameterValue(value: number, unit: string): string {
  if (!Number.isFinite(value)) return "—";
  const abs = Math.abs(value);
  if (unit === "rpm" || unit === "" || abs >= 1000) {
    return Math.round(value).toLocaleString("en-US");
  }
  if (abs >= 100) return value.toFixed(1);
  if (abs >= 1) return value.toFixed(2);
  if (abs >= 0.01) return value.toFixed(3);
  return value.toExponential(2);
}
