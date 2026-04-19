#!/usr/bin/env bash
# Bump the sankoch VERSION file. cyrius.cyml pulls from VERSION via
# ${file:VERSION}, so this is the single source of truth — no other
# file to edit.
#
# Usage: ./scripts/version-bump.sh 1.3.0

set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <version>" >&2
    exit 1
fi

NEW_VERSION="$1"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "$NEW_VERSION" > "$REPO_ROOT/VERSION"
echo "VERSION -> ${NEW_VERSION}"
echo
echo "Next steps:"
echo "  1. Update CHANGELOG.md ([Unreleased] → [${NEW_VERSION}] + release date)"
echo "  2. cyrius distlib       # regenerate dist/sankoch.cyr"
echo "  3. git commit -am 'release ${NEW_VERSION}'"
echo "  4. git tag ${NEW_VERSION} && git push --tags"
