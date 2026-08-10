# Wikikracja

**Democratic platform for collaborative decision-making and community building.**
**Hardcoded Direct Democracy**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![GitHub last commit](https://img.shields.io/github/last-commit/soma115/wikikracja)
[![Website](https://img.shields.io/website?url=https%3A%2F%2Fwikikracja.pl)](https://wikikracja.pl)
[![Build Docker Image](https://github.com/soma115/wikikracja/actions/workflows/docker-build.yml/badge.svg)](https://github.com/soma115/wikikracja/actions/workflows/docker-build.yml)
[![ghcr.io](https://img.shields.io/badge/ghcr.io-soma115%2Fwikikracja-blue?logo=docker)](https://github.com/soma115/wikikracja/pkgs/container/wikikracja)

## Features

A community platform with modules for voting, citizens, chat, board, bookkeeping, events and tasks.

## Demo

Try the live demo: **https://demo.wikikracja.pl/**

## Tech Stack

- **Backend**: Django, Django Channels, Python
- **Frontend**: Bootstrap, TinyMCE
- **Database**: SQLite (development), PostgreSQL (production)
- **Cache/Channels**: Redis
- **Deployment**: Docker
- **Authentication**: django-allauth

## Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/soma115/wikikracja.git
   cd wikikracja
   ```

2. **Run the development server**
   ```bash
   python scripts/start_dev.py --full
   ```

3. **Access the application**
   - Web: http://localhost:8000

For detailed setup, deployment, Docker, configuration and management commands, see [docs/DEPLOYMENT_INSTRUCTIONS.md](docs/DEPLOYMENT_INSTRUCTIONS.md).

## Documentation

- [Deployment & Development](docs/DEPLOYMENT_INSTRUCTIONS.md)
- [Onboarding Process](docs/ONBOARDING_PROCESS.md)
- [System Parameters Voting - Users](docs/Glosowanie_nad_parametrami_systemu-dla_uzytkownikow.md)
- [System Parameters Voting - Developers](docs/Glosowanie_nad_parametrami_systemu-dla_developerow.md)
- [Notifications](docs/POWIADOMIENIA.md)
- [Contributing](docs/CONTRIBUTING.md)
- [Changelog](docs/CHANGELOG.md)
- [Roadmap / TODO](docs/TODO.md)

## Support

- **Issues**: [GitHub Issues](https://github.com/soma115/wikikracja/issues)
- **Discussions**: [GitHub Discussions](https://github.com/soma115/wikikracja/discussions)
- **Demo**: https://demo.wikikracja.pl/
- **Philosophy**: https://wikikracja.pl

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
