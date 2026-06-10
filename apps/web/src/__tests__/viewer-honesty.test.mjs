/**
 * Viewer honesty unit tests — stub badge, error overlay, progressive LOD,
 * HUD truth, download gating.
 *
 * Run with: node src/__tests__/viewer-honesty.test.mjs
 *
 * Mirrors (in plain JS, same pattern as filter-dsl.test.mjs — the TS source
 * is authoritative; this guards the runtime behaviour) the predicates in
 * src/components/flowpath/impeller-viewer.tsx:
 *  - Stub badge: shown iff a candidate is picked AND the served mesh is a
 *    server stub (X-Cascade-Stub: true).
 *  - Error overlay: shown iff picked AND the stream errored AND not
 *    currently loading AND not already explained by the stub badge.
 *  - Progressive LOD: upgrade standard → high only after the standard
 *    mesh for THIS pick has rendered and is real (never upgrade a stub).
 *  - HUD: U_tip/r2/b2 derive from the merged geometry; without it the HUD
 *    shows "—" — it never fabricates values from missing candidate keys.
 *  - Download strip: all formats disabled while the mesh is a stub.
 * And in src/lib/three/gltf-loader.ts:
 *  - A failed load for a NEW url clears the stale `current` mesh; a failed
 *    re-load of the SAME url keeps it.
 */

import assert from "node:assert/strict";

// ---------------------------------------------------------------------------
// Mirrors of the impeller-viewer.tsx predicates
// ---------------------------------------------------------------------------

function showStubBadge({ pickedId, showMeridional = false, isStub }) {
  return Boolean(pickedId) && !showMeridional && isStub;
}

function showErrorOverlay({ pickedId, showMeridional = false, error, loading, isStub }) {
  return (
    Boolean(pickedId) && !showMeridional && Boolean(error) && !loading && !isStub
  );
}

function nextMeshUrl({ current, baseUrl, highUrl, crossfade = 1 }) {
  if (
    current &&
    current.url === baseUrl &&
    !current.isStub &&
    highUrl &&
    crossfade >= 1
  ) {
    return highUrl;
  }
  return null; // no upgrade
}

function hudUTip(merged) {
  const r2 = merged?.geometry_params?.impeller_outlet_radius ?? null;
  const rpm = merged?.meanline_rpm_rpm ?? null;
  if (r2 === null || rpm === null) return null;
  return (2 * Math.PI * rpm * r2) / 60;
}

function downloadDisabled({ meshStubbed }) {
  return meshStubbed;
}

// Mirror of the gltf-loader failLoad staleness rule: candidate identity is
// the URL path (lod query ignored). A failed LOD UPGRADE of the on-screen
// candidate keeps the good mesh; a failed load for a DIFFERENT candidate
// clears the stale mesh.
function meshKey(u) {
  return u.split("?")[0];
}

function currentAfterFailedLoad({ current, failedUrl }) {
  if (
    current &&
    current.url !== failedUrl &&
    meshKey(current.url) === meshKey(failedUrl)
  ) {
    return current; // failed LOD upgrade — keep the good mesh
  }
  if (current && current.url !== failedUrl) return null;
  return current;
}

// ---------------------------------------------------------------------------
// Stub badge
// ---------------------------------------------------------------------------

assert.equal(showStubBadge({ pickedId: "c1", isStub: true }), true);
assert.equal(showStubBadge({ pickedId: "c1", isStub: false }), false);
assert.equal(showStubBadge({ pickedId: null, isStub: true }), false);

// ---------------------------------------------------------------------------
// Error overlay
// ---------------------------------------------------------------------------

const err = new Error("422 CANDIDATE_GEOMETRY_INVALID");
assert.equal(
  showErrorOverlay({ pickedId: "c1", error: err, loading: false, isStub: false }),
  true,
);
// While a retry/new load is in flight the overlay yields to the spinner.
assert.equal(
  showErrorOverlay({ pickedId: "c1", error: err, loading: true, isStub: false }),
  false,
);
// The stub badge already explains the situation — don't double-banner.
assert.equal(
  showErrorOverlay({ pickedId: "c1", error: err, loading: false, isStub: true }),
  false,
);
assert.equal(
  showErrorOverlay({ pickedId: null, error: err, loading: false, isStub: false }),
  false,
);

// ---------------------------------------------------------------------------
// Progressive LOD upgrade
// ---------------------------------------------------------------------------

const base = "/api/candidates/c1/geometry?lod=standard";
const high = "/api/candidates/c1/geometry?lod=high";

// Standard mesh for this pick rendered AND crossfade settled → upgrade.
assert.equal(
  nextMeshUrl({ current: { url: base, isStub: false }, baseUrl: base, highUrl: high }),
  high,
);
// Crossfade still running (candidate switch in progress) → DO NOT upgrade:
// swapping the URL mid-fade cancels the fade and leaves the previous
// candidate's mesh at full opacity under this candidate's HUD.
assert.equal(
  nextMeshUrl({
    current: { url: base, isStub: false },
    baseUrl: base,
    highUrl: high,
    crossfade: 0.4,
  }),
  null,
);
// Stub rendered → never upgrade (would re-request a stub at high LOD).
assert.equal(
  nextMeshUrl({ current: { url: base, isStub: true }, baseUrl: base, highUrl: high }),
  null,
);
// Current mesh belongs to the previous pick → no upgrade for this pick yet.
assert.equal(
  nextMeshUrl({
    current: { url: "/api/candidates/c0/geometry?lod=high", isStub: false },
    baseUrl: base,
    highUrl: high,
  }),
  null,
);
// Nothing loaded yet → no upgrade.
assert.equal(nextMeshUrl({ current: null, baseUrl: base, highUrl: high }), null);

// ---------------------------------------------------------------------------
// HUD truth — U_tip from the merged geometry only
// ---------------------------------------------------------------------------

// No merged geometry → null (renders "—"), never a fabricated 96 krpm value.
assert.equal(hudUTip(null), null);
assert.equal(hudUTip({ geometry_params: {}, meanline_rpm_rpm: 70000 }), null);

// Eckardt-scaled example: r2 = 38 mm → rpm = 14000 / (0.038 / 0.2) ≈ 73684,
// U_tip = 2π·rpm/60·r2 ≈ 293 m/s (constant-U2 scaling).
const merged = {
  geometry_params: { impeller_outlet_radius: 0.038 },
  meanline_rpm_rpm: 14000 / (0.038 / 0.2),
};
const uTip = hudUTip(merged);
assert.ok(Math.abs(uTip - 293.2) < 1.0, `U_tip ${uTip} should be ~293 m/s`);

// ---------------------------------------------------------------------------
// Download gating
// ---------------------------------------------------------------------------

assert.equal(downloadDisabled({ meshStubbed: true }), true);
assert.equal(downloadDisabled({ meshStubbed: false }), false);

// ---------------------------------------------------------------------------
// Stale-mesh clearing on failed load
// ---------------------------------------------------------------------------

const prevMesh = { url: "/api/candidates/c0/geometry?lod=high", isStub: false };
// New candidate's fetch failed → the old candidate's mesh must NOT stay
// on screen under the new candidate's HUD.
assert.equal(currentAfterFailedLoad({ current: prevMesh, failedUrl: base }), null);
// Re-fetch of the SAME url failed (e.g. transient) → keep what we have.
assert.equal(
  currentAfterFailedLoad({ current: prevMesh, failedUrl: prevMesh.url }),
  prevMesh,
);
assert.equal(currentAfterFailedLoad({ current: null, failedUrl: base }), null);
// Failed HIGH upgrade of the SAME candidate → keep the good standard mesh
// (it rendered fine; a false "generation failed" must not replace it).
const stdMesh = { url: base, isStub: false };
assert.equal(
  currentAfterFailedLoad({ current: stdMesh, failedUrl: high }),
  stdMesh,
);

console.log("viewer-honesty.test.mjs: all assertions passed");
