-- Enable foreign key support
PRAGMA foreign_keys = ON;

-- Create User Table - Stores user information
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id INTEGER NOT NULL UNIQUE, -- Discord's user ID
    username TEXT NOT NULL, 
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
);

CREATE INDEX IF NOT EXISTS idx_users_discord_id ON users(discord_id);