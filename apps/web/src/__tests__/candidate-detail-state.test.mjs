/**
 * U8 unit tests — candidate detail state classification + runs adaptation.
 *
 * Run with: node src/__tests__/candidate-detail-state.test.mjs
 *
 * Mirrors (in plain JS, same pattern as filter-dsl.test.mjs — the TS source
 * is authoritative; this guards the runtime behaviour):
 *  - `classifyCandidateDetail` in src/lib/flowpath/candidate-detail.ts:
 *    loading / ok / stale / expired / cross-project / error mapping for the
 *    deep-linkable candidate detail route.
 *  - `objectiveDisplay` sentinel handling: the M_rel 9.99 marker and the
 *    zeroed objectives of non-VALID candidates render as "—", never as
 *    numbers.
 *  - `handoffDisabledReason`: non-VALID candidates and no-Compressor
 *    projects disable "Send to cycle" with a reason.
 *  - `adaptJobToRunRecord` in src/lib/api/client.ts: backend JobModel →
 *    RunRecord status mapping (done→succeeded; refusals keep failed +
 *    gain `refused`), explore `best_id` extraction, duration derivation.
 */

import assert from "node:assert/strict";

// ---------------------------------------------------------------------------
// Mirror of classifyCandidateDetail (src/lib/flowpath/candidate-detail.ts)
// ---------------------------------------------------------------------------

function classifyCandidateDetail({ outcome, routeProjectId, latestExploreJobId }) {
  if (outcome === null) return "loading";
  if (outcome.kind === "not-found") return "expired";
  if (outcome.kind === "error") return "error";
  const cand = outcome.candidate;
  if (!cand.project_id || cand.project_id !== routeProjectId) {
    return "cross-project";
  }
  if (latestExploreJobId !== null && cand.job_id !== latestExploreJobId) {
    return "stale";
  }
  return "ok";
}

const M_REL_SENTINEL = 9.99;

function objectiveDisplay(key, value, status, decimals = 4) {
  if (value === undefined || !Number.isFinite(value)) {
    return { text: "—", sentinel: true };
  }
  if (key === "M_rel" && Math.abs(value - M_REL_SENTINEL) < 1e-9) {
    return { text: "—", sentinel: true };
  }
  if (status !== "VALID" && value === 0) {
    return { text: "—", sentinel: true };
  }
  return { text: value.toFixed(decimals), sentinel: false };
}

function handoffDisabledReason({ candidate, hasCompressor }) {
  if (!candidate) return "Candidate not loaded.";
  if (candidate.status === "MANUFACTURABILITY_FAILED") {
    // The design point solved fine — the geometry just can't be made.
    return (
      "This candidate cannot be produced on a standard 5-axis machining " +
      "cell — an unmakeable geometry cannot honestly drive the cycle " +
      "co-simulation. Loosen the manufacturability overrides and re-run " +
      "the exploration to reconsider it."
    );
  }
  if (candidate.status !== "VALID") {
    return (
      "This candidate's own design point refused " +
      `(${candidate.status}) — its geometry cannot honestly drive the ` +
      "cycle co-simulation."
    );
  }
  if (hasCompressor === false) {
    return (
      "This project's cycle canvas has no Compressor component to " +
      "receive the geometry. Add one on the Cycle page first."
    );
  }
  return null;
}

// ---------------------------------------------------------------------------
// Mirror of adaptJobToRunRecord (src/lib/api/client.ts)
// ---------------------------------------------------------------------------

const RUN_KINDS = new Set(["cycle", "explore", "analysis", "map", "rotor"]);

function adaptJobToRunRecord(job) {
  const kind = RUN_KINDS.has(job.kind) ? job.kind : "cycle";
  const status =
    job.status === "done"
      ? "succeeded"
      : job.status === "failed"
        ? "failed"
        : job.status === "cancelled"
          ? "cancelled"
          : job.status === "running"
            ? "running"
            : "queued";
  const startedMs = Date.parse(job.created_at);
  const finishedMs = job.finished_at ? Date.parse(job.finished_at) : NaN;
  const durationMs =
    Number.isFinite(startedMs) && Number.isFinite(finishedMs)
      ? Math.max(0, finishedMs - startedMs)
      : undefined;
  const result = job.result ?? undefined;
  const refused =
    job.status === "failed" &&
    job.error == null &&
    Boolean(result && typeof result === "object" && "failure" in result);
  const bestId =
    kind === "explore" && typeof result?.best_id === "string"
      ? result.best_id
      : undefined;
  return {
    id: job.id,
    kind,
    status,
    startedAt: job.created_at,
    finishedAt: job.finished_at ?? undefined,
    durationMs,
    summary: job.message || undefined,
    bestCandidateId: bestId,
    refused: refused || undefined,
  };
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const CAND = {
  id: "abc123",
  job_id: "job-latest",
  project_id: "proj-a",
  index: 4,
  params: { rotor_outlet_radius: 0.03, blade_count: 14, tip_clearance: 2e-4 },
  objectives: { eta_tt: 0.8712, eta_ts: 0.8011, power: 31.2, mass: 0.41, M_rel: 0.92 },
  constraints: { M_rel_under_choke: true },
  status: "VALID",
};

// ---------------------------------------------------------------------------
// classifyCandidateDetail
// ---------------------------------------------------------------------------

// Loading: fetch in flight.
assert.equal(
  classifyCandidateDetail({
    outcome: null,
    routeProjectId: "proj-a",
    latestExploreJobId: null,
  }),
  "loading",
);

// OK: resolvable, right project, latest job.
assert.equal(
  classifyCandidateDetail({
    outcome: { kind: "ok", candidate: CAND },
    routeProjectId: "proj-a",
    latestExploreJobId: "job-latest",
  }),
  "ok",
);

// OK when recency is unknowable (no runs yet): never falsely stale.
assert.equal(
  classifyCandidateDetail({
    outcome: { kind: "ok", candidate: CAND },
    routeProjectId: "proj-a",
    latestExploreJobId: null,
  }),
  "ok",
);

// Stale: resolvable but from a non-latest exploration job.
assert.equal(
  classifyCandidateDetail({
    outcome: { kind: "ok", candidate: { ...CAND, job_id: "job-old" } },
    routeProjectId: "proj-a",
    latestExploreJobId: "job-latest",
  }),
  "stale",
);

// Expired: 404 — unknown id or restart-expired both land here.
assert.equal(
  classifyCandidateDetail({
    outcome: { kind: "not-found" },
    routeProjectId: "proj-a",
    latestExploreJobId: "job-latest",
  }),
  "expired",
);

// Cross-project: candidate exists but belongs to another project.
assert.equal(
  classifyCandidateDetail({
    outcome: { kind: "ok", candidate: { ...CAND, project_id: "proj-b" } },
    routeProjectId: "proj-a",
    latestExploreJobId: "job-latest",
  }),
  "cross-project",
);

// Missing project_id (out-of-date server) is treated as foreign, not ok.
assert.equal(
  classifyCandidateDetail({
    outcome: { kind: "ok", candidate: { ...CAND, project_id: undefined } },
    routeProjectId: "proj-a",
    latestExploreJobId: null,
  }),
  "cross-project",
);

// Network error is distinct from not-found.
assert.equal(
  classifyCandidateDetail({
    outcome: { kind: "error", message: "boom" },
    routeProjectId: "proj-a",
    latestExploreJobId: null,
  }),
  "error",
);

// ---------------------------------------------------------------------------
// objectiveDisplay sentinel handling
// ---------------------------------------------------------------------------

// The M_rel 9.99 sentinel never renders as a real number.
assert.deepEqual(objectiveDisplay("M_rel", 9.99, "REGIME_OUT_OF_VALIDITY"), {
  text: "—",
  sentinel: true,
});
// ...even if a sentinel somehow rides on a VALID record.
assert.deepEqual(objectiveDisplay("M_rel", 9.99, "VALID"), {
  text: "—",
  sentinel: true,
});

// Zeroed objectives on a non-VALID candidate are sentinels.
assert.deepEqual(objectiveDisplay("eta_tt", 0, "NON_CONVERGED"), {
  text: "—",
  sentinel: true,
});

// Zero on a VALID candidate is a real number (e.g. mass of 0 would be a
// solver value, not a sentinel) — formatting still applies.
assert.deepEqual(objectiveDisplay("eta_tt", 0, "VALID"), {
  text: "0.0000",
  sentinel: false,
});

// Real values format with the requested precision.
assert.deepEqual(objectiveDisplay("eta_tt", 0.87123, "VALID"), {
  text: "0.8712",
  sentinel: false,
});

// Missing / non-finite values are placeholders.
assert.deepEqual(objectiveDisplay("power", undefined, "VALID"), {
  text: "—",
  sentinel: true,
});
assert.deepEqual(objectiveDisplay("power", NaN, "VALID"), {
  text: "—",
  sentinel: true,
});

// ---------------------------------------------------------------------------
// handoffDisabledReason
// ---------------------------------------------------------------------------

assert.equal(
  handoffDisabledReason({ candidate: CAND, hasCompressor: true }),
  null,
);
assert.equal(
  handoffDisabledReason({ candidate: CAND, hasCompressor: null }),
  null, // components still loading — don't pre-emptively disable
);
assert.match(
  handoffDisabledReason({
    candidate: { ...CAND, status: "REGIME_OUT_OF_VALIDITY" },
    hasCompressor: true,
  }),
  /design point refused/,
);
assert.match(
  handoffDisabledReason({ candidate: CAND, hasCompressor: false }),
  /no Compressor component/,
);
// MANUFACTURABILITY_FAILED solved fine — the reason must say "can't be
// made", not "design point refused".
assert.match(
  handoffDisabledReason({
    candidate: { ...CAND, status: "MANUFACTURABILITY_FAILED" },
    hasCompressor: true,
  }),
  /standard 5-axis machining/,
);
assert.match(
  handoffDisabledReason({ candidate: null, hasCompressor: true }),
  /not loaded/,
);

// ---------------------------------------------------------------------------
// adaptJobToRunRecord
// ---------------------------------------------------------------------------

const T0 = "2026-06-09T10:00:00+00:00";
const T1 = "2026-06-09T10:00:02.500000+00:00";

// done → succeeded, with duration derived from timestamps.
{
  const r = adaptJobToRunRecord({
    id: "j1",
    project_id: "p",
    kind: "cycle",
    status: "done",
    progress: 1,
    message: "Completed.",
    created_at: T0,
    updated_at: T1,
    finished_at: T1,
    error: null,
    result: { converged: true },
  });
  assert.equal(r.status, "succeeded");
  assert.equal(r.kind, "cycle");
  assert.equal(r.durationMs, 2500);
  assert.equal(r.refused, undefined);
  assert.equal(r.bestCandidateId, undefined);
}

// Refused cycle run (U1 contract: failed + error null + result.failure)
// shows failed AND carries the refused qualifier.
{
  const r = adaptJobToRunRecord({
    id: "j2",
    project_id: "p",
    kind: "cycle",
    status: "failed",
    progress: 1,
    message: "Cycle canvas is missing required components: Compressor.",
    created_at: T0,
    updated_at: T1,
    finished_at: T1,
    error: null,
    result: { converged: false, failure: { kind: "design" } },
  });
  assert.equal(r.status, "failed");
  assert.equal(r.refused, true);
  assert.match(r.summary, /missing required components/);
}

// Crash (error set, no envelope) is failed but NOT refused.
{
  const r = adaptJobToRunRecord({
    id: "j3",
    project_id: "p",
    kind: "cycle",
    status: "failed",
    progress: 0.4,
    message: "RuntimeError: boom",
    created_at: T0,
    updated_at: T1,
    finished_at: T1,
    error: "RuntimeError: boom",
    result: null,
  });
  assert.equal(r.status, "failed");
  assert.equal(r.refused, undefined);
}

// Explore job exposes best_id for the candidate-detail deep link.
{
  const r = adaptJobToRunRecord({
    id: "j4",
    project_id: "p",
    kind: "explore",
    status: "done",
    progress: 1,
    message: "Completed.",
    created_at: T0,
    updated_at: T1,
    finished_at: T1,
    error: null,
    result: { n_candidates: 8, n_valid: 8, best_id: "cand-77" },
  });
  assert.equal(r.kind, "explore");
  assert.equal(r.bestCandidateId, "cand-77");
}

// Explore with no valid candidates (best_id null) → no link.
{
  const r = adaptJobToRunRecord({
    id: "j5",
    project_id: "p",
    kind: "explore",
    status: "done",
    progress: 1,
    message: "Completed.",
    created_at: T0,
    updated_at: T1,
    finished_at: T1,
    error: null,
    result: { n_candidates: 8, n_valid: 0, best_id: null },
  });
  assert.equal(r.bestCandidateId, undefined);
}

// cancelled / running / queued pass through.
for (const [backend, ui] of [
  ["cancelled", "cancelled"],
  ["running", "running"],
  ["queued", "queued"],
]) {
  const r = adaptJobToRunRecord({
    id: "jx",
    project_id: "p",
    kind: "map",
    status: backend,
    progress: 0,
    message: "",
    created_at: T0,
    updated_at: T0,
    finished_at: null,
    error: null,
    result: null,
  });
  assert.equal(r.status, ui);
  assert.equal(r.durationMs, undefined);
}

console.log("candidate-detail-state.test.mjs: all assertions passed");
