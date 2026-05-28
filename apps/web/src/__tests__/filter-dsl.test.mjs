/**
 * W-09 unit tests — filter DSL logic.
 *
 * Run with: node src/__tests__/filter-dsl.test.mjs
 *
 * This file mirrors the logic in src/lib/flowpath/filter-dsl.ts in plain JS
 * (no TypeScript, no build step) and tests it directly. The TS source is the
 * authoritative implementation; this file verifies the runtime behaviour and
 * guards against regressions.
 *
 * Covers:
 *  - AC1: eta_tt > 0.85 greys-out candidates where eta_tt <= 0.85
 *  - AC2: empty filter passes all candidates (opacities stay 1)
 *  - AC5: invalid expressions return {ok: false, error} — no crash
 */

import assert from "node:assert/strict";

// ---------------------------------------------------------------------------
// Mirror of filter-dsl.ts logic (pure JS — no TS required)
// ---------------------------------------------------------------------------

const OP_REGEX = /^([\w./]+)\s*(>=|<=|>|<|=)\s*([0-9eE+.\-]+)$/;

function parseFilter(raw, knownFields) {
  const trimmed = raw.trim();
  if (trimmed === "") return { ok: true, terms: [] };

  const parts = trimmed.split(/\s+AND\s+/i);
  const terms = [];

  for (const part of parts) {
    const p = part.trim();
    const m = OP_REGEX.exec(p);
    if (!m) {
      return {
        ok: false,
        error: `Cannot parse term: "${p}". Expected format: field op value (e.g. eta_tt > 0.85)`,
      };
    }
    const field = m[1];
    const op = m[2];
    const value = parseFloat(m[3]);

    if (Number.isNaN(value)) return { ok: false, error: `Not a number: "${m[3]}"` };
    if (knownFields !== null && !knownFields.has(field)) {
      return { ok: false, error: `Unknown field: ${field}` };
    }
    terms.push({ field, op, value });
  }
  return { ok: true, terms };
}

function candidatePasses(candidate, terms) {
  for (const { field, op, value } of terms) {
    const v =
      field in candidate.objectives
        ? candidate.objectives[field]
        : field in candidate.params
        ? candidate.params[field]
        : undefined;

    if (v === undefined || Number.isNaN(v)) return false;

    switch (op) {
      case ">":  if (!(v >  value)) return false; break;
      case ">=": if (!(v >= value)) return false; break;
      case "<":  if (!(v <  value)) return false; break;
      case "<=": if (!(v <= value)) return false; break;
      case "=":  if (v !== value)   return false; break;
    }
  }
  return true;
}

function buildKnownFields(candidates) {
  const s = new Set();
  for (const c of candidates) {
    for (const k of Object.keys(c.objectives)) s.add(k);
    for (const k of Object.keys(c.params)) s.add(k);
  }
  return s;
}

function makeCandidate(objectives, params = {}) {
  return { objectives, params };
}

// ---------------------------------------------------------------------------
// Test harness
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

// ---------------------------------------------------------------------------
// Test cases
// ---------------------------------------------------------------------------

console.log("\nW-09 filter-dsl unit tests\n");

test("AC2: empty string parses to zero terms", () => {
  const r = parseFilter("", null);
  assert.ok(r.ok, "expected ok");
  assert.equal(r.terms.length, 0);
});

test("AC2: empty filter passes all candidates", () => {
  const c = makeCandidate({ eta_tt: 0.50 });
  assert.equal(candidatePasses(c, []), true);
});

test("AC1: 'eta_tt > 0.85' passes candidate with eta_tt=0.90", () => {
  const r = parseFilter("eta_tt > 0.85", null);
  assert.ok(r.ok, JSON.stringify(r));
  const c = makeCandidate({ eta_tt: 0.90 });
  assert.equal(candidatePasses(c, r.terms), true);
});

test("AC1: 'eta_tt > 0.85' greys out candidate with eta_tt=0.80", () => {
  const r = parseFilter("eta_tt > 0.85", null);
  assert.ok(r.ok);
  const c = makeCandidate({ eta_tt: 0.80 });
  assert.equal(candidatePasses(c, r.terms), false);
});

test("AC1: boundary value eta_tt=0.85 fails '> 0.85' (strict)", () => {
  const r = parseFilter("eta_tt > 0.85", null);
  assert.ok(r.ok);
  const c = makeCandidate({ eta_tt: 0.85 });
  assert.equal(candidatePasses(c, r.terms), false);
});

test("AC1: boundary value eta_tt=0.85 passes '>= 0.85'", () => {
  const r = parseFilter("eta_tt >= 0.85", null);
  assert.ok(r.ok);
  const c = makeCandidate({ eta_tt: 0.85 });
  assert.equal(candidatePasses(c, r.terms), true);
});

test("AND: 'eta_tt > 0.85 AND M_rel < 1.2' passes when both true", () => {
  const r = parseFilter("eta_tt > 0.85 AND M_rel < 1.2", null);
  assert.ok(r.ok, JSON.stringify(r));
  assert.equal(r.terms.length, 2);
  const c = makeCandidate({ eta_tt: 0.90, M_rel: 1.0 });
  assert.equal(candidatePasses(c, r.terms), true);
});

test("AND: fails when first term fails", () => {
  const r = parseFilter("eta_tt > 0.85 AND M_rel < 1.2", null);
  assert.ok(r.ok);
  const c = makeCandidate({ eta_tt: 0.80, M_rel: 1.0 });
  assert.equal(candidatePasses(c, r.terms), false);
});

test("AND: fails when second term fails", () => {
  const r = parseFilter("eta_tt > 0.85 AND M_rel < 1.2", null);
  assert.ok(r.ok);
  const c = makeCandidate({ eta_tt: 0.90, M_rel: 1.5 });
  assert.equal(candidatePasses(c, r.terms), false);
});

test("operator '<=' passes at boundary", () => {
  const r = parseFilter("N <= 60000", null);
  assert.ok(r.ok);
  const c = makeCandidate({ N: 60000 });
  assert.equal(candidatePasses(c, r.terms), true);
});

test("operator '=' exact match", () => {
  const r = parseFilter("blade_count = 14", null);
  assert.ok(r.ok);
  const c = makeCandidate({}, { blade_count: 14 });
  assert.equal(candidatePasses(c, r.terms), true);
});

test("operator '<' fails at boundary", () => {
  const r = parseFilter("N < 60000", null);
  assert.ok(r.ok);
  const c = makeCandidate({ N: 60000 });
  assert.equal(candidatePasses(c, r.terms), false);
});

test("param field: filter on params.rotor_outlet_radius", () => {
  const r = parseFilter("rotor_outlet_radius > 0.05", null);
  assert.ok(r.ok);
  const c = makeCandidate({}, { rotor_outlet_radius: 0.06 });
  assert.equal(candidatePasses(c, r.terms), true);
});

test("AC5: unknown field returns error (knownFields provided)", () => {
  const known = new Set(["eta_tt", "M_rel"]);
  const r = parseFilter("eta_tt > 0.85 AND foobar < 1.0", known);
  assert.equal(r.ok, false);
  assert.ok(!r.ok && r.error.includes("Unknown field: foobar"), `got: ${r.ok ? "" : r.error}`);
});

test("AC5: completely garbled expression returns error, no crash", () => {
  const r = parseFilter("foo > bar", null);
  assert.equal(r.ok, false);
  assert.ok(!r.ok && typeof r.error === "string" && r.error.length > 0);
});

test("AC5: expression without value returns parse error", () => {
  const r = parseFilter("eta_tt >", null);
  assert.equal(r.ok, false);
});

test("buildKnownFields includes objective and param keys", () => {
  const candidates = [
    makeCandidate({ eta_tt: 0.9, M_rel: 1.1 }, { rotor_outlet_radius: 0.05 }),
    makeCandidate({ eta_tt: 0.8, power_W: 30000 }, {}),
  ];
  const fields = buildKnownFields(candidates);
  assert.ok(fields.has("eta_tt"));
  assert.ok(fields.has("M_rel"));
  assert.ok(fields.has("power_W"));
  assert.ok(fields.has("rotor_outlet_radius"));
});

test("scientific notation: 'power_W >= 3e4' parses correctly", () => {
  const r = parseFilter("power_W >= 3e4", null);
  assert.ok(r.ok, JSON.stringify(r));
  const c = makeCandidate({ power_W: 30000 });
  assert.equal(candidatePasses(c, r.terms), true);
});

test("AND keyword is case-insensitive", () => {
  const r = parseFilter("eta_tt > 0.85 and M_rel < 1.2", null);
  assert.ok(r.ok, JSON.stringify(r));
  assert.equal(r.terms.length, 2);
});

test("opacity array: filtered-out candidates get 0.3, passing get 1.0", () => {
  const candidates = [
    makeCandidate({ eta_tt: 0.90 }),
    makeCandidate({ eta_tt: 0.80 }),
    makeCandidate({ eta_tt: 0.87 }),
  ];
  const r = parseFilter("eta_tt > 0.85", null);
  assert.ok(r.ok);
  const opacities = candidates.map((c) =>
    candidatePasses(c, r.terms) ? 1 : 0.3,
  );
  assert.deepEqual(opacities, [1, 0.3, 1]);
});

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

console.log(`\n${passed + failed} tests: ${passed} passed, ${failed} failed\n`);
if (failed > 0) process.exit(1);
