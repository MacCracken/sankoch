# Sankoch Development Roadmap

> **Status**: Pre-Alpha | **Last Updated**: 2026-04-14

---

## v0.1.0 — LZ4 Block Compression (Phase 1)

The starting point. Byte-aligned, simple format, proves the infrastructure. **Greenfield** — LZ4 has no equivalent in shravan.

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | types.cyr — error codes, format constants | Scaffolded | |
| 2 | checksum.cyr — Adler-32 + CRC-32 | Scaffolded | ~60 lines, inline |
| 3 | lz4.cyr — LZ4 block decompression | Scaffolded | ~80 lines, needs testing |
| 4 | lz4.cyr — LZ4 block compression (hash table match-finder) | Not started | Store-only placeholder exists |
| 5 | Round-trip tests (random, text, binary) | Scaffolded | 8 tests in tests/sankoch.tcyr |
| 6 | Fuzz harness | Not started | |
| 7 | Benchmarks (MB/s, ratio) | Not started | |
| 8 | lib.cyr — public API | Scaffolded | compress()/decompress()/detect_format() |

**Target**: ~500 lines of Cyrius. Zero deps. Usable by ark and kernel immediately.

## v0.2.0 — DEFLATE Decompression (Phase 2)

Unlocks `git clone` and `git fetch`. **Extraction** — bit-reader and Huffman decode exist in shravan.

| # | Item | Status | Source |
|---|------|--------|--------|
| 1 | bitreader.cyr — generic bit-stream reader | Not started | **Lift from** shravan/main.cyr:1244-1283, add LSB-first mode |
| 2 | huffman.cyr — canonical Huffman decode | Not started | **Lift structure from** shravan/aac.cyr:843-873, replace codebooks |
| 3 | huffman.cyr — Fixed Huffman trees (RFC 1951 3.2.6) | Not started | New — hardcoded tables from spec |
| 4 | huffman.cyr — Dynamic Huffman tree decode | Not started | New — HLIT/HDIST/HCLEN header parsing |
| 5 | deflate.cyr — DEFLATE decompression | Not started | New — block framing, length/distance codes |
| 6 | Known-vector tests (decompress zlib-generated data) | Not started | |
| 7 | Round-trip tests (compress w/ host zlib, decompress w/ sankoch) | Not started | |

**Spec**: RFC 1951 (DEFLATE Compressed Data Format Specification)
**Key extraction**: shravan's AAC Huffman decoder is canonical Huffman with table-based matching — same structure DEFLATE uses. The work is replacing AAC-specific codebook tables with DEFLATE's fixed/dynamic trees.

## v0.3.0 — DEFLATE Compression (Phase 3)

Unlocks `git push`. **Mixed** — bitwriter from shravan, LZ77 match-finder is new.

| # | Item | Status | Source |
|---|------|--------|--------|
| 1 | bitwriter.cyr — LSB-first bit-stream writer | Not started | **Lift from** shravan/flac.cyr:1007-1147, strip FLAC-specific |
| 2 | lz77.cyr — Sliding window match-finder | Not started | **New** — 32KB window, 3-byte hash, chains |
| 3 | huffman.cyr — Huffman tree construction (encode) | Not started | New — frequency count → canonical codes |
| 4 | deflate.cyr — DEFLATE compression | Not started | New — dynamic Huffman blocks |
| 5 | Round-trip tests (sankoch compress → sankoch decompress) | Not started | |
| 6 | Cross-compatibility (sankoch compress → zlib decompress) | Not started | Must produce valid DEFLATE |
| 7 | Compression levels (fast vs ratio) | Not started | Match-finder effort tuning |

**Key extraction**: shravan's FLAC bitwriter handles dynamic buffer growth, arbitrary bit counts, byte alignment. Strip `flac_bw_write_unary()` and `flac_bw_write_utf8_u64()` (FLAC-specific), keep the core.

## v0.4.0 — zlib + gzip Wrappers (Phase 4)

The framing layer. Thin wrappers over DEFLATE with checksums.

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | zlib.cyr — RFC 1950 wrapper (2-byte header + Adler-32) | Not started | What git objects use |
| 2 | gzip.cyr — RFC 1952 wrapper (10-byte header + CRC-32) | Not started | Archive interchange |
| 3 | Format auto-detection (magic bytes) | Not started | |
| 4 | Streaming API (incremental compress/decompress) | Not started | For large files |

## v1.0.0 — Stable Release

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | All Phase 1-4 complete and hardened | Not started | |
| 2 | Security audit pass | Not started | |
| 3 | Fuzz all formats extensively | Not started | |
| 4 | Performance parity with zlib on DEFLATE | Not started | Throughput benchmark |
| 5 | Integration tested with git object format | Not started | |
| 6 | API stable, documented, CHANGELOG complete | Not started | |

## Future (post-1.0)

- **Zstandard** — tANS + LZ77. Shravan's Opus range encoder (`opus.cyr:175-284`) is the entropy coding primitive tANS generalizes from. ~30K lines in reference impl. May warrant a separate crate or a major sankoch version. Research Duda's ANS paper (arXiv:1311.2540) first.
- **LZMA** — LZ77 + range coding + LPC prediction. Shravan's FLAC LPC decoder (`flac.cyr:517-580`) is the prediction stage. The range coder from Opus covers the entropy stage. The combination is LZMA's architecture.
- **Brotli** — if web serving needs arise
- **GPU texture compression** (BC1-BC7, ASTC) — mabda has generic compute dispatch (`compute.cyr`). Texture format enums are defined but codecs not yet implemented. When this lands, sankoch or a sibling crate provides the codec, mabda provides the GPU dispatch.

## Extraction Sources

Primitives that already exist in the AGNOS ecosystem, mapped to where they live:

| Primitive | Home | File | Lines | Reuse Path |
|-----------|------|------|-------|------------|
| Bit-reader (generic) | shravan | main.cyr | 1244-1283 | Lift → bitreader.cyr |
| Bit-writer (with grow) | shravan/FLAC | flac.cyr | 1007-1147 | Lift core → bitwriter.cyr |
| Canonical Huffman decode | shravan/AAC | aac.cyr | 843-873 | Lift structure → huffman.cyr |
| Rice/Golomb coding | shravan/FLAC | flac.cyr | 367-437 | Reference (future codecs) |
| Range encoder | shravan/Opus | opus.cyr | 175-284 | Reference (future Zstandard/LZMA) |
| LPC prediction | shravan/FLAC | flac.cyr | 517-580 | Reference (future LZMA) |
| FFT/MDCT | shravan | fft.cyr | 29-356 | Not needed for lossless |
| GPU compute dispatch | mabda | compute.cyr | 142 lines | Future GPU texture compression |

---

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

*Last Updated: 2026-04-14*
