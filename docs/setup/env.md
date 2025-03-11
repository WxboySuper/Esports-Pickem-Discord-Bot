# Environment Variables Configuration

This guide explains how to set up the required environment variables for the Esports Pickem Discord Bot.

## Overview

The bot uses environment variables to store sensitive credentials and configuration settings. These are stored in a `.env` file in the root directory of the project.

## Creating a Discord Application

Before setting up your environment variables, you'll need to create a Discord application:

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Navigate to the "Bot" tab and click "Add Bot"
4. Under the "Token" section, click "Copy" to copy your bot token
5. Navigate to the "OAuth2" tab to find your application ID and public key

## Setting Up Your .env File

Create a file named `.env` in the root directory of the project with the following structure:

```
# Production Bot Settings
PROD_DISCORD_TOKEN=your_production_bot_token
PROD_PUBLIC_KEY=your_production_public_key
PROD_APP_ID=your_production_application_id

# Test Bot Settings (optional but recommended)
TEST_DISCORD_TOKEN=your_test_bot_token
TEST_PUBLIC_KEY=your_test_public_key
TEST_APP_ID=your_test_application_id

# Discord IDs
OWNER_USER_DISCORD_ID=your_discord_user_id

# Database Settings
PROD_DB_NAME=discord_esports_pickem
TEST_DB_NAME=discord_esports_pickem_test
```

## Required Variables

### Discord Bot Credentials

For production:
- `PROD_DISCORD_TOKEN`: Your Discord bot's token
- `PROD_PUBLIC_KEY`: Your Discord application's public key
- `PROD_APP_ID`: Your Discord application's ID

For testing (recommended):
- `TEST_DISCORD_TOKEN`: Token for a separate testing bot
- `TEST_PUBLIC_KEY`: Public key for the testing bot
- `TEST_APP_ID`: Application ID for the testing bot

### User and Server IDs

- `OWNER_USER_DISCORD_ID`: Your Discord user ID (used for admin commands)

### Database Configuration

- `PROD_DB_NAME`: Name of your production database
- `TEST_DB_NAME`: Name of your testing database

## How to Get Your Discord IDs

### User ID
1. Enable Developer Mode in Discord (Settings > Advanced > Developer Mode)
2. Right-click on your username and select "Copy ID"

### Server ID
1. Enable Developer Mode in Discord (Settings > Advanced > Developer Mode)
2. Right-click on your server name and select "Copy ID"

## Security Considerations

- Keep your `.env` file confidential and never commit it to version control
- Add `.env` to your `.gitignore` file to prevent accidental commits
- Regularly rotate your bot tokens for better security
- Use separate tokens for production and testing environments

## Troubleshooting

If your bot fails to connect to Discord, check:
1. Your token is correct and not expired
2. The bot has been invited to your server with the proper permissions
3. Your `.env` file is in the correct location and properly formatted
