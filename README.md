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

- **Backend**: Django ~6.0.4, Django Channels 4.3.2 + Daphne (ASGI), Python >=3.14, JavaScript, CSS
- **Frontend**: Bootstrap 5 + crispy-bootstrap5, TinyMCE
- **Database**: SQLite (development), PostgreSQL (production)
- **Cache/Channels**: Redis (cache and channel layer)
- **Deployment**: Docker, GitHub Actions
- **Authentication**: django-allauth
- **Additional libraries**: django-tables2, django-filter, APScheduler, firebase-admin (FCM)
- **Testing**: Jest (JavaScript, Node 22), pytest (Python), Ruff (linting)

## Prerequisites

- Python 3.14+
- Redis (for channels/cache; can run via Docker)
- Node 22 (optional, for JavaScript tests)

## Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/soma115/wikikracja.git
   cd wikikracja
   ```

2. **Start Redis**
   ```bash
   docker run -d -p 6379:6379 redis:latest
   ```

3. **Create and activate a virtual environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate            # Windows
   # source .venv/bin/activate       # Linux/Mac
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   npm install
   pre-commit install
   ```

## Quick Start

Run the automated development setup:

```bash
python scripts/start_dev.py --full
```

For subsequent runs:

```bash
python scripts/start_dev.py
```

Access the application at http://localhost:8000.

For detailed setup, deployment, Docker, configuration and management commands, see [docs/DEPLOYMENT_INSTRUCTIONS.md](docs/DEPLOYMENT_INSTRUCTIONS.md).

## Testing

After changes, run the test suites and linting:

```bash
npx jest
python -m pytest -q
ruff check .
ruff format --check .
```

For a single combined command, use:

```bash
python scripts/run_tests.py
```

Pre-commit hooks run `ruff` and `ruff-format` automatically before each commit.

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
