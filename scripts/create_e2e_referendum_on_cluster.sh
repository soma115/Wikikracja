#!/usr/bin/env bash
set -Eeuo pipefail

NS="${NS:-wikikracja}"
INSTANCE="${INSTANCE:-1}"
E2E_EMAIL="${E2E_EMAIL:?Set E2E_EMAIL to the dedicated E2E account email}"
TITLE="${E2E_REFERENDUM_TITLE:-[E2E SQLITE] reliability fixture $(date -u +%Y%m%d%H%M%S)}"

KUBECTL=(microk8s kubectl)
LABEL="instance=instance-${INSTANCE},app.kubernetes.io/component=http"

POD="$(${KUBECTL[@]} get pods -n "$NS" \
  -l "$LABEL" \
  --field-selector=status.phase=Running \
  --sort-by=.metadata.creationTimestamp \
  -o name | tail -n 1 | sed 's#^pod/##')"

[[ -n "$POD" ]] || {
  echo "No running HTTP pod found for instance-${INSTANCE}." >&2
  exit 1
}

echo "Using HTTP pod: $POD"
echo "Creating or reusing an E2E referendum fixture. Existing fixture data is preserved."

"${KUBECTL[@]}" exec -i -n "$NS" "$POD" -- \
  env E2E_EMAIL="$E2E_EMAIL" E2E_REFERENDUM_TITLE="$TITLE" python - <<'PY'
import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from glosowania.models import Decyzja, ZebranePodpisy

email = os.environ["E2E_EMAIL"]
title = os.environ["E2E_REFERENDUM_TITLE"]
User = get_user_model()
user = User.objects.get(email=email)

decision = Decyzja.objects.filter(
    title=title,
    author=user,
).order_by("-pk").first()

if decision is None:
    today = timezone.localdate()
    decision = Decyzja.objects.create(
        author=user,
        title=title,
        tresc="E2E-only SQLite reliability test fixture.",
        uzasadnienie="Created by the explicit E2E fixture command.",
        kara="No operational effect.",
        status=Decyzja.Status.REFERENDUM,
        path="E2E SQLite reliability fixture",
        data_referendum_start=today,
        data_referendum_stop=today + timedelta(days=7),
    )

if decision.status != Decyzja.Status.REFERENDUM:
    raise SystemExit(
        f"Fixture {decision.pk} has status {decision.get_status_display()}, not REFERENDUM"
    )

if decision.data_referendum_stop and decision.data_referendum_stop < timezone.localdate():
    raise SystemExit(f"Fixture {decision.pk} is no longer open for voting")

ZebranePodpisy.objects.get_or_create(
    projekt=decision,
    podpis_uzytkownika=user,
)

print(f"referendum_id={decision.pk}")
print(f"referendum_url=/glosowania/details/{decision.pk}/")
print(f"status={decision.get_status_display()}")
print(f"title={decision.title}")
PY
