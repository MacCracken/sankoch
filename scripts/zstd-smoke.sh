#!/bin/sh
# zstd-smoke.sh — validate sankoch's sovereign zstd decoder against the reference `zstd` tool.
# For a spread of inputs (compressible text, incompressible random, highly repetitive, multi-block)
# compressed at several levels, sankoch decodes and we cmp byte-for-byte against the original.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/build/zstd_smoke"
for t in zstd cmp head; do command -v "$t" >/dev/null 2>&1 || { echo "ERROR: missing '$t'"; exit 1; }; done

CYRIUS_NO_WARN_PIN_DRIFT=1 CYRIUS_NO_WARN_SHADOW_LIB=1 sh -c "cd '$ROOT' && cyrius build programs/zstd_smoke.cyr build/zstd_smoke" >/dev/null 2>&1 || { echo "ERROR: build failed"; exit 1; }
[ -x "$BIN" ] || { echo "ERROR: zstd_smoke not built"; exit 1; }

WORK="$(mktemp -d /tmp/sankoch-zstd-XXXXXX)"
IN="/tmp/sankoch-zstd-in.zst"
OUT="/tmp/sankoch-zstd-out"
trap 'rm -rf "$WORK" "$IN" "$OUT"' EXIT

# --- build a spread of source files ---
# tiny text, medium compressible text, incompressible random, highly repetitive, multi-block (>128 KiB).
printf 'hello zstd\n'                          > "$WORK/tiny.bin"
seq 1 20000 | tr '\n' ' '                       > "$WORK/text.bin"       # compressible
head -c 200000 /dev/urandom                     > "$WORK/rand.bin"       # incompressible -> raw
yes 'AGNOS-the-sovereign-operating-system-0123' | head -c 300000 > "$WORK/repeat.bin"  # many matches
cat "$WORK/text.bin" "$WORK/rand.bin" "$WORK/repeat.bin" "$WORK/text.bin" > "$WORK/mixed.bin"  # multi-block

rc=0
total=0
pass=0
for f in tiny text rand repeat mixed; do
    src="$WORK/$f.bin"
    for lvl in 1 3 9 19; do
        for chk in check nocheck; do
            total=$((total + 1))
            if [ "$chk" = "nocheck" ]; then
                zstd -q -$lvl --no-check -f -o "$IN" "$src" 2>/dev/null
            else
                zstd -q -$lvl -f -o "$IN" "$src" 2>/dev/null
            fi
            rm -f "$OUT"
            "$BIN"; e=$?
            if [ "$e" -ne 0 ]; then echo "  FAIL $f L$lvl/$chk: decoder exit $e"; rc=1; continue; fi
            if cmp -s "$OUT" "$src"; then
                pass=$((pass + 1))
            else
                echo "  FAIL $f L$lvl/$chk: output differs ($(stat -c %s "$src") B src, $(stat -c %s "$OUT" 2>/dev/null || echo 0) B out)"; rc=1
            fi
        done
    done
done

echo ""
echo "  $pass/$total cases byte-identical"
[ "$rc" -eq 0 ] && echo "zstd-smoke: PASS — sankoch decodes reference zstd across levels 1/3/9/19 (text/random/repeat/multi-block), byte-identical" || echo "zstd-smoke: FAIL"
exit $rc
