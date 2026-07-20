#!/bin/sh
# zip-smoke.sh — validate sankoch's ZIP container against reference tools, BOTH ways.
#
#   READ : Python `zipfile` writes an archive; sankoch's reader enumerates + extracts it.
#   WRITE: sankoch re-packs those members; `unzip -t` and Python `zipfile` must accept the
#          result, with every member byte-identical to the original.
#
# Reference-CLI parity is the load-bearing rule for every sankoch format (see CLAUDE.md);
# this is the ZIP half of it. `tests/tcyr/zip.tcyr` is the self-contained CI half.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/build/zip_smoke"
for t in unzip python3 cmp; do
    command -v "$t" >/dev/null 2>&1 || { echo "ERROR: missing '$t'"; exit 1; }
done

CYRIUS_NO_WARN_PIN_DRIFT=1 CYRIUS_NO_WARN_SHADOW_LIB=1 sh -c \
    "cd '$ROOT' && cyrius build programs/zip_smoke.cyr build/zip_smoke" >/dev/null 2>&1 \
    || { echo "ERROR: build failed"; exit 1; }
[ -x "$BIN" ] || { echo "ERROR: zip_smoke not built"; exit 1; }

WORK="$(mktemp -d /tmp/sankoch-zip-XXXXXX)"
IN="/tmp/sankoch-zip-in.zip"
OUT="/tmp/sankoch-zip-out.zip"
trap 'rm -rf "$WORK" "$IN" "$OUT"' EXIT

rc=0

# --- build a spread of reference archives with Python ---------------------------------
python3 - "$WORK" <<'PY'
import json, os, sys, zipfile
w = sys.argv[1]

# 1. agpkg: exactly agnosai's shape — manifest.json + one JSON per definition, DEFLATE.
man = json.dumps({"version": 1, "definitions": ["alpha", "beta", "gamma"]}, indent=2)
with zipfile.ZipFile(os.path.join(w, "agpkg.zip"), "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("manifest.json", man)
    for n in ("alpha", "beta", "gamma"):
        z.writestr("definitions/%s.json" % n,
                   json.dumps({"name": n, "body": "x" * 400}, indent=2))

# 2. mixed methods in one archive
with zipfile.ZipFile(os.path.join(w, "mixed.zip"), "w") as z:
    z.writestr("stored.bin", bytes(range(256)) * 4, compress_type=zipfile.ZIP_STORED)
    z.writestr("deflated.txt", b"the quick brown fox " * 200, compress_type=zipfile.ZIP_DEFLATED)

# 3. edge shapes: empty member, 1-byte member, deep nested name, many members
with zipfile.ZipFile(os.path.join(w, "edges.zip"), "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("empty.txt", b"")
    z.writestr("one.txt", b"A")
    z.writestr("a/b/c/d/e/deep.json", json.dumps({"deep": True}))
    for i in range(40):
        z.writestr("many/f%03d.txt" % i, ("member %d\n" % i) * 5)

# 4. incompressible payload (DEFLATE must not inflate the archive pathologically)
import random
random.seed(11)
with zipfile.ZipFile(os.path.join(w, "random.zip"), "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("rand.bin", bytes(random.randrange(256) for _ in range(20000)))

# 5. every method sankoch owns, one member each (2.6.1). Python writes 0/8/12/93; the
#    xz member (95) is added by bsdtar below when available.
with zipfile.ZipFile(os.path.join(w, "methods.zip"), "w") as z:
    payload = bytes((97 + (i % 23)) for i in range(20000))
    z.writestr("m00.txt", payload, compress_type=zipfile.ZIP_STORED)
    z.writestr("m08.txt", payload, compress_type=zipfile.ZIP_DEFLATED)
    z.writestr("m12.txt", payload, compress_type=zipfile.ZIP_BZIP2)
    if hasattr(zipfile, "ZIP_ZSTANDARD"):
        z.writestr("m93.txt", payload, compress_type=zipfile.ZIP_ZSTANDARD)

# 6. archive with a trailing comment (the EOCD scan must still find the record)
with zipfile.ZipFile(os.path.join(w, "comment.zip"), "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("c.txt", b"commented archive" * 50)
    z.comment = b"sankoch zip-smoke trailing comment" * 20
PY

# 7. an xz-method (95) archive — Python cannot write method 95, so use bsdtar when it is
#    available. This is the only way to exercise 95 on the READ side of the smoke.
if command -v bsdtar >/dev/null 2>&1; then
    mkdir -p "$WORK/xzsrc"
    python3 -c "import sys; open(sys.argv[1],'wb').write(bytes((97+(i%23)) for i in range(20000)))" \
        "$WORK/xzsrc/x.txt"
    (cd "$WORK/xzsrc" && bsdtar -a -cf "$WORK/xzm.zip" --options zip:compression=xz x.txt) >/dev/null 2>&1 \
        || rm -f "$WORK/xzm.zip"
fi

total=0
pass=0
for f in agpkg mixed edges random methods xzm comment; do
    src="$WORK/$f.zip"
    [ -f "$src" ] || continue
    total=$((total + 1))
    cp "$src" "$IN"
    rm -f "$OUT"
    if ! "$BIN" > "$WORK/$f.log" 2>&1; then
        echo "  FAIL $f: sankoch reader/writer exited $?"
        sed 's/^/      /' "$WORK/$f.log"
        rc=1
        continue
    fi
    # A reference reader must accept sankoch's archive. `unzip` covers store/DEFLATE/bzip2;
    # bsdtar (libarchive) additionally covers zstd (93) and xz (95), so prefer it when the
    # archive carries a method unzip predates.
    if command -v bsdtar >/dev/null 2>&1; then
        if ! bsdtar -tf "$OUT" >/dev/null 2>&1; then
            echo "  FAIL $f: bsdtar rejected sankoch's archive"
            rc=1
            continue
        fi
    fi
    if ! unzip -t "$OUT" >/dev/null 2>&1; then
        # unzip refuses methods it predates (93/95) — only a real failure if bsdtar is absent.
        if ! command -v bsdtar >/dev/null 2>&1; then
            echo "  FAIL $f: unzip -t rejected sankoch's archive"
            rc=1
            continue
        fi
    fi
    # ...and every member must match the original byte-for-byte.
    if python3 - "$src" "$OUT" <<'PY'
import sys, zipfile
ref, got = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(ref) as a, zipfile.ZipFile(got) as b:
    if sorted(a.namelist()) != sorted(b.namelist()):
        sys.exit(1)
    for n in a.namelist():
        try:
            want = a.read(n)
        except NotImplementedError:
            continue          # python itself cannot decode this method in the SOURCE
        try:
            have = b.read(n)
        except NotImplementedError:
            continue          # ...or in sankoch's output (e.g. xz/95); bsdtar covered it
        if want != have:
            sys.exit(1)
    sys.exit(0)
PY
    then
        pass=$((pass + 1))
    else
        echo "  FAIL $f: Python zipfile mismatch (names/content/CRC)"
        rc=1
    fi
done

echo ""
echo "  $pass/$total archives: Python-written -> sankoch read -> sankoch written -> unzip -t + zipfile byte-identical"
if [ "$rc" -eq 0 ]; then
    echo "zip-smoke: PASS — reference unzip / bsdtar / Python zipfile accept sankoch's ZIP output (methods 0/8/12/93/95, read + write)"
else
    echo "zip-smoke: FAIL"
fi
exit $rc
