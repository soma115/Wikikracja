#!/bin/sh
# Used to run local development instances

if [ -z "$VIRTUAL_ENV" ]; then
    echo "Please activate virtualenv first. For example: source venv/bin/activate"
    exit 1
fi

if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
    else
        echo "Missing .env and .env.example"
        exit 1
    fi
fi

if grep -q '^SECRET_KEY=change-me$' .env; then
    secret_key="$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 50 | head -n 1)"
    tmpfile="$(mktemp)"
    sed "s/^SECRET_KEY=change-me$/SECRET_KEY=$secret_key/" .env > "$tmpfile" && mv "$tmpfile" .env
fi

set -a
. ./.env
set +a

db_path=$(python -c "from zzz.settings import DATABASES; print(DATABASES['default']['NAME'])")

echo ''
echo "- Wikikracja will be installed in current directory"
echo "- If you want fresh install - delete $db_path"
echo "- You have to have virtualenv activated"
echo ''

if ! dpkg -l | grep -q gettext; then
    sudo apt install gettext -y
fi
if ! dpkg -l | grep -q sqlite3; then
    sudo apt install sqlite3 -y
fi
if ! dpkg -l | grep -q redis; then
    sudo apt install redis -y
fi

if ! dpkg -l | grep -q redis-server; then
    sudo apt install redis-server -y
fi
if ! sudo systemctl is-active --quiet redis-server; then
    sudo systemctl enable redis-server
    sudo systemctl start redis-server
fi

mkdir -p ./media/uploads

pip install --no-cache-dir -q -r requirements.txt

./manage.py makemigrations obywatele
./manage.py makemigrations glosowania
./manage.py makemigrations chat
./manage.py makemigrations home
./manage.py makemigrations bookkeeping
./manage.py makemigrations board
./manage.py makemigrations events
./manage.py makemigrations tasks
./manage.py migrate
./manage.py makemessages -v 0 --no-wrap --no-obsolete -l 'en' --ignore=.git/* --ignore=static/* --ignore=.mypy_cache/*
./manage.py makemessages -v 0 --no-wrap --no-obsolete -l 'pl' --ignore=.git/* --ignore=static/* --ignore=.mypy_cache/*
./manage.py compilemessages -v 0 --ignore=.git/* --ignore=static/* --ignore=.mypy_cache/*
./manage.py collectstatic -v 0 --no-input -c

# No need for that. First user can create account by himself.
# if ./manage.py shell -c "from django.contrib.auth.models import User; print(User.objects.exists())" | grep -q False; then
#     echo ''
#     echo "I'll create first user 'a'"
#     ./manage.py createsuperuser --noinput --username a --email a@a.pl
#     echo "Set password for 'a'"
#     ./manage.py changepassword a
# fi

echo ''
echo 'Development instance started'
echo ''

daphne zzz.asgi:application  # chat works only on daphne
