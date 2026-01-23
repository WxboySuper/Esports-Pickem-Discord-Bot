# Developer & Agent Guidelines

This file serves as the technical manual and rulebook for developers and AI agents working on the **Esports Pick'em Discord Bot**. It consolidates architectural decisions, coding standards, and project-specific "gotchas".

**All contributors (human and AI) must follow these guidelines.**

## 1. Tech Stack & Core Libraries

- **Language**: Python 3.10+
- **Web/Async**: `asyncio`, `aiohttp`
- **Database**: SQLite, `SQLModel` (ORM), `Alembic` (Migrations)
- **Discord**: `discord.py`
- **Scheduling**: `APScheduler`
- **Data Source**: PandaScore API (`PandaScoreClient`)

## 2. Database & Models

### SQLModel & Async SQLAlchemy
- **Avoid N+1 Queries**: When fetching objects that have relationships (e.g., `Match` with `Result`), you **must** use `.options(selectinload(Model.relationship))` in your query.
  ```python
  # DO:
  statement = select(Match).options(selectinload(Match.result))
  # DON'T:
  statement = select(Match) # Accessing match.result later will fail or cause extra queries
  ```
- **Timezones**: Use the custom `TZDateTime` type decorator for all datetime fields to ensure timezone awareness is preserved (stored as ISO strings in SQLite).
  ```python
  scheduled_time: datetime = Field(sa_column=Column(TZDateTime(), nullable=False))
  ```

### CRUD Patterns
- **Module Structure**: Database operations live in `src/crud/`.
- **Function Signatures**: List functions should accept optional boolean arguments to toggle eager loading.
  ```python
  def list_picks(session, with_users: bool = False):
      stmt = select(Pick)
      if with_users:
          stmt = stmt.options(selectinload(Pick.user))
      return session.exec(stmt).all()
  ```

### Migrations (Alembic)
- **Idempotency**: SQLite does not support transactional DDL well. Wrap operations like `create_table` or `add_column` in checks to prevent crashes if the schema partially exists.
  ```python
  # Example: Check if column exists before adding
  conn = op.get_bind()
  inspector = sqlalchemy.inspect(conn)
  if "image_url" not in [c["name"] for c in inspector.get_columns("contest")]:
      with op.batch_alter_table("contest") as batch_op:
          batch_op.add_column(...)
  ```
- **Environment**: `alembic/env.py` is configured to read `DATABASE_URL` from the environment. Do not hardcode connection strings.

## 3. Asynchronous Patterns

- **Concurrent Requests**: When fetching independent data (e.g., multiple API endpoints), use `asyncio.gather` instead of sequential awaits.
- **Blocking Code**: Never run blocking DB calls (synchronous `session.exec` without `await` is only for sync contexts, but this app is largely async). Note that `SQLModel` has both sync and async sessions; ensure you are using the correct one for the context (Discord commands are async).

## 4. Testing

- **Command**: Run tests using `python -m pytest` to ensure `sys.path` is correctly set.
- **Mocking Strategy**: Mock the **immediate dependency**, not the database driver.
  - *Good*: Mock `src.crud.get_match_by_id` when testing a Discord command.
  - *Bad*: Mocking `session.exec` or `sqlalchemy.engine`.
- **Discord Views**: When testing `discord.ui.View` subclasses in isolation, you may need to mock `discord.Interaction` and ensure items added to views behave correctly.

## 5. Discord UI Constraints

- **Select Menus**: Discord limits dropdown options to **25 items**. Always use `.limit(25)` in database queries that populate select menus.
- **Interaction Responses**: Always `defer()` if an operation might take >3 seconds.
- **Message Architecture**: Prefer single message responses (using Embeds) that can be edited/updated rather than sending multiple separate messages. This keeps channels organized.

## 6. Project Architecture

### Data Synchronization
- **Source**: We use **PandaScore**. (Legacy `Leaguepedia` code has been removed).
- **Jobs**:
  - `perform_pandascore_sync`: Runs every **1 hour** (full sync).
  - `poll_running_matches_job`: Runs every **1 minute** (updates live scores/results).

### Configuration
- **Environment Variables**: Managed in `.env` (local) and injected in production.
- **Config Access**: Use `src/config.py` to access variables. Do not use `os.getenv` directly in business logic files.

## 7. Workflow & Git

### Commit Messages
- **Format**: Semantic Commits (`type: message`)
- **Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`.
- **Example**: `feat: add auto-refresh to leaderboard view`

### Pre-commit Checks
Before submitting code, you must ensure:
1. **Linting**: Run `flake8` and `black .`
2. **Tests**: Run `python -m pytest` and ensure all tests pass.
