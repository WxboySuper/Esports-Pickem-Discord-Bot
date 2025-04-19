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

-- Table: Picks
CREATE TABLE IF NOT EXISTS Picks (
    pick_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    match_id INTEGER NOT NULL,
    pick_selection TEXT NOT NULL,
    pick_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_correct BOOLEAN,
    points_earned INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(match_id) REFERENCES Matches(match_id)
);
CREATE INDEX IF NOT EXISTS idx_picks_user_id ON Picks(user_id);
CREATE INDEX IF NOT EXISTS idx_picks_match_id ON Picks(match_id);

-- Schema Version Table
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);