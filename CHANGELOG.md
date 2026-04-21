# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **Toolchain**: Cyrius 5.4.7 → **5.5.22**. No source changes required
  — the stdlib modules sankoch consumes (`syscalls`, `string`, `alloc`,
  `fmt`, `vec`, `fnptr`, `thread`, `assert`) keep the same public API
  across the jump. Notable 5.5.x stdlib evolution, none of which
  affects sankoch's Linux x86_64 path: `syscalls` split into
  arch-dispatched files (x86_64 / aarch64 / windows); `alloc` added
  per-OS dispatch (Windows `VirtualAlloc` at 5.5.0; macOS mmap at
  5.5.16 — Darwin has no brk); `thread` moved the clone trampoline
  into inline asm (fixes the `majra-cbarrier` crash at 5.5.10);
  `fnptr` raised the fncallN ceiling from 6 to 8 and gained a Win64
  shadow-space shim at 5.5.7. Two late scaffold wins: 5.5.21 fixed
  the SSE m128 / inline-asm 16-byte-alignment codegen bug, and
  5.5.22 landed `cyrfmt --write` / `-w` (closes the "cyrius fmt
  in-place mode" scaffold follow-up on sankoch's roadmap).
- **`cyrius.cyml` pin** updated to `cyrius = "5.5.22"`. CI extracts
  the toolchain version from this line, so no workflow-yaml edits
  beyond a comment refresh.
- **Docs sweep**: CLAUDE.md, README.md, roadmap, cyrius-usage doc
  refreshed to reference 5.5.22. Roadmap's `cyrius fmt` scaffold
  entry moved from "blocked" to closed; the `cyrfmt` workflow in
  `docs/development/cyrius-usage.md` now uses `cyrfmt --write`.
  Deferred `PCLMULQDQ` CRC-32 item is no longer gated on asm
  support — Cyrius 5.5.x exposes raw `asm { byte; … }` blocks
  (`lib/thread.cyr:_thread_spawn` uses them). Item stays deferred on
  priority grounds (table-driven CRC-32 is fast enough for today's
  consumers), not capability.

### Optimized
- **Adler-32 streaming path now matches batch throughput**
  (closes INFO-02 from `docs/audit/2026-04-19-pre-2.0.0.md`).
  `adler32_update` gained the same 16-byte unrolled closed-form inner
  loop as batch `adler32`. Safe within the NMAX window — the block
  bound ensures s1/s2 cannot overflow i64 between modulo reductions.
  Wire-format identical; 128 KB streaming zlib is ~6 % faster end-to-
  end, and the checksum path itself roughly doubles in throughput
  (~300 MB/s → ~620 MB/s on 4 KB chunks). Fuzz (196 streaming
  round-trips) and the incremental known-vector test remain green.



**Stable cut. Closes the v2.0.0 track.**

The four v2.0.0-track feature areas — 1.5.0 adaptive DEFLATE block
splitting, 1.6.0 LZ4 multi-block frames, 1.6.1 xxHash32 spec
compliance, 1.7.0 true incremental streaming across all four formats
(DEFLATE / zlib / gzip / LZ4F) — are all shipped and production-
settled. 2.0.0 declares the API stable and closes out the P(-1)
audit findings. No new features; no API changes from 1.7.0.

See `docs/audit/2026-04-19-pre-2.0.0.md` for the pre-release audit.

### Fixed (from the pre-2.0.0 audit)
- **LOW-01: `stream_compress_finish` / `stream_decompress_finish`
  now validate mode.** Previously, calling the wrong finish on a
  mismatched-mode ctx would dispatch `deflate_enc_finish` against a
  buffer pointer (or vice versa) and crash or emit garbage. Both
  functions now return `-ERR_INVALID_INPUT` up front if the ctx's
  mode doesn't match. Test: `test_stream_mode_mismatch`.
- **LOW-02: dead encoder-accessor helpers removed.**
  `_denc_load_level` and `_denc_state` in `src/deflate.cyr` were
  prospective getters that never got used. `_denc_err` stays.

### Known limitations (not blocking 2.0.0)
- **INFO-01**: `*_enc_init` functions don't check `alloc()` return
  for OOM — inherited project-wide pattern, rarely triggered by the
  auto-growing bump allocator. Backlogged for a v2.x hardening pass.
- **INFO-02**: `adler32_update` is byte-at-a-time; batch `adler32`
  uses a 16-byte unroll. `crc32_update` already has the matching
  unroll. Backlogged as a v2.x perf item.

### No public-API breaks vs 1.7.0
Anything compiling against 1.7.0 compiles + runs against 2.0.0
unchanged. Same function signatures, same return semantics, same
wire-format output byte-for-byte.

### Metrics
- **Source**: 4369 lines across 12 modules.
- **Tests**: 1028625 + 134 = 1028759 assertions; 0 failures.
- **Fuzz**: 1564 iterations across both harnesses; 0 failures.
- **Cleanliness**: `cyrius build` 0 warnings, `cyrius lint` 0,
  `cyrius fmt --check` clean.
- **SIZE md5** (batch + streaming lines):
  `83a039b0bbaa40dbbaca4f7fd4961197` — unchanged from 1.7.0.
- **End-to-end reference compatibility** still holds:
  `zlib.decompress`, `gunzip`, `lz4 -dc` each accept our streamed
  output byte-for-byte.

### Roadmap
- v2.0.0 → **shipped**.
- v2.x candidates (post-2.0.0, no commitment): true incremental
  decompression; ring-buffer LZ77 match-finder (replaces the
  slide-rebase scheme); `<fmt>_enc_init_dict` with preset dictionary;
  configurable LZ4F block-max size; Adler-32 16-byte unroll in the
  incremental path; defensive `alloc()` failure handling.
- Long-term (separate major version or separate crate): Zstandard,
  LZMA, Brotli, GPU texture codecs.

## [1.7.0] — 2026-04-19

**True incremental streaming across all four formats + MED-01 closed.
Third of four v2.0.0-track features.**

Before 1.7.0, `stream_compress_finish` accumulated the caller's full
input in a growing buffer and then called the batch compressor once.
Useless for inputs larger than memory. 1.7.0 replaces that with
per-format `*_enc_init/write/finish` triplets that emit compressed
output as each chunk arrives; `stream.cyr` dispatches to them. All
four formats stream now: DEFLATE (foundation), zlib and gzip (thin
wrappers over `deflate_enc_*` with incremental Adler-32 / CRC-32
trailers), and LZ4F (multi-block frame with per-64KB-block emit and
incremental xxHash32 content checksum).

The 1.6.1 audit's MED-01 — direct-entry batch APIs bypassing
`_sankoch_mtx` — is closed. Every public function that touches shared
mutable state now takes the mutex and delegates to an unlocked
`_*_inner` variant; internal callers use the inner variants to avoid
self-deadlock.

### Added
- **`deflate_enc_init(level, dst, dst_cap)` / `_write(ctx, chunk, len)`
  / `_finish(ctx)`** (`src/deflate.cyr`). 64 KB sliding window,
  slides every 32 KB with `lz77_rebase(delta)` keeping the hash
  tables consistent. LOOKAHEAD = 258 bytes held back during `_write`
  so matches can extend across chunks; `_finish` processes the full
  window. Dynamic path reuses 1.5.0 adaptive block splitting via
  three new primitives refactored out of the batch path —
  `_dyn_reset` / `_dyn_collect_at` / `_dyn_flush_subblock` — so
  batch and streaming share sub-block emit code. Fixed path
  (levels 1-3) emits one continuous BFINAL=0 block then a 5-byte
  BFINAL=1 stored-LEN=0 trailer; lazy matching disabled in the
  streaming fixed path (greedy only).
- **`zlib_enc_init/write/finish`** (`src/zlib.cyr`) wrapping
  `deflate_enc_*` with CMF/FLG header and a big-endian Adler-32
  trailer. Incremental Adler-32 in `src/checksum.cyr`:
  `adler32_init/update/final`.
- **`gzip_enc_init/write/finish`** (`src/gzip.cyr`) wrapping
  `deflate_enc_*` with a 10-byte gzip header and a little-endian
  CRC-32 + ISIZE trailer. Incremental CRC-32:
  `crc32_init/update/final`.
- **`lz4f_enc_init/write/finish`** (`src/lz4.cyr`). Accumulates up
  to `LZ4F_BLOCK_MAX = 65536` bytes, emits one LZ4 block per full
  buffer (B.Indep=1 makes each block independent), incremental
  xxHash32 across the frame. New checksum API: `xxhash32_init`
  (seed=0, stripe accumulators initialized), `xxhash32_update`
  (partial-stripe buffer + full-stripe direct processing),
  `xxhash32_final` (short vs long path by `total_len >= 16`).
- **`FORMAT_LZ4F = 5`** in `src/types.cyr`. Batch
  `compress(FORMAT_LZ4F, …)` and `decompress(FORMAT_LZ4F, …)` now
  dispatch through `_compress_inner` / `_decompress_inner`.
- **Rewritten `src/stream.cyr`**: `stream_compress_init(format,
  level, dst, dst_cap)` dispatches to the right `*_enc_init`;
  `stream_write` dispatches to the right `*_enc_write`;
  `stream_compress_finish(ctx)` dispatches to `*_enc_finish` and
  returns total bytes written. Decompression side unchanged
  (still buffers then batch-decompresses — true incremental
  decompression is future work). `FORMAT_LZ4` (raw block format)
  returns 0 from `stream_compress_init` — use `FORMAT_LZ4F` for
  streaming LZ4.

### Changed (MED-01 closed)
- Every batch public compression / DEFLATE-decompression entry
  takes `_sankoch_mtx` and delegates to a new internal
  `_*_inner(...)` function:
  - `lz4_compress`, `lz4f_compress`
  - `deflate_compress`, `deflate_compress_level`,
    `deflate_decompress`, `deflate_decompress_dict`
  - `zlib_compress`, `zlib_compress_level`, `zlib_decompress`,
    `zlib_decompress_dict`
  - `gzip_compress`, `gzip_compress_level`, `gzip_decompress`
- `lib.cyr`'s `_compress_inner` / `_decompress_inner` call the
  `_*_inner` variants directly (avoids double-lock via `compress()`
  wrapper).
- `lz4_decompress` / `lz4f_decompress` stay lock-free — they touch
  no shared mutable state.
- **Contract**: a live streaming encoder holds `_sankoch_mtx` from
  `enc_init` through `enc_finish`. On the same thread, `compress()`
  / `decompress()` calls in between deadlock (non-recursive mutex).
  Document this as a single-threaded invariant; concurrent
  encoders across threads serialize naturally.
- `_deflate_build_len_lookup` / `_dist_lookup` switched to forward
  iteration — audit INFO-01 from 2026-04-19.md. ~285 comparisons
  instead of ~7.4K at startup.

### Tests (selected — 1028623 total assertions, 0 failures)
- `test_deflate_enc_smoke/chunked/empty/fixed/slide/levels/window_boundary/varied_chunks`
  — cross-level, boundary, byte-at-a-time, 100 KB slide + rebase
- `test_zlib_enc_roundtrip/empty`, `test_gzip_enc_roundtrip/empty`,
  `test_lz4f_enc_roundtrip/multiblock/empty`
- `test_adler32_incremental`, `test_crc32_incremental`,
  `test_xxhash32_incremental` — each checks byte-at-a-time and
  varied-chunk updates against the batch function
- `test_stream_format_dispatch` — DEFLATE/ZLIB/GZIP/LZ4F through
  `stream_compress_*`; verifies `FORMAT_LZ4` raw-block is rejected
- `test_compress_dispatch_lz4f` — batch `compress(FORMAT_LZ4F, ...)`
- `test_enc_error_paths` — dst-overflow poisons ctx, sticky error,
  mutex released on error, subsequent compress works
- `test_enc_zero_write` — `enc_write(ctx, _, 0)` is a no-op

### Fuzz (new — 204 streaming iterations, 0 failures)
- `fuzz_deflate_stream` — 120 iters: 5 seeds × 6 sizes
  (0 / 1 KB / 64 KB / 65536 / 100 KB / 200 KB) × 4 levels
- `fuzz_zlib_stream` — 36 iters: 3 seeds × 4 sizes × 3 levels
- `fuzz_gzip_stream` — 36 iters: 3 seeds × 4 sizes × 3 levels
- `fuzz_lz4f_stream` — 12 iters: 3 seeds × 4 sizes, random chunks
  up to 16 KB (crosses the 64 KB LZ4 block boundary)

### End-to-end reference-CLI validation
- `zlib_enc_*` output on 100 KB decoded by Python `zlib.decompress`,
  md5 matches expected input.
- `gzip_enc_*` output on 100 KB decoded by `gunzip`, md5 matches.
- `lz4f_enc_*` output on 150 KB decoded by `lz4 -dc`, md5 matches.

### Metrics
- **Source**: ~3770 lines across 12 domain modules.
- **Tests**: 1028623 assertions (many from large per-byte round-trip
  checks in streaming tests), 0 failures.
- **git_object suite**: 134 assertions, 0 failures.
- **Fuzz**: 1564 iterations across both harnesses, 0 failures.
- **Cleanliness**: `cyrius build` 0 warnings, `cyrius lint` 0,
  `cyrius fmt --check` clean, `cyrius vet` 18/0/0.
- **Streaming throughput** (128 KB input, 4 KB chunks, 50 iters):
  - `stream deflate L1 text`: 3.25 ms/op (~40 MB/s)
  - `stream deflate L6 text`: 3.27 ms/op
  - `stream zlib L6 text`: 3.59 ms/op
  - `stream gzip L6 text`: 3.75 ms/op
  - `stream lz4f text`: 1.25 ms/op (~105 MB/s)
- **Streaming output sizes** vs batch (128 KB text, level 6):
  - `stream_deflate6_text_128K = 440` (batch: ~440 interpolated)
  - `stream_zlib6_text_128K = 446`
  - `stream_gzip6_text_128K = 458`
  - `stream_lz4f_text_128K = 647` (byte-identical to batch `lz4f_text_128K`)
- **Batch SIZE lines** unchanged from 1.6.1 baseline (md5
  `085f17f1227b863a21597969dea9a74a` on the original 35 entries).

### Breaking changes
- `stream_compress_init` signature: `(format, level)` →
  `(format, level, dst, dst_cap)`. Output dst is now provided at
  init, not finish.
- `stream_compress_finish` signature: `(ctx, dst, dst_cap)` →
  `(ctx)`. Returns total bytes written to the dst passed at init.
- `FORMAT_LZ4` is no longer accepted by `stream_compress_init` —
  use `FORMAT_LZ4F` for streaming LZ4.

No downstream consumer has shipped against these stream APIs
(CLAUDE.md lists all consumers as planned). The break was taken
deliberately to match the incremental shape for 1.7.0+.

### Roadmap
- v1.7.0 "True incremental streaming + MED-01" → **shipped**
  (third of four v2.0.0-track features).
- Next: **v2.0.0** — cut once the feature stack is stable. Any
  remaining scaffolding / polish work lives in 1.7.x point releases.
- Follow-up candidates for 1.7.x (not blocking v2.0.0): true
  incremental decompression; ring-buffer match-finder (replaces
  the slide-rebase scheme); zlib/gzip `_enc_*_dict` with preset
  dictionary; LZ4F with configurable block-max size.

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
