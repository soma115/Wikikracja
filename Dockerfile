# Optimized multi-stage Dockerfile with Alpine for production
# check=skip=SecretsUsedInArgOrEnv

# 1. Builder stage - dependencies first (better cache utilization)
FROM python:3.14-alpine AS builder
WORKDIR /app

# Build environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    DEBUG=False \
    SECRET_KEY=build-time-insecure-secret-key \
    EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend \
    PATH=/root/.local/bin:$PATH

# Install build dependencies only once
RUN apk add --no-cache gettext-dev

# Install Python dependencies to user directory
# AUTOBAHN_USE_NVX=0 forces pure-Python autobahn (its NVX C extension has no
# musllinux wheel and would otherwise need a full C toolchain to compile)
COPY requirements.txt /app/
RUN AUTOBAHN_USE_NVX=0 pip install --no-cache-dir --no-compile --user -r requirements.txt

# Copy application code (after dependencies for better caching)
COPY . /app/

# Build-time operations
RUN python manage.py collectstatic --noinput -v 2 \
    || (echo "Static collection failed, continuing..." && python manage.py collectstatic --noinput -v 2 --clear)
RUN python manage.py compilemessages --ignore=.git/* --ignore=static/* --ignore=.mypy_cache/* --ignore=.venv/*

# 2. Runtime stage - minimal Alpine image
FROM python:3.14-alpine AS runtime
WORKDIR /app

# Runtime environment
ENV PYTHONUNBUFFERED=1 \
    SCHEDULER_ENABLED=true \
    SECRET_KEY=build-time-insecure-secret-key \
    PATH=/root/.local/bin:$PATH \
    EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# Install ONLY runtime dependencies
RUN apk add --no-cache sqlite \
    && mkdir -p /app/db /app/media /app/static

# Copy only what's needed from builder
COPY --from=builder /root/.local /root/.local
COPY --from=builder /app/static /app/static
COPY --from=builder /app/locale /app/locale
COPY --from=builder /app/manage.py /app/
COPY --from=builder /app/requirements.txt /app/
COPY --from=builder /app/BUILD_SHA /app/

# Copy application modules (exclude development files)
COPY --from=builder /app/obywatele /app/obywatele
COPY --from=builder /app/home /app/home
COPY --from=builder /app/board /app/board
COPY --from=builder /app/chat /app/chat
COPY --from=builder /app/events /app/events
COPY --from=builder /app/tasks /app/tasks
COPY --from=builder /app/ankiety /app/ankiety
COPY --from=builder /app/glosowania /app/glosowania
COPY --from=builder /app/bookkeeping /app/bookkeeping
COPY --from=builder /app/site_settings /app/site_settings
COPY --from=builder /app/categories /app/categories
COPY --from=builder /app/zzz /app/zzz
COPY --from=builder /app/templates /app/templates
COPY --from=builder /app/locale /app/locale
COPY --from=builder /app/pyproject.toml /app/

EXPOSE 8000

# Health check and startup
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import django; django.setup(); from django.http import HttpResponse; print('OK')" || exit 1

CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py update_site && daphne -b 0.0.0.0 -p 8000 zzz.routing:application"]