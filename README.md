# Esports Pickem Discord Bot

Welcome to the Discord Esports Pickem project! This bot allows users to compete in esports by making predictions on match outcomes. Users can select their picks, view personal stats, and see a leaderboard of competitors within their Discord server.

## Features

- **User Picks**: Users can make predictions on match outcomes and save them to a database.
- **Personal Stats**: Users can view their own statistics and performance.
- **Leaderboard**: A leaderboard displays the rankings of users based on their picks.
- **Admin Dashboard**: An admin interface to manage matchups, view statistics, and oversee bot operations.

**Note: Current Implementation currently only works with Tier 1 LoL Esports as it is manually updated**

## Project Structure

```
discord-esports-pickem
├── src
│   ├── bot
│   ├── dashboard
│   └── models
├── config
└── requirements.txt
```

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   ```
2. Navigate to the project directory:
   ```
   cd discord-esports-pickem
   ```
3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Configuration

Update the `config/config.yml` file with your Discord bot token and database connection details.

## Running the Bot

To start the Discord bot, run:
```
python src/bot/bot.py
```

## Running the Admin Dashboard

To start the admin dashboard, run:
```
python src/dashboard/app.py
```

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or features.

## License

This project is licensed under the MIT License. See the LICENSE file for details.
