# Sankoch vs Reference Implementations — Compressed Size Comparison

**Date:** 2026-04-15 (superseded by `scripts/compare-sizes.sh` — run that for current numbers)
**Reference:** C zlib 1.3.1 (via Python 3 bindings), lz4 v1.10.0 CLI
**Input:** byte-exact same data for both sankoch and reference

## DEFLATE (raw, no wrapper)

4KB repeating text (`The quick brown fox jumps over the lazy dog. ` × 91):

| Level | sankoch | C zlib | delta |
|-------|---------|--------|-------|
| L1 (fixed Huffman) | 80 | 89 | **-9 B** (sankoch smaller) |
| L3 (fixed Huffman) | 80 | — | |
| L6 (dynamic Huffman) | 71 | 72 | **-1 B** |
| L9 (dynamic Huffman) | 71 | 72 | **-1 B** |

4KB zeros:

| Level | sankoch | C zlib | delta |
|-------|---------|--------|-------|
| L6 | 20 | 20 | **0** (identical) |

4KB random (deterministic PRNG):

| Level | sankoch | C zlib | delta |
|-------|---------|--------|-------|
| L6 | 4141 | 4101 | **+40 B** (sankoch larger) |

## zlib (DEFLATE + Adler-32 wrapper)

4KB text:

| Level | sankoch | C zlib | delta |
|-------|---------|--------|-------|
| L1 | 86 | 95 | **-9 B** |
| L6 | 77 | 78 | **-1 B** |
| L9 | 77 | 78 | **-1 B** |

## gzip (DEFLATE + CRC-32 wrapper)

4KB text:

| Level | sankoch | C zlib | delta |
|-------|---------|--------|-------|
| L1 | 98 | 107 | **-9 B** |
| L6 | 89 | 90 | **-1 B** |
| L9 | 89 | 90 | **-1 B** |

## LZ4

Sankoch implements LZ4 **block format** (no frame header). The `lz4` CLI uses **frame format** (adds 11+ byte frame header/footer). Direct size comparison is not meaningful, but ratios are:

4KB text:

| | sankoch (block) | lz4 CLI (frame) | note |
|-|-----------------|-----------------|------|
| text 4K | 71 | 90 | frame adds ~19 B overhead |
| zeros 4K | 26 | 45 | frame adds ~19 B overhead |
| rand 4K | 4114 | 4115 | ~same (incompressible) |
| text 1K | 59 | 78 | frame adds ~19 B overhead |

Subtracting the ~19-byte frame overhead, the raw block sizes are equivalent.

## Summary

| Input | Format | sankoch | C reference | verdict |
|-------|--------|---------|-------------|---------|
| 4K text | DEFLATE L1 | 80 | 89 | sankoch 10% smaller |
| 4K text | DEFLATE L6 | 71 | 72 | match (1 B) |
| 4K text | zlib L6 | 77 | 78 | match (1 B) |
| 4K text | gzip L6 | 89 | 90 | match (1 B) |
| 4K zeros | DEFLATE L6 | 20 | 20 | identical |
| 4K random | DEFLATE L6 | 4141 | 4101 | sankoch 1% larger |
| 4K text | LZ4 block | 71 | ~71 (frame−19) | equivalent |

**Conclusion:** Sankoch matches C zlib output sizes within 1-2 bytes on compressible data. On random/incompressible data, sankoch is ~1% larger (40 bytes on 4KB). At L1, sankoch produces slightly smaller output because its fixed Huffman encoder uses a different greedy match strategy than C zlib's lazy evaluation at level 1.

## Interoperability

All sankoch zlib/gzip output decompresses correctly with standard tools — verified by `scripts/cross-compat.sh` using Python's `zlib.decompress()` and `gzip.decompress()`.

## What's not compared yet

- **Large inputs (64KB+):** sankoch's current benchmark only tests up to 4KB. The single-block compression architecture means behavior at larger sizes is untested.
- **Zstandard:** not in scope (future crate).
- **Decompression of externally-produced streams:** covered by cross-compat tests, not by size comparison.
