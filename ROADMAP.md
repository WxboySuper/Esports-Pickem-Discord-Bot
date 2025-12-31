# MatchPoint Roadmap

## Overview

MatchPoint v1.0 is a production Discord bot for picks/contests (currently supports League of Legends). This roadmap captures planned refactors, feature milestones, and priorities to expand supported titles, improve reliability, and build admin/user-facing web tooling.

## Goals

- Expand PandaScore-backed title support (CS2, Valorant, Rocket League, Dota2) using a reusable adapter template.
- Improve reliability: accurate rate-limit tracking, internal feature flags, stronger test coverage.
- Provide admin operations tooling (internal dashboard) and later a public-facing website.
- Defer advanced live/paid statistics until feasibility/cost is evaluated.

## Versioning Policy

- Follow a lightweight semantic approach: `MAJOR.MINOR.PATCH`.
  - MINOR bump for each new supported title or large feature (e.g., v1.1 = CS2).
  - PATCH for small command changes, bugfixes, tests.
  - MAJOR only for breaking changes.

## Milestones

### Milestone A — Refactor & Hardening (Adapter Template)

Purpose: create a robust, testable foundation so new titles can be added quickly and safely.

Scope:

- Refactor parsing into modular pieces: core parsing helpers + per-game parser files. Use the current LoL parser as the adapter template.
- Move game-specific logic into `parsers/` (or equivalent) files (example: `parsers/lol.py`).
- Fix rate-limit monitor: track the actual reset/lift time from API responses (not inferred counters), persist across restarts if needed, and add automatic backoff/retry.
- Implement internal feature flags (config-driven, toggle per-title or per-feature) for quick rollback or staged rollout.
- Strengthen tests: add unit/integration tests for parser modules, rate-limit behavior, and feature-flag gating. Add fixtures/mocked PandaScore responses.

Deliverables:

- New parser structure and LoL adapter refactor.
- Reliable rate-limit monitor with tests and documented behavior.
- Feature-flag implementation and toggle examples.
- Test coverage improved to cover parsing, polling, and edge-cases.

Acceptance criteria:

- New parser module used by production flows with no regression on LoL features.
- Rate-limit monitor reports actual reset times and avoids over-requesting.
- Tests run in CI with recorded API fixtures; coverage increased for key modules.

Estimated effort: 2–4 weeks (depending on availability and test polish).

### Milestone B — Title Expansion (Incremental)

Purpose: add new games using the LoL adapter template and established patterns.

Scope (per-title pipeline):

- Implement `parsers/<title>.py` using the LoL adapter as a template.
- Add per-title config (enable/disable, pick window defaults, BO rules).
- Add necessary DB migrations for title-specific fields (if any, e.g., map-level results).
- Add tests and recorded fixtures for each title.

Suggested order: Valorant, Rocket League, CS2, Dota2.

Deliverables:

- Reuseable rollout checklist for each subsequent title.

Estimated effort: 1–3 weeks per title for MVP each (CS2 may require extra work for map/series parsing).

### Milestone C — Admin Operations Dashboard (Internal)

Purpose: give operators control, visibility, and tools to recover/override jobs quickly.

Scope:

- Internal auth (Discord OAuth or local admin accounts).
- Match list and detail view, manual match overrides, job retry/cancel controls.
- PandaScore usage dashboard (hourly quotas, history), job logs, error list, health checks.
- Manual pick window adjustments and per-title toggles (feature flags UI).

Deliverables:

- Internal web app (MVP) accessible to maintainers.
- Basic operational runbook documented.

Estimated effort: 4–6 weeks (MVP).

### Milestone D — Public-Facing Site (User Experience)

Purpose: provide end-users with leaderboards, pick history, match pages, and account linking.

Scope:

- Public match pages and leaderboards.
- User account linking (Discord) and opt-in notifications.
- Pick history and basic analytics (no live-play-by-play initially).

Deliverables:

- User-facing web app and basic signup/link flow.

Estimated effort: 6–12 weeks (MVP), depending on scope.

## Advanced / Deferred Features

- Live, play-by-play statistics and advanced in-game analytics (deferred). These are expensive with PandaScore — evaluate alternate providers, scraping options, or funding before committing.
- Monetization or premium tiers to cover API costs (if needed later).

## Implementation Notes & Constraints

- PandaScore rate limits: implement request batching, caching, and backoff. Prefer scheduled prefetching around reset windows.
- Parser modularity: keep a small, stable core parsing helper library and move only game-specific transformations into adapters.
- DB changes: create Alembic migrations for any schema changes; keep migrations small and incremental per title.
- Tests & CI: use recorded API fixtures and mocks to avoid hitting PandaScore in CI; aim to cover parser edge-cases and polling loops.
- Observability: add health endpoints, logs, and optional Sentry/metrics as part of the admin dashboard milestone.

## Next Steps

1. Finalize acceptance criteria for Milestone A and schedule a sprint.
2. Implement parser refactor for LoL and the improved rate-limit monitor.
3. Iterate adding CS2 using the new adapter template.

---
If you want, I can convert this to a Git commit and open a PR, or tweak estimates and scope per your available time.
