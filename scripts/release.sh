#!/usr/bin/env bash
# release.sh - cut a release tag for Mycelium, kept in lockstep with version.py.
#
# "Newest version" for the in-field hub updater means the newest vX.Y.Z git tag
# (see api/services/hub_update_service.py). This script is the ONE place a tag is
# created, and it derives the tag name from version.py::__version__ so a tag can
# never disagree with the code it points at.
#
# Usage:
#   ./scripts/release.sh            create the annotated tag for the current
#                                   version.py, then print the push command
#   ./scripts/release.sh --push     also run `git push origin <tag>` for you
#
# It intentionally does NOT push by default: pushing a tag is what makes every
# field hub offer this version, so that stays a deliberate, separate step.
set -euo pipefail

cd "$(dirname "$0")/.." || exit 2   # repo root (scripts/ is one level down)

DO_PUSH=0
for arg in "$@"; do
    case "$arg" in
        --push) DO_PUSH=1 ;;
        -h|--help) sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown option: $arg" >&2; exit 2 ;;
    esac
done

die() { echo "release: $*" >&2; exit 1; }

command -v git >/dev/null || die "git not found"
[ -f version.py ] || die "version.py not found (run from the repo)"

# --- Version (single source of truth) -----------------------------------------
VERSION="$(python3 -c 'import version; print(version.__version__)')" \
    || die "could not read version.py::__version__"
[ -n "$VERSION" ] || die "empty version"
case "$VERSION" in
    [0-9]*.[0-9]*.[0-9]*) : ;;
    *) die "version '$VERSION' is not semver X.Y.Z" ;;
esac
TAG="v${VERSION}"

# --- Preconditions ------------------------------------------------------------
branch="$(git rev-parse --abbrev-ref HEAD)"
[ "$branch" = "master" ] || die "must be on master (on '$branch'); tags ship to customers"

git diff --quiet && git diff --cached --quiet \
    || die "working tree is dirty; commit or stash before tagging"

if git rev-parse -q --verify "refs/tags/${TAG}" >/dev/null; then
    die "tag ${TAG} already exists — bump version.py::__version__ for a new release"
fi

# --- Tag ----------------------------------------------------------------------
git tag -a "${TAG}" -m "Release ${TAG}"
echo "release: created annotated tag ${TAG} at $(git rev-parse --short HEAD)"

if [ "$DO_PUSH" -eq 1 ]; then
    git push origin "${TAG}"
    echo "release: pushed ${TAG} — field hubs will now offer ${VERSION}"
else
    echo "release: to publish it (field hubs will then offer ${VERSION}), run:"
    echo "    git push origin ${TAG}"
fi
