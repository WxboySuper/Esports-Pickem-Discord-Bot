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

## Migrations

- Alembic setup in `alembic/`
- Run `alembic upgrade head` to initialize/update schema

## Future Extensions

- Advanced analytics (streaks, badges)
- Integration with external APIs
- Scaling to Postgres

---

*For detailed DB fields/types, see `src/models.py`.*
