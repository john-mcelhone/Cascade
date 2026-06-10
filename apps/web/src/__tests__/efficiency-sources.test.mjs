/**
 * U9 unit tests — per-rotor efficiency attribution + fallback surfacing.
 *
 * Run with: node src/__tests__/efficiency-sources.test.mjs
 *
 * Mirrors (in plain JS, same pattern as burner-fuel-mode-chips.test.mjs —
 * the TS source is authoritative; this guards the runtime behaviour):
 *  - the `recordOf` adaptation of `component_efficiencies`,
 *    `efficiency_modes`, `requested_efficiency_modes` and
 *    `efficiency_fallbacks` in `adaptCycleResult`
 *    (src/lib/api/client.ts);
 *  - `efficiencySourceRows` + `showEfficiencySources` in
 *    src/components/cycle/result-panel.tsx (the "Efficiency sources"
 *    block's state mapping and the fallback-warning predicate);
 *  - the FastAPI error-detail message extraction in `fetchJson`
 *    (src/lib/api/client.ts) AND its twin in `flowPathJson`
 *    (src/lib/api/flowpath.ts) — both must surface `detail.message` (or a
 *    JSON-stringified dict) for structured details, never
 *    "[object Object]";
 *  - `geometrySourceCandidateId` in
 *    src/components/cycle/properties-panel.tsx — the geometry chip's
 *    provenance: per-component `geometry_source_candidate_id` (written by
 *    send-to-cycle) wins over the project-level pin, with the pin as the
 *    fallback for old projects.
 */

import assert from "node:assert/strict";

// ---------------------------------------------------------------------------
// Mirror of adaptCycleResult's recordOf() extraction (client.ts)
// ---------------------------------------------------------------------------

function recordOf(raw, key, isV) {
  const v = raw[key];
  if (!v || typeof v !== "object" || Array.isArray(v)) return undefined;
  const out = {};
  for (const [name, val] of Object.entries(v)) {
    if (isV(val)) out[name] = val;
  }
  return out;
}

function adaptAttribution(raw) {
  return {
    componentEfficiencies: recordOf(
      raw,
      "component_efficiencies",
      (v) => typeof v === "number" && Number.isFinite(v),
    ),
    efficiencyModes: recordOf(
      raw,
      "efficiency_modes",
      (v) => typeof v === "string",
    ),
    requestedEfficiencyModes: recordOf(
      raw,
      "requested_efficiency_modes",
      (v) => typeof v === "string",
    ),
    efficiencyFallbacks: recordOf(
      raw,
      "efficiency_fallbacks",
      (v) => typeof v === "boolean",
    ),
  };
}

// ---------------------------------------------------------------------------
// Mirror of efficiencySourceRows / showEfficiencySources (result-panel.tsx)
// ---------------------------------------------------------------------------

const EFFICIENCY_MODE_LABELS = {
  constant: "isentropic",
  polytropic: "polytropic",
  live_meanline: "live mean-line",
};

function efficiencySourceRows(result) {
  const modes = result.efficiencyModes ?? {};
  const requested = result.requestedEfficiencyModes ?? {};
  const fallbacks = result.efficiencyFallbacks ?? {};
  return Object.keys(modes).map((name) => ({
    componentId: name,
    eta: result.componentEfficiencies?.[name],
    modeLabel: EFFICIENCY_MODE_LABELS[modes[name]] ?? modes[name],
    fellBack:
      fallbacks[name] === true ||
      (requested[name] === "live_meanline" && modes[name] !== "live_meanline"),
  }));
}

function showEfficiencySources(result) {
  return (
    Object.values(result.efficiencyModes ?? {}).includes("live_meanline") ||
    Object.values(result.requestedEfficiencyModes ?? {}).includes(
      "live_meanline",
    ) ||
    Object.values(result.efficiencyFallbacks ?? {}).some(Boolean)
  );
}

// ---------------------------------------------------------------------------
// Mirror of geometrySourceCandidateId (properties-panel.tsx)
// ---------------------------------------------------------------------------

function geometrySourceCandidateId(params, activeCandidateId) {
  const fromParams = params?.geometry_source_candidate_id;
  if (typeof fromParams === "string" && fromParams) return fromParams;
  return typeof activeCandidateId === "string" && activeCandidateId
    ? activeCandidateId
    : undefined;
}

// ---------------------------------------------------------------------------
// Mirror of fetchJson's (client.ts) / flowPathJson's (flowpath.ts)
// FastAPI error message extraction — the two implementations are
// intentionally identical; this single mirror guards both.
// ---------------------------------------------------------------------------

function extractErrorMessage(detail, status) {
  let msg = `HTTP ${status}`;
  if (typeof detail === "string" && detail) {
    msg = detail;
  } else if (typeof detail === "object" && detail !== null && "detail" in detail) {
    const inner = detail.detail;
    if (typeof inner === "string") {
      msg = inner;
    } else if (
      inner !== null &&
      typeof inner === "object" &&
      typeof inner.message === "string"
    ) {
      msg = inner.message;
    } else if (inner != null) {
      try {
        msg = JSON.stringify(inner);
      } catch {
        /* keep the HTTP fallback */
      }
    }
  }
  return msg;
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

console.log("efficiency-sources attribution + fallback surfacing (U9)\n");

// ---------------------------------------------------------------------------
// Adapter: snake_case payload → camelCase records
// ---------------------------------------------------------------------------

test("adapter lifts all four attribution dicts from the payload", () => {
  const r = adaptAttribution({
    component_efficiencies: { C1: 0.892, T1: 0.84 },
    efficiency_modes: { C1: "live_meanline", T1: "constant" },
    requested_efficiency_modes: { C1: "live_meanline", T1: "constant" },
    efficiency_fallbacks: { C1: false, T1: false },
  });
  assert.deepEqual(r.componentEfficiencies, { C1: 0.892, T1: 0.84 });
  assert.deepEqual(r.efficiencyModes, { C1: "live_meanline", T1: "constant" });
  assert.deepEqual(r.requestedEfficiencyModes, {
    C1: "live_meanline",
    T1: "constant",
  });
  assert.deepEqual(r.efficiencyFallbacks, { C1: false, T1: false });
});

test("adapter drops malformed entries instead of crashing", () => {
  const r = adaptAttribution({
    component_efficiencies: { C1: 0.9, T1: "oops", X: NaN },
    efficiency_modes: { C1: "constant", T1: 42 },
    requested_efficiency_modes: "not-a-dict",
    efficiency_fallbacks: { C1: "yes" },
  });
  assert.deepEqual(r.componentEfficiencies, { C1: 0.9 });
  assert.deepEqual(r.efficiencyModes, { C1: "constant" });
  assert.equal(r.requestedEfficiencyModes, undefined);
  assert.deepEqual(r.efficiencyFallbacks, {});
});

test("adapter returns undefined for absent fields (legacy payloads)", () => {
  const r = adaptAttribution({ thermal_efficiency: 0.26 });
  assert.equal(r.componentEfficiencies, undefined);
  assert.equal(r.efficiencyModes, undefined);
  assert.equal(r.requestedEfficiencyModes, undefined);
  assert.equal(r.efficiencyFallbacks, undefined);
});

// ---------------------------------------------------------------------------
// Row mapping: η + source label per rotor
// ---------------------------------------------------------------------------

test("live mean-line rotor renders η with the live mean-line label", () => {
  const rows = efficiencySourceRows({
    componentEfficiencies: { C1: 0.812, T1: 0.84 },
    efficiencyModes: { C1: "live_meanline", T1: "constant" },
    requestedEfficiencyModes: { C1: "live_meanline", T1: "constant" },
    efficiencyFallbacks: { C1: false, T1: false },
  });
  const c1 = rows.find((r) => r.componentId === "C1");
  assert.equal(c1.eta, 0.812);
  assert.equal(c1.modeLabel, "live mean-line");
  assert.equal(c1.fellBack, false);
  const t1 = rows.find((r) => r.componentId === "T1");
  assert.equal(t1.modeLabel, "isentropic");
  assert.equal(t1.fellBack, false);
});

test("solver-convention 'constant' is labelled 'isentropic' for humans", () => {
  const rows = efficiencySourceRows({
    efficiencyModes: { C1: "constant" },
  });
  assert.equal(rows[0].modeLabel, "isentropic");
});

test("fallback flag marks the rotor that fell back, not its neighbour", () => {
  const rows = efficiencySourceRows({
    componentEfficiencies: { C1: 0.78, T1: 0.84 },
    efficiencyModes: { C1: "constant", T1: "constant" },
    requestedEfficiencyModes: { C1: "live_meanline", T1: "constant" },
    efficiencyFallbacks: { C1: true, T1: false },
  });
  assert.equal(rows.find((r) => r.componentId === "C1").fellBack, true);
  assert.equal(rows.find((r) => r.componentId === "T1").fellBack, false);
});

test("requested-vs-actual mismatch implies fallback even without the flag", () => {
  // Defensive: an older payload carrying requested modes but no explicit
  // efficiency_fallbacks dict must still produce the warning.
  const rows = efficiencySourceRows({
    efficiencyModes: { C1: "constant" },
    requestedEfficiencyModes: { C1: "live_meanline" },
  });
  assert.equal(rows[0].fellBack, true);
});

test("missing η renders as undefined (the row shows an em-dash), not 0", () => {
  const rows = efficiencySourceRows({
    efficiencyModes: { C1: "live_meanline" },
  });
  assert.equal(rows[0].eta, undefined);
});

// ---------------------------------------------------------------------------
// Visibility predicate: requested OR fallback, never on plain isentropic
// ---------------------------------------------------------------------------

test("block hidden for a plain isentropic run", () => {
  assert.equal(
    showEfficiencySources({
      efficiencyModes: { C1: "constant", T1: "constant" },
      requestedEfficiencyModes: { C1: "constant", T1: "constant" },
      efficiencyFallbacks: { C1: false, T1: false },
    }),
    false,
  );
});

test("block shown when live mean-line was actually used", () => {
  assert.equal(
    showEfficiencySources({
      efficiencyModes: { C1: "live_meanline", T1: "constant" },
      requestedEfficiencyModes: { C1: "live_meanline", T1: "constant" },
      efficiencyFallbacks: { C1: false, T1: false },
    }),
    true,
  );
});

test("block shown on fallback (requested live, got constant) — AE4", () => {
  assert.equal(
    showEfficiencySources({
      efficiencyModes: { C1: "constant", T1: "constant" },
      requestedEfficiencyModes: { C1: "live_meanline", T1: "constant" },
      efficiencyFallbacks: { C1: true, T1: false },
    }),
    true,
  );
});

test("block shown when only the explicit fallback flag survives", () => {
  assert.equal(
    showEfficiencySources({ efficiencyFallbacks: { C1: true } }),
    true,
  );
});

test("block hidden when attribution fields are absent (legacy result)", () => {
  assert.equal(showEfficiencySources({}), false);
});

// ---------------------------------------------------------------------------
// Geometry chip provenance (properties-panel.tsx)
// ---------------------------------------------------------------------------

test("chip prefers the per-component geometry_source_candidate_id", () => {
  assert.equal(
    geometrySourceCandidateId(
      {
        geometry_params: { blade_count: 12 },
        geometry_source_candidate_id: "cand-sent-1234",
      },
      "cand-pinned-5678",
    ),
    "cand-sent-1234",
  );
});

test("chip falls back to the pin when the params key is absent (old projects)", () => {
  assert.equal(
    geometrySourceCandidateId(
      { geometry_params: { blade_count: 12 } },
      "cand-pinned-5678",
    ),
    "cand-pinned-5678",
  );
});

test("chip provenance is undefined with neither source nor pin", () => {
  assert.equal(
    geometrySourceCandidateId({ geometry_params: {} }, undefined),
    undefined,
  );
  assert.equal(geometrySourceCandidateId(undefined, undefined), undefined);
});

test("non-string / empty provenance values are ignored, not rendered", () => {
  // A malformed params value must not shadow a valid pin…
  assert.equal(
    geometrySourceCandidateId(
      { geometry_source_candidate_id: 42 },
      "cand-pinned-5678",
    ),
    "cand-pinned-5678",
  );
  assert.equal(
    geometrySourceCandidateId(
      { geometry_source_candidate_id: "" },
      "cand-pinned-5678",
    ),
    "cand-pinned-5678",
  );
  // …and a malformed pin yields no chip suffix at all.
  assert.equal(geometrySourceCandidateId({}, 42), undefined);
  assert.equal(geometrySourceCandidateId({}, ""), undefined);
});

// ---------------------------------------------------------------------------
// 422 error-detail message extraction (run-button toast path + flowpath
// candidate-handoff errors — flowPathJson shares this exact extraction)
// ---------------------------------------------------------------------------

test("structured 422 detail surfaces detail.message, not [object Object]", () => {
  const body = {
    detail: {
      error_code: "INCOMPATIBLE_SETTINGS",
      message:
        "air_standard cycle mode is incompatible with live_meanline co-simulation; choose one.",
      conflicting_components: ["C1"],
    },
  };
  const msg = extractErrorMessage(body, 422);
  assert.ok(!msg.includes("[object Object]"), msg);
  assert.ok(msg.startsWith("air_standard cycle mode is incompatible"), msg);
});

test("plain-string detail passes through verbatim", () => {
  assert.equal(
    extractErrorMessage({ detail: "Project 'nope' not found." }, 404),
    "Project 'nope' not found.",
  );
});

test("structured detail without message falls back to JSON, not [object Object]", () => {
  const msg = extractErrorMessage({ detail: { error_code: "X" } }, 422);
  assert.ok(!msg.includes("[object Object]"), msg);
  assert.equal(msg, '{"error_code":"X"}');
});

test("whole-body string (text fallback / JSON string body) passes through", () => {
  assert.equal(extractErrorMessage("upstream proxy error", 502), "upstream proxy error");
});

test("empty body falls back to the HTTP status", () => {
  assert.equal(extractErrorMessage(undefined, 500), "HTTP 500");
});

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

console.log(`\n${passed + failed} tests: ${passed} passed, ${failed} failed\n`);
if (failed > 0) process.exit(1);
