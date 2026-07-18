#!/bin/sh
# zstd-encode-smoke.sh — validate sankoch's sovereign zstd ENCODER against the reference `zstd` tool.
# For a spread of inputs, sankoch compresses (zstd_encode_smoke) and the reference `zstd -d` decodes;
# we cmp byte-for-byte against the original. The encoder also self-checks via sankoch's own decoder.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/build/zstd_encode_smoke"
for t in zstd cmp head; do command -v "$t" >/dev/null 2>&1 || { echo "ERROR: missing '$t'"; exit 1; }; done

CYRIUS_NO_WARN_PIN_DRIFT=1 CYRIUS_NO_WARN_SHADOW_LIB=1 sh -c "cd '$ROOT' && cyrius build programs/zstd_encode_smoke.cyr build/zstd_encode_smoke" >/dev/null 2>&1 || { echo "ERROR: build failed"; exit 1; }
[ -x "$BIN" ] || { echo "ERROR: zstd_encode_smoke not built"; exit 1; }

WORK="$(mktemp -d /tmp/sankoch-zenc-XXXXXX)"
IN="/tmp/sankoch-zstd-enc-in"
ZST="/tmp/sankoch-zstd-enc-out.zst"
OUT="/tmp/sankoch-zstd-enc-dec"
trap 'rm -rf "$WORK" "$IN" "$ZST" "$OUT"' EXIT

# --- build a spread of source files (incl. empty, tiny, block-boundary, multi-block) ---
: 						> "$WORK/empty.bin"
printf 'hello zstd sovereign\n'                 > "$WORK/tiny.bin"
seq 1 20000 | tr '\n' ' '                       > "$WORK/text.bin"        # compressible
head -c 200000 /dev/urandom                     > "$WORK/rand.bin"        # incompressible -> raw
head -c 100000 /dev/zero                        > "$WORK/zeros.bin"       # -> RLE
yes 'AGNOS-the-sovereign-operating-system-0123' | head -c 300000 > "$WORK/repeat.bin"
head -c 131072 "$WORK/text.bin" 2>/dev/null | cat > "$WORK/blk128.bin" || true
head -c 131073 /dev/zero                        > "$WORK/blk128p1.bin"    # 128 KiB + 1 (2 blocks)
# small compressible inputs (<= 1023) exercise the Huffman-literal Compressed block:
yes 'the quick brown fox jumps over the lazy dog ' | head -c 900 > "$WORK/htext.bin"
yes '{"key":"value","num":1234},'                  | head -c 800 > "$WORK/hjson.bin"
awk 'BEGIN{a=1;b=1;for(s=0;s<14;s++){for(i=0;i<a;i++)printf "%c",65+s;t=a+b;a=b;b=t}}' > "$WORK/hfib.bin"   # deep tree -> length limiter

rc=0; total=0; pass=0
for f in empty tiny text rand zeros repeat blk128 blk128p1 htext hjson hfib; do
    src="$WORK/$f.bin"
    [ -f "$src" ] || continue
    total=$((total + 1))
    cp "$src" "$IN"
    "$BIN"; e=$?
    if [ "$e" -ne 0 ]; then echo "  FAIL $f: encoder exit $e"; rc=1; continue; fi
    rm -f "$OUT"
    if zstd -d -q -f -o "$OUT" "$ZST" 2>/dev/null && cmp -s "$OUT" "$src"; then
        pass=$((pass + 1))
    else
        echo "  FAIL $f: reference zstd -d rejected or mismatch ($(stat -c %s "$src" 2>/dev/null || echo 0) B src)"; rc=1
    fi
done

echo ""
echo "  $pass/$total cases: sankoch-encoded frame decoded byte-identical by reference zstd -d"
[ "$rc" -eq 0 ] && echo "zstd-encode-smoke: PASS — reference zstd -d accepts sankoch's zstd_compress output (store + Huffman literals + LZ77/FSE sequences)" || echo "zstd-encode-smoke: FAIL"
exit $rc
