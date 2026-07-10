#!/bin/sh
# tar-smoke.sh — validate sankoch's tar cursor against real archives in every envelope it sniffs:
# plain .tar, .tar.gz, .tar.xz, .tar.bz2. For each, tar_smoke extracts to /tmp/sankoch-tar-out and
# we `diff -r` against the original tree (files, nested dirs, and a symlink), byte for byte.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/build/tar_smoke"
for t in tar gzip xz bzip2 diff; do command -v "$t" >/dev/null 2>&1 || { echo "ERROR: missing '$t'"; exit 1; }; done

CYRIUS_NO_WARN_PIN_DRIFT=1 CYRIUS_NO_WARN_SHADOW_LIB=1 sh -c "cd '$ROOT' && cyrius build programs/tar_smoke.cyr build/tar_smoke" >/dev/null 2>&1 || { echo "ERROR: build failed"; exit 1; }
[ -x "$BIN" ] || { echo "ERROR: tar_smoke not built"; exit 1; }

WORK="$(mktemp -d /tmp/sankoch-tar-XXXXXX)"
TAR="/tmp/sankoch-tar-test.tar"
OUT="/tmp/sankoch-tar-out"
trap 'rm -rf "$WORK" "$TAR" "$OUT"' EXIT

SRC="$WORK/tree"
mkdir -p "$SRC/bin" "$SRC/etc/conf.d" "$SRC/usr/lib"
printf 'AGNOS base\n'          > "$SRC/etc/os-release"
printf 'key=value\n'           > "$SRC/etc/conf.d/app.conf"
printf '#!/bin/agnsh\necho\n'  > "$SRC/bin/hello"; chmod 755 "$SRC/bin/hello"
head -c 1300000 /dev/urandom   > "$SRC/usr/lib/libbig.so"    # multi-block file
ln -s /bin/agnsh "$SRC/bin/sh"                               # symlink

rc=0
for mode in tar gz xz bz2; do
    case "$mode" in
        tar) ( cd "$SRC" && tar --format=ustar -cf  "$TAR" . ) ;;
        gz)  ( cd "$SRC" && tar --format=ustar -czf "$TAR" . ) ;;
        xz)  ( cd "$SRC" && tar --format=ustar -cJf "$TAR" . ) ;;
        bz2) ( cd "$SRC" && tar --format=ustar -cjf "$TAR" . ) ;;
    esac
    rm -rf "$OUT"; mkdir -p "$OUT"
    "$BIN"; e=$?
    if [ "$e" -ne 0 ]; then echo "  FAIL [$mode]: tar_smoke exit $e"; rc=1; continue; fi
    # --no-dereference: the symlink target (/bin/agnsh) is dangling on the host, so plain diff -r
    # would try to follow it. Compare symlink-as-symlink, then verify the target separately.
    ok=1
    if ! diff -r --no-dereference "$SRC" "$OUT" >"$WORK/diff.$mode" 2>&1; then ok=0; fi
    lnk="$(readlink "$OUT/bin/sh" 2>/dev/null)"
    [ "$lnk" = "/bin/agnsh" ] || { ok=0; echo "  (symlink target wrong: '$lnk')" >>"$WORK/diff.$mode"; }
    if [ "$ok" -eq 1 ]; then
        echo "  PASS [$mode]: extracted tree identical to source ($(find "$OUT" -type f | wc -l) files, symlink -> $lnk)"
    else
        echo "  FAIL [$mode]: tree differs:"; sed 's/^/    /' "$WORK/diff.$mode" | head -12; rc=1
    fi
done

echo ""
[ "$rc" -eq 0 ] && echo "tar-smoke: PASS — sankoch tar cursor extracts ustar from plain/gz/xz/bz2, byte-identical incl. symlinks" || echo "tar-smoke: FAIL"
exit $rc
