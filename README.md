# Wikikracja

**Democratic platform for collaborative decision-making and community building.**
**Hardcoded Direct Democracy**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![GitHub last commit](https://img.shields.io/github/last-commit/soma115/wikikracja)
[![Website](https://img.shields.io/website?url=https%3A%2F%2Fwikikracja.pl)](https://wikikracja.pl)
[![Build Docker Image](https://github.com/soma115/wikikracja/actions/workflows/docker-build.yml/badge.svg)](https://github.com/soma115/wikikracja/actions/workflows/docker-build.yml)
[![ghcr.io](https://img.shields.io/badge/ghcr.io-soma115%2Fwikikracja-blue?logo=docker)](https://github.com/soma115/wikikracja/pkgs/container/wikikracja)

## Features

A comprehensive community platform with the following modules:

- 🗳️ **Voting** - Democratic referendum system with Zero Knowledge Proof for anonymous voting
- 👥 **Citizens** - User management and authentication with django-allauth
- 💬 **Chat** - Real-time communication using Django Channels and WebSockets
-  **Board** - Announcements and news board
- 💰 **Bookkeeping** - Financial transparency and tracking
- 📅 **Events** - Event management and scheduling
- ✅ **Tasks** - Collaborative task management with voting-based prioritization

## Demo

Try the live demo: **https://demo.wikikracja.pl/**

## Tech Stack

- **Backend**: Django 6.0.3, Django Channels 4.3.2, Python 3.14
- **Frontend**: Bootstrap 5, TinyMCE 5.0, Crispy Bootstrap5
- **Database**: SQLite (development), PostgreSQL (production ready)
- **Cache/Channels**: Redis 7.2.1
- **Deployment**: Docker, Linux (production), Windows (development)
- **Authentication**: django-allauth 65.14.3 with email verification
- **Security**: CSRF protection, django-simple-captcha, secure password policies
- **Real-time**: Daphne ASGI server, WebSockets via Django Channels

## Quick Start

### Development Environment

#### Prerequisites
- Python 3.14 (install from [python.org](https://www.python.org/downloads/) on Windows; add to PATH)
- Redis server (for Django Channels and caching)
- SMTP account (optional for development, required for production email functionality)

#### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/soma115/wikikracja.git
   cd wikikracja
   ```

2. **Create & activate virtual environment**
   ```bash   
   # Windows
   py -3.14 -m venv .venv 
   .venv\Scripts\activate 

   # Linux / macOS
   python -m venv .venv
   source .venv/bin/activate 
   ```

3. **Install dependencies (manual option)**
   ```bash   
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings (SECRET_KEY, email config, etc.)
   ```

5. **Initialize database and create superuser**
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

6. **Start Redis server** (required for Django Channels)
   ```bash
   # Linux/macOS
   redis-server
   
   # Windows (if installed via WSL or native)
   redis-server
   # Or use Docker: docker run -p 6379:6379 redis:latest
   ```

7. **Run development server**
   ```bash
   # Using helper script
   python ./scripts/start_dev.py --full
   
   # Or manually
   python manage.py runserver
   ```

8. **Access the application**
   - Web: http://localhost:8000

### Docker Development

#### Quick start with docker-compose

```bash
# Copy environment file
cp .env.example .env

# Edit .env with your configuration
nano .env

# Start services
docker-compose up

# Access at http://localhost:8000
```

## Docker Images

### Official Images

Pre-built images are automatically published to GitHub Container Registry:

```bash
# Pull latest official image
docker pull ghcr.io/soma115/wikikracja:latest

# Run with docker-compose
docker-compose up
```

**Available tags:**
- `latest` - Latest stable release (main branch)
- `develop` - Development branch
- `v1.2.3` - Specific version tags
- `main-abc1234` - Commit-specific builds

### Building Your Own Image

#### Option 1: Using the build script

```bash
# Build and push to your own registry
REGISTRY_IMAGE=ghcr.io/<your-username>/wikikracja ./scripts/build_and_push_docker_image.sh

# Or for other registries:
# GitLab: REGISTRY_IMAGE=registry.gitlab.com/<username>/wikikracja ./scripts/build_and_push_docker_image.sh
# Docker Hub: REGISTRY_IMAGE=<username>/wikikracja ./scripts/build_and_push_docker_image.sh
```

#### Option 2: Manual build

```bash
# Build locally
docker build -t wikikracja:test .

# Test locally
docker run -p 8000:8000 --env-file .env wikikracja:test
```

#### Option 3: Automatic builds with GitHub Actions

Fork this repository and GitHub Actions will automatically build and push images on every commit to `main`.

**Setup:**
1. Fork the repository
2. Enable GitHub Actions in your fork
3. Images will be automatically built and pushed to `ghcr.io/<your-username>/wikikracja`
4. (Optional) Make package public in GitHub settings

See `.github/workflows/docker-build.yml` for details.

## Configuration

All configuration is done via environment variables. See `.env.example` for all available options.

### Essential Settings in .env

```bash
# Security (REQUIRED in production)
SECRET_KEY=your-secret-key-here
DEBUG=False

# Site configuration
SITE_DOMAIN=yourdomain.com
SITE_NAME="Your Site Name"
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com

# Email (REQUIRED for user registration)
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@example.com
EMAIL_HOST_PASSWORD=your-password
SERVER_EMAIL=noreply@yourdomain.com
DEFAULT_FROM_EMAIL=noreply@yourdomain.com

# Redis (for Django Channels and caching)
# Use 'redis' hostname when running with docker-compose
# Use '127.0.0.1' when running Django locally
REDIS_HOST=redis://redis:6379/1
```

### Generate SECRET_KEY

```bash
# Using Django
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Using OpenSSL
openssl rand -base64 50
```

## Contributing

We welcome contributions! Here's how you can help:

### Reporting Issues

- Use the [GitHub issue tracker](https://github.com/soma115/wikikracja/issues)
- Include steps to reproduce
- Provide error messages and logs
- Mention your environment (OS, Python version, Docker version, etc.)

### Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (if available)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to your fork (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guide
- Add comments for complex logic
- Update documentation for new features
- Test your changes locally before submitting
- Keep commits atomic and well-described

## Deployment

### Docker Deployment

See `docker-compose.yml` for a production-ready setup with Redis.

**Key features:**
- Automatic Site domain configuration via initContainer
- Node selectors for specific node placement
- PersistentVolumeClaims for data storage
- CronJobs for scheduled tasks

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Web Browser (User)                             │
└────────────────┬────────────────────────────────┘
                 │ HTTPS
                 ▼
┌─────────────────────────────────────────────────┐
│  Django Application (Daphne ASGI Server)        │
│  ┌────────────────────────────────────────────┐ │
│  │ Django Views (HTTP)                        │ │
│  │ Django Channels (WebSocket)                │ │
│  └────────────────────────────────────────────┘ │
└──────┬──────────────────────┬───────────────────┘
       │                      │
       ▼                      ▼
┌─────────────┐      ┌──────────────────┐
│   SQLite    │      │   Redis          │
│  (Database) │      │ (Channels Layer) │
└─────────────┘      └──────────────────┘
```

## Management Commands

Custom management commands available:

```bash
# Chat management
python manage.py chat_messages      # Manage chat messages
python manage.py chat_rooms         # Manage chat rooms

# User management
python manage.py count_citizens     # Count registered citizens

# Voting system
python manage.py vote               # Voting-related operations

# Site configuration
python manage.py update_site        # Update site domain and name from environment variables
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Additional Configuration

### Environment Variables

Key configuration options in `.env`:

- **Logging**: `LOGGING_DESTINATION` (console/file), `LOG_LEVEL` (DEBUG/INFO/WARNING/ERROR)
- **Sessions**: `SESSION_EXPIRE_AT_BROWSER_CLOSE`, `SESSION_COOKIE_AGE`, `REMEMBER_ME_DAYS`
- **Voting**: `WYMAGANYCH_PODPISOW`, `CZAS_NA_ZEBRANIE_PODPISOW`, `CZAS_TRWANIA_REFERENDUM`
- **Chat**: `ARCHIVE_PUBLIC_CHAT_ROOM`, `DELETE_PUBLIC_CHAT_ROOM`
- **Uploads**: `UPLOAD_IMAGE_MAX_SIZE_MB`, `DATA_UPLOAD_MAX_MEMORY_SIZE`
- **Citizens**: `ACCEPTANCE`, `DELETE_INACTIVE_USER_AFTER`

See `.env.example` for complete list and descriptions.

## Support

- **Issues**: [GitHub Issues](https://github.com/soma115/wikikracja/issues)
- **Discussions**: [GitHub Discussions](https://github.com/soma115/wikikracja/discussions)
- **Demo**: https://demo.wikikracja.pl/
- **Philosophy**: https://wikikracja.pl

---

Made with ❤️ for democratic communities
