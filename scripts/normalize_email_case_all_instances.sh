#!/usr/bin/env bash
set -u

namespace=wikikracja
apply=false
# Keep this list aligned with the active instances in DEPLOYMENT_INSTRUCTIONS.md.
expected_deployments=(
    wikikracja-instance-1
    wikikracja-instance-2
    wikikracja-instance-3
    wikikracja-instance-5
    wikikracja-instance-6
    wikikracja-instance-7
    wikikracja-instance-8
    wikikracja-instance-9
    wikikracja-instance-10
    wikikracja-instance-11
    wikikracja-instance-12
    wikikracja-instance-13
    wikikracja-instance-14
)

if [[ $# -gt 1 ]] || { [[ $# -eq 1 ]] && [[ "$1" != "--apply" && "$1" != "--dry-run" ]]; }; then
    printf 'Uzycie: %s [--dry-run|--apply]\n' "$0" >&2
    exit 2
fi
if [[ ${1:-} == "--apply" ]]; then
    apply=true
fi

if ! command -v microk8s >/dev/null 2>&1; then
    printf 'Brak microk8s w PATH; uruchom skrypt na serwerze z dostepem do klastra.\n' >&2
    exit 2
fi

deployment_output=$(microk8s kubectl get deployments -n "$namespace" -o name) || {
    printf 'Nie udalo sie pobrac deploymentow z namespace %s.\n' "$namespace" >&2
    exit 1
}

deployments=()
for resource in $deployment_output; do
    name=${resource#deployment.apps/}
    if [[ $name =~ ^wikikracja-instance-[0-9]+$ ]]; then
        deployments+=("$name")
    fi
done

if (( ${#deployments[@]} == 0 )); then
    printf 'Nie znaleziono deploymentow HTTP wikikracja-instance-N.\n' >&2
    exit 1
fi

if (( ${#deployments[@]} != ${#expected_deployments[@]} )); then
    printf 'Oczekiwano %s instancji, znaleziono %s. Przejrzyj liste deploymentow przed uruchomieniem.\n' \
        "${#expected_deployments[@]}" "${#deployments[@]}" >&2
    exit 1
fi
for expected in "${expected_deployments[@]}"; do
    if [[ ! " ${deployments[*]} " =~ " ${expected} " ]]; then
        printf 'Brak oczekiwanego deploymentu %s.\n' "$expected" >&2
        exit 1
    fi
done
for deployment in "${deployments[@]}"; do
    if [[ ! " ${expected_deployments[*]} " =~ " ${deployment} " ]]; then
        printf 'Nieoczekiwany deployment %s; przerwano zamiast pomijac instancje.\n' "$deployment" >&2
        exit 1
    fi
done

printf 'Instancje do sprawdzenia (%s):\n' "${#deployments[@]}"
printf '  %s\n' "${deployments[@]}"

check_ready() {
    local deployment=$1
    local state desired ready updated generation observed_generation
    state=$(microk8s kubectl get deployment "$deployment" -n "$namespace" -o jsonpath='{.spec.replicas}:{.status.readyReplicas}:{.status.updatedReplicas}:{.metadata.generation}:{.status.observedGeneration}') || return 1
    IFS=: read -r desired ready updated generation observed_generation <<< "$state"
    desired=${desired:-0}
    ready=${ready:-0}
    updated=${updated:-0}
    generation=${generation:-0}
    observed_generation=${observed_generation:-0}
    [[ $desired -eq 1 && $ready -eq $desired && $updated -eq $desired && $observed_generation -ge $generation ]]
}

run_command() {
    local deployment=$1
    shift
    local container
    container=$(microk8s kubectl get deployment "$deployment" -n "$namespace" -o jsonpath='{.spec.template.spec.containers[0].name}') || return 1
    microk8s kubectl exec "deployment/$deployment" -n "$namespace" -c "$container" -- python manage.py normalize_email_case "$@"
}

failures=0
for deployment in "${deployments[@]}"; do
    if ! check_ready "$deployment"; then
        printf 'BLAD: deployment %s nie ma wszystkich replik Ready.\n' "$deployment" >&2
        failures=$((failures + 1))
    fi
done
if (( failures > 0 )); then
    printf 'Przerwano przed audytem; nie zmieniono danych.\n' >&2
    exit 1
fi

printf '\n=== Audyt bez zmian ===\n'
for deployment in "${deployments[@]}"; do
    printf '\n--- %s ---\n' "$deployment"
    if ! run_command "$deployment"; then
        failures=$((failures + 1))
    fi
done
if (( failures > 0 )); then
    printf '\nAudyt nie przeszedl na wszystkich instancjach; niczego nie zmieniono.\n' >&2
    exit 1
fi

if [[ $apply == false ]]; then
    printf '\nDry run zakonczony. Brak zmian w bazach.\n'
    exit 0
fi

printf '\nPrzed zastosowaniem wykonaj i zweryfikuj backup SQLite wszystkich instancji.\n'
read -r -p 'Jesli backupy sa gotowe, wpisz NORMALIZUJ-MAILE: ' confirmation
if [[ $confirmation != "NORMALIZUJ-MAILE" ]]; then
    printf 'Nie potwierdzono. Bazy pozostaly bez zmian.\n'
    exit 1
fi

printf '\n=== Normalizacja adresow ===\n'
for deployment in "${deployments[@]}"; do
    printf '\n--- %s ---\n' "$deployment"
    if ! run_command "$deployment" --apply --confirm; then
        failures=$((failures + 1))
        printf 'BLAD: normalizacja %s nie powiodla sie; mozliwe, ze wczesniejsze instancje sa juz zaktualizowane.\n' "$deployment" >&2
    fi
done

if (( failures > 0 )); then
    printf '\nCzesc instancji mogla zostac zaktualizowana. Po usunieciu bledow ponowne uruchomienie jest bezpieczne i idempotentne.\n' >&2
    exit 1
fi

printf '\nNormalizacja zakonczona na wszystkich znalezionych instancjach.\n'
