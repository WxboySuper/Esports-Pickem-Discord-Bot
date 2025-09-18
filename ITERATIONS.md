# Iterations and Acceptance Criteria

This document defines the two-week iterations, goals, and acceptance criteria for the Esports-Pickem-Discord-Bot project. Iteration cadence: 2 weeks per iteration.

Current schedule

- Iteration 1 — 2025-09-18 to 2025-10-01
- Iteration 2 — 2025-10-02 to 2025-10-15
- Iteration 3 — 2025-10-16 to 2025-10-29
- Iteration 4 — 2025-10-30 to 2025-11-12
- Iteration 5 — 2025-11-13 to 2025-11-26

Issue assignments

- Iteration 1: #1 Project Setup, #2 Bot Skeleton, #3 Database Models and Schema
- Iteration 2: #4 Admin CSV Upload (Create Contest & Register Matches), #5 User Commands (Submit Picks, View Picks, Leaderboards)
- Iteration 3: #6 Scoring Engine & Result Entry, #7 Scheduled Reminders and Result Polling
- Iteration 4: #8 Valorant Adapter, #9 Testing (Unit & E2E Coverage)
- Iteration 5: #10 Documentation, #11 Optional FastAPI Leaderboard & Admin Dashboard

Iteration details

Iteration 1 (2025-09-18 → 2025-10-01)
Goals:

- Provide developer onboarding files: README quickstart, .gitignore, env.example.
- Add a minimal GitHub Actions workflow (lint + test placeholder).
- Implement a basic Discord bot skeleton that connects and responds to /ping.
- Create DB models and migrations for Users, Contests, Matches, Picks.

Acceptance criteria:

- README contains quickstart steps and required env vars.
- A developer can run migrations and start the bot locally against a test DB.
- The bot responds to /ping with a pong.
- Migration scripts apply cleanly and tables can be queried.

Iteration 2 (2025-10-02 → 2025-10-15)
Goals:

- Implement admin CSV upload command to register contests and matches.
- Add user-facing commands: /pick, /picks, /leaderboard (basic behavior).

Acceptance criteria:

- CSV upload validates rows, reports per-row errors, and creates Match records idempotently.
- Users can submit picks for unlocked matches, view their picks, and fetch the contest leaderboard.

Iteration 3 (2025-10-16 → 2025-10-29)
Goals:

- Implement admin result entry (single & bulk) and scoring engine.
- Add background jobs for scheduled reminders and optional result polling.

Acceptance criteria:

- Entering results updates pick scores and recomputes leaderboards deterministically.
- Scheduled reminders run and post to configured channels on schedule.
- Result polling (if configured) can fetch updates and apply them or flag discrepancies.

Iteration 4 (2025-10-30 → 2025-11-12)
Goals:

- Implement or scaffold game-specific adapter (e.g., Valorant VLRGGAPI) for importing matches/results.
- Expand test coverage: unit tests for CSV parsing and scoring, integration tests for command flows.

Acceptance criteria:

- Adapter can ingest sample/mocked data and create/update Matches and Results.
- CI runs unit and integration tests; core logic has guarded coverage.

Iteration 5 (2025-11-13 → 2025-11-26)
Goals:

- Finalize and publish documentation: admin guide, user guide, developer reference.
- Optionally add FastAPI read-only leaderboard and secure admin upload UI.

Acceptance criteria:

- Documentation covers setup, CSV spec, admin workflows, and developer instructions.
- FastAPI (optional) serves read-only leaderboard endpoints and an authenticated CSV upload page.

Notes and guidance

- Tests should be added continuously while features are implemented; the Iteration 4 testing milestone is a coverage target, not the start of testing.
- Keep integrations (issue #8) and the optional FastAPI UI (#11) scoped as non-blocking enhancements so the Discord-first MVP can ship fast.
- Admin-only actions should be protected by role or a configurable list of admin Discord IDs.
- Data migration and idempotency are important for CSV uploads and result entries: include deduplication checks and the ability to recompute scores.

Usage

- Place this file in the repository root (ITERATIONS.md) and link from the README or project board/milestones.

Maintainers

- Owner: @WxboySuper
