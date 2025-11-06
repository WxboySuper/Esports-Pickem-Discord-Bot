## Plan: Reduce Complexity of poll_live_match_job

TL;DR: Extract 4–5 focused helpers from `poll_live_match_job` in `src/scheduler.py` into a helper module `src/scheduler_helpers.py`. The main job becomes an orchestrator calling those helpers, keeping DB transaction semantics and post-commit announcements unchanged. This will reduce cyclomatic complexity below Flake8's threshold.

### Steps
1. Create `src/scheduler_helpers.py` and add `load_match_or_unschedule(session, match_db_id, job_id)`.
2. Add `check_and_unschedule_if_timed_out(match, job_id, now)` to `src/scheduler_helpers.py`.
3. Add `fetch_scoreboard_and_filter_relevant_games(leaguepedia_id, match)` to `src/scheduler_helpers.py`.
4. Add `compute_scores_and_winner(relevant_games, match)` (pure function) to `src/scheduler_helpers.py`.
5. Add `persist_result_and_update_picks(session, match, winner, current_score_str)` to `src/scheduler_helpers.py`.
6. Replace the large body of `poll_live_match_job` in `src/scheduler.py` with an orchestration sequence calling the above helpers, then call `send_result_notification` or `send_mid_series_update` as appropriate.

### Further Considerations
1. Tests: Add/adjust tests in `tests/test_polling_logic.py` and create `tests/test_persist_result_and_update_picks.py` to cover DB commit and pick-updates. Option: run existing integration tests after refactor.
2. Transactions: Keep DB writes in same session; `persist_result_and_update_picks` must re-check `match.result` to avoid race conditions and commit inside the helper.
3. Design choice: Place helpers in `src/scheduler_helpers.py` for clarity; keep calls lightweight in `scheduler.py` to meet complexity limits.

