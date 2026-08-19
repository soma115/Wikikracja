# Deployment Instructions for WikiKracja

This document contains instructions for developers setting up the development environment and deploying the Wikikracja application.

## Table of Contents
1. [Development Setup](#development-setup)
2. [Running the Application](#running-the-application)
3. [Database Management](#database-management)
4. [Deployment](#deployment)
5. [Common Issues and Fixes](#common-issues-and-fixes)
6. [Chat Room Categorization Fix](#chat-room-categorization-fix)

## Development Setup

### Prerequisites
- Python 3.11+
- PostgreSQL (for production) or SQLite (for development)
- Redis (for chat functionality)
- Docker and Docker Compose (optional)

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd wikikracja
   ```

2. **Start Redis with Docker Desktop**
   - Open Docker Desktop
   - Run Redis container:
   ```bash
   docker run -d -p 6379:6379 redis:latest
   ```

3. **Create and activate virtual environment**
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # Linux/Mac
   source .venv/bin/activate
   ```

4. **Run the automated setup**
   ```bash
   python scripts/start_dev.py --full
   ```

The `start_dev.py --full` command will:
- Copy `.env.example` to `.env` if needed
- Generate a secure `SECRET_KEY`
- Install dependencies from `requirements.txt`
- Create and apply migrations
- Update translation files
- Collect static files
- Start the development server

### Quick Start (Subsequent Runs)
For subsequent development sessions, just run:
```bash
# Start Redis if not running (ensure Docker Desktop is open)
docker run -d -p 6379:6379 redis:latest

# Activate virtual environment
.venv\Scripts\activate

# Start development server
python scripts/start_dev.py
```

## Development Scripts

The `scripts/` directory contains utility scripts to streamline development and deployment tasks:

### Development Setup Scripts

#### `start_dev.py` (Cross-platform)
Quick development server starter for Windows/Linux.
```bash
# Basic start (fast)
python scripts/start_dev.py

# Full setup (slower, includes migrations, i18n, static files)
python scripts/start_dev.py --full
```

Features:
- Automatically copies `.env.example` to `.env` if needed
- Generates secure `SECRET_KEY` automatically
- Runs migrations and starts development server
- With `--full`: installs dependencies, creates migrations, updates translations

#### `start_dev.sh` (Linux)
Linux-specific development setup with system dependencies.
```bash
./scripts/start_dev.sh
```

Features:
- Installs system dependencies (gettext, sqlite3, redis)
- Sets up and starts Redis server
- Runs full migration and translation setup
- Starts Daphne server (required for chat functionality)

### Docker Scripts

#### `build_docker_localy_on_windows.ps1` (Windows)
Build and run Docker containers locally on Windows.
```powershell
# Start containers
.\scripts\build_docker_localy_on_windows.ps1

# Start in detached mode
.\scripts\build_docker_localy_on_windows.ps1 -Detached

# Stop containers
.\scripts\build_docker_localy_on_windows.ps1 -Stop

# Restart containers
.\scripts\build_docker_localy_on_windows.ps1 -Restart

# Reset database
.\scripts\build_docker_localy_on_windows.ps1 -ResetDb
```

#### `build_and_push_docker_image.sh` (Linux)
Build and push Docker image to registry.
```bash
# Push to custom registry
REGISTRY_IMAGE=ghcr.io/username/wikikracja ./scripts/build_and_push_docker_image.sh

# Push to official registry (maintainer only)
CONFIRM_OFFICIAL_PUSH=1 ./scripts/build_and_push_docker_image.sh

# Custom tag
TAG=v1.2.3 ./scripts/build_and_push_docker_image.sh
```

### Utility Scripts

#### `import_fixtures.sh`
Import database fixtures for initial data.
```bash
./scripts/import_fixtures.sh
```

#### `repair_file_rights.sh`
Fix file permissions for production deployment.
```bash
./scripts/repair_file_rights /path/to/app user group
# Example:
./scripts/repair_file_rights . www-data www-data
```

#### `update_translations.ps1` (Windows)
Update translation files on Windows.
```powershell
./scripts/update_translations.ps1

# With specific Python binary
./scripts/update_translations.ps1 -PythonBin .venv\Scripts\python.exe
```

## Running the Application

### Development Server
```bash
python manage.py runserver
```

### Using Docker
```bash
# Build and run with Docker Compose
docker-compose up --build

# Or use the Windows script
.\scripts\build_docker_localy_on_windows.ps1
```

### Running Tests
```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test chat
python manage.py test tasks

# Linting and formatting checks
ruff check .
ruff format --check .
```

## Database Management

### Creating New Migrations
```bash
python manage.py makemigrations <app_name>
```

### Applying Migrations
```bash
python manage.py migrate
```

### Database Backup
```bash
# PostgreSQL
pg_dump wikikracja_db > backup.sql

# SQLite
cp db.sqlite3 backup.sqlite3
```

### Database Restore
```bash
# PostgreSQL
psql wikikracja_db < backup.sql

# SQLite
cp backup.sqlite3 db.sqlite3
```

## Deployment

### Official Docker Images

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

### Production Deployment with Docker

1. **Build the image**
   ```bash
   docker build -t wikikracja .
   ```

2. **Deploy with Docker Compose**
   ```bash
   docker-compose -f docker-compose.yml up -d
   ```

### Manual Deployment

1. **Install dependencies on server**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables**
   ```bash
   export DEBUG=False
   export DATABASE_URL=postgresql://user:pass@localhost/wikikracja
   export SECRET_KEY=your-secret-key
   ```

3. **Apply migrations**
   ```bash
   python manage.py migrate
   ```

4. **Collect static files**
   ```bash
   python manage.py collectstatic --noinput
   ```

5. **Restart application server**
   ```bash
   systemctl restart gunicorn
   # or
   supervisorctl restart wikikracja
   ```

## Common Issues and Fixes

### Multiple Users with Same Email Error

**Problem**: `django.contrib.auth.models.User.MultipleObjectsReturned: get() returned more than one User`

**Solution**: The authentication backend in `obywatele/auth_backends.py` automatically handles duplicate emails:
- Catches `MultipleObjectsReturned` exceptions
- Falls back to authenticating with the single active user if exactly one exists
- Logs errors for unresolved cases

The issue is resolved at the source - no manual migration required.

### Chat Room Categorization Issues

See the dedicated section below for detailed fix instructions.

### Static Files Not Loading

```bash
python manage.py collectstatic --noinput
```

### Permission Issues

```bash
# Fix file permissions for media files
chmod -R 755 media/
```

## Chat Room Categorization Fix

### Problem
Chat rooms are not properly categorized in production. Rooms have Polish prefixes ("Zadanie #", "Głosowanie #"), but the code filters by English prefixes.

### Solution
Changes have been made to:
1. Use constant English prefixes ("Task #", "Vote #") in room titles
2. Filter rooms by English prefixes (without translation)
3. Add a command to update existing rooms

### Implementation Steps

1. **Deploy code changes**
   Deploy the following files to production:
   - `chat/views.py` (lines 80-88) - changed filtering
   - `tasks/models.py` (lines 74-76) - English prefix in get_chat_room_title
   - `glosowania/models.py` (lines 90-92) - English prefix in get_chat_room_title
   - `glosowania/signals.py` (lines 21-22, 69-70) - English prefix in signals
   - `glosowania/views.py` (lines 227-231) - use model methods
   - `chat/management/commands/fix_room_titles.py` - new command

2. **Run the fix command**
   After deploying code, run the command on production server:
   ```bash
   python manage.py fix_room_titles
   ```

3. **Restart the server**
   ```bash
   systemctl restart gunicorn
   # or
   systemctl restart uwsgi
   # or
   supervisorctl restart wikikracja
   ```

4. **Verify the fix**
   Check that:
   - Rooms are properly categorized in chat interface
   - Links from Tasks and Votes work correctly
   - New rooms are created with English prefixes

### Command Output Example
```
Updated: "Zadanie #1: test" -> "Task #1: test"
Updated: "Zadanie #2: przykład" -> "Task #2: przykład"
Updated: "Głosowanie #1: propozycja" -> "Vote #1: propozycja"
Updated: "Głosowanie #2: test" -> "Vote #2: test"

Total rooms updated: 4 (2 tasks, 2 votes)
```

### What Changed

**Before:**
- Rooms created with translated prefixes (language-dependent)
- Filtering used `_("Task #")` and `_("Vote #")` (translated at runtime)
- Inconsistency between room titles and filtering

**After:**
- Rooms always created with English prefixes "Task #" and "Vote #"
- Filtering uses constant strings "Task #" and "Vote #"
- Consistency between room titles and filtering

### Notes
- The command is safe and can be run multiple times
- If no rooms need updating, it will show an appropriate message
- The command doesn't delete or modify message content in rooms
- Only room titles are changed

## Configuration

All configuration is done via environment variables. See `.env.example` for the complete list of available options.

### Essential Settings in `.env`

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

### Additional Environment Variables

Key configuration options in `.env`:

- **Logging**: `LOGGING_DESTINATION` (console/file), `LOG_LEVEL` (DEBUG/INFO/WARNING/ERROR)
- **Sessions**: `SESSION_EXPIRE_AT_BROWSER_CLOSE`, `SESSION_COOKIE_AGE`, `REMEMBER_ME_DAYS`
- **Voting**: `WYMAGANYCH_PODPISOW`, `CZAS_NA_ZEBRANIE_PODPISOW`, `CZAS_TRWANIA_REFERENDUM`
- **Chat**: `ARCHIVE_PUBLIC_CHAT_ROOM`, `DELETE_PUBLIC_CHAT_ROOM`
- **Uploads**: `UPLOAD_IMAGE_MAX_SIZE_MB`, `DATA_UPLOAD_MAX_MEMORY_SIZE`
- **Citizens**: `ACCEPTANCE`, `DELETE_INACTIVE_USER_AFTER`

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

