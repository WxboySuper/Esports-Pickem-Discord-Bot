# Test Plan: Esports Pick'em Discord Bot

## Scope

Covers basic bot skeleton, command registration, and minimal functionality for Issue #2.

---

## 1. Automated Tests

### Run All Unit Tests

- Install dependencies (including `pytest`, `pytest-asyncio`):

```bash
  pip install -r requirements.txt
  pip install pytest pytest-asyncio
```

- Run tests:

```bash
  python -m pytest -v tests/
```

#### Tests covered

- **Package imports**: Verifies `src.commands` is importable.
- **Command modules**: Each module in `src.commands` exposes a `setup()` function.
- **Bot instantiation**: Bot can be created (does not crash).
- **Ping command setup**: `ping` command/cog setup can be loaded (sync or async).

---

## 2. Manual Verification

### Service Startup

- Start the Discord bot service (systemd, docker, or CLI).
- Check logs for:
  - Successful login (e.g., "Logged in as ...")
  - Loaded command modules (e.g., "Loaded command module: ...")
  - Global command sync (e.g., "Performed GLOBAL command sync.")

### Discord Command Check

- In a Discord server where the bot is present:
  - Use `/ping` or `!ping` and verify the bot responds appropriately.
  - Use `/help` or `!help` and verify the help/info command responds.

---

## 3. Error Handling

- Confirm that missing/invalid `DISCORD_TOKEN` in env causes the bot to log a clear error and exit.
- If a command module fails to load or has no `setup`, this is reported in logs and does not crash the bot.

---

## 4. CI/CD

- Ensure the GitHub Actions workflow (if present) runs `pytest` on push/PR and reports status.

---

## 5. Acceptance Criteria

- All automated tests pass.
- Bot starts and commands register (see logs).
- Manual Discord command check succeeds.
- No unhandled exceptions or warnings in logs.
- Documentation (README and this file) describes testing steps.

---

## Notes

- For further development: add integration tests for user flows, scoring, DB functions, and adapters.
