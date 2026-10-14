#!/bin/sh
# crc32-clmul-asm.sh — provenance for the PCLMULQDQ CRC-32 fold's machine code (2.8.5).
#
# src/checksum.cyr's _crc32_clmul emits the fold as raw bytes inside an `asm { }` block (Cyrius has
# no SSE mnemonics). Those bytes come from docs/sources/crc32-pclmul/crc32_fold.S, assembled by GNU
# as, never typed by hand. Local only (needs binutils, and gcc + a PCLMULQDQ CPU for --check).
#
#   scripts/crc32-clmul-asm.sh           print the Cyrius byte lines for crc32_fold.S
#   scripts/crc32-clmul-asm.sh --check   1. the bytes between the BEGIN / END markers in
#                                           src/checksum.cyr equal a fresh assembly of the .S;
#                                        2. the fold is mathematically right: docs/sources/
#                                           crc32-pclmul/check.c links the .S and compares fold +
#                                           table finish with a bitwise CRC-32 on 20,000 buffers.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
SRC=docs/sources/crc32-pclmul
W=build/clmul
mkdir -p "$W"
for t in as objdump awk; do command -v "$t" >/dev/null 2>&1 || { echo "ERROR: missing '$t'"; exit 1; }; done
as --64 -o "$W/crc32_fold.o" "$SRC/crc32_fold.S" || { echo "ERROR: as failed"; exit 1; }

# objdump -> "        0xf3; 0x0f; 0x6f; 0x06;  # movdqu xmm0,XMMWORD PTR [rsi]"
emit() {
    objdump -d -M intel --insn-width=16 "$W/crc32_fold.o" | awk -F'\t' '
        /^ *[0-9a-f]+:\t/ {
            n = split($2, b, " "); line = "        ";
            for (i = 1; i <= n; i++) if (b[i] != "") line = line "0x" b[i] "; ";
            ins = $3; gsub(/ +/, " ", ins); sub(/ $/, "", line);
            printf "%-56s # %s\n", line, ins
        }'
}

if [ "${1:-}" != "--check" ]; then emit; exit 0; fi

rc=0
emit > "$W/expected.txt"
awk '/# BEGIN crc32_fold.S/{f=1; next} /# END crc32_fold.S/{f=0} f' src/checksum.cyr > "$W/actual.txt"
if [ ! -s "$W/actual.txt" ]; then
    echo "FAIL: no BEGIN/END crc32_fold.S markers in src/checksum.cyr"; rc=1
elif diff -u "$W/expected.txt" "$W/actual.txt" > "$W/diff.txt"; then
    echo "ok: src/checksum.cyr carries exactly the assembled bytes ($(grep -c '0x' "$W/actual.txt") instructions)"
else
    echo "FAIL: src/checksum.cyr bytes differ from crc32_fold.S:"; cat "$W/diff.txt"; rc=1
fi
if command -v gcc >/dev/null 2>&1 && grep -q pclmulqdq /proc/cpuinfo 2>/dev/null; then
    { cat "$SRC/crc32_fold.S"; printf '        ret\n'; } > "$W/fold_ret.S"
    if gcc -O2 -o "$W/check" "$SRC/check.c" "$W/fold_ret.S" && "$W/check"; then
        echo "ok: fold + table finish == bitwise CRC-32 (native)"
    else
        echo "FAIL: native fold check"; rc=1
    fi
else
    echo "SKIP: native check (needs gcc and a PCLMULQDQ CPU)"
fi
[ "$rc" -eq 0 ] && echo "crc32-clmul-asm: PASS" || echo "crc32-clmul-asm: FAIL"
exit $rc
