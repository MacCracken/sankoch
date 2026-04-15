# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [1.2.0] — 2026-04-15

**Feature release: LZ4 frame format, concatenated gzip, zlib dictionary support, multi-block DEFLATE.**

### Added
- **LZ4 frame format** (`lz4f_compress`, `lz4f_decompress`) — full LZ4F
  frame wrapper with magic bytes, frame descriptor, header checksum,
  content checksum (xxHash32), and uncompressed block fallback.
  Byte-identical output to `lz4` CLI v1.10.0 on tested inputs.
- **xxHash32** (`xxhash32()`) — fast 32-bit hash in `checksum.cyr`,
  used by LZ4 frame format for header and content checksums.
- **Concatenated gzip decompression** — `gzip_decompress` now loops
  over multiple back-to-back gzip members per RFC 1952 Section 2.2.
- **zlib preset dictionary** (`zlib_decompress_dict`) — handles FDICT
  flag in zlib streams. Verifies dictionary Adler-32, pre-fills the
  DEFLATE sliding window, and decompresses with back-references into
  the dictionary. Also adds `deflate_decompress_dict` for raw DEFLATE
  with a preset dictionary.
- **Multi-block DEFLATE infrastructure** — `deflate_compress_level`
  now uses block-based functions (`_deflate_compress_fixed_block`,
  `_deflate_compress_dynamic_block`) that accept a shared bitwriter
  and BFINAL flag. Currently uses 1MB block size (single block for
  most inputs). Enables future adaptive block splitting.
- 9 new tests: `test_lz4f_roundtrip`, `test_lz4f_empty`,
  `test_lz4f_checksum`, `test_gzip_concat`, `test_zlib_fdict`.
  Total: 5897 assertions, 0 failures.

## [1.1.0] — 2026-04-15

**Huffman table bug fix. All 15 disabled tests now passing.**

### Fixed
- **Huffman table heap overflow** — `_huff_alloc_tables()` allocated
  2288 bytes for litlen lens/codes (286 entries) but needed 2304
  (288 entries), and 240 bytes for dist lens/codes (30 entries) but
  needed 256 (32 entries). The 16-byte overflow from `litlen_codes`
  into `dist_fast` corrupted canonical code assignment for the entire
  distance Huffman table, causing DEFLATE decompression to produce
  wrong output whenever back-references were present. This was the
  root cause behind round-trip content mismatches, zlib/gzip wrapper
  failures, and the dynamic Huffman "stack corruption" symptoms
  reported in v1.0.0.
- **Stale `_huff_fixed_built` flag** — after dynamic Huffman tables
  overwrite the shared decoder tables (during zlib/gzip decompress of
  dynamic blocks), `huff_build_fixed()` returned early because the
  cache flag was still set. Fixed by resetting `_huff_fixed_built = 0`
  in `huff_build_litlen` so the next fixed-block decompress rebuilds
  the tables correctly.
- **`test_stream_decompress` pointer bug** — used `&c + half` (address
  of stack variable) instead of `c + half` (heap data offset).

### Added
- **15 tests uncommented** — `test_deflate_dec_backref`,
  `test_deflate_rt_repetitive`, `test_deflate_rt_all_bytes`,
  `test_deflate_rt_2kb`, `test_zlib_rt_hello`, `test_zlib_rt_via_api`,
  `test_zlib_corrupt_checksum`, `test_gzip_rt_hello`,
  `test_gzip_rt_via_api`, `test_gzip_corrupt_crc`,
  `test_gzip_truncated`, `test_format_detect_roundtrip`,
  `test_levels_deflate`, `test_levels_zlib`, `test_dynamic_huffman_rt`,
  `test_dynamic_vs_fixed`, `test_stream_compress`,
  `test_stream_decompress`, `test_stream_reset`. Total: 5762
  assertions, 0 failures.
- **Benchmark size comparison** — `benches/bench_sankoch.bcyr` now
  emits machine-readable `SIZE` lines for 1K, 4K, 16K, 64K, 256K
  inputs across all formats and levels.
- **`scripts/compare-sizes.sh`** — runnable pre-release script that
  compares sankoch compressed output sizes against C zlib (via Python
  bindings) and the `lz4` CLI. Prints a side-by-side delta table.
  Dynamic Huffman (L6) matches or beats C zlib at every size tested
  (1K–256K). LZ4 block output is byte-identical to the reference.

## [1.0.0] — 2026-04-15

**First stable release. Full lossless compression suite.**

### Added
- **LZ4 block compression** — hash-table match-finder (4096 entries,
  Knuth multiplicative hash), greedy matching. Compress + decompress.
- **DEFLATE** (RFC 1951) — all three block types (uncompressed, fixed
  Huffman, dynamic Huffman). Compression with LZ77 sliding window
  (32KB, 3-byte hash, configurable chain depth). 9 compression levels.
- **zlib wrapper** (RFC 1950) — CMF/FLG header, Adler-32 checksum.
- **gzip wrapper** (RFC 1952) — full header parsing (FEXTRA, FNAME,
  FCOMMENT, FHCRC), CRC-32 + ISIZE verification.
- **Checksums** — Adler-32 and CRC-32, inline implementations.
- **Format auto-detection** — `detect_format()` identifies gzip/zlib.
- **Streaming API** — `stream_compress_init/write/finish`,
  `stream_decompress_init/write/finish`, `stream_reset`.
- **Compression levels** — `compress_level()` and per-format level
  variants. Level 1-3: fixed Huffman (fast). Level 4-9: dynamic
  Huffman (better ratio).
- **Public API** — `compress()`, `decompress()`, `detect_format()`,
  `compress_level()` supporting FORMAT_LZ4, FORMAT_DEFLATE,
  FORMAT_ZLIB, FORMAT_GZIP.
- **Bundle script** — `scripts/bundle.sh` generates `dist/sankoch.cyr`
  for use as a Cyrius stdlib dep.
- **Test suite** — 1993 assertions (sankoch.tcyr) + 134 assertions
  (git_object.tcyr) covering all algorithms, round-trips, compression
  levels, dynamic Huffman, streaming, error paths, and git object
  format compatibility.

### Fixed
- **Dynamic Huffman repeat-call crash** — `_deflate_write_dynamic_header`
  passed `&_huff_cl_fast` (8-byte global address) instead of
  `_huff_cl_fast` (4096-byte heap buffer). Wrote 4096 bytes to an
  8-byte location, corrupting the data segment. Silent on first call,
  segfault on second. Fixed by passing the heap pointer and adding
  `_huff_alloc_tables()` guard.
- **Duplicate variable declarations** — `var rep`/`var j` in
  `deflate.cyr` elif branches, `var found` in `gzip.cyr` if blocks.
  Hoisted to function scope.
- **Reserved word as variable** — `var match` in deflate compress path
  renamed to `var mresult`.
- **Large static arrays** — `_lz77_head` (256KB), `_lz77_prev` (256KB),
  `_lz4_htab` (32KB) moved from static data to heap-allocated via
  `alloc()`. Eliminates output buffer overflow for bundled builds.
- **Stack arrays in dynamic header** — `cl_freqs`, `cl_lens_opt`,
  `cl_codes_opt`, `cl_order` migrated to heap workspace.

### Changed
- `cyrius.toml` — `[project]` → `[package]`, toolchain min 4.9.3.
- Test files — added missing stdlib includes, `assert_summary()` exit
  pattern for CI compatibility.
