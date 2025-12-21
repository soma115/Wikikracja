FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gettext \
        libjpeg62-turbo \
        zlib1g \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

RUN mkdir -p /app/db /app/media /app/static

ENV DEBUG=True \
    SECRET_KEY=build-time-insecure-secret-key

RUN python manage.py compilemessages -v 0 --ignore=.git/* --ignore=static/* --ignore=.mypy_cache/* \
    && python manage.py collectstatic --noinput -c -v 2 \
    && echo "=== Verifying collected static files ===" \
    && ls -la /app/static/ \
    && echo "=== Static files count ===" \
    && find /app/static -type f | wc -l

EXPOSE 8000

CMD sh -c "python manage.py migrate --noinput && python manage.py update_site && daphne -b 0.0.0.0 -p 8000 zzz.asgi:application"
