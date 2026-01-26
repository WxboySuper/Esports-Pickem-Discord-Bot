# Sentinel's Journal

## 2025-02-18 - Race Condition in Pick Creation
**Vulnerability:** Users can create duplicate picks for the same match by exploiting a race condition in the `pick` command, potentially allowing double voting.
**Learning:** The `Pick` model lacks a unique constraint on `(user_id, match_id)`, and the check-then-act logic in `create_pick` is not atomic.
**Prevention:** Add a unique constraint to the database schema and use `ON CONFLICT DO UPDATE` (upsert) logic or explicit locking.
