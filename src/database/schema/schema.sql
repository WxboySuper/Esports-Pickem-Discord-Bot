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

-- Schema Version Table
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);