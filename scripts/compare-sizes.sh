#!/bin/sh
# sankoch — compressed-size comparison vs reference implementations
#
# Runs sankoch benchmarks and Python zlib/gzip on identical data,
# then prints a side-by-side table. Use before release to verify
# sankoch output sizes match (or beat) the C reference.
#
# Prerequisites:
#   - build/bench_sankoch (run: cyrius build benches/bench_sankoch.bcyr build/bench_sankoch)
#   - python3 with zlib module (standard library)
#   - lz4 CLI (optional — skipped if missing)
#
# Usage: ./scripts/compare-sizes.sh

set -e

BENCH="${1:-build/bench_sankoch}"

if [ ! -x "$BENCH" ]; then
    echo "ERROR: bench binary not found at $BENCH"
    echo "Build first: cyrius build benches/bench_sankoch.bcyr build/bench_sankoch"
    exit 1
fi

# ---- Step 1: Run sankoch bench, capture SIZE lines ----
SANKOCH_SIZES=$("$BENCH" 2>&1 | grep '^SIZE ' | sed 's/^SIZE //')

# ---- Step 2: Generate reference sizes with Python ----
REF_SIZES=$(python3 -c "
import zlib, gzip, io, sys

# Fill functions matching bench_sankoch.bcyr exactly
def fill_text(n):
    pat = b'The quick brown fox jumps over the lazy dog. '
    return bytes(pat[i % 45] for i in range(n))

def fill_zeros(n):
    return b'\\x00' * n

def fill_random(n):
    state = 42
    out = bytearray(n)
    for i in range(n):
        state = (state * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        out[i] = (state >> 33) & 255
    return bytes(out)

def raw_deflate(data, level):
    co = zlib.compressobj(level, zlib.DEFLATED, -15)
    return len(co.compress(data) + co.flush())

def zlib_size(data, level):
    return len(zlib.compress(data, level))

def gzip_size(data, level):
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb', compresslevel=level, mtime=0) as f:
        f.write(data)
    return len(buf.getvalue())

sizes = [1024, 4096, 16384, 65536, 262144]
labels = ['1K', '4K', '16K', '64K', '256K']

for sz, lab in zip(sizes, labels):
    t = fill_text(sz)
    print(f'lz4_text_{lab} {sz} -1')  # no LZ4 block reference in python
    print(f'deflate1_text_{lab} {sz} {raw_deflate(t, 1)}')
    print(f'deflate6_text_{lab} {sz} {raw_deflate(t, 6)}')
    if lab == '4K':
        print(f'deflate9_text_{lab} {sz} {raw_deflate(t, 9)}')
        print(f'zlib1_text_{lab} {sz} {zlib_size(t, 1)}')
    print(f'zlib6_text_{lab} {sz} {zlib_size(t, 6)}')
    print(f'gzip6_text_{lab} {sz} {gzip_size(t, 6)}')

# Special 4K inputs
z = fill_zeros(4096)
print(f'deflate6_zeros_4K 4096 {raw_deflate(z, 6)}')
r = fill_random(4096)
print(f'deflate6_rand_4K 4096 {raw_deflate(r, 6)}')
")

# ---- Step 3: Merge and print table ----
echo ""
echo "=== Sankoch vs C zlib — Compressed Output Sizes ==="
echo ""
printf "%-26s %8s %8s %8s %6s\n" "Tag" "Input" "Sankoch" "C ref" "Delta"
printf "%-26s %8s %8s %8s %6s\n" "--------------------------" "--------" "--------" "--------" "------"

echo "$SANKOCH_SIZES" | while read tag inlen outlen; do
    ref=$(echo "$REF_SIZES" | grep "^$tag " | awk '{print $3}')
    if [ -z "$ref" ] || [ "$ref" = "-1" ]; then
        printf "%-26s %8s %8s %8s %6s\n" "$tag" "$inlen" "$outlen" "—" ""
    else
        delta=$((outlen - ref))
        if [ "$delta" -gt 0 ]; then
            ds="+${delta}"
        elif [ "$delta" -lt 0 ]; then
            ds="$delta"
        else
            ds="0"
        fi
        printf "%-26s %8s %8s %8s %6s\n" "$tag" "$inlen" "$outlen" "$ref" "$ds"
    fi
done

echo ""

# ---- Step 4: LZ4 CLI comparison (if available) ----
if command -v lz4 >/dev/null 2>&1; then
    echo "--- LZ4 frame format (lz4 CLI) ---"
    echo "(sankoch uses block format; CLI uses frame format with ~19B overhead)"
    echo ""
    printf "%-18s %8s %8s %8s %8s\n" "Input" "Size" "Sankoch" "lz4 CLI" "CLI-19"
    printf "%-18s %8s %8s %8s %8s\n" "------------------" "--------" "--------" "--------" "--------"

    TMPDIR=$(mktemp -d)
    trap "rm -rf $TMPDIR" EXIT

    for sz_label in "1024 1K" "4096 4K" "16384 16K" "65536 64K" "262144 256K"; do
        sz=$(echo "$sz_label" | awk '{print $1}')
        lab=$(echo "$sz_label" | awk '{print $2}')

        python3 -c "
pat = b'The quick brown fox jumps over the lazy dog. '
import sys
sys.stdout.buffer.write(bytes(pat[i % 45] for i in range($sz)))
" > "$TMPDIR/text_${lab}.bin"

        lz4out=$(lz4 -c "$TMPDIR/text_${lab}.bin" 2>/dev/null | wc -c)
        adjusted=$((lz4out - 19))
        sk=$(echo "$SANKOCH_SIZES" | grep "^lz4_text_${lab} " | awk '{print $3}')
        printf "%-18s %8s %8s %8s %8s\n" "text $lab" "$sz" "$sk" "$lz4out" "$adjusted"
    done
    echo ""
fi

echo "=== comparison complete ==="
