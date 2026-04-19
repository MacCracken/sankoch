# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.6.1] — 2026-04-19

**xxHash32 spec-compliance fix + P(-1) scaffold hardening.**

During the P(-1) pass before v1.7.0, a deep audit of `src/checksum.cyr`
turned up that our `xxhash32` was the short-length variant only and
additionally used the wrong prime (`PRIME2` instead of `PRIME4`) in
the 4-byte tail. Our LZ4F encoder and decoder were self-consistent —
round-trip through sankoch worked — but the reference `lz4` CLI
rejected every one of our frames with a checksum error. That
contradicts the v1.6.0 "byte-identical to `lz4` CLI on inputs >64KB"
claim.

1.6.1 fixes the hash to match the [xxHash32 reference
spec](https://github.com/Cyan4973/xxHash/blob/dev/doc/xxhash_spec.md):
adds the 4-parallel-stripe accumulator path for `len ≥ 16`, corrects
the 4-byte tail multiplier, and pins the behavior with 9 known-vector
tests generated from `xxh32sum`.

**Wire-format break**: LZ4 frames written by sankoch 1.4.0–1.6.0
carry the divergent content checksum and will fail verification under
1.6.1's decoder. No shipping downstream consumer existed against the
LZ4F path — all consumers listed in CLAUDE.md are planned, not yet
shipped — so the break was taken deliberately. If you have stored
lz4f frames produced by sankoch ≤1.6.0, regenerate them with 1.6.1+.

### Fixed
- **`xxhash32` now matches reference xxHash32.** End-to-end validated:
  compressed 150KB of text via `lz4f_compress` (724-byte frame, 3
  blocks), decoded byte-identically via `lz4 -dc`, MD5 matches input.
  Pre-1.6.1, the same round-trip failed at the reference decoder's
  checksum step.

### Added
- `XXH32_PRIME4 = 0x27D4EB2F` constant + `_xxh32_round` helper.
- Full stripe-accumulator path in `xxhash32` for `len ≥ 16`.
- `test_xxhash32_known_vectors` with 9 reference vectors covering
  both short and long paths (`""`, `"a"`, `"abc"`, `"abcd"`,
  `"abcdefg"`, `"abcdef…mno"`, 16×0x00, `"Nobody inspects the spammish
  repetition"`, 64×0x00).
- `docs/audit/2026-04-19.md` — full P(-1) audit report covering HIGH
  (xxhash32), MEDIUM (direct-entry mutex gap; tracked for v1.7.0),
  LOW/cosmetics (all fixed), INFO (backlogged).

### Changed
- `src/checksum.cyr` header rewritten — removed the false "SIMD
  (SSE2)" claim; the unrolled loops are scalar. Real SIMD deferred to
  when Cyrius ships inline-asm.
- `src/stream.cyr` usage doc — function is `stream_write`, not the
  previously-shown `stream_compress_write` / `stream_decompress_write`.
- `src/deflate.cyr` — condensed the adaptive-block-splitting comment
  from 10 lines to 6; version-evolution history lives in this
  CHANGELOG.
- Cosmetic: `src/types.cyr:35` trailing `;`; `src/checksum.cyr` spacing
  on CRC-32 table references.

### Known limitations (tracked for v1.7.0)
- **Direct-entry APIs bypass `_sankoch_mtx`** (MED-01 in audit):
  `lz4f_compress/decompress`, `zlib_*`, `gzip_*`, `deflate_*`,
  `stream_*` are all publicly exported but only the
  `compress()`/`decompress()` wrappers take the mutex. Concurrent
  direct calls race on shared state (LZ4 hash table, DEFLATE tables,
  lazy-init flags). Fix deferred to v1.7.0 — a proper two-tier public/
  internal API split aligns with the streaming refactor that release
  needs anyway.

### Metrics
- **Test suite**: 286988 assertions (5897 + 281082 multi-block +
  9 xxhash32 vectors), 0 failures.
- **git_object suite**: 134 assertions, 0 failures.
- **Fuzz**: 1360 iterations across both harnesses, 0 failures.
- **Cleanliness**: `cyrius build` 0 warnings, `cyrius lint` 0
  warnings, `cyrius fmt --check` diff-clean, `cyrius vet` 18/0/0.
- **`dist/sankoch.cyr`** regenerated: 3410 lines (was 3370 in 1.6.0).
- **Throughput tradeoff** (correctness tax): `lz4f c text 128K`
  762199 → 819233 ns/op (+7.5%); `lz4f c rand 128K` 1180045 →
  1279163 ns/op (+8.4%). The extra cost is the proper stripe-path
  xxHash32 over the full input — the broken short-path version was
  cheaper but wrong. Compressed-size benchmarks are unchanged (SIZE
  lines byte-identical; the 4-byte checksum value differs but the
  frame length does not).

### Roadmap
- v1.6.1 "xxHash32 compliance + P(-1) closeout" → **shipped**.
- Next: **v1.7.0 — true incremental DEFLATE streaming** (third of
  four v2.0.0-track features). Will also land the public/internal API
  split that fixes MED-01.

## [1.6.0] — 2026-04-19

**LZ4 multi-block frames. Second bite on the v2.0.0 track.**

Pre-1.6.0 `lz4f_compress` emitted a single data block per frame
regardless of input size — even though the frame header (BD byte =
0x40) advertises a 64KB block max. On inputs over 64KB this violated
the LZ4 Frame spec and the reference `lz4` CLI would reject the
output.

1.6.0 chunks the input into ≤64KB blocks and emits one data block per
chunk. Each chunk is compressed independently (B.Indep=1 in FLG,
matching our existing header), and falls back to an uncompressed block
per-chunk when that chunk doesn't shrink. The content checksum still
covers the whole uncompressed input. The decompressor (`lz4f_decompress`)
was already multi-block-capable — its block-size loop handles the new
output without change.

### Fixed
- **LZ4 frames over 64KB are now spec-compliant.** Inputs up to any
  size are chunked into 64KB blocks per the BD byte; reference `lz4`
  CLI will accept the output.

### Changed
- **`lz4f_compress`** (`src/lz4.cyr:303`) — single-block body replaced
  with a chunking loop over `LZ4F_BLOCK_MAX = 65536`. Uncompressed
  fallback now applies per-chunk rather than to the whole frame. Empty
  input and content-checksum behavior unchanged.

### Added
- `enum LZ4F { LZ4F_BLOCK_MAX = 65536 }` — names the chunk size that
  matches our BD byte.
- `tests/tcyr/sankoch.tcyr` — two new tests:
  - `test_lz4f_multiblock_roundtrip` — 150KB input, verifies 3 blocks
    and byte-for-byte round-trip (≈150K per-byte assertions).
  - `test_lz4f_boundary` — exactly 65536 bytes → 1 block; 65537 bytes
    → 2 blocks; both round-trip.
  - Adds a small `_count_lz4f_blocks` helper that walks the frame and
    returns the block count (excluding the end mark).
- `tests/bcyr/sankoch.bcyr` — new throughput benches `lz4f c text 128K`
  and `lz4f c rand 128K`, plus SIZE lines `lz4f_text_64K/128K/256K`
  and `lz4f_rand_128K`.

### Metrics
- **Sizes** (text = compressible, rand = incompressible):
  - `lz4f_text_64K` (1 block): 331 bytes
  - `lz4f_text_128K` (2 blocks): 647 bytes
  - `lz4f_text_256K` (4 blocks): 1279 bytes
  - `lz4f_rand_128K` (2 uncompressed blocks): 131095 bytes
    (= 131072 payload + 8 block headers + 7 frame header + 4 end mark
    + 4 content checksum — validates the uncompressed-block path
    across chunk boundaries)
- **Test suite**: 286979 assertions (5897 prior + 281082 new per-byte
  checks from the multi-block round-trips), 0 failures
- **git_object suite**: 134 assertions, 0 failures
- **No regression** on any existing SIZE line
- **`dist/sankoch.cyr`** regenerated: 3370 lines (was 3356 in 1.5.0)

### Roadmap
- v1.6.0 "LZ4 multi-block frames" → **shipped** (second of four
  v2.0.0-track features).
- Next: **v1.7.0 — true incremental DEFLATE streaming**
  (re-architect `stream.cyr` + expose a "consume up to N bytes, emit
  what's ready" API in `deflate.cyr`).
- Then: v2.0.0 cut.

## [1.5.0] — 2026-04-19

**Adaptive DEFLATE block splitting. First bite on the v2.0.0 track.**

When the dynamic-Huffman symbol buffer (`DYN_SYM_MAX = 16384`) fills,
1.4.0- would abort the dynamic block entirely and re-encode the whole
range with the universal fixed-Huffman tree. On large low-locality
inputs (random-ish, >16K symbols), this collapsed compression quality
to fixed-tree baseline and — for inputs over ~256K — could even
overflow the output buffer because fixed-Huffman on uniform bytes is
~8.44 bits/literal, exceeding the caller-provided capacity.

1.5.0 replaces the fallback with proper adaptive sub-block emission:
each sub-block flushes when the buffer is near full, writes its own
BFINAL=0 dynamic header with a Huffman tree tuned to *its own* symbol
frequencies, and the next sub-block starts fresh. The last sub-block
in the caller's range carries the caller's BFINAL flag.

### Fixed
- **256K random no longer returns `-ERR_BUFFER_TOO_SMALL`.** Pre-1.5.0
  the fallback-to-fixed path produced 276KB+ of output for 256K random
  input, overflowing a typical caller buffer. 1.5.0 compresses it to
  262858 bytes via multiple adaptive dynamic sub-blocks — comfortably
  within a standard output buffer sized at `src_len + small margin`.

### Changed
- **`_deflate_compress_dynamic_block`** refactored into a multi-sub-block
  emitter. Same signature; same invocation surface for callers; new
  internal flush loop. All 5897 DEFLATE assertions + 134 git-object
  assertions + 1360 fuzz iterations still green.
- **Comment on `DEFLATE_BLOCK_SIZE`** updated — it's now the outer
  chunker step, not the sole determinant of block count. The dynamic
  path subdivides further based on symbol-buffer fill.

### Added
- `tests/bcyr/sankoch.bcyr` — two new benchmarks exercising the
  previously-broken overflow path:
  - `deflate6_rand_64K`: 65719 bytes (was 69056 — **−3337, −4.8%**)
  - `deflate6_rand_256K`: 262858 bytes (was `-2` error — **works**)

### Metrics
- **Size wins** (random / low-locality data):
  - 64K random: 69056 → 65719 (−3337 bytes, −4.8%)
  - 256K random: error → 262858 (correctness fix)
- **No regression** on high-locality text inputs — 26/26 existing bench
  sizes byte-identical to 1.4.0.
- **Test suite**: 5897 + 134 = 6031 assertions, 0 failures
- **Fuzz**: 1360 iterations, 0 failures
- **`dist/sankoch.cyr`** regenerated: 3356 lines (was 3316 in 1.4.0)

### Roadmap
- v1.5.0 "Adaptive DEFLATE block splitting" → **shipped** (first of
  four v2.0.0-track features).
- Next: **v1.6.0 — LZ4 multi-block frames** (wrapper-level work in
  `lz4.cyr`, chunks >64KB inputs into multiple 64KB frame blocks to
  match the reference `lz4` CLI).
- Then: v1.7.0 incremental streaming; v2.0.0 cut.

## [1.4.0] — 2026-04-19

**Fuzz harnesses fixed and wired into CI. Roadmap 1.4.0 scaffold
follow-up, shipped.**

### Fixed
- **`fuzz/fuzz_lz4.fcyr` / `fuzz/fuzz_deflate.fcyr`** — every
  stack-array call site was passing the bare name (`src`, `compressed`,
  `decompressed`) to `lz4_compress` / `deflate_decompress` / etc.,
  which loaded the first 8 bytes of the array instead of its address
  (per `memory/reference_stack_array_addr.md`). Every non-pointer
  call rewritten to `&buf`. Root cause for the silent segfault /
  early-exit under every prior toolchain; the harnesses have almost
  certainly been broken since 1.0.0.
- **`fuzz/fuzz_deflate.fcyr`** — missing `alloc_init()` at main entry,
  added.

### Added
- **Fuzz gate in CI + release workflows**. Each `.fcyr` harness is
  built with DCE and run under a 60-second timeout; any non-zero exit
  fails the pipeline. Current coverage: 500 LZ4 round-trips + 200
  LZ4 malformed + 240 DEFLATE round-trips + 100 DEFLATE malformed +
  160 zlib round-trips + 160 gzip round-trips = **1360 fuzz
  iterations per run**, all green.
- **Stack-array pointer note** at the top of each `.fcyr` file —
  documents the `&buf` discipline for future editors.

### Metrics
- **Fuzz coverage**: 1360 iterations/run, 0 failures
- **Test suite** (unchanged from 1.3.0): 5897 + 134 = 6031 assertions
- **`dist/sankoch.cyr`**: 3316 lines (no source changes; bundle
  regenerated to pick up the new VERSION header)

### Roadmap
- v1.4.0 "Wire fuzz harnesses into CI" → **shipped**.
- `cyrius fmt --write` still not available in 5.4.7 — the `--check`
  stdout-diff gate stays as-is. Deferred to the next Cyrius bump.

## [1.3.0] — 2026-04-19

**Toolchain bump to Cyrius 5.4.7. Scaffold hardening — full migration to
first-party AGNOS conventions (yukti 1.3.0 layout).**

### Changed
- **Toolchain**: Cyrius 4.10.0 → **5.4.7**. Pinned in
  `cyrius.cyml` via `cyrius = "5.4.7"`; CI reads the version from the
  manifest rather than a hardcoded env var.
- **Manifest**: `cyrius.toml` + `.cyrius-toolchain` → **`cyrius.cyml`**.
  Version pulled from `VERSION` via `${file:VERSION}` interpolation —
  single source of truth, no duplicated number to drift. `[lib]
  modules = [...]` declares the distlib include order.
- **Build system**: `scripts/bundle.sh` → **`cyrius distlib`**. The
  compiler's native bundler replaces the ad-hoc shell concatenator;
  CI regenerates `dist/sankoch.cyr` and asserts it matches the
  committed file (no stale bundles slipping through review).
- **Dependency resolution**: vendored `lib/*.cyr` removed from the
  tree. `cyrius deps` resolves stdlib into `lib/` on demand from
  `[deps.stdlib]` in the manifest; `lib/` is gitignored.
- **Layout**: tests → `tests/tcyr/`, benches → `tests/bcyr/`. Matches
  yukti / first-party AGNOS convention; lets downstream crates read
  this repo without re-learning where things live.
- **Tag style**: release workflow accepts bare semver tags only
  (`1.3.0`, not `v1.3.0`). Matches the pre-existing convention.
- **CI rebuilt**: separate `Build & Test`, `Security Scan`, and
  `Documentation` jobs. Adds `cyrius lint`, `cyrius fmt --check`,
  `cyrius vet`, and a distlib-in-sync gate. No `cyrius.lock` / deps
  verify gate — sankoch is stdlib-only, pinned implicitly by the
  toolchain version.
- **`src/lib.cyr`** now owns the full include chain (stdlib + domain
  modules). Individual `src/*.cyr` modules declare zero `include`
  statements — flat namespace, distlib-clean.

### Added
- `scripts/version-bump.sh` — one-shot VERSION updater with next-step
  reminders.
- `docs/development/cyrius-usage.md` — toolchain command reference:
  build, test, bench, distlib, deps, fmt, lint, vet, release.
- `src/*.cyr` fmt-pass — `cyrius fmt --check` now diff-clean across
  all domain modules (6 files re-aligned: `checksum`, `deflate`,
  `gzip`, `huffman`, `lz4`, `zlib`).

### Removed
- `cyrius.toml` (replaced by `cyrius.cyml`).
- `.cyrius-toolchain` (toolchain pin moved into `cyrius.cyml`).
- `scripts/bundle.sh` (replaced by `cyrius distlib`).
- Vendored `lib/*.cyr` (resolved by `cyrius deps` on demand).
- `tests/investigate_stack_array.tcyr` (investigation-only, never in
  CI — the `&buf` lesson lives in auto-memory now).
- Stubbed/unused CI steps (`cc3` bundle-compile path — the new build
  uses `cyrius build` end-to-end).

### Fixed
- `tests/tcyr/sankoch.tcyr` lint clean (`multiple consecutive blank
  lines` at line 376 removed).
- `fuzz/*.fcyr` updated to include `src/lib.cyr` + `lib/assert.cyr`
  and call `alloc_init()` at main entry — wires them into the new
  build system. (Runtime behavior of the fuzz harnesses themselves
  unchanged from 1.2.0; they remain out-of-CI pending a dedicated
  follow-up pass.)

### Metrics
- **Test suite**: 5897 + 134 = 6031 assertions, 0 failures
- **`dist/sankoch.cyr`**: 3316 lines (regenerated by `cyrius distlib`)
- **Toolchain**: Cyrius 5.4.7 (was 4.10.0)
- **External deps**: 0 (unchanged — still zero-dep)

### Consumer guidance

Downstream projects including `lib/sankoch.cyr` from the Cyrius stdlib
get 1.3.0 automatically once the toolchain ships it. Direct consumers
of this repo's `dist/sankoch.cyr`: no API changes — drop-in
replacement for 1.2.0.

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
