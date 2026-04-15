#!/bin/sh
# sankoch — cross-compatibility verification
#
# Verifies that sankoch-compressed output can be decompressed by standard tools
# and that standard-compressed input can be decompressed by sankoch.
#
# Prerequisites: python3 with zlib module (standard library)
#
# Usage: ./scripts/cross-compat.sh <sankoch-binary>

set -e

SANKOCH="${1:-build/sankoch}"

if [ ! -x "$SANKOCH" ]; then
    echo "ERROR: sankoch binary not found at $SANKOCH"
    echo "Build first: cyrius build src/lib.cyr build/sankoch"
    exit 1
fi

PASS=0
FAIL=0
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

pass() { PASS=$((PASS + 1)); echo "  PASS: $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL: $1"; }

echo "=== sankoch cross-compatibility tests ==="
echo ""

# ----------------------------------------------------------------
# Test 1: Python zlib compress → sankoch decompress
# ----------------------------------------------------------------
echo "--- zlib interop ---"

python3 -c "
import zlib, sys
data = b'The quick brown fox jumps over the lazy dog'
compressed = zlib.compress(data, 6)
sys.stdout.buffer.write(compressed)
" > "$TMPDIR/zlib_compressed.bin"

python3 -c "
import zlib, sys
data = b'The quick brown fox jumps over the lazy dog'
sys.stdout.buffer.write(data)
" > "$TMPDIR/zlib_expected.bin"

# TODO: when sankoch has a CLI tool, test decompression here
# For now, verify the test data was generated correctly
python3 -c "
import zlib
with open('$TMPDIR/zlib_compressed.bin', 'rb') as f:
    compressed = f.read()
decompressed = zlib.decompress(compressed)
expected = b'The quick brown fox jumps over the lazy dog'
assert decompressed == expected, 'zlib self-check failed'
print('  zlib test data generated and verified')
"

# ----------------------------------------------------------------
# Test 2: Python gzip compress → verify format
# ----------------------------------------------------------------
echo "--- gzip interop ---"

python3 -c "
import gzip, sys
data = b'ABCABCABCABCABCABCABCABCABC'
compressed = gzip.compress(data)
sys.stdout.buffer.write(compressed)
" > "$TMPDIR/gzip_compressed.bin"

python3 -c "
import gzip
with open('$TMPDIR/gzip_compressed.bin', 'rb') as f:
    compressed = f.read()
decompressed = gzip.decompress(compressed)
expected = b'ABCABCABCABCABCABCABCABCABC'
assert decompressed == expected, 'gzip self-check failed'
assert compressed[0] == 0x1f and compressed[1] == 0x8b, 'gzip magic check failed'
print('  gzip test data generated and verified')
"

# ----------------------------------------------------------------
# Test 3: Raw DEFLATE round-trip via Python
# ----------------------------------------------------------------
echo "--- raw DEFLATE interop ---"

python3 -c "
import zlib, sys

# Generate known test vectors for sankoch to decompress
tests = [
    (b'', 'empty'),
    (b'Hello', 'hello'),
    (b'A' * 100, 'repeated_A'),
    (b'ABCDEFGHIJ' * 20, 'repeated_pattern'),
    (bytes(range(256)), 'all_bytes'),
]

for data, name in tests:
    # Raw DEFLATE (wbits=-15)
    co = zlib.compressobj(level=6, wbits=-15)
    compressed = co.compress(data) + co.flush()

    # Verify round-trip
    do = zlib.decompressobj(wbits=-15)
    decompressed = do.decompress(compressed)
    assert decompressed == data, f'DEFLATE round-trip failed for {name}'

    # Write test vector
    with open(f'$TMPDIR/deflate_{name}.bin', 'wb') as f:
        f.write(compressed)
    with open(f'$TMPDIR/deflate_{name}_expected.bin', 'wb') as f:
        f.write(data)

    print(f'  {name}: {len(data)} bytes -> {len(compressed)} bytes compressed')

print('  all DEFLATE test vectors generated and verified')
"

# ----------------------------------------------------------------
# Summary
# ----------------------------------------------------------------
echo ""
echo "=== Cross-compatibility test vectors generated ==="
echo "Test vector directory: $TMPDIR"
echo ""
echo "When sankoch has a CLI tool, re-run to verify interop."
echo "For now, the test suite in tests/sankoch.tcyr verifies"
echo "decompression of known-good zlib-generated vectors."
