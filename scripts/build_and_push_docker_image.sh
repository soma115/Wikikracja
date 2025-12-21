#!/bin/sh
set -eu

if ! command -v docker >/dev/null 2>&1; then
    echo "docker is required"
    exit 1
fi

if ! command -v git >/dev/null 2>&1; then
    echo "git is required"
    exit 1
fi

REGISTRY_IMAGE_DEFAULT="ghcr.io/wikikracja/wikikracja"
REGISTRY_IMAGE="${REGISTRY_IMAGE:-$REGISTRY_IMAGE_DEFAULT}"

CONFIRM_OFFICIAL_PUSH="${CONFIRM_OFFICIAL_PUSH:-0}"

if [ -z "$REGISTRY_IMAGE" ]; then
    cat <<EOF

REGISTRY_IMAGE is required.

Set REGISTRY_IMAGE explicitly, e.g.:
  REGISTRY_IMAGE=ghcr.io/<username>/<project> ./scripts/build_and_push_docker_image.sh
EOF
    exit 1
fi

if [ "$REGISTRY_IMAGE" = "$REGISTRY_IMAGE_DEFAULT" ] && [ "$CONFIRM_OFFICIAL_PUSH" != "1" ]; then
    cat <<EOF

Refusing to push to the official image name by default:
  $REGISTRY_IMAGE_DEFAULT

If you are the maintainer and intentionally want to push the official image, run:
  CONFIRM_OFFICIAL_PUSH=1 ./scripts/build_and_push_docker_image.sh

Otherwise, set REGISTRY_IMAGE to your own namespace:
  REGISTRY_IMAGE=ghcr.io/<username>/wikikracja ./scripts/build_and_push_docker_image.sh

Alternative registries:
  - GitHub: REGISTRY_IMAGE=ghcr.io/<username>/wikikracja
  - GitLab: REGISTRY_IMAGE=registry.gitlab.com/<username>/wikikracja
  - Docker Hub: REGISTRY_IMAGE=docker.io/<username>/wikikracja
EOF
    exit 1
fi

TAG="${TAG:-$(git rev-parse --short HEAD)}"
PUSH_LATEST="${PUSH_LATEST:-1}"

echo "Building ${REGISTRY_IMAGE}:${TAG}"
docker build -t "${REGISTRY_IMAGE}:${TAG}" .

if [ "$PUSH_LATEST" = "1" ]; then
    docker tag "${REGISTRY_IMAGE}:${TAG}" "${REGISTRY_IMAGE}:latest"
fi

echo "Pushing ${REGISTRY_IMAGE}:${TAG}"
docker push "${REGISTRY_IMAGE}:${TAG}"

if [ "$PUSH_LATEST" = "1" ]; then
    echo "Pushing ${REGISTRY_IMAGE}:latest"
    docker push "${REGISTRY_IMAGE}:latest"
fi

cat <<EOF

Done.

Notes:
- Login to registry first:
  - GitHub: echo \$GITHUB_TOKEN | docker login ghcr.io -u <username> --password-stdin
  - GitLab: echo \$GITLAB_TOKEN | docker login registry.gitlab.com -u <username> --password-stdin
  - Docker Hub: docker login
- Override image name: REGISTRY_IMAGE=ghcr.io/<username>/wikikracja
- Override tag: TAG=v1.2.3
- Disable latest: PUSH_LATEST=0
- Build only (no push): docker build -t wikikracja:test .
EOF
