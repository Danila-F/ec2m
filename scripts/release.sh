#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./scripts/release.sh
  ./scripts/release.sh 2026.04.01
  ./scripts/release.sh v2026.04.01
  ./scripts/release.sh --dry-run

Behavior:
  - Uses today's UTC date if no version is provided
  - Requires a clean git worktree
  - Requires local main to match origin/main
  - Creates an annotated git tag in the form vYYYY.MM.DD
  - Pushes the tag to origin

After the tag is pushed, GitHub Actions publishes the release automatically.
EOF
}

log() {
  printf '[release] %s\n' "$*"
}

die() {
  printf '[release] error: %s\n' "$*" >&2
  exit 1
}

have() {
  command -v "$1" >/dev/null 2>&1
}

DRY_RUN=0
VERSION_INPUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    *)
      if [[ -n "${VERSION_INPUT}" ]]; then
        die "Only one version argument is allowed"
      fi
      VERSION_INPUT="$1"
      shift
      ;;
  esac
done

have git || die "git is required"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "Run this script inside the repository"

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "${REPO_ROOT}"

if [[ -z "${VERSION_INPUT}" ]]; then
  VERSION_INPUT="$(date -u +%Y.%m.%d)"
fi

if [[ "${VERSION_INPUT}" =~ ^v[0-9]{4}\.[0-9]{2}\.[0-9]{2}$ ]]; then
  TAG="${VERSION_INPUT}"
elif [[ "${VERSION_INPUT}" =~ ^[0-9]{4}\.[0-9]{2}\.[0-9]{2}$ ]]; then
  TAG="v${VERSION_INPUT}"
else
  die "Version must match YYYY.MM.DD or vYYYY.MM.DD"
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  die "Git worktree is not clean"
fi

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "${CURRENT_BRANCH}" != "main" ]]; then
  die "Release must be created from branch 'main' (current: ${CURRENT_BRANCH})"
fi

log "Fetching origin/main and tags"
git fetch origin main --tags

LOCAL_HEAD="$(git rev-parse HEAD)"
REMOTE_MAIN="$(git rev-parse origin/main)"

if [[ "${LOCAL_HEAD}" != "${REMOTE_MAIN}" ]]; then
  die "Local main is not up to date with origin/main"
fi

if git rev-parse "${TAG}" >/dev/null 2>&1; then
  die "Tag already exists locally: ${TAG}"
fi

if git ls-remote --exit-code --tags origin "refs/tags/${TAG}" >/dev/null 2>&1; then
  die "Tag already exists on origin: ${TAG}"
fi

log "Ready to create release tag ${TAG} at ${LOCAL_HEAD}"

if [[ "${DRY_RUN}" -eq 1 ]]; then
  log "Dry run only; no tag created"
  exit 0
fi

git tag -a "${TAG}" -m "Release ${TAG}"
git push origin "${TAG}"

log "Tag pushed: ${TAG}"
log "GitHub Actions will publish the release automatically"
