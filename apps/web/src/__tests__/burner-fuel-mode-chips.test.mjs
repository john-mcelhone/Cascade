/**
 * U7 unit tests — Burner fuel-mass-flow mode chip + adapter logic.
 *
 * Run with: node src/__tests__/burner-fuel-mode-chips.test.mjs
 *
 * Mirrors (in plain JS, same pattern as filter-dsl.test.mjs — the TS source
 * is authoritative; this guards the runtime behaviour):
 *  - `rebuildChips` burner branch in src/lib/api/client.ts: in fuel mode
 *    the T₃ chip is `derived` and NEVER renders the stored
 *    outlet_temperature_K; in TIT mode it renders the stored value.
 *  - The derived-chip display predicate in
 *    src/components/cycle/nodes/base-node.tsx: fresh result → value with
 *    computed tint; run in flight → previous value greyed; stale → "—"
 *    greyed.
 *  - `uiParamsToBackend` Burner translation in src/lib/api/client.ts:
 *    fuel_mass_flow_kg_s ships as a {value, unit: "kg/s"} Quantity and
 *    spec_mode passes through verbatim.
 *  - The result-panel "(derived)" predicate in
 *    src/components/cycle/result-panel.tsx.
 */

import assert from "node:assert/strict";

// ---------------------------------------------------------------------------
// Mirror of rebuildChips (burner branch) from src/lib/api/client.ts
// ---------------------------------------------------------------------------

function fmt(v, decimals = 2) {
  if (v === undefined || !Number.isFinite(v)) return "—";
  return v.toFixed(decimals).replace(/\.?0+$/, "");
}

function rebuildBurnerChips(params) {
  const num = (k, fallback) =>
    typeof params[k] === "number" ? params[k] : fallback;
  const fuelMode = params.spec_mode === "fuel_mass_flow";
  return [
    fuelMode
      ? { symbol: "T₃", value: "—", derived: true }
      : { symbol: "T₃", value: `${fmt(num("outlet_temperature_K"))} K` },
    {
      symbol: "ΔP",
      value: `${fmt((num("pressure_drop_fraction") ?? 0) * 100, 1)} %`,
    },
  ];
}

// ---------------------------------------------------------------------------
// Mirror of the derived-chip display predicate from base-node.tsx
// ---------------------------------------------------------------------------

function derivedChipDisplay(chip, solvedState, runStatus, lastDerivedT) {
  const freshT = solvedState ? solvedState.outletTemperature : undefined;
  const inFlight = runStatus === "running";
  const display =
    freshT !== undefined
      ? `${freshT.toFixed(0)} K`
      : inFlight && lastDerivedT !== undefined
        ? `${lastDerivedT.toFixed(0)} K`
        : chip.value;
  const fresh = freshT !== undefined && !inFlight;
  return { display, fresh };
}

// ---------------------------------------------------------------------------
// Mirror of uiParamsToBackend for the Burner kind (client.ts translation
// table: quantityFields + passthroughFields).
// ---------------------------------------------------------------------------

const BURNER_QUANTITY_FIELDS = [
  ["outlet_temperature", "outlet_temperature_K", "K"],
  ["fuel_lhv", "fuel_lhv_MJ_per_kg", "MJ/kg"],
  ["fuel_molar_mass", "fuel_molar_mass_g_per_mol", "g/mol"],
  ["fuel_mass_flow", "fuel_mass_flow_kg_s", "kg/s"],
];
const BURNER_PASSTHROUGH_FIELDS = [
  "pressure_drop_fraction",
  "combustion_efficiency",
  "spec_mode",
  "fuel_species",
  "fuel_carbon_atoms",
  "fuel_hydrogen_atoms",
  "air_standard",
  "material",
];

function burnerUiParamsToBackend(params) {
  const out = {};
  for (const [bk, uk, unit] of BURNER_QUANTITY_FIELDS) {
    const raw = params[uk];
    if (raw === undefined) continue;
    if (typeof raw === "number" && Number.isFinite(raw)) {
      out[bk] = { value: raw, unit };
    }
  }
  for (const k of BURNER_PASSTHROUGH_FIELDS) {
    if (params[k] === undefined) continue;
    out[k] = params[k];
  }
  return out;
}

// ---------------------------------------------------------------------------
// Mirror of the result-panel "(derived)" predicate (result-panel.tsx)
// ---------------------------------------------------------------------------

function titDerived(node) {
  return (
    node?.kind === "burner" && node.params?.spec_mode === "fuel_mass_flow"
  );
}

// ---------------------------------------------------------------------------
// Tiny test runner (same as filter-dsl.test.mjs)
// ---------------------------------------------------------------------------

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    console.log(`  ✓ ${name}`);
    passed++;
  } catch (err) {
    console.error(`  ✗ ${name}`);
    console.error(`    ${err.message}`);
    failed++;
  }
}

console.log("burner-fuel-mode chips + adapters (U7)\n");

// ---------------------------------------------------------------------------
// rebuildChips
// ---------------------------------------------------------------------------

test("TIT mode: T₃ chip renders the stored outlet_temperature_K", () => {
  const chips = rebuildBurnerChips({
    spec_mode: "outlet_temperature",
    outlet_temperature_K: 1116,
    pressure_drop_fraction: 0.04,
  });
  assert.equal(chips[0].symbol, "T₃");
  assert.equal(chips[0].value, "1116 K");
  assert.ok(!chips[0].derived);
});

test("no spec_mode (legacy bag): treated as TIT mode", () => {
  const chips = rebuildBurnerChips({
    outlet_temperature_K: 1100,
    pressure_drop_fraction: 0.03,
  });
  assert.equal(chips[0].value, "1100 K");
  assert.ok(!chips[0].derived);
});

test("fuel mode: T₃ chip is derived and NEVER shows the stale stored TIT", () => {
  const chips = rebuildBurnerChips({
    spec_mode: "fuel_mass_flow",
    outlet_temperature_K: 1116, // stale; solver no longer honours it
    fuel_mass_flow_kg_s: 0.0023,
    pressure_drop_fraction: 0.04,
  });
  assert.equal(chips[0].symbol, "T₃");
  assert.equal(chips[0].derived, true);
  assert.ok(
    !chips[0].value.includes("1116"),
    `stale TIT leaked into the chip: ${chips[0].value}`,
  );
  assert.equal(chips[0].value, "—");
});

test("fuel mode: ΔP chip is unaffected", () => {
  const chips = rebuildBurnerChips({
    spec_mode: "fuel_mass_flow",
    pressure_drop_fraction: 0.04,
  });
  assert.equal(chips[1].symbol, "ΔP");
  assert.equal(chips[1].value, "4 %");
});

// ---------------------------------------------------------------------------
// Derived-chip display (canvas)
// ---------------------------------------------------------------------------

const derivedChip = { symbol: "T₃", value: "—", derived: true };

test("fresh solve: derived chip shows back-derived TIT with computed tint", () => {
  const r = derivedChipDisplay(
    derivedChip,
    { outletTemperature: 1257.3 },
    "succeeded",
    undefined,
  );
  assert.equal(r.display, "1257 K");
  assert.equal(r.fresh, true);
});

test("run in flight: previous value stays visible but greyed", () => {
  const r = derivedChipDisplay(derivedChip, undefined, "running", 1257.3);
  assert.equal(r.display, "1257 K");
  assert.equal(r.fresh, false);
});

test("stale (edited, never re-solved): em-dash, greyed", () => {
  const r = derivedChipDisplay(derivedChip, undefined, "idle", undefined);
  assert.equal(r.display, "—");
  assert.equal(r.fresh, false);
});

test("failed solve: solvedState cleared → em-dash, greyed", () => {
  const r = derivedChipDisplay(derivedChip, undefined, "failed", 1257.3);
  assert.equal(r.display, "—");
  assert.equal(r.fresh, false);
});

// ---------------------------------------------------------------------------
// uiParamsToBackend round-trip keys
// ---------------------------------------------------------------------------

test("fuel_mass_flow_kg_s ships as a kg/s Quantity under fuel_mass_flow", () => {
  const out = burnerUiParamsToBackend({
    spec_mode: "fuel_mass_flow",
    fuel_mass_flow_kg_s: 0.0023,
  });
  assert.deepEqual(out.fuel_mass_flow, { value: 0.0023, unit: "kg/s" });
});

test("spec_mode passes through verbatim", () => {
  const out = burnerUiParamsToBackend({ spec_mode: "fuel_mass_flow" });
  assert.equal(out.spec_mode, "fuel_mass_flow");
});

test("mode flip ships BOTH retained values (merge-retention KTD)", () => {
  const out = burnerUiParamsToBackend({
    spec_mode: "outlet_temperature",
    outlet_temperature_K: 1116,
    fuel_mass_flow_kg_s: 0.0023,
  });
  assert.deepEqual(out.outlet_temperature, { value: 1116, unit: "K" });
  assert.deepEqual(out.fuel_mass_flow, { value: 0.0023, unit: "kg/s" });
  assert.equal(out.spec_mode, "outlet_temperature");
});

// ---------------------------------------------------------------------------
// Result-panel "(derived)" predicate
// ---------------------------------------------------------------------------

test("burner in fuel mode → TIT labelled (derived)", () => {
  assert.equal(
    titDerived({
      kind: "burner",
      params: { spec_mode: "fuel_mass_flow" },
    }),
    true,
  );
});

test("burner in TIT mode → no (derived) label", () => {
  assert.equal(
    titDerived({
      kind: "burner",
      params: { spec_mode: "outlet_temperature" },
    }),
    false,
  );
});

test("non-burner components never get the (derived) label", () => {
  assert.equal(
    titDerived({ kind: "turbine", params: { spec_mode: "fuel_mass_flow" } }),
    false,
  );
  assert.equal(titDerived(undefined), false);
});

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

console.log(`\n${passed + failed} tests: ${passed} passed, ${failed} failed\n`);
if (failed > 0) process.exit(1);
