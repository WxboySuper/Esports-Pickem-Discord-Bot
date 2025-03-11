# Esports Pickem Discord Bot

Welcome to the Discord Esports Pickem project! This bot allows users to compete in esports by making predictions on match outcomes. Users can select their picks, view personal stats, and see a leaderboard of competitors within their Discord server.

## Current Project Status

This project is currently being rebuilt with a focus on automation and efficiency. We're moving from manual match updates to automated match tracking with minimal intervention required. The goal is to create a system that's both feature-rich and cost-effective to host.

## Features

- **Match Management**
  - Automated match tracking and updates
  - Match data fetching from official APIs
  - Automatic winner detection and result processing
  - Support for multiple esports titles/leagues
  - Match reminders and notifications

- **User Interactions**
  - Match predictions via Discord interactions
  - Personal statistics tracking
  - Daily/Weekly summaries of picks
  - Active picks viewing
  - Customizable notification preferences

- **Competition System**
  - Server-based leaderboards (daily/weekly/all-time)
  - Point scoring system
  - Streak tracking
  - Season/Tournament-based rankings

- **Administrative Features**
  - Automated match management
  - Manual override capabilities
  - Error monitoring and reporting
  - Server configuration options
  - Analytics dashboard

### Note
Currently, this implementation supports only Tier 1 LoL Esports, with plans to expand to additional esports titles.

## Project Structure
Current Project Structure, this is expected to change when development continues.

```
discord-esports-pickem
├── docs
   └── setup
├── config
└── requirements.txt
```

## Technical Requirements

### Automation
- League/Tournament data scraping
- Match status monitoring
- Result verification
- Database maintenance
- Backup systems

### API Integration
- Official esports APIs
- Tournament platforms
- Stats providers

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

1. Create a `.env` file in the root directory with your Discord bot credentials and database settings
2. See detailed instructions in the [Environment Variables Setup Guide](docs/setup/env.md)
3. Update the `config/config.yml` file with any additional configuration settings

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

## Development Roadmap

- Implement automated match tracking for LoL Esports
- Add support for additional esports titles
- Enhance statistics and user interaction features
- Improve scalability and performance optimization
- Develop comprehensive monitoring systems

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or features.

## License

This project is licensed under the MIT License. See the LICENSE file for details.
