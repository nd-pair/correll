#!/usr/bin/env bash
# Fetch the shared chrome into .theme/ at the version pinned in theme.lock.
#
# A pinned tarball rather than a submodule: the version bump is a one-line diff
# you can read in review, clones and CI checkouts need no --recursive, and a
# build is reproducible from the lock file alone. .theme/ is gitignored.
#
# THEME_DIR points the build at a local checkout instead, for working on the
# theme and a site together:
#     THEME_DIR=../pair-theme python3 scripts/build_site.py
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="${THEME_REPO:-nd-pair/pair-theme}"
VERSION="$(tr -d '[:space:]' < "$ROOT/theme.lock")"
DEST="$ROOT/.theme"

if [ -f "$DEST/VERSION" ] && [ "$(tr -d '[:space:]' < "$DEST/VERSION")" = "$VERSION" ]; then
  echo "theme $VERSION already present"
  exit 0
fi

echo "fetching $REPO $VERSION"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
auth=()
[ -n "${GITHUB_TOKEN:-}" ] && auth=(-H "Authorization: Bearer $GITHUB_TOKEN")
curl -fsSL "${auth[@]}" \
  "https://github.com/$REPO/archive/refs/tags/$VERSION.tar.gz" -o "$tmp/theme.tgz"
rm -rf "$DEST"
mkdir -p "$DEST"
tar -xzf "$tmp/theme.tgz" -C "$DEST" --strip-components=1
[ -d "$DEST/partials" ] || { echo "::error::$REPO $VERSION has no partials/"; exit 1; }
echo "theme $VERSION in $DEST"
