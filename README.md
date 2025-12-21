# Wikikracja

**Democratic wiki platform for collaborative decision-making and community building.**

[![Build Docker Image](https://github.com/wikikracja/wikikracja/actions/workflows/docker-build.yml/badge.svg)](https://github.com/wikikracja/wikikracja/actions/workflows/docker-build.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Features

A comprehensive community platform with the following modules:

- 🗳️ **Voting** - Democratic referendum system with Zero Knowledge Proof for anonymous voting
- 👥 **Citizens** - User management and authentication with django-allauth
- 💬 **Chat** - Real-time communication using Django Channels and WebSockets
- 📚 **eLibrary** - Document management and sharing
- 📋 **Board** - Announcements and news board
- 💰 **Bookkeeping** - Financial transparency and tracking
- 📅 **Events** - Event management and scheduling

## Demo

Try the live demo: **https://demo.wikikracja.pl/**

Production instances:
- https://w1.wikikracja.pl/
- https://w2.wikikracja.pl/

## Tech Stack

- **Backend**: Django 5.1, Django Channels, Python 3.11
- **Frontend**: Bootstrap 4, TinyMCE, Crispy Forms
- **Database**: SQLite (development), PostgreSQL (production ready)
- **Cache/Channels**: Redis
- **Deployment**: Docker, Kubernetes (with Flux CD GitOps)
- **Authentication**: django-allauth with email verification
- **Security**: CSRF protection, reCAPTCHA, secure password policies

## Quick Start

### Development Environment

#### Prerequisites
- Python 3.11+
- Redis server (for Django Channels)
- SMTP account (for sending emails)

#### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/wikikracja/wikikracja.git
   cd wikikracja
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings (SECRET_KEY, email config, etc.)
   ```

5. **Run development server**
   ```bash
   ./scripts/start_dev.sh
   ```

   Or manually:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   python manage.py runserver
   ```

6. **Access the application**
   - Web: http://localhost:8000
   - Admin: http://localhost:8000/admin

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
docker pull ghcr.io/wikikracja/wikikracja:latest

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
# Docker Hub: REGISTRY_IMAGE=docker.io/<username>/wikikracja ./scripts/build_and_push_docker_image.sh
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

### Essential Settings

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

# Redis (for Django Channels)
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

- Use the [GitHub issue tracker](https://github.com/wikikracja/wikikracja/issues)
- Include steps to reproduce
- Provide error messages and logs
- Mention your environment (OS, Python version, etc.)

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

### Kubernetes Deployment

Example Kubernetes manifests are available in the deployment documentation. The official instances use Flux CD for GitOps-based deployment.

**Key features:**
- Automatic Site domain configuration via initContainer
- Node selectors for specific node placement
- PersistentVolumeClaims for data storage
- Traefik IngressRoutes with Let's Encrypt SSL
- CronJobs for scheduled tasks

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Web Browser (User)                             │
└────────────────┬────────────────────────────────┘
                 │ HTTPS
                 ▼
┌─────────────────────────────────────────────────┐
│  Traefik (Reverse Proxy + SSL)                  │
└────────────────┬────────────────────────────────┘
                 │
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

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Documentation**: See `/docs` folder (if available)
- **Issues**: [GitHub Issues](https://github.com/wikikracja/wikikracja/issues)
- **Discussions**: [GitHub Discussions](https://github.com/wikikracja/wikikracja/discussions)
- **Demo**: https://demo.wikikracja.pl/

## Acknowledgments

Built with Django and the amazing Django ecosystem. Special thanks to all contributors!

---

Made with ❤️ for democratic communities
