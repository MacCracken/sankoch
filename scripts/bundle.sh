#!/bin/sh
# Bundle sankoch into a single distributable file for cyrius stdlib
# Usage: sh scripts/bundle.sh
# Output: dist/sankoch.cyr

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION=$(cat "$ROOT/VERSION" | tr -d '[:space:]')

mkdir -p "$ROOT/dist"

{
echo "# sankoch.cyr — lossless compression library for Cyrius"
echo "# Bundled distribution of sankoch v${VERSION}"
echo "# Source: https://github.com/MacCracken/sankoch"
echo "# License: GPL-3.0-only"
echo "#"
echo "# Usage: include \"lib/sankoch.cyr\""
echo "# API:   compress(format, src, src_len, dst, dst_cap) -> len or -err"
echo "#        decompress(format, src, src_len, dst, dst_cap) -> len or -err"
echo "#        detect_format(src, src_len) -> Format or -err"
echo "#"
echo "# Formats: FORMAT_LZ4, FORMAT_DEFLATE, FORMAT_ZLIB, FORMAT_GZIP"
echo ""
for f in src/types.cyr src/checksum.cyr src/bitreader.cyr src/bitwriter.cyr \
         src/huffman.cyr src/lz4.cyr src/lz77.cyr src/deflate.cyr \
         src/zlib.cyr src/gzip.cyr src/lib.cyr; do
    echo ""
    echo "# --- $(basename "$f") ---"
    echo ""
    grep -v "^include " "$ROOT/$f"
done
} > "$ROOT/dist/sankoch.cyr"

echo "dist/sankoch.cyr: $(wc -l < "$ROOT/dist/sankoch.cyr") lines (v${VERSION})"
