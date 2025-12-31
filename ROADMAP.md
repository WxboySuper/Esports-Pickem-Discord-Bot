# MatchPoint Roadmap

## Overview

MatchPoint v1.0 is a production Discord bot for picks and contests (currently supports League of Legends).

This document is a concise, versioned roadmap describing refactors, feature milestones, priorities for additional titles, and release procedures.

## Goals

- Expand PandaScore-backed title support (CS2, Valorant, Rocket League, Dota2) using a reusable adapter template.
- Improve reliability: accurate rate-limit handling, feature flags, and stronger test coverage.
- Provide operational tooling (internal admin dashboard) and, later, a public-facing site for users.
- Defer advanced live/play-by-play features until feasibility, cost, and data-source options are evaluated.

## Versioning Policy

- Use a lightweight semantic scheme: `MAJOR.MINOR.PATCH`.

  - MINOR: add a supported title or a substantial feature (e.g., v1.1 = CS2).
  - PATCH: small command changes, bugfixes, or tests.
  - MAJOR: breaking changes.

## Milestones & Releases

Milestones are scoped for fast, incremental releases. Each milestone below maps to a target release.

### v1.0 — Baseline (released)

- Production LoL support: picks, contests, announcements

- Core scheduler, PandaScore ingestion, DB models, baseline tests

### v1.1 — Refactor & Hardening (Milestone A)

**Goal:** provide a reusable adapter and harden polling.

**Checklist:**

- Split parsing into: core parsing helpers and per-game adapters (e.g., `parsers/core.py`, `parsers/lol.py`).

- Define a per-game parser interface and helper utilities.

- Replace inferred rate-limit counters with real reset/lift tracking from API responses; persist reset state as needed and add backoff/retry logic.

- Implement feature flags (config-driven per-title/feature toggles) for staged rollouts and quick rollback.

- Add fixtures and mocked PandaScore responses; extend unit/integration tests and CI to run them.

**Acceptance:** no regressions vs v1.0; CI passing; documented rollback path.

**Estimate:** 2–4 weeks.

### v1.2 — CS2 (Counter-Strike)

**Goal:** CS2 MVP using the adapter template.

**Checklist:**

- Implement `parsers/cs2.py` following the LoL adapter.

- Add per-title configuration and enable flag.

- Apply DB/Alembic migrations for map/series fields if required.

- Add recorded fixtures and tests.

**Estimate:** 1–3 weeks (CS2 may need extra work for map/series parsing).

### v1.3 — Valorant

- Same pipeline as v1.2 using `parsers/valorant.py`.

### v1.4 — Rocket League

- Same pipeline as v1.2 using `parsers/rocketleague.py`.

### v1.5 — Dota2

- Same pipeline as v1.2 using `parsers/dota2.py` (Dota2 may require extra fields and validation).

### v2.0 — Admin Operations Dashboard (Milestone C)

**Goal:** internal ops tooling for visibility and recovery.

**Checklist:**

- Select lightweight stack (FastAPI/Flask + minimal frontend) and admin auth (Discord OAuth or local accounts).

- Views: match list/detail, job queue, logs, errors, feature-flag controls.

- Panels: PandaScore quota/usage, health checks, manual override and retry/cancel actions.

- Tests for key admin flows and documented runbook.

**Estimate:** 4–6 weeks (MVP).

### v3.0 — Public-Facing Site (Milestone D)

**Goal:** user-facing site with leaderboards, pick history, and account linking.

**Checklist (MVP):**

- Public match pages and leaderboards.

- Discord account linking and user settings.

- Pick history and basic exports.

- Opt-in notifications and privacy review (TOS/Privacy policy).

**Estimate:** 6–12 weeks (MVP depending on scope).

## Advanced / Deferred Items

- Live, play-by-play statistics and deep in-game analytics are deferred due to cost and data availability. Evaluate alternate providers, scraping legality, or funding before implementation.

- Monetization or premium tiers can be considered later to offset paid-data costs.

## Implementation Notes

- Rate limits: batch requests, cache results, prefetch around reset windows, and use exponential backoff.

- Parser pattern: keep a lean core and move only game-specific transforms into adapters.

- DB changes: create small, incremental Alembic migrations per title.

- Testing: use recorded API fixtures and mocks for CI to avoid hitting PandaScore directly.

- Observability: add health endpoints, structured logs, and optional Sentry/metrics during Milestone C.

## Release Procedure (template)

For each release:

- Update `pyproject.toml` or version source.

- Add changelog entry and release notes with acceptance criteria met.

- Run full test suite in CI (including parser fixtures).

- Tag release and open PR with release notes.

- Smoke test in staging if available before merging to `main`.

## Next Steps

1. Finalize acceptance criteria for v1.1 and schedule a sprint.
2. Begin parser refactor for LoL and implement improved rate-limit tracking.
3. Start v1.2 (CS2) once v1.1 is validated in CI.
