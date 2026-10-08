#!/usr/bin/env bash
set -u

if ! command -v microk8s >/dev/null 2>&1; then
    printf 'Brak microk8s w PATH; uruchom skrypt na serwerze z dostepem do klastra.\n' >&2
    exit 2
fi

namespace=wikikracja
pods=(
    wikikracja-instance-1-7f5c7cd4f5-fjhlr
    wikikracja-instance-10-5d4bdb666b-8g79k
    wikikracja-instance-11-6747cd5677-w864j
    wikikracja-instance-12-6bb59db46d-5c2fm
    wikikracja-instance-13-5f577f9c75-68fsv
    wikikracja-instance-14-8d97b5f68-wjvxq
    wikikracja-instance-2-7d54f67c56-9484f
    wikikracja-instance-3-ff7b5b4b9-zx69t
    wikikracja-instance-5-85c4fbb787-mrnjm
    wikikracja-instance-6-7c465b57dd-86dkj
    wikikracja-instance-7-6b58586cfc-g854l
    wikikracja-instance-8-bb5ddd567-mtmdj
    wikikracja-instance-9-689bd6866b-vx4dr
)

ok=0
blocked=0
errors=0
for pod in "${pods[@]}"; do
    printf '\n=== %s ===\n' "$pod"
    microk8s kubectl -n "$namespace" exec -i "$pod" -- python - <<'PY'
import os
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

sources = {
    'board': 'board_post',
    'glosowania': 'glosowania_decyzja',
    'ankiety': 'ankiety_survey',
    'tasks': 'tasks_task',
}
path = Path(os.environ.get('SQLITE_DATABASE_PATH', '/app/db/db.sqlite3')).absolute()
blockers = []
reviews = []

try:
    if not path.is_file():
        raise FileNotFoundError(f'Baza nie istnieje: {path}')
    with sqlite3.connect(f'file:{quote(str(path), safe="/")}?mode=ro', uri=True, timeout=10) as db:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        required = {'chat_room', 'chat_room_allowed', 'auth_user', *sources.values()}
        available = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if required - available:
            raise ValueError(f'Brak tabel: {sorted(required - available)}')

        rooms = {room_id: (app, object_id) for room_id, app, object_id in db.execute('SELECT id, source_app, source_object_id FROM chat_room')}
        rooms_by_source = defaultdict(list)
        for room_id, (app, object_id) in rooms.items():
            if object_id is not None:
                rooms_by_source[app, object_id].append(room_id)
                if not app:
                    blockers.append(f'pokoj #{room_id}: source_object_id={object_id} bez source_app')
        for (app, object_id), room_ids in rooms_by_source.items():
            if len(room_ids) > 1:
                blockers.append(f'duplikat zrodla {app!r} #{object_id}: pokoje {room_ids}')

        active_ids = {user_id for user_id, in db.execute('SELECT id FROM auth_user WHERE is_active=1')}
        members = defaultdict(set)
        for room_id, user_id in db.execute('SELECT room_id, user_id FROM chat_room_allowed'):
            members[room_id].add(user_id)

        def check_members(label, room_id):
            missing = active_ids - members[room_id]
            inactive = members[room_id] - active_ids
            if missing:
                reviews.append(f'{label}, pokoj #{room_id}: brak {len(missing)} aktywnych czlonkow')
            if inactive:
                reviews.append(f'{label}, pokoj #{room_id}: {len(inactive)} nieaktywnych czlonkow')

        owners_by_room = defaultdict(list)
        for app, table in sources.items():
            objects = dict(db.execute(f'SELECT id, chat_room_id FROM {table}'))
            for object_id, room_id in objects.items():
                if room_id is not None:
                    owners_by_room[room_id].append(f'{app} #{object_id}')

            for room_id, (room_app, source_id) in rooms.items():
                if room_app != app:
                    continue
                if source_id is None:
                    reviews.append(f'{app}: pokoj #{room_id} bez source_object_id')
                elif source_id not in objects:
                    reviews.append(f'{app}: pokoj #{room_id} wskazuje brakujacy obiekt #{source_id}')
                check_members(app, room_id)

            for object_id, room_id in objects.items():
                if room_id is None:
                    reviews.append(f'{app} #{object_id}: brak relacji chat_room')
                elif room_id not in rooms:
                    blockers.append(f'{app} #{object_id}: brak pokoju #{room_id}')
                elif rooms[room_id] != (app, object_id):
                    blockers.append(f'{app} #{object_id}: pokoj #{room_id} ma zrodlo {rooms[room_id]!r}')
                    check_members(f'{app} #{object_id}', room_id)

        for room_id, owners in owners_by_room.items():
            if len(owners) > 1:
                blockers.append(f'pokoj #{room_id} przypisany do wielu obiektow: {owners}')

        for room_id, in db.execute("SELECT id FROM chat_room WHERE public=0 AND source_app='' AND source_object_id IS NULL AND system_key IS NULL AND federated_instance_url IS NULL"):
            if len(members[room_id]) != 2:
                reviews.append(f'niejednoznaczny prywatny pokoj #{room_id}: {len(members[room_id])} czlonkow zamiast 2')
except (OSError, sqlite3.Error, ValueError) as exc:
    print(f'BLAD ODCZYTU: {exc}', file=sys.stderr)
    sys.exit(20)

for issue in blockers:
    print(f'BLOKER: {issue}')
for issue in reviews:
    print(f'DO PRZEJRZENIA: {issue}')
print(f'Wynik: {len(blockers)} blokerow, {len(reviews)} uwag; niczego nie zmieniono.')
sys.exit(10 if blockers else 0)
PY
    result=$?
    case "$result" in
        0) ok=$((ok + 1)) ;;
        10) blocked=$((blocked + 1)) ;;
        *) errors=$((errors + 1)); printf 'Nie udalo sie skontrolowac %s (kod %s).\n' "$pod" "$result" >&2 ;;
    esac
done

printf '\nPodsumowanie: %s sprawdzonych bez blokerow, %s z blokerami, %s bledow na %s podow.\n' "$ok" "$blocked" "$errors" "${#pods[@]}"
if (( blocked > 0 || errors > 0 )); then
    exit 1
fi
