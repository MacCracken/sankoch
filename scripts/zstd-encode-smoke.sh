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
ZST9="/tmp/sankoch-zstd-enc-out9.zst"   # 2.7.3 level-9 DP optimal parse
OUT="/tmp/sankoch-zstd-enc-dec"
trap 'rm -rf "$WORK" "$IN" "$ZST" "$ZST9" "$OUT"' EXIT

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
# Skewed full-range distribution: 25% of bytes in 128..255 (maxsym > 128 -> the
# direct weight table can't fit, forcing FSE-compressed literal weights), 75% in
# 0..7 (skew -> Huffman literals win). Exercises the 2.5.6 FSE-weight encode path.
awk 'BEGIN{for(i=0;i<40000;i++){if(i%4==0)printf "%c",128+(i%128);else printf "%c",i%8}}' > "$WORK/hwide.bin"
# Structured records: mostly-constant rows with a few varying fields -> hundreds of
# sequences with skewed LL/ML/OF distributions -> adaptive FSE_Compressed sequence
# tables (2.5.7). Exercises the FSE-table description + RLE-mode wire format.
awk 'BEGIN{for(i=0;i<4000;i++)printf "row%05d | const-field | %03d\n", i, i%7}' > "$WORK/hstruct.bin"
# JSON-shaped records with a MONOTONICALLY DRIFTING id field (2.5.8). The record body
# recurs at an offset that grows by one per record, so a greedy-longest parse pays a
# full literal offset every record; the priced parse spends a literal and takes a
# repeat code instead. Multi-block, and the shape the 2.5.8 parse targets.
awk 'BEGIN{for(i=0;i<3000;i++)printf "{\"id\":%d,\"name\":\"item-%04d\",\"tags\":[\"a\",\"b\"],\"price\":%d.%02d,\"ok\":true}\n",i,i%733,i%90,i%100}' > "$WORK/hjsonrec.bin"
# Ascending decimal integers — the input where 2.5.7's length-based lazy accept test
# inverted the level ladder (level 2 was 67 % larger than level 1). Exercises the
# repcode-heavy offset stream the priced parse now produces.
awk 'BEGIN{for(i=1;i<20000;i++)printf "%d ", i}' > "$WORK/hasc.bin"
# 2.7.4: a LARGE record fixture (~840 KB, ~6-7 blocks). The record body recurs far
# beyond the 128 KiB block boundary, so it exercises the cross-block match window
# (a block's sequences referencing matches in PRIOR blocks) that 2.7.4 added — the
# case that must decode under reference zstd -d (single-segment window == full content).
awk 'BEGIN{for(i=0;i<12000;i++)printf "%08d,2026-07-21T%02d:%02d:%02d,user_%04d,GET,/api/v2/resource/%d,200,%d\n",i,i%24,i%60,(i*7)%60,i%1000,i%500,120+i%80}' > "$WORK/bigrec.bin"

rc=0; total=0; pass=0
for f in empty tiny text rand zeros repeat blk128 blk128p1 htext hjson hfib hwide hstruct hjsonrec hasc bigrec; do
    src="$WORK/$f.bin"
    [ -f "$src" ] || continue
    total=$((total + 1))
    cp "$src" "$IN"
    "$BIN"; e=$?
    if [ "$e" -ne 0 ]; then echo "  FAIL $f: encoder exit $e"; rc=1; continue; fi
    # Reference-decode BOTH the level-6 (greedy) and level-9 (DP optimal) frames.
    ok=1
    rm -f "$OUT"
    zstd -d -q -f -o "$OUT" "$ZST" 2>/dev/null && cmp -s "$OUT" "$src" || { echo "  FAIL $f (L6): reference zstd -d rejected or mismatch"; ok=0; }
    rm -f "$OUT"
    zstd -d -q -f -o "$OUT" "$ZST9" 2>/dev/null && cmp -s "$OUT" "$src" || { echo "  FAIL $f (L9 opt): reference zstd -d rejected or mismatch"; ok=0; }
    if [ "$ok" -eq 1 ]; then pass=$((pass + 1)); else rc=1; fi
done

echo ""
echo "  $pass/$total cases: sankoch-encoded frame (levels 6 + 9) decoded byte-identical by reference zstd -d"
[ "$rc" -eq 0 ] && echo "zstd-encode-smoke: PASS — reference zstd -d accepts sankoch's zstd_compress output (store + Huffman literals + LZ77 + Predefined/RLE/adaptive-FSE sequences)" || echo "zstd-encode-smoke: FAIL"
exit $rc
