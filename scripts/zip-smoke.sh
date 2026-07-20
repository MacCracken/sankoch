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

# 5. archive with a trailing comment (the EOCD scan must still find the record)
with zipfile.ZipFile(os.path.join(w, "comment.zip"), "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("c.txt", b"commented archive" * 50)
    z.comment = b"sankoch zip-smoke trailing comment" * 20
PY

total=0
pass=0
for f in agpkg mixed edges random comment; do
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
    # unzip must accept sankoch's archive...
    if ! unzip -t "$OUT" >/dev/null 2>&1; then
        echo "  FAIL $f: unzip -t rejected sankoch's archive"
        rc=1
        continue
    fi
    # ...and every member must match the original byte-for-byte.
    if python3 - "$src" "$OUT" <<'PY'
import sys, zipfile
ref, got = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(ref) as a, zipfile.ZipFile(got) as b:
    if b.testzip() is not None:
        sys.exit(1)
    ra = {n: a.read(n) for n in a.namelist()}
    rb = {n: b.read(n) for n in b.namelist()}
    sys.exit(0 if ra == rb else 1)
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
    echo "zip-smoke: PASS — reference unzip + Python zipfile accept sankoch's ZIP output (store + DEFLATE, read + write)"
else
    echo "zip-smoke: FAIL"
fi
exit $rc
