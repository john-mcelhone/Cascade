# Release record — feat/small-gas-turbine-release

PR could not be opened from this environment (no valid GitHub credentials: gh CLI absent, no SSH key, keychain token rejected). This file is the durable record of the prepared PR description and the review residuals until the PR exists.

Prepared PR title: `feat: small-gas-turbine release hardening and capability`

---

## Summary

Cascade now refuses honestly, persists deterministically, and carries its first end-to-end natural-gas capability paths. Before this branch, a blank project "solved" successfully with zero efficiency, the production web build failed, test runs polluted `~/.cascade/projects`, the README claimed two solvers that do not exist, and the Cycle page offered modes the solver never saw. All of that is fixed at root cause, and the project gains its public strategy documents.

## What is now possible

- **Specify fuel, get temperature.** The burner's fuel-mass-flow mode works end to end: set ṁ_fuel, run, and the back-derived turbine inlet temperature appears on the canvas with a computed-value tint. Degenerate inputs (zero, negative, NaN, missing) refuse with plain-English design messages; incompatible projects get a synchronous 422 and a disabled control with the reason.
- **Deep-link a candidate.** Every design-exploration candidate has a shareable URL with the merged geometry actually used, objectives with sentinel-safe rendering, candidate-scoped manufacturability, exports, and designed states for unknown, expired, stale, and cross-project ids.
- **Send a candidate to the cycle.** The handoff writes the normatively merged geometry, the candidate's rpm, and (default on, confirmable) an aligned operating point including the consistent turbine pressure ratio — so explore → send → live mean-line → solve converges as shipped. Pinning persists; detach is the escape hatch.
- **See where every η came from.** The result panel attributes each rotor's efficiency to live mean-line or isentropic, and a fallback is visibly flagged — never silent.

## Design decisions

- **Three-class job taxonomy.** Runs that produce no result end `failed` carrying the structured failure envelope (`error == null` + `result.failure` is the refusal signature); non-converged runs stay `done` with their envelope; crashes are `failed` with `error` set. The FailurePanel keeps working because the envelope rides on failed jobs.
- **Refusal over silent fallback (ADAPT-045).** Geometry that is attached but invalid (missing or non-finite required fields) refuses with the field names, in both rotor builders; absent geometry still falls back, now flagged in the payload. Two pinned tests changed under the strictly-more-restrictive rule and the change is recorded in the internal adaptations ledger.
- **Deterministic persistence.** Component PATCH, add, delete, and detach are save-through with serializability validation (a JSON null can no longer poison the TOML store); worker terminal paths save the run badge but a disk failure can never reclassify a refusal or converged result as a crash.
- **Strategy in public.** `docs/research/competitive-landscape.md` (public sources only, dated and hedged pricing) and `ROADMAP.md` (every deferred item anchored to a stable KG-ID, honest served-segment statement) anchor the small-gas-turbine positioning.

## Contract changes (release notes)

- Cycle refusals now end `failed` (previously `done` with η=0). External pollers keying on `done` should branch on the refusal signature instead.
- Projects with partial `geometry_params` bags refuse instead of silently solving at constant η (intentional, ADAPT-045; escape hatches: detach endpoint or a fresh handoff).
- `GET /api/jobs` returns newest-first and accepts `project_id`.

## Test plan

- Core suite 991 passed (34 expected OCC skips, 1 expected xfail), validation pass-gates 130 passed, API contract suite 89 passed (was 28 with 1 failure before the branch), web unit suites green, `tsc --noEmit` clean, production build green, citations gate green. `make ci` now chains all of it.
- 60+ new contract tests: refusal taxonomy matrix (incl. cancel races and disk-failure reclassification), burner params-bag matrix, handoff replace/alignment/reload-survival, manufacturability candidate routing, SSE strict-JSON wire format, storage isolation meta-tests.
- Browser-level automation (`agent-browser`) is not installed on this machine; the candidate-detail and handoff flows were manually verified against live servers during implementation.

## Post-Deploy Monitoring & Validation

Self-hosted single-user app; no production deployment exists yet. On any deployed instance: watch the API log for `_save_last_run_status` warnings (disk-persistence degradation), `NON_SERIALIZABLE_PARAM` 422s (clients sending nulls), and `ALIGNMENT_SOLVE_FAILED` rates (candidates that cannot align); healthy signal is refusals presenting as FailurePanel explanations rather than red crash toasts. Rollback is a branch revert; the TOML store has no migrations.

## Known residuals (accepted, tracked for follow-up)

- `apps/api/routers/cycle.py` (~1,600 lines) and `apps/web/src/lib/api/client.ts` (~2,000 lines) want decomposition; concrete extraction seams identified in review.
- The `ApiClient` interface does not cover the new flowpath handoff surface (lives in `flowpath.ts`).
- Pinned-candidate snapshots persist but have no post-restart reader; candidates remain ephemeral by design.
- No per-project lock: concurrent saves are last-writer-wins (single-user posture; documented).
- Run-button cancel does not call the cancel endpoint (pre-existing); double-click double-job window (pre-existing).
- Test-helper duplication across the four new API test files.
