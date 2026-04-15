# Sankoch Development Roadmap

> **Status**: Alpha | **Last Updated**: 2026-04-15

---

## v0.1.0 — LZ4 Block Compression (Phase 1)

The starting point. Byte-aligned, simple format, proves the infrastructure. **Greenfield** — LZ4 has no equivalent in shravan.

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | types.cyr — error codes, format constants | **Done** | Enums, limits, magic bytes |
| 2 | checksum.cyr — Adler-32 + CRC-32 | **Done** | ~56 lines, inline, RFC-verified |
| 3 | lz4.cyr — LZ4 block decompression | **Done** | Token parsing, extended lengths, overlapping match copy |
| 4 | lz4.cyr — LZ4 block compression (hash table match-finder) | **Done** | 4096-entry hash table, Knuth multiplicative hash on 4-byte sequences, greedy matching |
| 5 | Round-trip tests (random, text, binary) | **Done** | 8 LZ4 tests: empty, small, repetitive, all-same, short, buffer-too-small |
| 6 | Fuzz harness | Not started | |
| 7 | Benchmarks (MB/s, ratio) | Not started | |
| 8 | lib.cyr — public API | **Done** | compress()/decompress()/detect_format() |

**Actual**: ~266 lines in lz4.cyr. Zero deps. Compress + decompress functional with real compression.

## v0.2.0 — DEFLATE Decompression (Phase 2)

Unlocks `git clone` and `git fetch`. **Extraction** — bit-reader and Huffman decode lifted from shravan.

| # | Item | Status | Source |
|---|------|--------|--------|
| 1 | bitreader.cyr — LSB-first bit-stream reader | **Done** | **Lifted from** shravan/main.cyr:1244-1283, adapted MSB→LSB |
| 2 | huffman.cyr — canonical Huffman decode | **Done** | **Lifted structure from** shravan/aac.cyr:843-873, replaced AAC codebooks |
| 3 | huffman.cyr — Fixed Huffman trees (RFC 1951 3.2.6) | **Done** | 288 literal/length + 32 distance codes, 9-bit fast table |
| 4 | huffman.cyr — Dynamic Huffman tree decode | **Done** | HLIT/HDIST/HCLEN header, code-length alphabet, repeat codes 16/17/18 |
| 5 | deflate.cyr — DEFLATE decompression | **Done** | All 3 block types: stored (00), fixed (01), dynamic (10) |
| 6 | Known-vector tests (decompress zlib-generated data) | **Done** | 5 tests with vectors from Python zlib |
| 7 | Round-trip tests (compress w/ host zlib, decompress w/ sankoch) | **Done** | Verified against known-good output |

**Spec**: RFC 1951 (DEFLATE Compressed Data Format Specification)
**Key extraction**: shravan's AAC Huffman decoder restructured with DEFLATE fixed/dynamic trees. Bit-reader inverted from MSB-first to LSB-first.

## v0.3.0 — DEFLATE Compression (Phase 3)

Unlocks `git push`. **Mixed** — bitwriter lifted from shravan, LZ77 match-finder is new.

| # | Item | Status | Source |
|---|------|--------|--------|
| 1 | bitwriter.cyr — LSB-first bit-stream writer | **Done** | **Lifted from** shravan/flac.cyr:1007-1057, stripped FLAC-specific (unary, UTF-8), inverted to LSB-first |
| 2 | lz77.cyr — Sliding window match-finder | **Done** | **New** — 32KB window, 3-byte hash, chain collision resolution, 64-deep chain search |
| 3 | huffman.cyr — Huffman tree construction (encode) | **Done** | Canonical code generation with bit-reversal for LSB-first output |
| 4 | deflate.cyr — DEFLATE compression | **Done** | Fixed Huffman blocks, length/distance encoding with extra bits |
| 5 | Round-trip tests (sankoch compress → sankoch decompress) | **Done** | Empty, Hello, repetitive data with compression ratio assertion |
| 6 | Cross-compatibility (sankoch compress → zlib decompress) | Not started | Needs host-side verification script |
| 7 | Compression levels (fast vs ratio) | Not started | Match-finder effort tuning |

**Key extraction**: shravan's FLAC bitwriter core (buffer management, arbitrary bit counts, byte alignment) with FLAC-specific functions removed.

## v0.4.0 — zlib + gzip Wrappers (Phase 4)

The framing layer. Thin wrappers over DEFLATE with checksums.

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | zlib.cyr — RFC 1950 wrapper (2-byte header + Adler-32) | **Done** | Compress + decompress, header validation, checksum verification |
| 2 | gzip.cyr — RFC 1952 wrapper (10-byte header + CRC-32) | **Done** | Compress + decompress, FEXTRA/FNAME/FCOMMENT skip, CRC-32 + ISIZE verification |
| 3 | Format auto-detection (magic bytes) | **Done** | detect_format() handles gzip magic + zlib CMF/FLG |
| 4 | Streaming API (incremental compress/decompress) | Not started | For large files |

## v1.0.0 — Stable Release

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | All Phase 1-4 complete and hardened | **In progress** | Core algorithms done, needs hardening |
| 2 | Security audit pass | Not started | |
| 3 | Fuzz all formats extensively | Not started | |
| 4 | Performance parity with zlib on DEFLATE | Not started | Throughput benchmark |
| 5 | Integration tested with git object format | Not started | |
| 6 | API stable, documented, CHANGELOG complete | Not started | |
| 7 | Cross-compatibility verified (sankoch ↔ zlib/gzip tools) | Not started | |

## Remaining Work (pre-1.0)

Items across all phases that are not yet done:

| Item | Phase | Effort | Notes |
|------|-------|--------|-------|
| Fuzz harness (all formats) | 1-4 | Medium | Random data round-trip, malformed input |
| Benchmarks (MB/s, ratio) | 1-4 | Medium | 1KB/64KB/1MB/16MB, text/binary/random |
| Cross-compat test script | 3-4 | Low | sankoch compress → host zlib/gzip decompress |
| Compression levels | 3 | Medium | Match-finder effort tuning (fast/default/best) |
| Streaming API | 4 | Large | Incremental compress/decompress for large files |
| Dynamic Huffman encoding | 3 | Medium | Currently uses fixed only; dynamic gives better ratio |
| Security audit | All | Large | **Done 2026-04-15** — see docs/audit/2026-04-15.md |
| Git object format integration test | 2-4 | Low | **Done** — tests/git_object.tcyr |

### Deferred from Security Audit (2026-04-15)

| ID | Severity | Item | Notes |
|----|----------|------|-------|
| CRIT-02-FOLLOWUP | Critical | Verify DEFLATE stream consumed exact byte count before zlib/gzip trailer | Requires exposing bitreader position after decompress |
| MED-01 | Medium | Thread-safe state — replace globals with caller-provided context | Blocked until Cyrius has threading; document as known limitation |
| LOW-03 | Low | Replace linear scan in `_deflate_len_code`/`_deflate_dist_code` | Performance-only; binary search or lookup table |

## Future (post-1.0)

- **Zstandard** — tANS + LZ77. Shravan's Opus range encoder (`opus.cyr:175-284`) is the entropy coding primitive tANS generalizes from. ~30K lines in reference impl. May warrant a separate crate or a major sankoch version. Research Duda's ANS paper (arXiv:1311.2540) first.
- **LZMA** — LZ77 + range coding + LPC prediction. Shravan's FLAC LPC decoder (`flac.cyr:517-580`) is the prediction stage. The range coder from Opus covers the entropy stage. The combination is LZMA's architecture.
- **Brotli** — if web serving needs arise
- **GPU texture compression** (BC1-BC7, ASTC) — mabda has generic compute dispatch (`compute.cyr`). Texture format enums are defined but codecs not yet implemented. When this lands, sankoch or a sibling crate provides the codec, mabda provides the GPU dispatch.

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
| FFT/MDCT | shravan | fft.cyr | 29-356 | Not needed for lossless |
| GPU compute dispatch | mabda | compute.cyr | 142 lines | Future GPU texture compression |

---

## File Summary

| File | Lines | Phase | Role |
|------|-------|-------|------|
| types.cyr | 35 | 1 | Enums: formats, errors, limits |
| checksum.cyr | 56 | 1 | Adler-32, CRC-32 |
| lz4.cyr | 266 | 1 | LZ4 block compress + decompress |
| bitreader.cyr | 89 | 2 | LSB-first bit-stream reader |
| huffman.cyr | 309 | 2 | Huffman build/decode, fixed trees |
| deflate.cyr | 617 | 2-3 | DEFLATE decompress + compress |
| bitwriter.cyr | 141 | 3 | LSB-first bit-stream writer |
| lz77.cyr | 98 | 3 | Sliding window match-finder |
| zlib.cyr | 76 | 4 | RFC 1950 wrapper |
| gzip.cyr | 120 | 4 | RFC 1952 wrapper |
| lib.cyr | 74 | All | Public API |
| **Total** | **1881** | | |

Tests: 24 in tests/sankoch.tcyr (510 lines)

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

*Last Updated: 2026-04-15*
