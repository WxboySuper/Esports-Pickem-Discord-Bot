# Database Documentation

This document describes the database implementation for the Esports Pick'em Discord Bot.

## IMPORTANT INFOMRATION
> \[!IMPORTANT]
> The Database Schema is actively being upgraded from v1 to v2 to fully implement the user database.
>
> If using a v1 database ensure that the v2 migration works correctly.

## Architecture

The database module uses SQLite with `aiosqlite` for asynchronous access. The main components are:

1. `Database` class - Core handler for all database operations
2. Model classes - Interfaces for specific data entities (users, matches, etc.)

## Connection Management

The database uses a connection pooling pattern to efficiently manage database connections:

### Connection Pool

- A pool of connections is maintained to avoid the overhead of creating new connections for each operation
- Default pool size is 5 connections
- Connections are automatically returned to the pool after use
- If the pool is exhausted, new connections are created as needed

### Connection Lifecycle

1. **Initialization**: A pool of connections is created when the database is first initialized
2. **Acquisition**: When a database operation is requested, a connection is taken from the pool
3. **Release**: After the operation completes, the connection is returned to the pool
4. **Cleanup**: When the application shuts down, all connections are properly closed

### Usage

Database operations are designed to automatically handle connection management:

```python
# Execute a query (connection management is handled automatically)
await db.execute("INSERT INTO users (discord_id, username) VALUES (?, ?)", (12345, "User"))

# Fetch data (connection management is handled automatically)
user = await db.fetch_one("SELECT * FROM users WHERE discord_id = ?", (12345,))
```

## Transaction Management

Transactions are automatically handled by the database operations:

1. Each operation acquires a connection
2. The SQL is executed
3. For write operations, the transaction is committed
4. The connection is returned to the pool
5. Any exceptions are properly handled and logged

## Error Handling

The database module includes comprehensive error handling:

- All exceptions are caught and logged
- Failed operations return appropriate values (None, False, or empty lists)
- Connection errors are properly managed to prevent resource leaks

## Log Management

The application includes functionality to manage log files:

- Logs are stored in the `logs/app.log` file by default
- Log files can be cleared on application startup to prevent excessive growth
- RotatingFileHandler is used to automatically limit log file size

### Clearing Logs on Startup

To enable log clearing on application startup:

```python
from src.utils.logging_config import configure_logging

# Clear log file when initializing logging
log = configure_logging(clear_logs=True)
```

## Database Schema

The database schema is defined in `src/database/schema/schema.sql` and includes the following tables:

### User
Stores information about Discord users interacting with the bot.
- `user_id` (Primary Key): Internal user identifier
- `discord_user_id`: Discord's unique user identifier
- `discord_guild_id`: Discord server identifier where the user is active
- `username`: Discord username (optional)
- `joined_date`: When the user first interacted with the bot
- `is_active`: Boolean flag to track active status

#### Indexes
```sql
CREATE INDEX idx_user_discord_id ON User(discord_user_id);
CREATE INDEX idx_user_guild_id ON User(discord_guild_id);
```

### Matches
Contains information about esports matches that users can make predictions on.
- `match_id` (Primary Key): Internal match identifier
- `team1_id`: Identifier for first team
- `team1_name`: Name of first team
- `team2_id`: Identifier for second team
- `team2_name`: Name of second team
- `region`: Geographic region or league (e.g., LCS, LEC, LCK)
- `tournament`: Specific tournament name
- `match_date`: Date of the match
- `match_time`: Time of the match
- `result`: Match outcome (team1, team2, draw, or null if pending)
- `is_complete`: Boolean indicating if match is finished
- `match_metadata`: JSON field for additional match data (optional)

### Picks
Stores user predictions for matches.
- `pick_id` (Primary Key): Unique identifier for each pick
- `user_id` (Foreign Key): References User table
- `match_id` (Foreign Key): References Matches table
- `pick_selection`: User's prediction (team1, team2)
- `pick_timestamp`: When the pick was made
- `is_correct`: Boolean indicating if prediction was correct (null until match is complete)
- `points_earned`: Points awarded for correct prediction

### Statistics
Aggregated performance metrics for users.
- `stat_id` (Primary Key): Unique identifier for statistics record
- `user_id` (Foreign Key): References User table
- `guild_id`: Discord server identifier for server-specific stats
- `total_picks`: Total number of predictions made
- `correct_picks`: Number of correct predictions
- `accuracy`: Percentage of correct predictions
- `total_points`: Cumulative points earned
- `streak_current`: Current streak of correct predictions
- `streak_best`: Best streak of correct predictions
- `rank`: User rank within their server
- `last_updated`: Timestamp of last statistics update

### Teams
Information about esports teams.
- `team_id` (Primary Key): Unique team identifier
- `team_name`: Official team name
- `team_code`: Short code/abbreviation (e.g., T1, G2)
- `region`: Primary region of the team
- `logo_url`: URL to team logo image
- `active`: Whether the team is currently active

#### Index
```sql
CREATE UNIQUE INDEX idx_unique_team_code ON Teams(team_code);
```

### Tournaments
Details about esports tournaments.
- `tournament_id` (Primary Key): Unique tournament identifier
- `tournament_name`: Full name of the tournament
- `region`: Region where the tournament is held
- `start_date`: Tournament start date
- `end_date`: Tournament end date
- `is_active`: Whether tournament is currently running

### Schema Version
Tracks the current schema version for migrations.
- `version` (Primary Key): Schema version number
- `applied_at`: Timestamp when version was applied

## Schema Versioning

The database tracks schema versions to support future migrations:

1. A `schema_version` table stores the current schema version
2. During initialization, the schema version is checked
3. Migration functions can be added as needed to update from one version to another

## Relationships
- **User and Picks**: A User can have many Picks (one-to-many).
    - Foreign Key: `Picks.user_id` references `User.user_id`.

- **Match and Picks**: A Match can have many Picks (one-to-many).
    - Foreign Key: `Picks.match_id` references `Matches.match_id`.

- **User and Statistics**: Statistics has a one-to-one relationship with User.
    - Foreign Key: `Statistics.user_id` references `User.user_id`.

- **Teams and Matches**: Teams participate in many Matches (many-to-many).
    - This relationship can be implemented using a join table (e.g., `Team_Match`), with foreign keys `Team_Match.team_id` referencing `Teams.team_id` and `Team_Match.match_id` referencing `Matches.match_id`.

- **Tournaments and Matches**: Tournaments contain many Matches (one-to-many).
    - Foreign Key: `Matches.tournament` references `Tournaments.tournament_id`.

## Best Practices

- Consider implementing a caching strategy for frequently accessed data
- Statistics table should be updated through triggers or scheduled jobs
- Guild-specific information is tracked via the discord_guild_id in the User table
- Consider implementing a leaderboard view/materialized view for performance