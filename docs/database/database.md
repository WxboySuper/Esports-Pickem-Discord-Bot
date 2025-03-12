# Esports Pick'em Discord Bot - Database Schema

## Overview
This document outlines the database structure for the Esports Pick'em Discord Bot, including tables, fields, and relationships.

## Tables

### User
Stores information about Discord users interacting with the bot.
- `user_id` (Primary Key): Internal user identifier
- `discord_user_id`: Discord's unique user identifier
- `discord_guild_id`: Discord server identifier where the user is active
- `username`: Discord username (optional)
- `joined_date`: When the user first interacted with the bot
- `is_active`: Boolean flag to track active status

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
Records user predictions for matches.
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

### Tournaments
Details about esports tournaments.
- `tournament_id` (Primary Key): Unique tournament identifier
- `tournament_name`: Full name of the tournament
- `region`: Region where tournament is held
- `start_date`: Tournament start date
- `end_date`: Tournament end date
- `is_active`: Whether tournament is currently running

## Relationships
- A User can have many Picks (one-to-many)
- A Match can have many Picks (one-to-many)
- Statistics has a one-to-one relationship with User
- Teams participate in many Matches (many-to-many)
- Tournaments contain many Matches (one-to-many)

## Notes
- Consider implementing a caching strategy for frequently accessed data
- Statistics table should be updated through triggers or scheduled jobs
- Guild-specific information is tracked via the discord_guild_id in the User table
- Consider implementing a leaderboard view/materialized view for performance