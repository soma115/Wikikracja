# Wikikracja

**Democratic platform for collaborative decision-making and community building.**
**Hardcoded Direct Democracy**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![GitHub last commit](https://img.shields.io/github/last-commit/soma115/wikikracja)
[![Website](https://img.shields.io/website?url=https%3A%2F%2Fwikikracja.pl)](https://wikikracja.pl)
[![Build Docker Image](https://github.com/soma115/wikikracja/actions/workflows/docker-build.yml/badge.svg)](https://github.com/soma115/wikikracja/actions/workflows/docker-build.yml)
[![ghcr.io](https://img.shields.io/badge/ghcr.io-soma115%2Fwikikracja-blue?logo=docker)](https://github.com/soma115/wikikracja/pkgs/container/wikikracja)

## Features

A community platform for citizen-led groups, with modules for proposals and voting, surveys, documents, chat, events, tasks and bookkeeping.

## Demo

Try the live demo: **https://demo.wikikracja.pl/**

## Tech Stack

- **Backend**: Django ~6.0.4, Django Channels 4.3.2 + Daphne (ASGI), Python >=3.14, JavaScript, CSS
- **Frontend**: Tailwind CSS 3.4 (prefixed `tw-`), django-crispy-forms, TinyMCE
- **Database**: SQLite in development and production (one database per deployed instance)
- **Cache/Channels**: Redis (cache, channel layer and notification queue)
- **Deployment**: Docker images published to GitHub Container Registry; production is managed with Kubernetes and Flux
- **Authentication**: django-allauth
- **Additional libraries**: APScheduler, firebase-admin (FCM)
- **Testing**: Jest (JavaScript, Node 22), pytest (Python), Ruff (linting)

## Prerequisites

- Python 3.14+
- Redis 7 (for Channels, cache and notification delivery; it can run in Docker)
- Node.js 22+ and npm (optional, for frontend tests and CSS development)
- Docker and Docker Compose (optional, for the local container setup)

## Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/soma115/wikikracja.git
   cd wikikracja
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate            # Windows
   # source .venv/bin/activate       # Linux/macOS
   ```

3. **Install Python dependencies**
   ```bash
   python -m pip install --upgrade pip setuptools==80.9.0
   python -m pip install --no-build-isolation -r requirements.txt
   ```

4. **Start Redis 7** (for example, with Docker)
   ```bash
   docker run -d -p 6379:6379 redis:7
   ```
   You can use an existing local or managed Redis service instead.

   Before the first start, copy `.env.example` to `.env` (`copy .env.example .env` on Windows, `cp .env.example .env` on Linux/macOS). For Django running directly on your computer, set `REDIS_HOST=redis://127.0.0.1:6379/1`; the sample `host.docker.internal` address is for Docker containers.

5. **Optional: install frontend dependencies** (for Jest, Playwright and CSS builds)
   ```bash
   npm ci
   ```

## Quick Start

With the virtual environment activated and Redis running, start the development setup:

```bash
python scripts/start_dev.py --full
```

The script prepares `.env` on first run, applies migrations and starts the development server. Subsequent runs can skip the slower setup tasks:

```bash
python scripts/start_dev.py
```

The server listens at http://localhost:8006 by default; pass `--port 8000` to use another port.

For detailed development, testing, Docker, deployment, configuration and management instructions, see [docs/DEPLOYMENT_INSTRUCTIONS.md](docs/DEPLOYMENT_INSTRUCTIONS.md).

## Testing

Run focused checks from the activated virtual environment, for example:

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
npm test
```

The full project verification pipeline is available through:

```bash
python scripts/run_tests.py
```

It also runs Playwright end-to-end tests, so install the Node dependencies and Chromium and configure the dedicated test account in the ignored `.env.local` (`E2E_EMAIL` and `E2E_PASSWORD`). The runner prepares `.env` and runs `collectstatic --clear`; use focused checks when you do not need the full pipeline.

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

---

Made with ❤️ for democratic communities
