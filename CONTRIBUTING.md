# Contributing to Esports Pickem Discord Bot

Thank you for your interest in contributing to the Esports Pickem Discord Bot! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone. Please be kind and constructive in your communications with other contributors.

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Discord developer account
- Git

### Development Environment Setup
For more information about the [Development Environment](docs/setup/environment.md) 

1. Fork the repository
2. Clone your fork:
   ```shell
   git clone https://github.com/your-username/Esports-Pickem-Discord-Bot.git
   cd Esports-Pickem-Discord-Bot
   ```
3. Set up a virtual environment:
   ```shell
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
4. Install dependencies:
   ```shell
   pip install -r requirements.txt
   ```
5. Set up environment variables:
   - Create a `.env` file based on the instructions in [Environment Variables Setup Guide](docs/setup/environment-variables.md)

## Development Workflow

1. Create a new branch for your feature/fix:
   ```shell
   git checkout -b feature/your-feature-name
   ```
   or
   ```shell
   git checkout -b fix/your-bugfix-name
   ```

2. Make your changes and commit them:
   ```shell
   git add .
   git commit -m "Description of your changes"
   ```

3. Push your branch to your fork:
   ```shell
   git push origin feature/your-feature-name
   ```

4. Open a Pull Request to the main repository

## Pull Request Process

1. Ensure your code follows the project's coding standards
2. Update documentation if needed
3. Include tests for new features
4. Fill out the pull request template completely
5. Request reviews from maintainers
6. Address any feedback or requested changes

## Issue Management

### Reporting Bugs

1. Check existing issues to prevent duplicates
2. Use the "Bug Report" issue template
3. Provide detailed steps to reproduce
4. Include error messages and logs if applicable

### Requesting Features

1. Check existing issues and roadmap
2. Use the "Feature Request" issue template
3. Clearly describe the feature and its benefits
4. Consider implementation details if possible

## Labeling System

We use a comprehensive labeling system to organize issues and pull requests. Please see the [Label System Documentation](docs/Label-System.md) for details.

## Coding Standards

### Python Guidelines

- Follow PEP 8 style guide
- Use type hints where appropriate
- Maximum line length: 150 characters
- Use docstrings for functions and classes
- Maintain test coverage for new code

### Discord Bot Guidelines

- Keep command responses concise and helpful
- Follow Discord API best practices
- Consider rate limits in API calls
- Use embeds for formatted responses
- Implement proper error handling for user interactions

## Testing

- Write unit tests for new functionality
- Test commands in a development server before submitting
- Ensure database migrations are tested
- Verify API integrations work as expected

## Documentation

- Update README.md for major changes
- Document new commands in appropriate documentation files
- Add inline comments for complex code
- Update API documentation when integrating new services

## Project Structure

```
discord-esports-pickem/
├── docs/               # Documentation files
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

## Review Process

1. Pull requests require approval from at least one maintainer
2. Automated tests must pass
3. Documentation must be updated
4. Code style must be consistent

Thank you for contributing to the Esports Pickem Discord Bot!
