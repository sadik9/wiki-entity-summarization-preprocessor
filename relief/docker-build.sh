#!/usr/bin/env bash
# Build the RELIEF image with the current git commit recorded in it (and "-dirty" for uncommitted changes),
# so every run can report exactly which code produced it. Run from anywhere inside the repository.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
commit="$(git rev-parse --short HEAD)"
# changed *or* untracked files under relief/ mark the build as dirty
[ -z "$(git status --porcelain -- relief)" ] || commit="${commit}-dirty"
RELIEF_GIT_COMMIT="$commit" docker compose build relief "$@"
echo "built wikes-relief:latest at commit $commit"
