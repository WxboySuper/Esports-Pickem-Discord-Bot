# Esports Pick'em Discord Bot

## Project Overview

This project is a Discord bot designed for managing esports pick'em contests. It allows users to predict match outcomes and compete on leaderboards. The bot integrates with the Leaguepedia API to fetch match data and results.

## Architecture & Technologies

- **Language:** Python 3.10+
- **Framework:** `discord.py` (using `app_commands` for slash commands)
- **Database:** PostgreSQL (production), SQLite (local dev)
- **ORM:** `SQLModel` (SQLAlchemy wrapper)
- **Migrations:** `Alembic`
- **Scheduling:** `APScheduler`
- **External API:** Leaguepedia (via `mwclient` likely, wrapped in `leaguepedia_client.py`)

## Key Directories

- `src/`: Main application source code.
  - `commands/`: Discord slash command implementations.
  - `models.py`: Database models (SQLModel).
  - `scheduler.py`: Job scheduling logic (sync, polling).
  - `leaguepedia_client.py`: Client for fetching data from Leaguepedia.
- `tests/`: Unit and integration tests (`pytest`).
- `alembic/`: Database migration scripts.

## Setup & Installation

1. **Prerequisites:**

- Python 3.10+
- PostgreSQL (optional for local dev, SQLite is supported)

2. **Install Dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

3. **Environment Variables:**

Create a `.env` file (see `.env.example`) with:

- `DISCORD_TOKEN`: Your Bot Token.
- `DATABASE_URL`: Connection string (e.g., `sqlite:///database.db` or `postgresql://...`).
- `LOG_LEVEL`: `DEBUG`, `INFO`, etc.

4. **Database Setup:**

Initialize the database and run migrations:

```bash
    python -m alembic upgrade head
```

## Building and Running

**Start the Bot:**
Run the bot as a module from the project root:

```bash
python -m src.app
```

**Running Tests:**
Execute the test suite using `pytest`:

```bash
python -m pytest
```

## Development Workflow

- **Database Changes:**

If you modify `src/models.py`, generate a new migration:

```bash
    python -m alembic revision --autogenerate -m "description_of_change"
    python -m alembic upgrade head
```

- **Adding Commands:**

Create new command modules in `src/commands/` and ensure they have a `setup(bot)` function. They are automatically loaded in `src/app.py`.

- **Match Lifecycle Logic:**
The bot synchronizes data in three stages:

1. **Sync (`perform_leaguepedia_sync`)**: Fetches upcoming matches/tournaments every 6 hours.
2. **Orchestrator (`schedule_live_polling`)**: Checks every minute for matches starting soon and schedules a poller.
3. **Poller (`poll_live_match_job`)**: Polls for results of a specific live match every 5 minutes until completed.

## Code Style

- Follows standard Python conventions (PEP 8).
- Use `black` for formatting and `flake8` for linting (implied by `CONTRIBUTING.md`).
