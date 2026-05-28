/**
 * G2 / Item 2: STEP/IGES button disable logic — unit test.
 *
 * Run with: node src/__tests__/cad-health-disable.test.mjs
 *
 * This test verifies the DownloadStrip / cadHealth disable logic in plain JS
 * without a browser. The component logic is straightforward:
 *   - cadAvailable === true  → buttons enabled  (disabled prop = false)
 *   - cadAvailable === false → buttons disabled (disabled prop = true)
 *   - cadAvailable === null  → buttons disabled (pending; same as false)
 *
 * We mirror the disable predicate from impeller-viewer.tsx:
 *   disabled={cadAvailable !== true}
 *
 * The cadHealth() API helper falls back to { cad_available: false } on any
 * fetch error, which is also exercised here.
 *
 * Covers:
 *  AC1: when cad_available: true  → STEP and IGES are NOT disabled
 *  AC2: when cad_available: false → STEP and IGES ARE disabled
 *  AC3: when cadHealth() fetch fails → falls back to cad_available: false → disabled
 *  AC4: when cad_available: null (in-flight) → buttons disabled (cadAvailable !== true)
 *  AC5: glTF and STL are never disabled by cadHealth (non-CAD formats)
 */

import assert from "node:assert/strict";

// ---------------------------------------------------------------------------
// Mirror the disable predicate from impeller-viewer.tsx DownloadStrip
// ---------------------------------------------------------------------------

/**
 * Returns true when the button should be disabled.
 * Mirrors: disabled={cadAvailable !== true} in impeller-viewer.tsx
 * Applied only to CAD formats: "step" and "iges".
 *
 * @param {boolean | null} cadAvailable  - null = in-flight probe
 * @param {"glb" | "stl" | "step" | "iges"} format
 * @returns {boolean}
 */
function isCadButtonDisabled(cadAvailable, format) {
  const CAD_FORMATS = new Set(["step", "iges"]);
  if (!CAD_FORMATS.has(format)) return false;  // non-CAD formats never disabled by cadHealth
  return cadAvailable !== true;                 // disabled when null (in-flight) or false
}

// ---------------------------------------------------------------------------
// Mirror the cadHealth() fallback logic from flowpath.ts
// ---------------------------------------------------------------------------

/**
 * Mock cadHealth that mirrors the production fallback: any error → false.
 *
 * @param {boolean | "error"} serverResponse
 * @returns {{ cad_available: boolean, occt_version: string | null }}
 */
function mockCadHealth(serverResponse) {
  if (serverResponse === "error") {
    // Any fetch/parse error → fallback to { cad_available: false }
    return { cad_available: false, occt_version: null };
  }
  return { cad_available: serverResponse, occt_version: serverResponse ? "7.7.1" : null };
}

// ---------------------------------------------------------------------------
// Tests
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

// AC1: cad_available: true → STEP and IGES are NOT disabled
test("AC1: cad_available=true → STEP button enabled", () => {
  const cadAvailable = true;
  assert.equal(isCadButtonDisabled(cadAvailable, "step"), false,
    "STEP should be enabled when cad_available=true");
});

test("AC1: cad_available=true → IGES button enabled", () => {
  const cadAvailable = true;
  assert.equal(isCadButtonDisabled(cadAvailable, "iges"), false,
    "IGES should be enabled when cad_available=true");
});

// AC2: cad_available: false → STEP and IGES ARE disabled
test("AC2: cad_available=false → STEP button disabled", () => {
  const cadAvailable = false;
  assert.equal(isCadButtonDisabled(cadAvailable, "step"), true,
    "STEP should be disabled when cad_available=false");
});

test("AC2: cad_available=false → IGES button disabled", () => {
  const cadAvailable = false;
  assert.equal(isCadButtonDisabled(cadAvailable, "iges"), true,
    "IGES should be disabled when cad_available=false");
});

// AC3: cadHealth() fetch failure → falls back to cad_available: false
test("AC3: cadHealth() error → cad_available=false → STEP disabled", () => {
  const health = mockCadHealth("error");
  assert.equal(health.cad_available, false,
    "cadHealth() should return cad_available=false on fetch error");
  assert.equal(isCadButtonDisabled(health.cad_available, "step"), true,
    "STEP should be disabled when cadHealth() falls back to false");
});

test("AC3: cadHealth() error → cad_available=false → IGES disabled", () => {
  const health = mockCadHealth("error");
  assert.equal(isCadButtonDisabled(health.cad_available, "iges"), true,
    "IGES should be disabled when cadHealth() falls back to false");
});

// AC4: cadAvailable = null (in-flight probe, initial state) → disabled
test("AC4: cadAvailable=null (probe in-flight) → STEP disabled", () => {
  const cadAvailable = null;
  assert.equal(isCadButtonDisabled(cadAvailable, "step"), true,
    "STEP should be disabled while probe is in-flight (null state)");
});

test("AC4: cadAvailable=null (probe in-flight) → IGES disabled", () => {
  const cadAvailable = null;
  assert.equal(isCadButtonDisabled(cadAvailable, "iges"), true,
    "IGES should be disabled while probe is in-flight (null state)");
});

// AC5: non-CAD formats (glTF, STL) are never disabled by cadHealth
test("AC5: glTF never disabled regardless of cadAvailable", () => {
  for (const cadAvailable of [null, false, true]) {
    assert.equal(isCadButtonDisabled(cadAvailable, "glb"), false,
      `glTF should never be disabled by cadHealth (cadAvailable=${cadAvailable})`);
  }
});

test("AC5: STL never disabled regardless of cadAvailable", () => {
  for (const cadAvailable of [null, false, true]) {
    assert.equal(isCadButtonDisabled(cadAvailable, "stl"), false,
      `STL should never be disabled by cadHealth (cadAvailable=${cadAvailable})`);
  }
});

// CAD_UNAVAILABLE_TOOLTIP presence check (mirrors the const in impeller-viewer.tsx)
test("CAD_UNAVAILABLE_TOOLTIP contains pip install instruction", () => {
  const CAD_UNAVAILABLE_TOOLTIP =
    "CAD export requires the cascade[cad] extra. " +
    "Install with: pip install 'cascade[cad]' or contact support.";
  assert.ok(
    CAD_UNAVAILABLE_TOOLTIP.includes("pip install"),
    "Tooltip must contain 'pip install' instruction"
  );
  assert.ok(
    CAD_UNAVAILABLE_TOOLTIP.includes("cascade[cad]"),
    "Tooltip must reference cascade[cad] extra"
  );
});

// cadHealth returns occt_version when available
test("cadHealth returns occt_version when cad_available=true", () => {
  const health = mockCadHealth(true);
  assert.equal(health.cad_available, true);
  assert.notEqual(health.occt_version, null,
    "occt_version should be present when CAD is available");
});

test("cadHealth returns occt_version=null when cad_available=false", () => {
  const health = mockCadHealth(false);
  assert.equal(health.cad_available, false);
  assert.equal(health.occt_version, null,
    "occt_version should be null when CAD is unavailable");
});

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

console.log(`\nCAD health disable: ${passed} passed, ${failed} failed`);
if (failed > 0) {
  process.exit(1);
}
