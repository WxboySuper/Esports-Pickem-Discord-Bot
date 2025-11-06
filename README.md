# Esports Pick'em Discord Bot

A Discord bot for managing esports pick'em contests where users can predict match outcomes and compete on leaderboards.

> [!NOTE]
> This project is currently in active development and all features and commands may not be fully implemented yet. Please refer to [ITERATIONS.md](./ITERATIONS.md) for the development roadmap.

## Overview

This bot allows Discord communities to run esports prediction contests where:

- Admins can upload match schedules via CSV and enter results
- Users can submit picks for upcoming matches
- Automatic scoring and leaderboard tracking
- Scheduled reminders for upcoming matches
- Support for multiple game integrations (starting with Valorant)

See [ITERATIONS.md](./ITERATIONS.md) for the development roadmap and detailed feature timeline.

## Prerequisites

- Python 3.10 or higher
- PostgreSQL database
- Discord Application with Bot Token
- Git

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/WxboySuper/Esports-Pickem-Discord-Bot.git
cd Esports-Pickem-Discord-Bot
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Up Environment Variables

Copy the example environment file and configure your settings:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

- `DISCORD_TOKEN`: Your Discord bot token from the Discord Developer Portal
- `DATABASE_URL`: PostgreSQL connection string (e.g., `postgresql://user:password@localhost:5432/pickem_bot`)
- `ADMIN_IDS`: Comma-separated list of Discord user IDs who can run admin commands
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `SENTRY_DSN`: (Optional) Sentry DSN for error tracking

### 4. Set Up Database

Run database migrations to create the required tables:

```bash
python -m alembic upgrade head
```

### 5. Run the Bot

Start the Discord bot:

```bash
python bot.py
```

The bot should now be online in your Discord server. Test with `/ping` to verify it's working.

## Local Development

### Database Setup

For local development, you can use a local PostgreSQL instance:

```bash
# Install PostgreSQL (Ubuntu/Debian)
sudo apt-get install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql
CREATE DATABASE pickem_bot;
CREATE USER pickem_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE pickem_bot TO pickem_user;
\q
```

Update your `.env` file with the local database URL:

```plaintext
DATABASE_URL=postgresql://pickem_user:your_password@localhost:5432/pickem_bot
```

### Running Tests

```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=src tests/
```

### Code Style

```bash
# Format code
black .

# Check linting
flake8 .

# Type checking
mypy .
```

## Basic Commands

Once the bot is running in your Discord server:

- `/ping` - Test if the bot is responsive
- `/pick <match_id> <prediction>` - Submit a pick for a match (users)
- `/picks` - View your current picks (users)
- `/leaderboard` - View contest leaderboard (users)
- `/upload_matches` - Upload match schedule via CSV (admins only)
- `/enter_result <match_id> <result>` - Enter match result (admins only)

## Project Structure

```plaintext
├── src/               # Main application code
├── tests/             # Test files
├── migrations/        # Database migrations
├── bot.py            # Main bot entry point
├── requirements.txt   # Python dependencies
├── .env.example      # Environment variables template
└── ITERATIONS.md     # Development roadmap
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and add tests
4. Run tests and ensure code style compliance
5. Submit a pull request

Please refer to [ITERATIONS.md](./ITERATIONS.md) for the current development priorities and planned features.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For questions or issues:

- Open an issue on GitHub
- Contact the maintainer: @WxboySuper
