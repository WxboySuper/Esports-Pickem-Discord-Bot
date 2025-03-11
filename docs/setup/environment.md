# Development Environment

This document outlines the development environment used for the Esports Pickem Discord Bot project.

## Core Technologies

### Languages and Runtime
- **Python 3.12** - Primary programming language
- **Markdown** - Used for documentation

### Version Control
- **Git** - For source code management
- **GitHub** - For repository hosting, PR management, and CI/CD
- **.gitignore** - Configured for Python projects

### Development Environment
- **Virtual Environment** - Using Python's built-in `venv` module
- **.env** files - For environment variable management (not committed to repository)

## Project Structure
```
discord-esports-pickem/
├── docs/               # Documentation files
│   └── setup/          # Setup-related documentation
├── src/                # Source code
│   ├── api/            # API integrations
│   ├── bot/            # Discord bot framework
│   ├── commands/       # Bot commands
│   ├── database/       # Database models and utilities
│   ├── framework/      # Core functionality
│   ├── match/          # Match tracking
│   ├── picks/          # User picks system
│   └── monitoring/     # Logging and monitoring
├── tests/              # Test files
└── scripts/            # Utility scripts
```

## Dependency Management
- **requirements.txt** - Lists Python package dependencies
- **pip** - Used for package installation

## Discord Integration
- **Discord Developer Portal** - For bot registration
- **Discord API** - For bot functionality and interactions
- **Discord Gateway** - For receiving real-time events

## Testing and Quality Assurance
- **Coverage** - For measuring test coverage (.coveragerc)
- **unittest** - For running tests
- **DeepSource** - For automated code quality analysis (.deepsource.toml)
- **CodeRabbit** - For automated PR Reviews
- **Copilot** - For automated PR Reviews among other things

## Continuous Integration / Continuous Deployment
- **GitHub Actions** - For automated workflows
  - PR labeling automation
  - Dependency updates via Dependabot
  - Code quality checks

## Environment Variables
The following environment variables are used:
- Discord Bot Credentials (tokens, IDs)
- Database settings
- API keys for external services

Refer to [Environment Variables Setup Guide](environment-variables.md) for detailed configuration.

## Development Workflow
1. Feature development is tracked in GitHub issues
2. Development follows the branch-based workflow:
   ```
   git checkout -b feature/feature-name
   ```
3. Changes are submitted via Pull Requests
4. CI/CD validates changes before merging
5. The project follows the phases outlined in the rebuild checklist

## Editor Configuration
While any text editor can be used, the project is optimized for:
- **Visual Studio Code** with Python extensions
  - Settings are stored in `.vscode/` (gitignored)
  
## Setup Instructions
For detailed instructions on setting up your development environment, please refer to the [CONTRIBUTING.md](../../CONTRIBUTING.md) file in the root directory.
