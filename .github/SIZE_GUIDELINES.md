# Size selector - Quick descriptions & on-the-spot guidance

Use these short descriptions as visible helper text for each size option (XS, S, M, L, XL). Keep the one-liners in the UI; this doc is the authoritative triage guidance.

## One-line UI descriptions (copy these into each size's description)

- XS — Trivial: 0–50 LOC; tiny docs/config change or one-line bugfix; <2 files; <2 hours.
- S — Small: 50–200 LOC; single feature/config or small handler; 1–4 files; half-day to 1 day.
- M — Medium: 200–800 LOC; multi-file feature, DB model or command flow; 3–10 files; 1–3 days.
- L — Large: 800–2,000 LOC; cross-cutting feature, migrations, background jobs; 10–30 files; 3–7 days.
- XL — Extra-large: >2,000 LOC or multi-week cross-systems change; many teams/files; planned rollout & migration.

## Literal guidance to display in the issue chooser (longer help text)

XS (Extra-small)

- Lines changed: 0–50
- Files touched: 0–2
- Time: ~0.5–2 hours
- Review: single reviewer, trivial tests or none
- DB/Infra: no migrations; no infra touches
- When to pick: docs, typos, small config tweak, tiny one-line fixes

S (Small)

- Lines changed: 50–200
- Files touched: 1–4
- Time: ~2–8 hours
- Review: simple code review; 1–2 small unit tests
- DB/Infra: no schema changes or a single trivial migration
- When to pick: add a simple command, example env file, or small endpoint

M (Medium)

- Lines changed: 200–800
- Files touched: 3–10
- Time: ~1–3 days
- Review: multi-file review; unit tests and basic integration/smoke checks
- DB/Infra: may include non-trivial model + migration
- When to pick: core command flows, DB models + migrations, non-trivial feature touching multiple modules

L (Large)

- Lines changed: 800–2,000
- Files touched: 10–30+
- Time: ~3–7 days
- Review: multiple reviewers, cross-module impact, integration tests
- DB/Infra: likely schema changes, data re-compute, background job changes
- When to pick: scoring engine, bulk-import with idempotency, adapter touching many components

XL (Extra-large)

- Lines changed: >2,000 or touches many subsystems
- Files touched: many (>30)
- Time: multi-week; multiple engineers
- Review: design reviews, rollout/migration strategy, staging verification
- DB/Infra: major migrations, backward compatibility concerns
- When to pick: entire new adapter with live imports + dashboard, major architecture change

## Quick on-the-spot checklist (use to nudge size up)

- Add +1 size step if change includes:
  - DB schema migration with data changes or re-compute requirement
  - External integration / infra changes (CI, deployment, credentials)
  - New background job or scheduler entry
  - Security-sensitive behavior (auth, admin)
- Add +1 size step if change touches >12 files even if LOC is low.
- Subtract 1 size only if change is purely comments/whitespace or generated files with no logic changes.

## Practical example — PR: WxboySuper/Esports-Pickem-Discord-Bot/pull/12 (489 changed lines)

- Raw metric: 489 changed lines → 200–800 LOC band.
- Likely files: README, .env.example, .gitignore, .github/workflows/ci.yml (multi-file onboarding).
- Decision: M — Medium.
  - Rationale: 489 LOC needs multi-file review and verification, but is not >800 LOC or multi-week.
- Example short description to paste:
  "M — Medium scope (200–800 LOC). Multi-file onboarding changes: README, env example, CI workflow. Requires multi-file review and basic smoke test; no multi-week rollout."

## Copy-ready short descriptions (one-liners for UI)

- XS — Trivial: 0–50 LOC; tiny docs/config fix; <2 files; <2 hrs.
- S — Small: 50–200 LOC; single-area feature/fix; 1–4 files; half-day→1 day.
- M — Medium: 200–800 LOC; multi-file feature or model; 3–10 files; 1–3 days.
- L — Large: 800–2,000 LOC; cross-cutting feature/migrations; 10–30 files; 3–7 days.
- XL — Major: >2,000 LOC; multi-week, multi-team, migration & rollout.

Place this file under .github/ so it’s easy to reference from issue templates or the CONTRIBUTING.md.
