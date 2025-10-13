# Esports Pickem Discord Bot - Architecture

## Overview

High-level description of the bot, its purpose, and key components.

## Technologies

- Python 3.x
- SQLModel (ORM)
- Alembic (Migrations)
- SQLite (dev) / Postgres (prod ready)
- Discord.py

## Database Schema

### Tables/Models

- **User**: Discord user info, links to Picks
- **Contest**: Esports contest, links to Matches and Picks
- **Match**: Individual match, links to Contest, Picks, Result
- **Pick**: User's prediction for a match
- **Result**: Final result of a match

(Include a diagram or table summary if possible)

### Relationships

- One User → Many Picks
- One Contest → Many Matches & Picks
- One Match → Many Picks, One Result

### Indexes

- Applied to user_id, contest_id, match_id for fast querying

## CRUD Utilities

- Located in `src/crud.py`
- Functions for create/read/update/delete for each entity
- Custom queries for analytics (by date, user, contest, etc.)

## Analytics

- Schema supports leaderboards, user stats, contest standings
- Example queries in `src/crud.py` and here

## Workflow Example

1. User makes a pick → Pick row created
2. Match ends → Result row added
3. Analytics/leaderboard queries aggregate Pick and Result data

## Leaguepedia Sync & Match Lifecycle

This section describes the automated process for synchronizing match data from the Leaguepedia API and managing the lifecycle of a match from scheduled to completed.

### Sync Architecture & Caching

The bot uses a local SQLite database as a cache for data fetched from the Leaguepedia API. This approach minimizes API requests, improves performance, and allows the bot to operate even if the API is temporarily unavailable. The core data models involved are `Tournament`, `Team`, and `Match`.

The primary synchronization is handled by the `/sync` command and a recurring scheduled job, which populates the database with upcoming matches from specified tournaments.

### Scheduled Jobs

The automation is powered by `APScheduler` and defined in `src/scheduler.py`. There are three key jobs that manage the match lifecycle:

1.  **`perform_leaguepedia_sync`**:
    -   **Trigger**: Runs every 6 hours.
    -   **Purpose**: Acts as the main data synchronization job. It queries the Leaguepedia API for all configured tournaments, fetching and storing information about teams and upcoming matches. For each new match, it automatically schedules reminder jobs.

2.  **`schedule_live_polling` (Orchestrator)**:
    -   **Trigger**: Runs every minute.
    -   **Purpose**: This job constantly checks for matches that are scheduled to begin within the next minute. For each match that is about to start, it schedules a dedicated `poll_live_match_job` to monitor it for results. This "just-in-time" scheduling prevents the need to keep persistent polling jobs running for all matches far in advance.

3.  **`poll_live_match_job` (Live Match Poller)**:
    -   **Trigger**: Runs every 5 minutes, scheduled dynamically by the orchestrator job.
    -   **Purpose**: This job is responsible for a single, specific match that is currently live. It repeatedly polls the Leaguepedia API for the match's result. Once a winner is identified, it performs the following actions:
        -   Creates a `Result` record in the database with the winner and final score.
        -   Calls `send_result_notification` to announce the result in Discord.
        -   Removes itself from the scheduler to stop further polling.

### Database State & Match Lifecycle

The state of a match is tracked implicitly through the database:

-   **Scheduled**: A `Match` record exists in the database, but it has no corresponding `Result` record.
-   **Live**: The `scheduled_time` for a `Match` is in the past, a `poll_live_match_job` is active for it, but it still has no `Result` record.
-   **Completed**: A `Result` record exists with a `match_id` linking it to the completed `Match`. The presence of this record signals the end of the lifecycle.

## Migrations

- Alembic setup in `alembic/`
- Run `alembic upgrade head` to initialize/update schema

## Future Extensions

- Advanced analytics (streaks, badges)
- Integration with external APIs
- Scaling to Postgres

---

*For detailed DB fields/types, see `src/models.py`.*
