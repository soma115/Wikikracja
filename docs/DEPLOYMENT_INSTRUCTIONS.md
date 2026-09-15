# Deployment Instructions for WikiKracja

This document contains instructions for developers setting up the development environment and deploying the Wikikracja application.

## Table of Contents
1. [Development Setup](#development-setup)
2. [Running the Application](#running-the-application)
3. [Database Management](#database-management)
4. [Deployment](#deployment)
5. [Chat Notification Worker](#chat-notification-worker)
6. [Common Issues and Fixes](#common-issues-and-fixes)
7. [Chat Room Categorization](#chat-room-categorization)

## Development Setup

### Prerequisites
- Python 3.14+ (the repository and CI currently target Python 3.14)
- SQLite3 (the application and the Kubernetes deployment use SQLite)
- Redis (for Channels, cache and notification delivery)
- Docker and Docker Compose (recommended for local development)
- Node.js 22+ and npm (for the Tailwind and Jest checks)

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

Wikikracja uses SQLite3. Create a consistent backup with the SQLite Backup API;
do not copy only `db.sqlite3` while its WAL sidecar may be active.

```bash
# Create a timestamped backup in SQLITE_BACKUP_DIR (or ./backups)
python scripts/sqlite_maintenance.py backup

# Create a backup at an explicit destination
python scripts/sqlite_maintenance.py backup backups/db-20260915-040000.sqlite3
```

The cluster's `backup-to-nas` CronJob runs this tool against every active instance
PVC and transfers the completed backup to the configured NAS. It is the production
backup path; the local commands above are for development or controlled recovery.

### Database Restore

Stop the application, scheduler and worker for the affected instance before
restoring SQLite. Move the current database and its `-wal`/`-shm` sidecars to a
quarantine directory instead of deleting them. Do not let the restored database
reuse old sidecars.

```bash
mkdir -p restore-quarantine
mv db.sqlite3 db.sqlite3-wal db.sqlite3-shm restore-quarantine/ 2>/dev/null || true
cp backup.sqlite3 db.sqlite3
python scripts/sqlite_maintenance.py integrity-check
```

For a Kubernetes restore, use the cluster's restore runbook and stop the relevant
per-instance HTTP, scheduler and worker workloads before touching the PVC. Never
restore a production database by copying files into a live mounted volume.

### SQLite Maintenance

The application and container image use the same database path:

```env
SQLITE_DATABASE_PATH=/app/db/db.sqlite3
```

`SQLITE_BACKUP_DIR` is available for local or explicitly configured maintenance
jobs, but the current Kubernetes backup CronJob writes a staged backup to NAS and
does not rely on a backup PVC or on this variable. For an active SQLite database,
use the SQLite Backup API:

```bash
# Verify the database
python scripts/sqlite_maintenance.py integrity-check

# Run a non-blocking WAL checkpoint
python scripts/sqlite_maintenance.py checkpoint --mode PASSIVE
```

Run `VACUUM` or a `TRUNCATE` checkpoint only as a controlled maintenance operation
after checking active processes and confirming a current backup.

## Deployment

### Official Docker Images

GitHub Actions publishes the image to GitHub Container Registry after the CI workflow
succeeds. The cluster consumes the public image
`ghcr.io/soma115/wikikracja`.

The important tags are:

- `latest` — convenience tag for the default branch;
- `main-<UTC timestamp>` — sortable tag consumed by Flux ImagePolicy;
- branch, pull-request, SHA and semver tags — auxiliary build tags.

Do not use `latest` as the deployment reference in GitOps manifests. Flux updates
all Wikikracja workloads, migration Jobs and the backup CronJob from the sortable
`main-<timestamp>` tag.

### Building and running a local image

```bash
docker build -t wikikracja:test .
docker run -p 8000:8000 --env-file .env wikikracja:test
```

For the local multi-container setup use Docker Compose:

```bash
docker compose up --build
docker compose up --build -d
docker compose down
```

The GitHub Actions workflow is defined in `.github/workflows/docker-build.yml`.
It builds multi-architecture images (`linux/amd64` and `linux/arm64`) and pushes
them to GHCR. A fork must configure its own package permissions and image name.

### Kubernetes deployment (GitOps)

The production-like deployment is managed in the separate `flux-cluster`
repository. Do not deploy the cluster by running `docker compose`, `gunicorn`,
`systemctl` or `manage.py migrate` manually on a node. Push the application
change to `main`; CI builds the image and Flux Image Automation updates the
sortable image tag in the GitOps repository.

The declarative deployment is split into the following Flux layers:

- `apps-wikikracja-base` — namespace, shared ConfigMaps, Redis and per-instance PVCs;
- `apps-wikikracja-shared` — middleware, Firebase secret reference and the NAS backup CronJob;
- `apps-wikikracja-instance-N-migrations` — one migration Job per active instance;
- `apps-wikikracja-instance-N` — one HTTP, scheduler and chat-notification-worker Deployment per active instance.

Active instances are `1`, `2`, `3` and `5–14` (there is no instance 4). Each
instance has one SQLite PVC (`ReadWriteOnce`, currently requested size `1Gi`),
one HTTP replica, one scheduler replica and one notification-worker replica.
The workloads are intentionally kept at one replica because each instance writes
to its own SQLite database.

The currently declared public hosts are:

| Instance | Primary host | Aliases |
| --- | --- | --- |
| 1 | `test.wikikracja.pl` | `t.wikikracja.pl` |
| 2 | `demo.wikikracja.pl` | — |
| 3 | `e501.wikikracja.pl` | — |
| 5 | `czik.wikikracja.pl` | — |
| 6 | `lobbyobywatelskie.wikikracja.pl` | `lo.wikikracja.pl` |
| 7 | `obywatele.wikikracja.pl` | — |
| 8 | `bractwo.wikikracja.pl` | — |
| 9 | `grupaperu.wikikracja.pl` | — |
| 10 | `lyski.wikikracja.pl` | — |
| 11 | `mojglos.wikikracja.pl` | — |
| 12 | `odswojego.wikikracja.pl` | `z.wikikracja.pl`, `ziomki.wikikracja.pl` |
| 13 | `wszyscywon.wikikracja.pl` | `w.wikikracja.pl` |
| 14 | `pls2027.wikikracja.pl` | `pls.wikikracja.pl` |

The runtime image is `ghcr.io/soma115/wikikracja:main-<timestamp>` and the
workloads use the `wikikracja` namespace. The HTTP container runs Daphne on port
`8000`; the scheduler runs `python manage.py run_scheduler`; the worker runs
`python manage.py run_chat_notifications_worker`. HTTP pods have the scheduler
disabled. Migration Jobs run `python manage.py migrate --noinput` before the
corresponding runtime layer is reconciled.

For the current domains, PVC names, Redis logical databases and resource limits,
treat the manifests in `flux-cluster/clusters/apps/wikikracja-base/` and
`flux-cluster/clusters/apps/wikikracja-instance-*/` as the source of truth.

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

The current manifests deploy one shared Redis 7 instance as `redis-1` in the
`wikikracja` namespace. It is scheduled on node `k8s`, has one replica and uses
`emptyDir` storage. It is a cache and queue, not durable application storage.
Each Wikikracja instance selects a separate logical Redis database (`1`, `2`, `3`
and `5` through `14`) and a separate `REDIS_CHANNEL_PREFIX`.

Both the HTTP and chat-notification-worker Deployments receive the same Redis
endpoint from the instance ConfigMap. The worker runs:

```yaml
command: ["python", "manage.py", "run_chat_notifications_worker"]
```

A Redis restart can lose queued personal notifications and Channels presence state;
messages and other durable application data remain in the instance SQLite PVCs.
Do not add a second Redis per instance or move SQLite databases to Redis.

The cluster manifests also provide:

- HTTP → HTTPS redirection and TLS through Traefik `IngressRoute` resources;
- `/healthz/live/` for liveness and `/healthz/ready/` for SQLite and Redis readiness;
- a dedicated migration Job before each instance runtime layer;
- one scheduler Deployment per instance with `SCHEDULER_ENABLED=true`;
- one notification-worker Deployment per instance;
- a daily `backup-to-nas` CronJob at `04:10 UTC` with `180` days of retention;
- Firebase Admin credentials through the cluster secret used for push delivery.

The source of truth is the `flux-cluster` repository, not a hand-written Secret
copied from this document. Keep credentials in the repository's secret-management
process and never put them into application documentation.

### Cluster placement

The declared placement relevant to Wikikracja is:

- `k8s` is the control-plane worker and hosts all Wikikracja HTTP, scheduler,
  notification-worker, migration, Redis and backup workloads;
- `k8s1` is a plain worker used by selected Jitsi workloads, not Wikikracja;
- `traefik` is the tainted, dedicated public-facing worker for Traefik, JVB and
  TURN, not Wikikracja.

The node role labels and the `traefik` taint are applied by
`flux-cluster/clusters/infrastructure/node-labels.yaml`. The live snapshot confirms
the expected node labels and that Wikikracja workloads run on `k8s`; the taint
still requires an explicit `get nodes -o yaml` or `describe node` check.

### Live cluster verification

The live output supplied on 2026-09-15 confirms the following:

- all listed Flux Kustomizations are `Ready=True`; application layers use
  `main@sha1:48dc738c`, while `infrastructure-secrets` is at
  `main@sha1:29bf8638`;
- all displayed Wikikracja application, migration and backup workloads use image
  `ghcr.io/soma115/wikikracja:main-20260915113429`;
- Redis `redis-1` is `1/1` and runs on `k8s`;
- every active instance (`1`, `2`, `3` and `5–14`) has HTTP, scheduler and
  chat-notifications-worker Deployments with `1/1` available, all on `k8s`;
- all migration Jobs are `Complete` (`1/1`); instance 1 uses the historical Job
  name `wikikracja-instance-1-migrate`, while the remaining instances use
  `wikikracja-instance-N-migrate-new`;
- every instance PVC is `Bound`, `1Gi`, `RWO` and uses `microk8s-hostpath`;
- the latest displayed `backup-to-nas` Job completed successfully;
- nodes `k8s`, `k8s1` and `traefik` are `Ready`; the expected control-plane,
  worker and `traefik` labels are present, and Wikikracja workloads run on `k8s`.

The supplied `get nodes --show-labels` output does not independently confirm the
`NoSchedule` taint on `traefik`. It also does not confirm backup transfer and
integrity, free disk space, application logs, smoke tests, SQLite filesystem
semantics or the absence of alerts. Those checks remain operational follow-ups.

For a later read-only verification on the MicroK8s control-plane host:

```bash
flux get kustomizations -n flux-system
microk8s kubectl get deployments -n wikikracja -o wide
microk8s kubectl get jobs -n wikikracja -l app.kubernetes.io/part-of=wikikracja-new -o wide
microk8s kubectl get pvc -n wikikracja
microk8s kubectl get pods -n wikikracja -o wide
microk8s kubectl get nodes --show-labels

# Check one migration separately.
microk8s kubectl get jobs -n wikikracja -l instance=instance-14 -o wide
```

### Redis availability and durability

The worker uses the existing `REDIS_HOST` setting and does not require or create a
second Redis server. In local Docker, configure the endpoint in `.env`. In the
current cluster, the endpoint is declared in each instance ConfigMap and points to
the shared `redis-1` Service with an instance-specific logical database.

Redis is a runtime dependency of both the web process and the worker. The current
cluster uses `emptyDir`, so a Redis restart can lose queued personal push/WebSocket
notifications and Channels presence state. Chat messages remain safe in SQLite.
Redis persistence would be a separate cluster-storage decision, not an application
configuration change.

## Common Issues and Fixes

### Multiple Users with Same Email Error

**Problem**: `django.contrib.auth.models.User.MultipleObjectsReturned: get() returned more than one User`

**Solution**: The authentication backend in `obywatele/auth_backends.py` automatically handles duplicate emails:
- Catches `MultipleObjectsReturned` exceptions
- Falls back to authenticating with the single active user if exactly one exists
- Logs errors for unresolved cases

The issue is resolved at the source - no manual migration required.

### Chat Room Categorization Issues

See the dedicated section below for the current room-title contracts and deployment path.

### Static Files Not Loading

```bash
python manage.py collectstatic --noinput
```

### Permission Issues

```bash
# Fix file permissions for media files
chmod -R 755 media/
```

## Chat Room Categorization

Chat rooms are linked to their source object through `source_app` and
`source_object_id`; categorization must not depend only on translated room names.
The current application uses these title contracts:

- tasks: `Task #<id>: <title>`;
- decisions/votes: `<id>. <title>`;
- surveys: `Survey #<id>: <title>`;
- documents: `Document #<id>: <title>`.

The code also derives notification and display names from the source relation.
There is no current `fix_room_titles` management command and no supported
procedure that rewrites all production room names. Do not copy old instructions
that restart Gunicorn/UWSGI or run that nonexistent command. Deploy chat changes
through the normal image build and Flux rollout, then verify the relevant room
links and notification names in the affected instance.

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
# Kubernetes: use the instance-specific endpoint from the GitOps ConfigMap,
# e.g. redis://redis-1:6379/1 for instance-1.
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
│   per-instance PVC  │      │ Channels + notification  │
└──────────┬──────────┘      │ Stream / cache           │
           │                 └────────────┬─────────────┘
           │                              │
           ▼                              ▼
┌─────────────────────┐      ┌──────────────────────────┐
│      scheduler      │      │ chat_notifications_worker│
│ one per instance    │      │ one per instance         │
└─────────────────────┘      └──────────────────────────┘
```

