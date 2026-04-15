# Sankoch Development Roadmap

> **Status**: Stable (v1.2.0) | **Last Updated**: 2026-04-15

---

## v2.0.0 — Performance and Streaming

### Adaptive block splitting (DEFLATE)

Replace the fixed 1MB block size with a cost-based heuristic that flushes a block when the Huffman tree becomes suboptimal. This is how C zlib achieves better L1 compression at large sizes. The multi-block infrastructure is in place (v1.2.0); this just needs the flush decision logic.

**Impact**: Closes the L1 size gap at 64K+ inputs. L6 dynamic already matches C zlib.

### True incremental DEFLATE streaming

Block-by-block compress/decompress without buffering the entire input. Currently `stream_compress_finish` accumulates all writes and compresses in one shot. True streaming would emit DEFLATE blocks as data arrives.

**Impact**: Required for compressing data larger than available memory.

### SIMD CRC-32

`PCLMULQDQ`-based CRC-32 for gzip. 4-10x speedup on x86_64. Requires Cyrius inline assembly or intrinsic support. Current table-driven CRC-32 runs at 278 MB/s on 4KB.

### LZ4 multi-block frames

Current LZ4F implementation emits a single block per frame. For inputs >64KB, split into multiple 64KB blocks within the frame, matching the `lz4` CLI behavior.

---

## Future (separate crate or major version)

- **Zstandard** — tANS + LZ77. Shravan's Opus range encoder (`opus.cyr:175-284`) is the entropy coding primitive tANS generalizes from. ~30K lines in reference impl. Research Duda's ANS paper (arXiv:1311.2540) first.
- **LZMA** — LZ77 + range coding + LPC prediction. Shravan's FLAC LPC decoder (`flac.cyr:517-580`) is the prediction stage. The range coder from Opus covers the entropy stage.
- **Brotli** — if web serving needs arise.
- **GPU texture compression** (BC1-BC7, ASTC) — mabda has generic compute dispatch (`compute.cyr`). Texture format enums are defined but codecs not yet implemented.

---

## Extraction Sources

Primitives that already exist in the AGNOS ecosystem, mapped to where they live:

| Primitive | Home | File | Lines | Status |
|-----------|------|------|-------|--------|
| Bit-reader (generic) | shravan | main.cyr | 1244-1283 | **Extracted** → bitreader.cyr (LSB-first) |
| Bit-writer (with grow) | shravan/FLAC | flac.cyr | 1007-1147 | **Extracted** → bitwriter.cyr (LSB-first, FLAC-specific stripped) |
| Canonical Huffman decode | shravan/AAC | aac.cyr | 843-873 | **Extracted** → huffman.cyr (DEFLATE codebooks) |
| Rice/Golomb coding | shravan/FLAC | flac.cyr | 367-437 | Reference (future codecs) |
| Range encoder | shravan/Opus | opus.cyr | 175-284 | Reference (future Zstandard/LZMA) |
| LPC prediction | shravan/FLAC | flac.cyr | 517-580 | Reference (future LZMA) |
| GPU compute dispatch | mabda | compute.cyr | 142 lines | Future GPU texture compression |

---

## File Summary

| File | Lines | Role |
|------|-------|------|
| types.cyr | 36 | Enums: formats, errors, limits |
| checksum.cyr | 189 | Adler-32, CRC-32, xxHash32 |
| bitreader.cyr | 99 | LSB-first bit-stream reader |
| bitwriter.cyr | 142 | LSB-first bit-stream writer |
| huffman.cyr | 491 | Huffman build/decode, fixed trees, optimal tree construction |
| lz4.cyr | 457 | LZ4 block + frame compress/decompress |
| lz77.cyr | 124 | Sliding window match-finder |
| deflate.cyr | 1257 | DEFLATE decompress + compress, multi-block, dictionary support |
| zlib.cyr | 102 | RFC 1950 wrapper + FDICT dictionary support |
| gzip.cyr | 159 | RFC 1952 wrapper + concatenated member support |
| lib.cyr | 115 | Public API, thread safety |
| stream.cyr | 124 | Streaming compress/decompress |
| **Total** | **3295** | |

Tests: 48 functions in sankoch.tcyr (856 lines) + git_object.tcyr (119 lines)
Assertions: 5897 + 134 = 6031 total

## Dependencies

**Zero.** Checksums (Adler-32, CRC-32) are inline. No sigil dependency. No stdlib beyond what cyrius.toml provides.

## Key References

- RFC 1951 — DEFLATE Compressed Data Format Specification
- RFC 1950 — ZLIB Compressed Data Format Specification
- RFC 1952 — GZIP File Format Specification
- LZ4 Block Format — github.com/lz4/lz4/blob/dev/doc/lz4_Block_format.md
- Feldspar, "An Explanation of the Deflate Algorithm" — clearest DEFLATE walkthrough
- Duda, "Asymmetric Numeral Systems" (arXiv:1311.2540) — for future Zstandard work

---

*Last Updated: 2026-04-15*
