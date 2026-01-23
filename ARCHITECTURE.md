# Esports Pickem Discord Bot - Architecture

## Overview

High-level description of the bot, its purpose, and key components.

## Technologies

- Python 3.10+
- SQLModel (ORM)
- Alembic (Migrations)
- SQLite
- Discord.py
- PandaScore API (Match Data Source)

## Database Schema

### Tables/Models

- **User**: Discord user info, links to Picks.
- **Contest**: Esports contest (e.g., "LCS Spring 2024"), links to Matches and Picks. Includes `image_url` for branding.
- **Match**: Individual match, links to Contest, Picks, Result. Uses `TZDateTime` for timezone-aware scheduling.
- **Pick**: User's prediction for a match.
- **Team**: Stores team metadata (name, acronym, logo) to avoid redundant API calls.
- **Result**: Final result of a match (winner, score).

### Relationships

- One User → Many Picks
- One Contest → Many Matches & Picks
- One Match → Many Picks, One Result

### Indexes

- Applied to foreign keys (`user_id`, `contest_id`, `match_id`) and frequent lookup fields (`discord_id`, `pandascore_id`) for fast querying.

## CRUD Utilities

- Located in `src/crud/`.
- Functions for create/read/update/delete for each entity.
- **Performance**: Uses `selectinload` to prevent N+1 queries when fetching related data (e.g., loading picks with their users).

## Analytics

- Schema supports leaderboards, user stats, contest standings.
- Example queries in `src/crud/` modules.

## Workflow Example

1. **Sync**: Bot fetches upcoming matches from PandaScore and stores them in `Match` table.
2. **User Interaction**: User runs `/pick`, selects a match via dropdown, and chooses a team.
3. **Storage**: A `Pick` row is created/updated.
4. **Conclusion**: Match ends, bot detects result via polling, creates `Result` row.
5. **Scoring**: Leaderboards calculate scores based on correct `Pick` entries linked to `Result`s.

## PandaScore Sync & Match Lifecycle

This section describes the automated process for synchronizing match data from the PandaScore API and managing the lifecycle of a match.

### Sync Architecture & Caching

The bot uses the local database as a cache for data fetched from the PandaScore API. This minimizes API requests (rate-limited) and ensures the bot works offline. The `PandaScoreClient` handles all API interactions.

### Scheduled Jobs

The automation is powered by `APScheduler` and defined in `src/scheduler.py`.

1.  **`perform_pandascore_sync`**:
    -   **Trigger**: Runs every 1 hour.
    -   **Purpose**: Main synchronization job. Fetches upcoming matches and tournaments from PandaScore. Updates start times, teams, and creates new match records.

2.  **`poll_running_matches_job`**:
    -   **Trigger**: Runs every 1 minute.
    -   **Purpose**: Monitors active or soon-to-start matches.
    -   **Logic**:
        -   Queries PandaScore for "running" matches.
        -   If a match in the DB is found to be completed (status "finished"), it fetches the result.
        -   Creates a `Result` record.
        -   Triggers result announcements in Discord.

### Database State & Match Lifecycle

The state of a match is tracked via the `Match` status and existence of a `Result` record:

-   **Scheduled**: `Match` exists, `status` is "not_started".
-   **Live**: `Match` exists, `status` is "running".
-   **Completed**: `Match` exists, `status` is "finished", and a `Result` record is linked.

## Migrations

- Alembic setup in `alembic/`.
- Run `alembic upgrade head` to apply schema changes.
- Migrations should ideally be idempotent (checking for column existence) to support SQLite's limited `ALTER TABLE` capabilities safely.

## Future Extensions

- Advanced analytics (streaks, badges).
- Scaling to PostgreSQL for high-volume production.
