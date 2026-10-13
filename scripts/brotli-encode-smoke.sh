#!/bin/sh
# brotli-encode-smoke.sh — validate sankoch's sovereign Brotli ENCODER against the reference `brotli`
# (1.2.0). Local only (not CI). For every fixture below, programs/brotli_encode_smoke.cyr compresses it
# at quality 0..11 and self-checks each stream through sankoch's own decoder; this script then decodes
# every stream with the reference `brotli -d` and cmps it against the fixture (the interop bar), and
# prints sankoch's size beside `brotli -q N -w 24`'s (informational: ratio is not gated).
#
#   scripts/brotli-encode-smoke.sh            all fixtures, 12 qualities each
#   scripts/brotli-encode-smoke.sh --sizes    also print the per-quality size table
#
# Work files live under build/brotli-enc/ (repo-local, survives a reboot).
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
BIN="build/brotli_encode_smoke"
W="build/brotli-enc"
SIZES=0
[ "${1:-}" = "--sizes" ] && SIZES=1
for t in brotli cmp head awk seq; do
    command -v "$t" >/dev/null 2>&1 || { echo "ERROR: missing '$t'"; exit 1; }
done
V="$(brotli --version 2>&1)"
echo "reference: $V"
CYRIUS_NO_WARN_PIN_DRIFT=1 CYRIUS_NO_WARN_SHADOW_LIB=1 cyrius build programs/brotli_encode_smoke.cyr "$BIN" >/dev/null 2>&1 \
    || { echo "ERROR: build failed"; exit 1; }
mkdir -p "$W/fx"
F="$W/fx"

# ---- fixtures ----
: > "$F/empty"
printf 'a' > "$F/one"
printf 'hello brotli\n' > "$F/tiny"
seq 1 20000 | tr '\n' ' ' > "$F/numbers"
head -c 200000 /dev/urandom > "$F/random"
head -c 100000 /dev/zero > "$F/zeros"
yes 'AGNOS-the-sovereign-operating-system-0123' | head -c 300000 > "$F/repeat"
cat src/*.cyr > "$F/source"                                       # ~770 KB: three meta-blocks
head -c 262144 "$F/source" > "$F/mb_exact"                        # exactly one meta-block
head -c 262145 "$F/source" > "$F/mb_plus1"                        # one byte into the second
awk 'BEGIN{for(i=0;i<4000;i++)printf "row%05d | const-field | %03d\n", i, i%7}' > "$F/records"
awk 'BEGIN{for(i=0;i<3000;i++)printf "{\"id\":%d,\"name\":\"item-%04d\",\"tags\":[\"a\",\"b\"],\"price\":%d.%02d,\"ok\":true}\n",i,i%733,i%90,i%100}' > "$F/json"
awk 'BEGIN{a=1;b=1;for(s=0;s<20;s++){for(i=0;i<a;i++)printf "%c",65+s;t=a+b;a=b;b=t}}' > "$F/fib"   # deep tree: length limiter
awk 'BEGIN{for(i=0;i<60000;i++){if(i%4==0)printf "%c",128+(i%128);else printf "%c",i%8}}' > "$F/wide"
{ head -c 50000 "$F/source"; head -c 50000 /dev/urandom; head -c 50000 "$F/records"; } > "$F/mixed"
head -c 300000 build/sankoch 2>/dev/null > "$F/elf" || true       # an ELF binary (cyrius build output)
printf '\303\244\303\266\303\274 \316\261\316\262\316\263 \320\260\320\261\320\262 \344\270\255\346\226\207 ' > "$F/utf8.1"
i=0; : > "$F/utf8"; while [ $i -lt 400 ]; do cat "$F/utf8.1" >> "$F/utf8"; printf '%d ' $i >> "$F/utf8"; i=$((i+1)); done
rm -f "$F/utf8.1"
[ -s "$F/elf" ] || rm -f "$F/elf"
# Past the 16 MiB - 16 window (WBITS 24): 1 MiB random, 16 MiB of source text, the same 1 MiB again
# (17 MiB back, out of reach), so a match beyond the window would decode as a dictionary reference.
head -c 1048576 /dev/urandom > "$F/big.x"
{ cat "$F/big.x"; i=0; while [ $i -lt 21 ]; do cat "$F/source"; i=$((i+1)); done | head -c 16777216; cat "$F/big.x"; } > "$F/big"
rm -f "$F/big.x"
# A real font (rekha's WOFF payloads are fonts), when that checkout is present.
FONT="$HOME/Repos/rekha/fonts/LiberationSans-Regular.ttf"
[ -f "$FONT" ] && cp "$FONT" "$F/font"

rc=0; total=0; pass=0
for src in "$F"/*; do
    f=$(basename "$src")
    total=$((total + 1))
    cp "$src" "$W/in"
    rm -f "$W"/q*.br
    out=$("$BIN" 2>&1); e=$?
    if [ "$e" -ne 0 ]; then echo "  FAIL $f: encoder exit $e $out"; rc=1; continue; fi
    ok=1
    line="$(printf '%-9s %8d' "$f" "$(wc -c < "$src")")"
    q=0
    while [ $q -le 11 ]; do
        qq=$(printf '%02d' $q)
        br="$W/q$qq.br"
        if ! brotli -dc "$br" 2>/dev/null | cmp -s - "$src"; then
            echo "  FAIL $f q$q: reference brotli -d rejected or mismatch"; ok=0
        fi
        if [ "$SIZES" -eq 1 ] && [ "$f" != big ]; then
            ref=$(brotli -c -q $q -w 24 "$src" | wc -c)
            line="$line | q$q $(wc -c < "$br")/$ref"
        fi
        q=$((q + 1))
    done
    [ "$SIZES" -eq 1 ] && echo "  $line"
    if [ "$ok" -eq 1 ]; then pass=$((pass + 1)); else rc=1; fi
done

echo ""
echo "  $pass/$total fixtures: every quality 0..11 decoded byte-identical by reference brotli -d (and by sankoch)"
[ "$rc" -eq 0 ] && echo "brotli-encode-smoke: PASS" || echo "brotli-encode-smoke: FAIL"
exit $rc
