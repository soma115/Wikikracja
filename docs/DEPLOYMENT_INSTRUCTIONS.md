# Deployment Instructions for WikiKracja

This document contains instructions for developers setting up the development environment and deploying the Wikikracja application.

## Table of Contents
1. [Development Setup](#development-setup)
2. [Running the Application](#running-the-application)
3. [Database Management](#database-management)
4. [Deployment](#deployment)
5. [Chat Notification Worker](#chat-notification-worker)
6. [Common Issues and Fixes](#common-issues-and-fixes)
7. [Chat Room Categorization Fix](#chat-room-categorization-fix)

## Development Setup

### Prerequisites
- Python 3.11+
- PostgreSQL (for production) or SQLite (for development)
- Redis (for chat functionality and notification delivery)
- Docker and Docker Compose (recommended for Redis and the notification worker)

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
# Build and start web, Redis and the chat notification worker
docker compose up --build

# Run in the background
docker compose up --build -d

# Stop the stack
docker compose down

# Or use the Windows script
.\scripts\build_docker_localy_on_windows.ps1
```

The Compose stack does not create or persist Redis. Both `web` and
`chat_notifications_worker` connect to the externally managed Redis configured by
`REDIS_HOST` in `.env`. The worker consumes the
`wikikracja:chat:notifications` Redis Stream. Configure Redis persistence and
availability outside this repository according to the cluster's policy.

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

# SQLite — run in the 04:00 maintenance window; backup first, then VACUUM
python scripts/sqlite_maintenance.py backup backups/db-$(date +%Y%m%d-%H%M%S).sqlite3 --vacuum-after
```

### Database Restore
Stop all application and scheduler processes before restoring SQLite. Move the
current database and its `-wal`/`-shm` sidecars to a quarantine directory instead
of deleting them. Do not let the restored database reuse old sidecars.

```bash
# PostgreSQL
psql wikikracja_db < backup.sql

# SQLite — after stopping the application
mkdir -p restore-quarantine
mv db.sqlite3 db.sqlite3-wal db.sqlite3-shm restore-quarantine/ 2>/dev/null || true
cp backup.sqlite3 db.sqlite3
python scripts/sqlite_maintenance.py integrity-check
```

### SQLite Maintenance
For containers, configure the database and backup volume explicitly:

```env
SQLITE_DATABASE_PATH=/app/db/db.sqlite3
SQLITE_BACKUP_DIR=/var/backups/wikikracja
SQLITE_BACKUP_RETENTION_DAYS=30
```

Mount `SQLITE_BACKUP_DIR` as a persistent volume. The application database path
and maintenance script use the same `SQLITE_DATABASE_PATH`. For an active SQLite
database, use the SQLite backup API instead of copying only `db.sqlite3` while
WAL files may be present:

```bash
# Create a consistent backup and then compact the live database
# Use only during the 04:00 maintenance window when application writes are blocked.
python scripts/sqlite_maintenance.py backup backups/db-$(date +%Y%m%d-%H%M%S).sqlite3 --vacuum-after

# Verify the database
python scripts/sqlite_maintenance.py integrity-check

# Run a non-blocking WAL checkpoint
python scripts/sqlite_maintenance.py checkpoint --mode PASSIVE
```

Run `TRUNCATE` checkpoints only as a controlled maintenance operation after
checking active processes and confirming a current backup.

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

## Chat Notification Worker

Chat message delivery is split into two parts:

1. the web process saves the message, updates unread state and broadcasts the message
   to the room immediately;
2. personal WebSocket notifications, push notifications and mention notifications are
   queued in Redis Streams and delivered by `chat_notifications_worker`.

The worker uses an at-least-once delivery model. It acknowledges a Redis Stream entry
only after delivery succeeds and reclaims entries left pending by a stopped worker.
A short-lived delivery marker prevents normal redelivery of an already completed job.
A crash between external delivery and the marker can still produce a duplicate, so
consumers must remain tolerant of duplicate notification IDs.

### Docker Compose

The worker starts automatically with:

```bash
docker compose up --build -d
```

Inspect worker logs with:

```bash
docker compose logs -f chat_notifications_worker
```

Restart only the worker with:

```bash
docker compose restart chat_notifications_worker
```

### Manual worker

When running Django outside Docker, start Redis first and run the worker in a separate
terminal using the same environment as Django:

```bash
.venv/Scripts/python.exe manage.py run_chat_notifications_worker
```

On Linux/macOS use `.venv/bin/python` instead. The worker must run continuously; it is
not started by Daphne automatically.

### Kubernetes

This repository does not deploy Redis to Kubernetes. Use the existing managed Redis
service and configure the same endpoint for both the web Deployment and the chat
notification worker Deployment.

Create or update a Secret (use your cluster's secret-management process in production):

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: wikikracja-runtime
  namespace: wikikracja
stringData:
  REDIS_HOST: rediss://:<redis-password>@managed-redis.example:6379/1
  REDIS_CHANNEL_PREFIX: wikikracja-production
```

Use `redis://` instead of `rediss://` only when Redis is inside a trusted private
network without TLS. The password must be URL-encoded if it contains URL-reserved
characters.

Reference the Secret from both application workloads:

```yaml
envFrom:
  - secretRef:
      name: wikikracja-runtime
```

The worker workload must use the same image and environment as the web workload, but
run this command instead of Daphne:

```yaml
command: ["python", "manage.py", "run_chat_notifications_worker"]
```

Do not add a Redis StatefulSet, Redis PVC, or Redis Service from this repository. Redis
is intentionally external and may be configured as in-memory only. With an in-memory
Redis, a Redis restart loses queued personal notifications and Channels presence state;
messages remain stored in SQLite. Run at least one worker replica, and scale workers
only when the shared Redis and database can support it. The consumer group safely
assigns new jobs between multiple workers.

The cluster must provide:

- network access from both Deployments to the Redis endpoint;
- Redis Streams commands (`XADD`, `XREADGROUP`, `XAUTOCLAIM`, `XACK`);
- enough memory for Channels, cache and the notification Stream;
- a restart policy for the worker;
- Firebase credentials separately if FCM push delivery is required.

### Redis availability and durability

The worker uses the existing `REDIS_HOST` setting and does not require or create a
second Redis server. Redis is an external dependency of both the web process and the
worker. Configure the endpoint in `.env` for local Docker, or through a Kubernetes
Secret/Deployment environment variable in the cluster.

This chat queue is compatible with an in-memory Redis. Chat messages remain safe in
SQLite, but queued personal push/WebSocket notifications may be lost if Redis restarts
before delivery. If the cluster's Redis policy allows persistence, it can be enabled
there independently of this repository.

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

# Redis (Channels, caching and chat notification queue)
# Docker Desktop with Redis exposed on the host:
REDIS_HOST=redis://host.docker.internal:6379/1
# Kubernetes: replace this with the managed Redis service endpoint.
# Local Django outside Docker can use redis://127.0.0.1:6379/1
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
- **Voting**: referendum parameters (`wymaganych_podpisow`, `czas_na_zebranie_podpisow`, `dyskusja`, `czas_trwania_referendum`) are stored in the `SiteParameters` database singleton and changed through the referendum workflow; they are not environment variables.
- **Chat**: `ARCHIVE_PUBLIC_CHAT_ROOM`, `DELETE_PUBLIC_CHAT_ROOM`
- **Uploads**: `UPLOAD_IMAGE_MAX_SIZE_MB`, `DATA_UPLOAD_MAX_MEMORY_SIZE`
- **Citizens**: `ACCEPTANCE`, `DELETE_INACTIVE_USER_AFTER`

## Management Commands

Custom management commands available:

```bash
# Chat management
python manage.py chat_rooms         # Manage chat rooms
python manage.py run_chat_notifications_worker  # Deliver Redis Stream notifications

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
┌────────────────────────────────────────────────────────┐
│  Web / Daphne ASGI                                     │
│  HTTP views + Django Channels WebSocket                │
└──────────────┬───────────────────────┬─────────────────┘
               │                       │
               ▼                       ▼
┌─────────────────────┐      ┌──────────────────────────┐
│       SQLite        │      │          Redis            │
│      (Database)     │      │ Channels + notification  │
└─────────────────────┘      │ Stream / cache           │
                             └────────────┬─────────────┘
                                          │
                                          ▼
                             ┌──────────────────────────┐
                             │ chat_notifications_worker│
                             │ Redis Stream consumer    │
                             └──────────────────────────┘
```

