# Sentinel's Journal

## 2025-02-18 - Race Condition in Pick Creation
**Vulnerability:** Users can create duplicate picks for the same match by exploiting a race condition in the `pick` command, potentially allowing double voting.
**Learning:** The `Pick` model lacked a unique constraint on `(user_id, match_id)`, and the check-then-act logic in `create_pick` was not atomic.
**Prevention:** Added a unique constraint `uq_pick_user_match` to the database and implemented `try/except IntegrityError` handling in the application logic to safely manage concurrent requests. Rate limiting was also added as a defense-in-depth measure.
