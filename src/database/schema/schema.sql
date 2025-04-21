-- Enable foreign key support
PRAGMA foreign_keys = ON;

-- Create User Table - Stores user information
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_user_id INTEGER NOT NULL UNIQUE, -- Discord's user ID
    discord_guild_id INTEGER NOT NULL,  -- Discord Guild ID
    username TEXT,                      -- Optional Additional Username
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (discord_user_id > 0)
);

CREATE INDEX IF NOT EXISTS idx_user_discord_user_id ON users(discord_user_id);
CREATE INDEX IF NOT EXISTS idx_user_guild_id ON users(discord_guild_id);

-- Table: Matches
CREATE TABLE IF NOT EXISTS Matches (
    match_id INTEGER PRIMARY KEY AUTOINCREMENT,
    team1_id INTEGER NOT NULL,
    team1_name TEXT NOT NULL,
    team2_id INTEGER NOT NULL,
    team2_name TEXT NOT NULL,
    region TEXT NOT NULL,
    tournament TEXT NOT NULL,
    match_date TEXT NOT NULL,    -- Stored in ISO format
    match_time TEXT NOT NULL,    -- Stored in ISO format
    result TEXT,                 -- team1, team2, draw, or null if pending
    is_complete BOOLEAN NOT NULL DEFAULT 0,
    match_metadata TEXT,         -- JSON string for additional match data
    CHECK (match_id > 0),
    CHECK (team1_id > 0),
    CHECK (team2_id > 0),
    CHECK (team1_id != team2_id),
    CHECK (result IN ('team1', 'team2', 'draw', NULL)),
    CHECK (match_date LIKE '____-__-__'), -- Enforces YYYY-MM-DD format
    CHECK (match_time LIKE '__:__:__')    -- Enforces HH:MM:SS format
);

-- Create indexes for common match queries
CREATE INDEX IF NOT EXISTS idx_matches_date ON Matches(match_date);
CREATE INDEX IF NOT EXISTS idx_matches_tournament ON Matches(tournament);
CREATE INDEX IF NOT EXISTS idx_matches_region ON Matches(region);

-- Table: Picks
CREATE TABLE IF NOT EXISTS Picks (
    pick_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    match_id INTEGER NOT NULL,
    pick_selection TEXT NOT NULL,
    pick_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_correct BOOLEAN,
    points_earned INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY(match_id) REFERENCES Matches(match_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CHECK (pick_id > 0),
    CHECK (pick_selection IN ('team1', 'team2', 'draw')),
    CHECK (points_earned IS NULL OR points_earned >= 0)
);

CREATE INDEX IF NOT EXISTS idx_picks_user_id ON Picks(user_id);
CREATE INDEX IF NOT EXISTS idx_picks_match_id ON Picks(match_id);

-- Schema Version Table
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);