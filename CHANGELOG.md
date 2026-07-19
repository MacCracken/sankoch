# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security
- **zstd decoder hardening against malformed input** (2.5.6) — the RFC-8878 decoder
  (`zstd_decompress`, shipped 2.5.0) trusted attacker-controlled length/size fields on
  the decode path and could be driven to read out of bounds, write past `dst_cap`, or
  spin/allocate unboundedly on a hostile `.zst`. An adversarial audit of every decoder
  section (verified independently) found **36 reachable issues** — 24 crashes,
  10 memory-corruption writes, 2 DoS. Root causes and fixes:
  - **Missing frame `end` bound.** The frame-header advance, 3-byte block header, and
    each block's `bsize` are now checked against `end = src + src_len` (minus a trailing
    content-checksum), so a truncated or oversized block can't push reads past the buffer.
  - **No output-capacity check until after a block was written.** Raw/RLE block copies,
    the no-sequence literal dump, per-sequence literal+match copies, and trailing
    literals now pre-check `_z_outpos + n ≤ _z_outcap`.
  - **Scratch overflows.** Raw/RLE literal `regenerated_size` (up to 20 bits) is bounded
    to the 256 KiB `_z_lit`; Huffman `Max_Number_of_Bits` and per-weight values are
    capped at 11 so the 2048-entry decode table can't overflow on build or lookup.
  - **Unbounded FSE.** `readNCount` now takes a read `limit` (bits past it read as 0, per
    spec padding) and a per-table `Accuracy_Log` cap (weights ≤6, LL/ML ≤9, OF ≤8), and
    rejects a distribution that doesn't sum to exactly `1<<log`, a symbol overshoot, or a
    truncated table — killing the 24 MB-alloc / 1 M-iteration DoS and the state-index and
    infinite-loop paths.
  - **Sequence execution.** Offset codes, LL/ML/OF symbols, match offsets
    (`mbase ≥ 0`), and the literal cursor are all range-checked before use.
  - Also fixed the same class of OOB read in `zstd_frame_content_size` (reachable from
    `tar.cyr` on a hostile archive).

  A 1,148-input malformed corpus went from **25 SIGSEGV + 133 hangs → 0/0**; a second
  1,784-input corpus of *valid* streams with byte-flips into the Huffman/FSE/sequence
  decoders is also clean. Reference `zstd -19` output (incl. a 1.2 MB binary) still
  decodes byte-identically and every round-trip test is unchanged. New
  `fuzz/fuzz_zstd.fcyr` (decode-survival + round-trip across 5 distributions +
  corruption) and a `test_zc_malformed_survive` regression case pinning the exact
  34-byte crash repro.

### Added
- **zstd encoder: lazy match parse** (2.5.6) — the LZ77 match finder now uses the
  classic one-step lazy heuristic: at each position it takes the longest match, but if
  the *next* position has a strictly longer one it defers, emitting the current byte as
  a literal and taking the better match. The search/insert loops are split into
  `_ze_find` / `_ze_insert` so the lookahead doesn't perturb the hash chain, and every
  consumed position is inserted exactly once; a "nice length" cutoff (128) skips the
  second search once a match is already long, keeping throughput up on long-match runs.
  Reference `zstd -d` decodes every output byte-identically. On source/binary this now
  **beats `zstd -1`** (`src/deflate.cyr` −2 %, `src/zstd.cyr` −1 %, `/bin/bash` ~tied),
  and narrows text (CHANGELOG.md +10 %→+7 %). Ratio-for-throughput: encode is ~2× the
  greedy cost on low-redundancy input (a compression-level knob to trade this is next on
  the 2.5.6 ladder).
- **zstd encoder: repeat-offset codes** (2.5.6) — the sequence encoder now maps a
  match offset that equals a recent offset to an `Offset_Value` of 1/2/3 (offset code
  0/1/1, zero-to-one extra bits) instead of a literal `offset + 3` (offset code up to
  ~17). A forward pass over the sequences (`_ze_offval`) mirrors the decoder's
  `_z_resolve_offset` recent-offset state machine — including the `literals_length == 0`
  index shift — so encode and decode stay in lockstep; the encoder's `_ze_ro1/2/3` reset
  to `{1,4,8}` per frame and are snapshotted/rolled back so only a *committed* sequence
  block advances them across a multi-block frame. Reference `zstd -d` (v1.5.7) decodes
  every output byte-identically. Never enlarges a stream (repeat codes cost ≤ literal
  offsets); on periodic/recurring-offset data it now **beats `zstd -1`** (e.g. a period-16
  pattern: 34 B vs zstd -1's 38 B). New `test_zc_repeat_offsets` regression case.
- **zstd encoder: FSE-compressed literal weights** (2.5.6) — the Huffman literals
  block now handles wide alphabets. When the max literal symbol value exceeds 128
  the direct weight table (header byte `127 + nw`, `nw ≤ 128`) can't represent the
  tree, so the weights are themselves FSE-coded (two interleaved states, backward
  bitstream) exactly as RFC 8878 §4.2.1.1 describes — the inverse of the decoder's
  `_z_huff_tree` FSE branch. Before this, wide-alphabet literals (UTF-8 text,
  binaries — any input reaching bytes ≥ 128) fell back to *raw* (uncompressed)
  literals; now they compress. Reference `zstd -d` (v1.5.7) decodes every output
  byte-identically. Measured on full 0–255-alphabet inputs: **+8–10 % vs `zstd -1`**
  (was effectively uncompressed literals); mixed UTF-8 text (CHANGELOG.md) closes to
  **+10 %**. New `test_zc_fse_weights` tcyr case (skewed full-range distribution,
  `maxsym > 128`) and a `hwide` reference-interop case in `zstd-encode-smoke.sh`.

### Changed
- **Toolchain pin 6.4.66 → 6.4.67** (part of the in-flight 2.5.6 work) — tracks the current Cyrius
  toolchain and clears the pin-vs-`cycc` drift warning. `cyrius deps` re-resolved the stdlib
  snapshot (no stdlib API changes surfaced); all gates green on 6.4.67 — lint / fmt / vet (25 deps,
  0 untrusted, 0 missing), full tcyr suite (4,483,964 assertions) + all fuzz harnesses, the 43-line
  SIZE wire-format gate, aarch64 cross-build, and the kernel-safe tripwire. **distlib output is
  byte-identical** across 6.4.66 → 6.4.67 (no source / API / wire-format change).

## [2.5.5] — 2026-07-18 — sovereign zstd encoder

Completes the Zstandard codec: `zstd_compress` — a sovereign RFC-8878 **encoder** to match the
decode-only `zstd.cyr` that shipped at 2.5.0. Produces valid frames that reference `zstd -d` v1.5.7
decodes **byte-identical** across hundreds of fuzz cases. Wired into `compress` / `compress_level`
as `FORMAT_ZSTD`, and unblocks the ZIP method-93 write path on the 2.6.x arc.

### Added
- **`zstd_compress(src, src_len, dst, dst_cap)`** — the full encode pipeline, built over the 2.5.5
  arc as verified bites:
  - **Frame + block framing** — single_segment frames, Raw / RLE / Compressed blocks, 128 KiB
    block chunking, frame-content-size flag arithmetic mirrored from the decoder.
  - **Huffman literals** — length-limited (≤ 11-bit) canonical codes whose assignment matches the
    decoder's `_z_huff_build`; direct weight table; single-stream (≤ 1023 B) and 4-stream (jump
    table) backward bitstreams; a size pre-estimate to skip non-beneficial blocks.
  - **LZ77 sequences** — a self-contained greedy hash-chain match finder (depth 128 + `best_len`
    quick-reject; `[lib.zstd]` can't pull in `lz77.cyr`) → LL/OF/ML sequences.
  - **FSE sequences** — FSE *encoding* tables (`FSE_buildCTable` shape, reusing the decoder's symbol
    spread) for LL/OF/ML in Predefined mode; the 3 interleaved states encoded **backward** (order
    derived by reversing the decoder's read order); Huffman-coded literals inside the sequences
    block. Lock-free + self-contained (no runtime/mutex dep), so the `[lib.zstd]` profile stays a
    closed closure.
- **Coverage**: `tests/tcyr/zstd_compress.tcyr` (16 round-trip tests, CI-gated — store / RLE /
  single- & 4-stream Huffman / length-limiter / LZ77+FSE sequences / wide-alphabet fallback) +
  `programs/zstd_encode_smoke.cyr` + `scripts/zstd-encode-smoke.sh` (reference `zstd -d` interop).

### Notes
- **Compression is within ~2–17 % of `zstd -1`** at this cut (within +2.4 % on ASCII source; it
  *beats* `zstd -1` on highly repetitive data and incompressible data). Ratios:
  [`docs/benchmarks/2026-07-18-2.5.5-zstd-encode.md`](docs/benchmarks/2026-07-18-2.5.5-zstd-encode.md).
  The remaining gap is FSE-compressed literal weights for wide/UTF-8/binary alphabets (which still
  store literals raw), repeat-offset codes, and a lazy parse — the **2.5.6** follow-on.
- Three spec bugs were caught **by reference `zstd -d`** during development — each a case where
  sankoch's own decoder was lenient enough to round-trip an invalid stream: a Huffman length-limiter
  overshoot (fixed with the exact zlib `gen_bitlen` repair), the direct-weight header-byte overflow
  for `maxsym > 128`, and a null-scratch SIGSEGV. Reference-CLI parity remains load-bearing (the
  1.6.1 xxHash32 lesson).

## [2.5.4] — 2026-07-18 — xz / bzip2 encoder throughput

Pure speed work on the two slow encoders — **output byte-identical**. Every codec's compressed
bytes are unchanged (xz stays within its ratio band; bzip2 stays byte-identical to `bzip2 -9`), so
the 43-line SIZE wire-format gate is untouched and no decode path is affected.

### Changed
- **xz optimal-parse encoder — ~5× faster on text, ~2.5× on repetitive input** (4 KB text
  119.4M → 24.0M ns/op; zeros 135.6M → 54.3M). The block-DP `_xze_dp_fill` did O(n × MATCH_MAX)
  work on inputs with long matches. Three output-preserving changes: (1) **hoisted the
  `_xze_price_dist` recompute** out of the normal-match length loop — the distance price depends on
  length only via `len_state = min(len-2, 3)`, so it has ≤ 3 distinct values per match but was
  recomputed once per length; (2) **inlined `_xze_relax`** at the two hot length loops with the
  loop-invariant state/rep-set/kind/dist args hoisted, so the common non-improving case is a
  load+compare not a 10-arg call; (3) a **match-finder `best` pre-check** in `_xze_get_matches`
  that skips the full byte-scan of candidates that cannot beat the current best. Random input is
  unaffected (its match loops rarely run).
- **bzip2 encoder — ~5% faster on random** (4 KB rand 3.65M → 3.45M ns/op). Two output-preserving
  changes: **`% n` → conditional subtraction** in the BWT prefix-doubling sort (`_bze_csort` +
  rank reassignment + last-column build), and a **scalarized 6-group cost accumulator** in
  `_bze_send_mtf` (the hot random-case Huffman-group loop). The random worst case is MTF/Huffman-
  bound, not BWT-bound, so the sort's modulo removal is the minor of the two.

### Notes
- Verified output-identical by a 40-input fingerprint battery (compressed length + CRC-32 unchanged
  across xz + bzip2 × 4 sizes × 5 input shapes), the full tcyr round-trip suite (4,483,866
  assertions), and the `fuzz_xz` / `fuzz_bzip2` encode→decode harnesses. Before/after numbers:
  [`docs/benchmarks/2026-07-18-2.5.4-encoder-throughput.md`](docs/benchmarks/2026-07-18-2.5.4-encoder-throughput.md).

## [2.5.3] — 2026-07-18 — xz / bzip2 ratio cap

Extends the DEFLATE-family decompression-bomb defense to the two remaining batch decoders, so a
consumer can inflate untrusted `.xz` / `.bz2` under the same relative-expansion bound the DEFLATE
family already enforces. No wire-format change — decode of legitimate streams is byte-identical
and unaffected (the 43-line SIZE gate is untouched).

### Added
- **`xz_decompress_with_ratio_cap(src, src_len, dst, dst_cap, max_ratio)`** and
  **`bzip2_decompress_with_ratio_cap(src, src_len, dst, dst_cap, max_ratio)`** — reject a stream
  whose output exceeds `max_ratio * src_len` with `ERR_RATIO_LIMIT`, checked **incrementally during
  decode** (xz at the `_xz_put` / `_xz_copy_match` output chokepoints; bzip2 at the RLE1 run-emit)
  before the bomb materialises. The 16 MB `DECOMPRESS_MAX_OUTPUT` ceiling and the caller's `dst_cap`
  remain the hard backstops; this adds a tunable *relative* bound. **Batch-only** — neither codec
  has a streaming decode path. The bzip2 cap is **cumulative across concatenated `.bz2` streams**
  (output position persists). `max_ratio < 1` (or negative `src_len` / `dst_cap`) →
  `ERR_INVALID_INPUT`.
- **Test + fuzz coverage**: 10 new `ratio_cap.tcyr` tests (bomb-rejected / generous-passes /
  boundary-crossover / uncapped-equivalence / arg-validation, × xz × bzip2) and a ratio-cap fuzz
  strategy in `fuzz_xz` / `fuzz_bzip2` (100 iterations each — a capped decode must return either
  `ERR_RATIO_LIMIT` or the *exact* uncapped output, never a partial or altered decode).

### Notes
- xz and bzip2 each carry a local `_xz_ratio_ceiling` / `_bz2_ratio_ceiling` (a copy of deflate's
  overflow-safe `min(src_len * max_ratio, 16 MB)` math) rather than calling deflate's, so the
  `[lib.xz]` / `[lib.bzip2]` distlib profiles stay self-contained closures — neither module may
  reference `deflate.cyr`.
- Closes the last open **INFO-F** item (the ratio cap previously covered the DEFLATE family only).

## [2.5.2] — 2026-07-18 — toolchain pin refresh (Cyrius 6.4.66)

Maintenance release: tracks the current Cyrius toolchain. **No source, API, or wire-format
changes** — every codec's output is byte-identical to 2.5.1, and the 43-line SIZE wire-format
gate is unchanged.

### Changed
- **Toolchain pin 6.4.43 → 6.4.66** (latest), so the bundle folds cleanly into the current
  Cyrius stdlib and clears the pin-vs-`cycc` drift warning. `cyrius deps` re-resolved the
  stdlib snapshot (`syscalls` / `string` / `alloc` / `fmt` / `vec` / `fnptr` / `thread` /
  `assert`) — no stdlib API changes surfaced. All gates green on 6.4.66: `lint` / `fmt` /
  `vet` (25 deps, 0 untrusted, 0 missing) clean; all tcyr suites (234 functions, 4,483,834
  assertions) and all fuzz harnesses (3,929 iterations) pass; the aarch64 cross-build and the
  kernel-safe tripwire (`programs/core_smoke.cyr`) hold.
- Regenerated the committed distlib bundles (`dist/sankoch.cyr`, `dist/sankoch-core.cyr`,
  `dist/sankoch-zlib.cyr`) — version-header line only; module content byte-identical.

## [2.5.1] — 2026-07-10 — per-codec distlib profiles

Organizes the distribution bundles by codec, so a consumer that needs only one archive envelope
pulls just that codec's closure instead of the whole compression library. No source/API changes.

### Added
- **Per-codec decode distlib profiles** in `cyrius.cyml` — `cyrius distlib <name>` →
  `dist/sankoch-<name>.cyr`:
  - **`[lib.zstd]`** — the RFC-8878 zstd decoder, fully self-contained (own bit reader / FSE /
    Huffman; no checksum/deflate/runtime). **782 lines vs the full bundle's ~11.4k** — the profile
    the installer path (agnova `base-system.tar.zst`) and takumi's zstd source tarballs want.
  - **`[lib.bzip2]`** (~2.0k), **`[lib.xz]`** (~2.7k), **`[lib.gzip]`** (~5.1k) — each codec's
    validated dependency closure.
  - **`[lib.tar]`** (~9.3k) — the sovereign tar cursor + every envelope its `tar_open_auto`
    dispatches to (gzip/xz/bzip2/zstd); the "extract any tarball" profile.
  Each closure was verified by compiling `<modules>` + the codec entry with no undefined sankoch
  symbols, and each generated bundle consumer-compiles against its `.deps` stdlib manifest.
- CI now regenerates + drift-checks **every** profile (previously only full + core); the release
  workflow ships each `dist/sankoch-<name>.cyr` as a tagged artifact.

## [2.5.0] — 2026-07-10 — sovereign zstd decode + a shared tar cursor

The compression library grows an **archive layer** (tar) and its last missing **codec** (zstd
decode), so the AGNOS ecosystem has one canonical, sovereign path for `.tar` / `.tar.gz` /
`.tar.xz` / `.tar.bz2` / `.tar.zst` — no `tar`/`gunzip`/`zstd` shell-outs anywhere.

### Added
- **`zstd.cyr` — sovereign Zstandard decoder** (RFC 8878, decode-only): `zstd_decompress(src,
  src_len, dst, dst_cap)` + `zstd_frame_content_size`. Frame/header parse, Raw/RLE/Compressed
  blocks, Raw/RLE/Compressed/Treeless literals (Huffman, 1- and 4-stream, FSE-compressed + direct
  weights), sequences (Predefined/RLE/FSE/Repeat for LL/OF/ML), the 3 recent (repeat) offsets, and
  overlap-safe match copy. No dictionary; content checksum parsed but not verified. Wired into
  `decompress` / `detect_format` as `FORMAT_ZSTD`. **Validated byte-identical against reference
  `zstd` v1.5.7** across text / random / repetitive / multi-block inputs × levels 1/3/9/19 ×
  checksum on/off — 40/40 (`programs/zstd_smoke.cyr`, `scripts/zstd-smoke.sh`). The predefined FSE
  tables + LL/ML/OF baseline tables were transcribed from the canonical format doc; the FSE
  distribution reader uses the canonical threshold-halving algorithm, and the FSE symbol count is
  bounded by exact stream exhaustion (the backward reader tracks consumed vs. useful bits).
- **`tar.cyr` — sovereign tar (POSIX ustar + pre-POSIX v7) reader** with a sink-agnostic pull
  cursor (`tar_open` / `tar_open_auto` / `tar_next` + `tar_kind`/`tar_path`/`tar_mode`/`tar_mtime`/
  `tar_size`/`tar_data`/`tar_link`). Lifted from takumi's proven `extract_archive` and made
  reusable so every consumer supplies its own write sink (takumi → filesystem, agnova → ext2).
  Handles header-checksum validation, PAX (`x`/`g`) + GNU (`L`/`K`) long names, the ustar prefix
  field, and path/symlink **traversal-safety** guards (enforced in-library — no `..`, no absolute
  paths, no control bytes; relative-symlink escape rejected). `tar_open_auto` sniffs the envelope
  and inflates in RAM via the gzip / xz / bzip2 / **zstd** decoders. Absolute-symlink policy is left
  to the consumer (source-tree extractors reject; rootfs writers keep). Validated across all five
  envelopes by `programs/tar_smoke.cyr` + `scripts/tar-smoke.sh` (byte-identical, symlinks preserved).

### Changed
- **Toolchain pin 6.3.18 → 6.4.43** (latest), so the bundle folds cleanly into the current Cyrius
  stdlib. All existing module tests remain green (millions of assertions).

## [2.4.9] — 2026-07-03

### Added
- **`[lib.zlib]` distlib profile → `dist/sankoch-zlib.cyr`** (`cyrius distlib zlib`). A DEFLATE/zlib-only
  bundle — just `zlib_compress` / `zlib_decompress` and their closure (types, checksum, bit I/O, huffman,
  lz77, deflate) — dropping the LZ4 / gzip / xz / bzip2 / streaming codecs. **53 initialised globals vs the
  full bundle's 175**, so a consumer that only inflates/deflates zlib streams (git objects: sit's read path,
  thoth's git producer) stays well under a downstream's `max 1024 initialised globals` compile budget while
  tracking the current sankoch, instead of pinning an old lean release. No new API — same `zlib_*` surface.

### Changed
- **Extracted the shared runtime seam into `src/runtime.cyr`** (`_sankoch_lock` / `_sankoch_unlock` /
  `_sankoch_alloc` + the fault-injection counter), out of `src/lib.cyr`. `lib.cyr` keeps the format-dispatch
  public API (`compress` / `decompress` / `detect_format`) and `_sankoch_reset_tables` (which references every
  codec's lazy globals, incl. `_lz4_htab` — hence not includable by a single-codec profile). This lets a lean
  profile pull the alloc/lock helpers its codec needs without dragging in the whole codec registry. Internal
  only — the full `[lib]` still includes both, so `dist/sankoch.cyr` is byte-equivalent in behavior. **No API
  change.**

### Notes
- 19/19 tcyr suites green (the runtime extraction is transparent to every codec). All three profiles
  (`[lib]` full / `[lib.zlib]` / `[lib.core]`) regenerated at 2.4.9; full bundle globals unchanged (175),
  new zlib profile 53. `[lib.core]` (pure LZ4 decode, kernel-safe) unaffected.

## [2.4.8] — 2026-07-01

### Fixed
- **Harness-wide undersized-array stack-smash sweep (SIGSEGV) under cyrius 6.3.13+ stack-allocated
  locals.** Eleven `var X[N]` array locals across the test **and fuzz** harnesses were the daimon
  footgun — declared as a **byte** count `[N]` but written as `N` i64 **slots** (`store64(&X + i*8)`),
  so each wrote `8×N` bytes into an `N`-byte (8-byte-rounded) slot. Benign while array locals lived in
  shared `.bss`; **frame-corrupting since cyrius 6.3.13** moved function-local arrays to the stack.
  `fuzz/fuzz_deflate.fcyr` was the one that actually SIGSEGV'd CI (`timeout … dumped core`); the others
  survived on frame-layout luck. All fixed to the element-typed slot spelling `var X: i64[N]`:
  - `fuzz/fuzz_deflate.fcyr` (7): `sizes[8]`, `stream_sizes[6]`, `levels[4]`, `sm_sizes[4]`,
    `sm_levels[3]`, `tree_entries[11]`, `skewed_sizes[5]`.
  - `fuzz/fuzz_lz4.fcyr` (1): `sizes[10]`.
  - `tests/tcyr/zlib_compress.tcyr` (1): `chunks[4]` (the 80 K streamed round-trip — first found).
  - `tests/tcyr/deflate_compress.tcyr` (2): `chunks[6]`, `levels[4]` (latent — passed by luck).
  - `tests/tcyr/git_object.tcyr` (1): `seeds[5]` (latent — passed by luck).
  The **library is unaffected** — a full compress-path array audit (zlib / deflate / huffman /
  bitwriter / lz77 / stream / checksum, adversarially verified) found every `var X[N]` correctly
  sized; every overrun was in a harness. **`cyrius test` (20/0) AND `cyrius fuzz` (4/0)** now pass on
  cycc 6.3.x (both were verified this time — the fuzz suite is the one that surfaced the CI crash).

### Changed
- **Pinned `cyrius = "6.3.18"`** (was 6.2.44) so CI validates against the current toolchain and the
  stack-locals drift cannot recur silently.

## [2.4.7] — 2026-06-30

### Fixed
- **bzip2 — two undersized array locals stack-smashed under cyrius 6.3.13+ stack-allocated locals.**
  `_bz_decode_block`'s MTF-undo `var pos[6]` (6 BYTES → one 8-byte slot) was written up to **48 bytes**
  (`store64(&pos + i*8)`, `i < n_groups ≤ 6`); `_bze_emit_block`'s symbol map `var present[16]` (16 bytes →
  two slots) was written **128 bytes** (`store64(&present + i*8)`, `i < 16`). Both were the daimon footgun
  (author meant i64 **slots**, declared **bytes**) — benign while array locals lived in shared `.bss`,
  **frame-corrupting since cyrius 6.3.13** moved function-local arrays to the stack. Sized to `[48]` / `[128]`.
  Surfaced by the AGNOS base-stack migration; caught by cyrius's v6.3.18 undersized-array audit. bzip2
  compress↔decompress roundtrips unchanged (all tests pass).

## [2.4.6] — 2026-06-25

**Streaming ratio cap (`*_dec_init_capped`).** Extends the 2.4.5 batch
zip-bomb defense to the incremental decode path, so a consumer that
stream-inflates untrusted objects (sit, on large wire objects) gets the
same ratio guarantee on `*_dec_init`/`write`/`finish` as on the one-shot
API.

### Added

- **`zlib_dec_init_capped(dst, dst_cap, expected_src_len, max_ratio)`**
  \+ `deflate_dec_init_capped` \+ `gzip_dec_init_capped`. The ceiling
  (`_deflate_ratio_ceiling(expected_src_len, max_ratio)`, shared with the
  batch path) is fixed at init and stored in the decoder ctx; the three
  streaming emit sites (stored / literal / match) reject with
  `ERR_RATIO_LIMIT` the moment cumulative output crosses it — checked
  incrementally across `dec_write` calls, so a bomb is poisoned
  mid-stream, not at the end. `expected_src_len` is the total compressed
  size the caller intends to feed (git object sizes are known up front).
  gzip enforces the cap **cumulatively across concatenated members** (dp
  and the ceiling both persist over `deflate_dec_reset`). The cap is a
  short-circuit compare gated on a `0` sentinel, so the uncapped
  streaming path is **byte-identical**. `max_ratio < 1` (or negative
  `expected_src_len`) → init returns `0`, no mutex taken. No preset-dict
  variant (capped streams are dict-less).

### Tests / fuzz

- [`tests/tcyr/ratio_cap.tcyr`](tests/tcyr/ratio_cap.tcyr): +6 streaming
  tests (30 assertions) — zlib bomb poisoned, generous round-trip,
  byte-at-a-time mid-stream rejection, raw-deflate cap, gzip cumulative
  across members, capped-init arg validation (incl. `expected_src_len == 0`
  rejection — a 0 would alias the uncapped sentinel). Suite now 16 tests /
  66 assertions.
- [`fuzz/fuzz_deflate.fcyr`](fuzz/fuzz_deflate.fcyr): +340 iterations
  (240 streaming generous-round-trip / tight-cap-trip + 100 streaming
  malformed-survival; `finish` always called so the mutex is released).

### Notes

- Decoder ctx grew one slot (`DDEC_CTX_SIZE` 176 → 184) for the cap
  ceiling; `deflate_dec_init` zeroes it so every existing init path stays
  uncapped (byte-identical). xz / bzip2 streaming decode remain uncapped
  (INFO-F).

## [2.4.5] — 2026-06-25

**Ratio-capped decompression (`*_with_ratio_cap`) + toolchain → 6.2.44.**
Defense-in-depth against decompression bombs for untrusted-input
consumers — sit inflates wire objects on fetch / clone / fsck. The
existing guards bound only *absolute* output (`DECOMPRESS_MAX_OUTPUT` =
16 MB plus the caller's `dst_cap`), so a crafted stream that stays under
16 MB but expands at a huge ratio (e.g. 4 KB → 15 MB, ~3800:1) slipped
through both. The new variants reject by *expansion ratio*, checked
incrementally during inflate. Closes the roadmap `sit` backlog item.

### Added

- **`zlib_decompress_with_ratio_cap(src, src_len, dst, dst_cap, max_ratio)`**
  \+ `deflate_decompress_with_ratio_cap` \+ `gzip_decompress_with_ratio_cap`.
  `max_ratio` is an integer output:input multiplier; the stream is
  rejected with the new **`ERR_RATIO_LIMIT` (11)** as soon as running
  output exceeds `max_ratio * src_len`, caught mid-inflate inside
  `_deflate_decode_block` (the expanding path) — and the stored-block
  arms test the same ceiling, so the cumulative output bound is **exact**
  (output never exceeds `max_ratio * src_len`, even for a mixed
  compressed+stored stream). Every check is gated on a `0` sentinel, so
  the uncapped path stays **byte-identical**. The 16 MB ceiling and
  `dst_cap` remain the hard backstops; this adds the tunable *relative*
  bound. gzip enforces the cap cumulatively across concatenated members.
  `max_ratio < 1` (or negative `src_len`) → `ERR_INVALID_INPUT`.

### Changed

- **Toolchain pin → `6.2.44`** (`cyrius.cyml [package].cyrius`, was
  6.2.15). `cyrius deps` re-resolved; build / full test suite / lint /
  fmt / vet all clean on the new toolchain; the wire-format SIZE gate is
  unchanged at 43 lines.

### Tests / fuzz / bench

- New suite [`tests/tcyr/ratio_cap.tcyr`](tests/tcyr/ratio_cap.tcyr)
  (10 tests, 36 assertions): bomb rejection (`ERR_RATIO_LIMIT`),
  generous-cap byte-exact round-trip, the exact crossover boundary
  derived from the measured compressed size, a hand-built stored-block
  stream through the stored arm, low-ratio data not false-tripped,
  capped/uncapped equivalence, the cumulative gzip-member cap, and
  argument validation.
- [`fuzz/fuzz_deflate.fcyr`](fuzz/fuzz_deflate.fcyr): +340 iterations
  (240 generous-cap round-trip / invalid-arg / run-bomb-rejection + 100
  malformed-survival across all three capped decoders).
- `bench`: an informational ratio-cap section (a 4 KB zeros bomb rejected
  at 2:1, accepted at 100000:1) — outside the SIZE gate.

### Notes

- Scope is the DEFLATE family (zlib / deflate / gzip) — the formats sit
  decompresses. xz / bzip2 decode funnel through analogous chokepoints
  (`_xz_put` / `_xz_copy_match`, the bzip2 RLE1 run-emit) and could take
  the same cap in a later cut; not wired this release.

## [2.4.4] — 2026-06-18

**AGNOS-compatible lock primitives.** `_sankoch_lock` / `_sankoch_unlock`
now no-op under `CYRIUS_TARGET_AGNOS`. AGNOS userland is single-threaded, so
the public-API mutex is unnecessary there; no-op'ing it means sankoch no longer
references `mutex_*` on agnos, so it builds `--agnos` with no thread/mutex
dependency even for a consumer that doesn't pull `thread.cyr`. (cyrius's
`thread.cyr` already self-guards agnos as of v6.2.3 — routing to
`thread_agnos.cyr`'s no-op mutexes — so this is the sankoch-layer counterpart
that makes sankoch self-sufficient, not a crash fix.) Host/Linux/macOS/Windows
behaviour is byte-identical — the lock is unchanged off agnos. Surfaced by kii
(PNG IDAT inflate), the first agnos consumer of sankoch. See the cyrius issue
`2026-06-12-sankoch-locks-not-agnos-compatible.md`.

## [2.4.3] — 2026-06-17

**bzip2 encode (`bzip2_compress` + `compress(FORMAT_BZIP2, …)`).** Closes
the bzip2 codec — sankoch now emits `.bz2` that `bzip2 -d` decodes and
our own `bzip2_decompress` round-trips. On the validation corpus the
output is **byte-identical to `bzip2 -9`**. Zero new dependencies.

### Added

- **`bzip2_compress(src, src_len, dst, dst_cap)`** (level 9) +
  `compress(FORMAT_BZIP2, …)` (the level 1–9 maps to the 100–900 KB block
  size). Encoder appended to [`src/bzip2.cyr`](src/bzip2.cyr) (~740
  lines): RLE1 → **forward BWT block-sort** (prefix-doubling suffix sort,
  counting-sort rounds, O(n log n)) → MTF + RLE2 → **multi-table Huffman**
  (libbzip2 `sendMTFValues`: 2–6 tables, 4 refinement passes, per-50-symbol
  group selectors, length-limited code construction capped at 20) →
  MSB-first bit packing → `.bz2` container (`BZh` header, per-block magic
  / CRC-32-BZIP2 / origPtr / symbol map, EOS magic + combined CRC).
  Multi-block by level.

### Tests / fuzz / bench

- New suite [`tests/tcyr/bzip2_compress.tcyr`](tests/tcyr/bzip2_compress.tcyr)
  (9 tests: empty / small / all-same / periodic / text / RLE-runs /
  pseudo-random / ~120 KB / public-API path) — our encode → our decode,
  byte-for-byte.
- [`fuzz/fuzz_bzip2.fcyr`](fuzz/fuzz_bzip2.fcyr): +300 encode→decode
  round-trip iterations (random / periodic / mostly-constant shapes).
- `bench`: a bzip2 compress/decompress section + a ratio line
  (informational — not in the SIZE gate).

### Conformance / ratio

- `bzip2 -d` decodes every fixture we emit; our own `bzip2_decompress`
  round-trips. Validated out-of-band across 0–1.2 MB (multi-block),
  random/zero/text/sequential/RLE-heavy content. **Byte-identical to
  `bzip2 -9`** on the corpus (faithful BWT + `sendMTFValues` port), so
  ratio is at parity.

### Notes

- The BWT block-sort dominates encode time (~0.7 ms/KB); fine for the
  archival/one-shot use this targets. The wire-format SIZE gate is
  unchanged at 43 lines (bzip2 encode is not gated).

**bzip2 decode (`bzip2_decompress` + `FORMAT_BZIP2`) — decode only.**
Rounds out the source-tarball codecs alongside the 2.4.0 xz decode path:
sankoch now extracts `.bz2` / `.tar.bz2`. From-scratch BWT-based decoder,
zero new dependencies.

### Added

- **`bzip2_decompress(src, src_len, dst, dst_cap)`** + `FORMAT_BZIP2`
  (= 7), wired into `decompress()` and `detect_format()` (magic `BZh` +
  level digit). New module [`src/bzip2.cyr`](src/bzip2.cyr) (~500 lines):
  MSB-first bit reader → Huffman decode (canonical, up to 6 tables, 50-
  symbol group selectors) → MTF + RLE2 inverse → **inverse BWT**
  (cumulative-count transform vector walked from the origin pointer) →
  RLE1 inverse, fused with the BWT walk. Per-block and combined-stream
  **CRC-32/BZIP2** validated. **Concatenated streams** (e.g. pbzip2
  output) decode; trailing data after a complete stream stops cleanly.
  Randomized blocks (extinct pre-0.9.5 feature) are rejected as
  unsupported.
- **CRC-32/BZIP2** (poly 0x04C11DB7, **non-reflected** — distinct from
  the reflected RFC-1952 CRC-32) in
  [`src/checksum.cyr`](src/checksum.cyr): `crc32_bzip2` + table init.
  Validated against the canonical `0xFC891918` check value for
  `"123456789"`.

### Tests / fuzz

- New suite [`tests/tcyr/bzip2_decompress.tcyr`](tests/tcyr/bzip2_decompress.tcyr)
  (8 tests: small/repetitive/text-multitable/empty/RLE1-runs/binary +
  corruption + public-API path) — real `bzip2` fixtures, decoded to the
  original byte-for-byte. CRC-32/BZIP2 test added to `checksum.tcyr`.
- New fuzz harness [`fuzz/fuzz_bzip2.fcyr`](fuzz/fuzz_bzip2.fcyr): 300
  random-input + 200 corruption iterations — never crash on hostile input.
- Out-of-band: 100+ `bzip2`-vs-sankoch round-trips across sizes 0–1.5 MB
  (multi-block), random/zero/text/sequential/RLE-heavy content, levels
  1–9; concatenated streams; a real multi-file `.tar.bz2`.

### Changed

- **Test suite split** (no source/behavior change; landed post-2.4.1).
  The monolithic `tests/tcyr/sankoch.tcyr` (~6,200 lines) was split by
  **codec × direction** into focused suites sharing
  `tests/tcyr/_harness.tcyr` (includes + 4 MB heap setup + cross-cutting
  helpers). The CI Test step auto-discovers every suite (skipping
  `_`-prefixed includes), so new suites (like `bzip2_decompress`) need no
  workflow edits. `git_object.tcyr` is unchanged.

## [2.4.1] — 2026-06-16

**xz / LZMA encode (`xz_compress` + `compress(FORMAT_XZ, …)`).** Closes
the xz codec — sankoch now emits valid `.xz` that `xz -d` decodes and our
own `xz_decompress` round-trips. From-scratch LZMA encoder with an
**optimal (price-table) parse**; zero new dependencies. Encode side lands
in [`src/xz.cyr`](src/xz.cyr) reusing the existing `lz77.cyr` match finder.

### Added

- **`xz_compress(src, src_len, dst, dst_cap)`** + `compress(FORMAT_XZ, …)`
  (the level argument is accepted but ignored — fixed lc=3/lp=0/pb=2 +
  optimal parse). Produces a complete `.xz` stream: header / single block
  (LZMA2 filter) / index / footer, all CRC-32 fields plus a **CRC-64**
  check over the uncompressed data (matching `xz`'s default).
- **LZMA range encoder** — carry-propagating `ShiftLow`, `encode_bit`
  (with the prob update), `encode_direct`, bit-tree / reverse-bit-tree
  encoders, 5-byte flush. Verified bit-exact against the 2.4.0 decoder.
- **Optimal parse** — a bounded forward DP (window `XZE_OPT_W`) minimizing
  the modeled bit-price of literal / normal-match / rep-match / short-rep
  moves, with rep-distance history tracked per path. Prices from a
  `ProbPrices` table (LzmaEnc-style) read against the live model; a
  per-window length-price cache keeps the hot loops O(1).
- **LZMA2 framing** — chunk control bytes with dict/state/props reset on
  the first chunk; up to ~2 MB uncompressed per chunk, cut early when the
  compressed size nears the 64 KB chunk limit (so incompressible input
  stays valid).

### Tests / fuzz / bench

- 8 new `.tcyr` encode tests (empty, small, all-same, periodic, text,
  pseudo-random, ~90 KB multi-window, and the public `compress` /
  `detect_format` / `decompress` path) — our encode → our decode,
  byte-for-byte.
- [`fuzz/fuzz_xz.fcyr`](fuzz/fuzz_xz.fcyr): +300 encode→decode round-trip
  iterations (random / periodic / mostly-constant shapes).
- `bench`: an `xz` compress/decompress section + a ratio line
  (informational — **not** in the wire-format SIZE gate, since the
  encoder will keep being tuned).

### Conformance / ratio

- `xz -d` decodes every fixture we emit; our own `xz_decompress`
  round-trips. Validated out-of-band across 1 B – 500 KB, random / zero /
  text / sequential content, plus a real `.tar.xz` extracted by `tar` +
  `xz`. **Numbers** (vs `xz -6`): within ~1–5 % on text/code (CHANGELOG
  39144 vs 37788; deflate.cyr 20192 vs 19304; lz4.cyr 8388 vs 8332),
  wider on pathological repetition (big.txt 308 vs 256). Not bit-identical
  to `xz` (different parse heuristics) — and not claimed to be.

### Notes

- **Decode-only formats unaffected.** The wire-format SIZE gate is
  unchanged at 43 lines (xz encode is not gated).
- Encoder throughput is modest (optimal-parse DP) — fine for the
  one-shot/archival use this targets; a throughput pass can follow.

## [2.4.0] — 2026-06-16

**xz / LZMA decode (`FORMAT_XZ`) — decode only.** Opens the 2.4.x
takumi-driven arc: adds a from-scratch `.xz` container parser + LZMA2
chunk framing + LZMA range/arithmetic decoder, unblocking takumi
`.tar.xz` source extraction. Zero new dependencies — pure Cyrius,
consistent with the rest of the library.

### Added

- **`xz_decompress(src, src_len, dst, dst_cap)`** + `FORMAT_XZ` (= 6)
  wired into `decompress()` and `detect_format()` (magic
  `FD 37 7A 58 5A 00`). New module [`src/xz.cyr`](src/xz.cyr) (~700
  lines): container parse → LZMA2 framing → LZMA core, all behind the
  existing `_sankoch_mtx` with a single lazily-allocated probability
  table (no per-call allocation on the decode path).
  - **Container**: stream header / block header(s) / index / stream
    footer, with the header CRC32, index CRC32, and footer CRC32 all
    validated; per-block **check field** verified for CRC-32 and
    CRC-64 (SHA-256 and "none" are parsed but not hashed — see
    [`roadmap.md`](docs/development/roadmap.md) § 2.4.0 scope).
  - **Concatenated streams** + 4-byte-aligned zero **Stream Padding**
    supported (matches `xz -dc`); **multi-block** and `xz -T` threaded
    streams decode.
  - **LZMA2**: uncompressed chunks, LZMA chunks, dict / state / props
    resets; **LZMA**: range decoder (normalize, bit / bit-tree /
    reverse-bit-tree / direct-bit), the full literal/match state
    machine with rep-distance history, and overlapping match copies.
- **CRC-64/XZ** (ECMA-182, reflected poly `0xC96C5795D7870F42`) in
  [`src/checksum.cyr`](src/checksum.cyr): `crc64` batch + `crc64_init`
  / `_update` / `_final` incremental, mirroring the CRC-32 APIs.
  Validated against the canonical `0x995DC9BBDF1939FA` check value for
  `"123456789"`.

### Tests

- 9 new `.tcyr` tests: 3 CRC-64 (empty / known-vector / incremental),
  6 xz decode (uncompressed-chunk, real-LZMA + CRC32, empty, check=none,
  binary-sequence + CRC64, multi-block) + a corruption-rejection test
  (flipped payload byte, bad magic, truncation, undersized dst).
  Fixtures are real `xz` output; the decoder must reproduce the original
  plaintext byte-for-byte.
- New fuzz harness [`fuzz/fuzz_xz.fcyr`](fuzz/fuzz_xz.fcyr): 300
  random-input + 200 corruption iterations — the parser must never
  crash, read out of bounds, or loop forever on hostile input.
- Out-of-band validation: 700+ `xz`-vs-sankoch round-trips across sizes
  1 B – 200 KB, random/zero/text/sequential content, all four check
  types, levels 0–9e; plus a real multi-file `.tar.xz`.

### Notes

- **Decode only** — no xz encoder (not required by takumi; stays in the
  full-codec Future bucket). The wire-format SIZE gate is unaffected
  (xz has no encode path, so no new SIZE lines).

## [2.3.8] — 2026-06-16

**P(-1) closeout for the 2.3.x line.** Process release — no source
changes. Verifies the 2.3.3–2.3.7 feature cuts before the 2.4.x
decode-only xz/bzip2 (takumi) arc opens.

### Audit

- **Security audit** [`docs/audit/2026-06-16-pre-2.4.0.md`](docs/audit/2026-06-16-pre-2.4.0.md):
  **zero HIGH / MEDIUM / LOW findings.** Re-checked the new `*_dec_*`
  state-machine source-bounds, the streaming-LZ4F block-buffer sizing
  under varied BD, the per-block checksum paths, the FDICT dict-scratch
  match-copy bounds, the bit-accumulator overpull rewind, and the
  alloc-fail propagation paths — all clean / in bounds. INFO-01 (FHCRC)
  and INFO-A (alloc-fail) confirmed CLOSED; INFO-B / INFO-C carried;
  one minor INFO-D noted (orphaned lazy-table memory on OOM-retry).
- **Benchmark baseline** [`docs/benchmarks/2026-06-16-pre-2.4.0.md`](docs/benchmarks/2026-06-16-pre-2.4.0.md):
  the 2.4.0 reference. All 43 SIZE wire-format lines byte-for-byte
  identical to the 2.3.4 baseline; no encode-hot-path throughput
  regression across the 2.3.5–2.3.7 decode/robustness work.
- **Gates:** clean rebuild 0 warnings, lint 0 warnings/file,
  `cyrfmt --check` clean, `vet` clean, both `.tcyr` suites + all fuzz
  harnesses + `core_smoke` + aarch64 cross-build all green.

## [2.3.7] — 2026-06-16

**Lazy-global alloc-failure propagation (INFO-A).** The ~33 lazy-global /
arena table allocations (Huffman tables, LZ77 hash, DEFLATE workspaces,
`_dyn_*` slabs, len/dist lookups, `crc32_table`, LZ4 hash, etc.) now
route through the fault-injectable `_sankoch_alloc` and propagate
allocation failure as a clean error instead of aborting on first-call
OOM. Closes the last item carried from the 2.2.1 / 2.2.3 audits.
Wire-format identical (all 43 SIZE lines unchanged).

### Added

- **`ERR_OOM` (code 10)** — a dedicated allocation-failure error code.
  Batch APIs return `0 - ERR_OOM`; streaming/ctx APIs return `0` (null
  ctx) with the mutex released, matching the 2.2.1 pattern.

### Changed

- **Lazy-init helpers return on OOM.** `crc32_init_table`,
  `_huff_alloc_tables`, `huff_build_fixed`, `_hcl_ws`, `lz77_init`,
  `_lz4_htab`, `_ddec_alloc_dyn_ws`, `_deflate_build_enc_fixed/_dist`,
  `_deflate_build_len/dist_lookup`, `_dh_ws`, `_deflate_alloc_dynamic_ws`,
  and `br_init` now check `_sankoch_alloc` and return a negative/null on
  failure. Public entry points (batch + streaming, encode + decode)
  check and propagate, releasing the mutex. Hot-path lazy-inits (the
  decode-loop Huffman builds, the encoder len/dist lookups + optimal-
  Huffman workspace) are pre-built at the public entry with a checked
  call, so the bit-by-bit state machines never allocate.
- `_deflate_alloc_dynamic_ws`'s 8-slab block is now retry-safe: a
  mid-block OOM zeroes the guard pointer so a later retry re-allocates
  the whole set instead of skipping it with null pointers.

### Fixed

- **Batch DEFLATE encoder segfault on bitwriter OOM.** `bw_init`'s
  allocation-failure return (`0`) was never checked on the batch
  compress path, so an OOM there dereferenced a null bitwriter. Now
  returns `0 - ERR_OOM`. (Pre-existing latent bug, surfaced by the new
  fault-injection sweep — exactly the kind of crash this work removes.)

### Added (tests)

- **OOM sweep fault-injection** (`test_oom_compress_sweep` /
  `test_oom_decompress_sweep`) + a test-only `_sankoch_reset_tables()`
  that zeroes the lazy globals so first-call OOM can be re-triggered.
  Each sweep injects a failure at every allocation offset along a public
  encode/decode path and asserts a clean result — completing the sweep
  proves both no-crash **and** no-deadlock (a path that OOMed without
  unlocking would hang the next iteration's lock). Suite: **3,862,492**
  assertions (sankoch) + 346,583 (git_object).

## [2.3.6] — 2026-06-16

**Streaming FDICT zlib.** The streaming zlib decoder can now decode
preset-dictionary (FDICT) streams when the caller supplies the matching
dictionary — previously rejected with `-ERR_UNSUPPORTED_FORMAT`. Closes
the last streaming/batch capability gap on the zlib path. Wire-format
identical (decode-only; all 43 SIZE lines unchanged).

### Added

- **`deflate_dec_init_dict(dst, dst_cap, dict, dict_len)`** — a
  streaming DEFLATE decoder pre-warmed with a preset dictionary. Unlike
  the batch path (which stages the dict at the front of `dst` and shifts
  the output afterward), the streaming variant keeps the dict in a
  separate scratch buffer beside the ctx; the match-copy reads it for
  back-references that reach before the stream's own output (negative
  logical offset). The decoded output therefore lands cleanly at `dst[0]`
  with no post-pass shift, and the layout survives chunk-boundary state
  saves. `dict_len == 0` is exactly `deflate_dec_init` and leaves the
  hot-path match-copy untouched (no common-path cost).
- **`zlib_dec_init_dict(dst, dst_cap, dict, dict_len)`** — streaming zlib
  decoder with a preset dictionary. On an FDICT stream it parses the
  4-byte big-endian DICTID (new `ZDEC_STATE_DICTID`) and validates it
  against `adler32(dict)` before decoding. `zlib_dec_init` now delegates
  to it with no dict; an FDICT stream fed to the no-dict path is still
  rejected (`-ERR_UNSUPPORTED_FORMAT` — nothing to satisfy it).
- New tests: streaming FDICT round-trip (whole + byte-at-a-time, with the
  input overlapping the dict so back-references reach into it) + wrong-
  dict (DICTID mismatch) and no-dict rejection. Suite: **3,862,327**
  assertions (sankoch) + 346,583 (git_object).

### Verified

- **Reference conformance.** sankoch's streaming decoder decodes a
  Python-`zlib`-produced FDICT stream (compressed with a preset
  dictionary) **byte-identical** to the reference output.

## [2.3.5] — 2026-06-16

**gzip streaming-decode hardening: FHCRC verify + concatenated members.**
Two decode-only correctness/capability additions to the streaming gzip
decoder (batch was already correct on both). Wire-format identical — all
43 SIZE lines unchanged.

### Added

- **gzip FHCRC verification** (closes INFO-01, carried from 2.1.3). Both
  the batch (`_gzip_decompress_member`) and streaming (`gzip_dec_write`)
  decoders now validate the optional 2-byte header CRC when FLG bit 1 is
  set, instead of skipping it. The streaming path folds header bytes into
  an incremental CRC-32 as they are parsed and checks the low 16 bits at
  the FHCRC field. **Spec correction:** RFC 1952 §2.3.1.2 defines FHCRC
  as the low 2 bytes of the **CRC-32** of the header — *not* CRC-16-IBM
  as the roadmap item supposed. Verified against reference `gunzip`
  (which reports "header checksum … != computed checksum" on a corrupted
  FHCRC). sankoch joins the enforce camp (zlib's gunzip 1.5+ behaviour).
- **Concatenated-member gzip streaming** (RFC 1952 §2.2). `gzip_dec_write`
  now decodes multiple gzip members in one stream — previously
  single-member only, while batch `gzip_decompress` already handled them.
  A new `GDEC_STATE_AFTER_TRAILER` probes for the next member's magic; on
  a match it resets the inner DEFLATE decoder (new `deflate_dec_reset` —
  keeps the output buffer + write offset so members append contiguously)
  and the per-member CRC / ISIZE bookkeeping. Each member's back-
  references can only reach its own emitted bytes, so the shared `dst` is
  safe. Output, trailer CRC, and ISIZE are validated per member.
- New tests: FHCRC round-trip (batch + streaming) + corruption rejection;
  concatenated 2-member round-trip (whole / byte-at-a-time / batch cross-
  check) + corrupt-2nd-member rejection. Suite: **3,862,108** assertions
  (sankoch) + 346,583 (git_object).

### Notes

- The other two 2.3.5-roadmap items were split into their own slots so
  each lands as a focused, well-tested release: **streaming FDICT zlib →
  2.3.6** (it modifies the DEFLATE match-copy hot path) and **lazy-global
  alloc-fail propagation → 2.3.7** (broad surface + large fault-injection
  matrix). P(-1) closeout moves to 2.3.8.

## [2.3.4] — 2026-06-16

**CRC-32 slice-by-8 (~2× throughput) + cyrius pin → 6.2.15.** Pure
performance + toolchain release — wire-format identical, no API change.
All 43 SIZE lines and every CRC-32 value are byte-for-byte unchanged
(gated by the gzip round-trip suites + fuzz).

### Changed

- **CRC-32 slice-by-8.** The batch `crc32` and incremental `crc32_update`
  paths now fold 8 bytes per iteration via one little-endian `load64` +
  eight parallel table lookups (Kadatch & Jenkins), replacing the serial
  byte-at-a-time table fold. The lookup table grew from one 256-entry
  slice to eight (16 KB). Both paths share a new `_crc32_fold` core.
  Pure integer, portable across x86_64 + aarch64. **~2.15×** on the
  reliable 1 KB / 256 KB benches (crc32 1 KB 2,951 → 1,370 ns/op);
  CRC-32 is now *faster* than Adler-32 at steady state, where it was
  ~1.5× slower before. See
  [`docs/benchmarks/2026-06-16-2.3.4-crc-sliceby8.md`](docs/benchmarks/2026-06-16-2.3.4-crc-sliceby8.md).
- **cyrius pin `6.2.14` → `6.2.15`** (folded into this release rather
  than a separate pin-bump patch). Clean rebuild + both `.tcyr` suites +
  fuzz + `core_smoke` green on 6.2.15; `dist/*` regenerated.

### Investigated, not adopted

- **`good_match` chain-walk early-exit** (the roadmap's other 2.3.4
  candidate). Implemented and measured: a no-op on every benchmarked
  text input (SIZE and throughput both unchanged), reproducing the prior
  revert. It's a speed/ratio tradeoff — wire-safe only where it gives no
  speedup, and faster only where it changes the selected matches and
  breaks the SIZE gate — so it cannot ship under the wire-identical
  mandate. Dropped (roadmap option c). PCLMULQDQ CRC-32 stays deferred
  (x86-only vs the aarch64 cross-build gate; the portable slice-by-8
  already lifts CRC-32 off the hot path).

### Added

- New benchmark: `crc32 256K text` / `adler32 256K text` — steady-state
  checksum throughput (the pre-2.3.4 benches were 4 KB / 1 KB only).

## [2.3.3] — 2026-06-16

**Configurable LZ4F block-max + per-block checksum.** The streaming
LZ4F encoder can now emit any of the four BD block-max sizes (64K /
256K / 1M / 4M) and optionally append a per-block xxHash32; both the
streaming and batch decoders parse the BD block-max ID and validate
per-block checksums. Additive API (new `lz4f_enc_init_ex`) → minor-
within-line bump. Default `lz4f_enc_init` output is byte-identical to
2.3.2 — all pre-existing SIZE lines unchanged.

### Added

- **`lz4f_enc_init_ex(dst, dst_cap, block_max_id, block_checksum)`** —
  configurable streaming encoder. `block_max_id` ∈ {4,5,6,7} selects
  64K/256K/1M/4M blocks (BD bits 4-6); `block_checksum != 0` sets FLG
  bit 4 and appends a 4-byte xxHash32 of each block's on-wire data.
  `lz4f_enc_init(dst, dst_cap)` is preserved as the default
  (id 4, no checksum) and delegates to the new entry point.
- **Streaming decoder: configurable block-max.** `lz4f_dec_write`
  parses BD bits 4-6, sizes its block buffer to the declared block-max
  (64K allocated at init; grown in the BD state only when the frame
  declares larger, so the common path never re-allocs), and rejects
  reserved IDs < 4. The old `block-max-ID != 4 → -ERR_UNSUPPORTED_FORMAT`
  reject is gone.
- **Per-block checksum validation** (both decoders). The streaming
  decoder adds `LDEC_STATE_BLOCK_CHECKSUM` between block data and the
  next block size, validating xxHash32 of the buffered block before
  emitting. Batch `lz4f_decompress` parses FLG bit 4 and validates the
  trailing 4-byte checksum after each block. The old FLG-bit-4 reject
  is gone.
- New tests: round-trips at 256K (single + multi-block), 1M, 4M through
  both decoders; per-block-checksum round-trips at 64K and 256K with
  corruption-rejection checks. Suite grows to **3,861,983** assertions
  (sankoch) + 346,583 (git_object).
- New benchmarks: LZ4F block-max sweep (256K text at each of the four
  block sizes) — throughput per size + four `SIZE lz4f_bm{4,5,6,7}`
  lines. Larger block-max compresses the 256K text input from 1279 →
  1102 bytes (cross-block match locality + fewer block headers).

### Verified

- **Reference-CLI conformance.** Frames at all four block sizes (single
  and multi-block) and with per-block checksums decode byte-for-byte via
  `lz4 -dc` (reference `lz4` v1.10.0).
- Built + tested green on the pinned toolchain (6.2.14): both `.tcyr`
  suites, all fuzz harnesses, `core_smoke`, `cyrfmt --check`,
  `cyrius vet`, `cyrius distlib` (full + core).

## [2.3.2] — 2026-06-16

**cyrius pin `6.2.1` → `6.2.14` (stdlib pin sweep).** No source changes —
sankoch's `[deps]` (syscalls/string/alloc/fmt/vec/fnptr/thread/assert)
contains no carved-out modules, so it builds clean against the 6.2.14 snapshot.

### Changed

- **cyrius pin → 6.2.14.** Verified green on 6.2.14: `cyrius deps` resolves
  cleanly, both `.tcyr` suites pass (1,361,935 + 346,583 assertions), bench
  2/2, `dist/sankoch.cyr` + `dist/sankoch-core.cyr` regenerated via
  `cyrius distlib` (version-line bump only — wire format unchanged).

## [2.3.1] — 2026-06-12

**cyrius pin `6.0.1` → `6.2.1` (ecosystem-wide stdlib pin sweep).** No source
changes — sankoch's `[deps]` (syscalls/string/alloc/fmt/vec/fnptr/thread/assert)
contains no carved-out modules, so it builds clean against the 6.2.1 snapshot.

### Changed

- **cyrius pin → 6.2.1.** Verified green on 6.2.1: `cyrius deps` resolves
  cleanly, full `.tcyr` suite passes (1,361,935 assertions), bench 2/2,
  `dist/sankoch.cyr` + `dist/sankoch-core.cyr` regenerated via `cyrius distlib`.

## [2.3.0] — 2026-05-23

**True incremental decompression — closes the streaming arc opened
by 1.7.0 on the encode side.** Adds `<fmt>_dec_init / write / finish`
for DEFLATE, zlib, gzip, and LZ4F; output bytes flow into the
caller's buffer as compressed input chunks arrive, instead of
buffering the whole stream and batch-decoding at finish.
`stream.cyr` grows an incremental-mode dispatch (`stream_decompress_init_inc`)
so the same format-agnostic shell wraps both modes. Minor bump
because the new APIs are additive; legacy `stream_decompress_*`
(buffered) and the batch `*_decompress` paths are untouched and
remain fully supported. Wire format identical across the entire
SIZE matrix — all 38 reference sizes byte-for-byte unchanged from
2.2.7.

Landed as 6 bites over 2026-05-23. See git history for the
incremental development log; the per-bite CHANGELOG entries
(2.3.0-bite-1 .. -bite-6) were collapsed into this release header.

### Added — streaming-decode public API (2026-05-23)

#### DEFLATE — `deflate_dec_init / dec_write / dec_finish`
- 160-byte ctx (20 i64 slots) with hold/bits accumulator
  (zlib / libdeflate / miniz pattern). Chunk-boundary suspension
  works via a single `_ddec_fill(ctx, chunk, cp, end, n)` primitive
  that pulls bytes one at a time until enough bits are available;
  state-machine arms check `bits >= n` after fill and return
  `cp` on insufficiency without losing input.
- **15-state machine** spans all three DEFLATE block types:
  - Stored (BTYPE=00): `STORED_LEN` → `STORED_NLEN` (XOR validate,
    preserves the HIGH-01 source-bound check from 2.1.3) →
    `STORED_DATA` (byte copy directly from chunk to dst).
  - Fixed Huffman (BTYPE=01): `DECODE_SYM` → `LEN_EXTRA` →
    `DECODE_DIST` → `DIST_EXTRA` → atomic match-copy → back to
    `DECODE_SYM`.
  - Dynamic Huffman (BTYPE=10): `DYN_HLIT` → `DYN_HDIST` →
    `DYN_HCLEN` → `DYN_CL_LENS` (loop reading hclen × 3-bit code
    lengths through the cl_order permutation) → `DYN_AL_SYM`
    (decode cl symbol, branch on literal/repeat-16/17/18) →
    `DYN_AL_EXTRA` (read 2/3/7 extra bits + emit repeat into the
    all_lens workspace, back to AL_SYM). MED-01 `hlit > 286`
    reject from 2.1.3 carried over verbatim.
- **`_ddec_decode_huff`** — Huffman-decode helper that drains
  `ctx.hold` into a 4-byte stack buffer, points a stack-allocated
  32-byte br struct at it, calls the existing battle-tested
  `_huff_decode`, then advances `ctx.hold/bits` by the consumed-bit
  count. No per-call alloc.
- **Phantom-decode guard** in `_ddec_decode_huff`: the bridge is
  byte-granular, so when `ctx.bits < 8` the high pad bits of the
  partial byte are zeros that the fast table or slow path can
  accidentally walk into and "decode" a code shorter than expected.
  The helper rejects any decode that consumed past `ctx.bits` and
  treats it as need-more (caller retries with more input). Without
  this guard, byte-at-a-time feeds produced spurious EOB hits at
  chunk boundaries.
- Lazy-global workspaces (`_ddec_cl_order`, `_ddec_cl_lens`,
  `_ddec_all_lens`) carry partial dynamic trees across chunk
  boundaries — same mutex-serialized lazy-alloc pattern as the
  encoder's `_dh_ws` / `_dyn_*` slabs.
- **Contract**: `deflate_dec_write` returns bytes consumed
  (0..in_len) on success; negative is error. This is the only
  visible API contract shift from 2.2.7 (the original bite-1
  shape returned 0 on success); the wrappers needed it to split
  each chunk between DEFLATE body and trailer.

#### zlib — `zlib_dec_init / dec_write / dec_finish`
- 72-byte ctx. 4-state machine: `HEADER` (2-byte CMF+FLG; FCHECK
  modulo-31 validate per RFC 1950 §2.2; LOW-01 CINFO > 7 reject
  preserved; FDICT reject — see deferred below) → `DEFLATE`
  (forward chunks to the inner DEFLATE decoder, update incremental
  Adler-32 on emitted bytes) → `TRAILER` (4-byte big-endian
  Adler-32, validate against incremental hash) → `DONE`.
- Mutex held init → finish via the inner `deflate_dec_init` /
  `deflate_dec_finish` (same pattern as encoder side).

#### gzip — `gzip_dec_init / dec_write / dec_finish`
- 80-byte ctx. **9-state machine** covers the full RFC 1952 §2
  surface: `HDR_FIXED` (10-byte magic+CM+FLG+MTIME+XFL+OS with
  magic+CM validation and LOW-02 reserved-FLG-bit reject preserved
  from 2.1.3) → `HDR_FEXTRA_LEN` (if FLG.FEXTRA) →
  `HDR_FEXTRA_DATA` → `HDR_FNAME` (NUL-terminated, if FLG.FNAME) →
  `HDR_FCOMMENT` (NUL-terminated, if FLG.FCOMMENT) → `HDR_FHCRC`
  (2 bytes; consumed but not validated, carrying INFO-01 from
  2.1.3) → `DEFLATE` → `TRAILER` (CRC-32 + ISIZE, both LE, both
  validated against the incremental hash and inner `dp`) → `DONE`.
- `_gdec_next_hdr_state(ctx, done_mask)` walks the on-wire
  FLG-bit chain at every header sub-state transition, so adding
  / skipping optional fields is a single shared code path.

#### LZ4F — `lz4f_dec_init / dec_write / dec_finish`
- 96-byte ctx. **10-state machine**: `MAGIC` (4 bytes LE) → `FLG`
  (version validate, bit-4 block-checksum reject, bit-1 reserved
  reject) → `BD` (block-max ID = 4 / 64KB only; larger sizes
  rejected — see deferred) → optional `CONTENT_SIZE` / `DICT_ID` →
  `HC` (consumed, not validated, mirroring batch) → `BLOCK_SIZE`
  (4 bytes LE; high bit = uncompressed flag; size 0 marks
  end-mark) → `BLOCK_DATA` (accumulate into the 64KB block buffer,
  then hand to `lz4_decompress` or memcpy if uncompressed; update
  incremental xxhash32) → `CONTENT_CHECKSUM` (4 bytes LE,
  validate) → `DONE`.

#### `stream.cyr` — incremental-mode dispatch
- **`stream_decompress_init_inc(format, dst, dst_cap)`** —
  new init function that takes the output buffer up-front and
  dispatches to the appropriate `*_dec_init`. Returns a ctx in
  the new `STREAM_DECOMPRESS_INC = 2` mode. `FORMAT_LZ4` (raw
  block, no streaming decoder) returns 0; the other four formats
  forward cleanly.
- **`stream_write` extended** with INC-mode dispatch routing to
  `*_dec_write`. Existing `STREAM_COMPRESS` and legacy
  `STREAM_DECOMPRESS` (buffered) dispatch paths unchanged.
- **`stream_decompress_finish_inc(ctx)`** — finish counterpart
  for INC-mode ctxs. Mirrors `*_dec_finish`'s return contract.

### Fixed — bit-accumulator overpull in zlib/gzip wrappers
- The streaming DEFLATE decoder's `_ddec_fill` pulls full bytes
  from input even when only a few bits are needed. When the inner
  transitioned to `DDEC_STATE_DONE` mid-byte, it could have a full
  unused byte still sitting in `ctx.hold` — one byte further than
  the deflate stream actually extends. Without correction, the
  zlib/gzip wrappers would see the trailer offset shifted by 1.
  Fix: both wrappers rewind `cp` by `(ctx.bits >> 3)` when the
  inner transitions to DONE. The encoder's `bw_align` reliably
  byte-pads at finish, so the trailer always starts at the byte
  boundary after the consumed bits — making the rewind safe.

### Deferred — scoped to follow-on 2.3.x patches
- **Streaming FDICT zlib** (`flg.bit5` = 1). The streaming decoder
  rejects FDICT-bearing zlib with `-ERR_UNSUPPORTED_FORMAT` for
  now. Full FDICT support needs a `deflate_dec_init_dict` analog
  plus the dictionary feed; planned for a 2.3.x patch alongside
  multi-member gzip.
- **Concatenated gzip members** (RFC 1952 §2.2). The streaming
  decoder handles a single member only; batch `gzip_decompress`
  still handles concatenated streams as before. Multi-member
  streaming needs a per-member inner-DEFLATE reset and a
  magic-or-EOF-after-trailer state.
- **LZ4F block-max ID > 4** (256K / 1M / 4M blocks). Bite-5 fixes
  the streaming block buffer at LZ4F_BLOCK_MAX = 64KB to match
  what sankoch's encoder emits. Lifting this is roadmap item
  **2.3.1** (configurable LZ4F block-max size); once the encoder
  learns to emit larger blocks, the streaming decoder will size
  its workspace based on the parsed BD byte.
- **LZ4F per-block checksum** (FLG bit 4). Not supported in
  bite-5; sankoch's encoder doesn't emit it. Streams that set it
  return `-ERR_UNSUPPORTED_FORMAT`.

### Tests — +332,597 assertions (2026-05-23)
sankoch.tcyr 1,029,338 → **1,361,935** (+332,597). git_object.tcyr
unchanged at 346,583. **Total: 1,708,518 assertions** across the
two suites. Most of the growth comes from per-byte content-loops
on the 64KB and 128KB LZ4F round-trips in bite-5. Bite-by-bite
test additions:
- Bite 1 (stored blocks): 13 hand-crafted tests, +57 assertions —
  empty stream, single block, byte-at-a-time, multi-block,
  NLEN-mismatch, unsupported BTYPE 01/10/11, incomplete-stream,
  buffer-too-small, post-DONE no-op, mutex-release proof, empty
  round-trip via `deflate_enc_*`.
- Bite 2 (fixed Huffman): 7 round-trips (level-1 fixed-path) at
  several payload shapes including distance=1 RLE and 1KB
  chunked-16, +1,105 assertions.
- Bite 3 (dynamic Huffman): 6 round-trips (level-6 dynamic-path)
  including a sweep across levels 4-9 plus a MED-01 streaming-path
  regression, +1,342 assertions.
- Bite 4 (zlib + gzip wrappers): 15 cases including round-trips
  at L1 and L6, byte-at-a-time chunked feeds, FDICT-rejected, bad
  Adler / bad magic / reserved-FLG / bad CRC / bad ISIZE, and a
  hand-crafted gzip FNAME-field stream, +2,233 assertions.
- Bite 5 (LZ4F): 9 cases including 64K single-block, 128K
  multi-block at 256-byte chunks, uncompressed-block path,
  bad-magic, bad-version, BD-too-large reject, and bad
  content-checksum, +327,774 assertions (dominated by 64K + 2×128K
  content-loops).
- Bite 6 (dispatch): 7 cases including a round-trip through each
  of the four format dispatch paths, byte-at-a-time gzip via the
  shell, FORMAT_LZ4 reject, and three mode-mismatch error checks,
  +86 assertions.

### Verified (2026-05-23)
- `cyrius build src/lib.cyr` — OK, 0 warnings on the library path.
- `cyrius test tests/tcyr/sankoch.tcyr` — **1,361,935 / 1,361,935**
  passed.
- `cyrius test tests/tcyr/git_object.tcyr` — 346,583 unchanged.
- `cyrius fuzz` — 1,649 iterations across 12 harness functions in
  2 files, all green.
- `cyrius vet src/lib.cyr` — clean (20 deps, 0 untrusted, 0
  missing).
- `cyrius lint` × all 20 source / program / test / fuzz files —
  0 warnings each.
- `cyrfmt --check` — clean across all touched files.
- Wire-format SIZE-line gate: all 38 entries byte-for-byte
  identical to the 2.2.7 baseline. The streaming-decode arc only
  added new public surface; encoder + batch decoder are untouched.
- `dist/sankoch.cyr` regenerated to 6326 lines (was 4871 at 2.2.7;
  +1455 source lines for the streaming decode surface).
  `dist/sankoch-core.cyr` unchanged at 315 lines (kernel-safe
  profile contains only LZ4 batch decompress, which gained nothing
  in this arc).

### Source — +1455 lines across 5 files
- `src/deflate.cyr` 1676 → 2276 (+600) — bites 1/2/3 add ~600
  lines for the state machine + hold/bits primitives + bridge
  Huffman helper.
- `src/lz4.cyr` 513 → 835 (+322) — bite 5 adds the LZ4F streaming
  decoder.
- `src/gzip.cyr` 270 → 531 (+261) — bite 4 streaming gzip wrapper.
- `src/zlib.cyr` 222 → 406 (+184) — bite 4 streaming zlib wrapper.
- `src/stream.cyr` 162 → 250 (+88) — bite 6 incremental dispatch.
- All other modules unchanged.

### `[lib.core]` — unchanged
The kernel-safe profile (`dist/sankoch-core.cyr`) is bite-by-bite
untouched. Streaming decode is alloc-using (ctx + workspaces +
incremental checksum state) and stays in the full `[lib]` profile.
The kernel-safe tripwire (`programs/core_smoke.cyr`) re-validates
clean; the AGNOS initrd LZ4-decompress contract is identical to
the 2.1.2 cut.

## [2.2.7] — 2026-05-23

**P(-1) closeout against Cyrius 6.0.1 — entry door to the 2.3.0
streaming-decompression arc.** Three patch-level toolchain-tracking
releases (2.2.4 / 2.2.5 / 2.2.6) collectively jumped the Cyrius pin
two minor lines plus one major (5.7.48 → 6.0.1). This pass re-runs
the full P(-1) scaffold-hardening checklist on the post-jump state
and captures a fresh throughput baseline 2.3.0 will be measured
against. **Zero HIGH/MEDIUM/LOW findings; three INFO observations
carried forward from 2026-05-01 unchanged.** No source changes,
no API changes, no test additions — pure process release.

### Verified — full P(-1) sweep against Cyrius 6.0.1 (2026-05-23)
- **Cleanliness gates**: `cyrius build src/lib.cyr` OK (0 warnings
  on library path); `cyrius lint` × 20 files all `0 warnings`;
  `cyrfmt --check` × 20 files all clean; `cyrius vet src/lib.cyr`
  reports 20 deps, 0 untrusted, 0 missing.
- **Test sweep**: `cyrius test tests/tcyr/sankoch.tcyr` →
  **1,029,338 / 1,029,338** assertions pass.
  `cyrius test tests/tcyr/git_object.tcyr` → **346,583 / 346,583**
  pass. Total **1,375,921 assertions** — identical to the 2.2.3
  closeout baseline (no test changes since).
- **Fuzz sweep**: `cyrius fuzz` exercises all 12 harness functions
  across `fuzz/fuzz_deflate.fcyr` + `fuzz/fuzz_lz4.fcyr`. **1,649
  iterations** pass; matches the documented headline.
- **Benchmark baseline**: full `cyrius bench tests/bcyr/sankoch.bcyr`
  archived as `docs/benchmarks/2026-05-23-pre-2.3.0.md`. SIZE-line
  wire-format gate: 38 entries, byte-for-byte identical to the
  2026-05-01 snapshot. Hot-path ns/op numbers sit within ±5%
  run-to-run noise vs the 2.2.3 reference — the toolchain churn
  did not perturb codegen meaningfully on the compression hot
  path. This is the reference 2.3.0's `*_dec_*` work will be
  measured against.
- **Security re-scan**: zero `sys_*` calls in `src/` (pure-compute
  confirmed); 17 stack `var buf[N]` sites, largest is the
  documented `all_lens[4672]` in deflate.cyr; the 11
  `_sankoch_alloc` defensive sites from 2.2.1 untouched; 37 raw
  `alloc()` lazy-global / arena sites unchanged (INFO-A —
  carried).
- **2.1.3 audit fixes re-verified**: HIGH-01 (DEFLATE stored-block
  OOB, `src/deflate.cyr:385`+`:467`), MED-01 (HLIT > 286 reject,
  `src/deflate.cyr:210`), LOW-01 (zlib CINFO > 7 reject,
  `src/zlib.cyr:53`), LOW-02 (gzip reserved FLG bits,
  `src/gzip.cyr:38`) — all intact post toolchain churn.
- **Cyrius 5.7 → 6.0 stdlib API drift**: every symbol sankoch
  consumes resolves clean. The 5.10.x REAL TYPE SYSTEM + 5.11.x
  annotation arc was the only material change visible from our
  side, and the 2.2.5 patch landed the response (`: i64` on every
  public fn in `src/*.cyr`). No new dependency on `sandhi` or
  other 5.7+-introduced stdlib modules.

### Documented — three INFO observations carried forward
- **INFO-A**: 35 lazy-global alloc sites (Huffman tables, LZ77
  hash, DEFLATE workspace, etc.) still abort on first-call OOM.
  Carried from 2.2.1 / 2.2.3. Deferred — failure here would need
  error propagation through many internal callers and the
  realistic OOM victim is the per-call ctx alloc, which 2.2.1
  hardened.
- **INFO-B**: `_deflate_decompress_dict` and `_zlib_decompress_dict`
  require `dst_cap >= dict_len`. Already enforced at runtime via
  the early `if (dict_len > dst_cap) return -ERR_BUFFER_TOO_SMALL`
  check. Carried as a docstring-polish item.
- **INFO-C**: aarch64 LZ77 8-byte word-compare in
  `_lz77_find_match` uses unaligned `load64`. ARMv6+ permits it
  but some implementations pay a cycle-count penalty. Flagged for
  future investigation if aarch64 perf benchmarks ever surface
  this section as hot. No consumer signal yet.

### Documentation — refreshed (2026-05-23)
- `docs/development/roadmap.md`: header bumped 2.2.3 → 2.2.6;
  last-updated date bumped to 2026-05-20; three new ✅ entries
  recording 2.2.4 / 2.2.5 / 2.2.6 as toolchain-tracking patches;
  new 🎯 2.2.7 entry describing this P(-1) closeout; File Summary
  table refreshed to current source line counts (4,844 total;
  was 4,635); dist bundle line count 4,662 → 4,871; cyrius
  stdlib min version 5.5.22 → 6.0.1.
- `docs/audit/2026-05-23-pre-2.3.0-redux.md`: full audit doc.
- `docs/benchmarks/2026-05-23-pre-2.3.0.md`: throughput baseline.

### Process — outputs
- **Test count**: unchanged at 1,375,921 assertions (no test
  additions).
- **Cleared to open 2.3.0** — true incremental decompression
  (the streaming-decomp arc). DEFLATE state-machine suspension
  lands first per the v2.x release ladder.
- `dist/sankoch.cyr` + `dist/sankoch-core.cyr` regenerated via
  `cyrius distlib` for the version stamp; body byte-identical
  otherwise.

## [2.2.6] — 2026-05-20

### Changed

- `cyrius` pin bumped 5.11.4 → 6.0.1. Build, both tcyr suites
  (1,029,338 + 346,583 = 1,375,921 assertions), `cyrius lint`,
  `cyrius vet`, and the CI fmt sweep all clean against 6.0.1 —
  pin-drift warning gone. Stale `5.7.48` references in `README.md`,
  `docs/development/cyrius-usage.md`, and `CLAUDE.md` (carried since
  the 2.2.4 / 2.2.5 bumps) refreshed at the same time.
- **CI/release `cc5_aarch64` → `cycc_aarch64`**: Cyrius 6.0 renamed
  the cross-compiler binary; the existing aarch64 gate in
  `.github/workflows/{ci,release}.yml` was looking for the old name
  and erroring out (`cc5_aarch64 missing from Cyrius`). Local
  `cyrius build --aarch64 src/lib.cyr` confirmed clean against the
  renamed binary (`ARM aarch64` ELF emitted).
- `dist/sankoch.cyr` regenerated via `cyrius distlib` at v2.2.6.

## [2.2.5] — 2026-05-11

### Changed

- **Stdlib annotation pass**: every public fn in `src/*.cyr`
  carries a `: i64` return-type annotation. Mechanical pass
  matching cyrius's v5.11.x annotation arc; parse-only, zero
  runtime / codegen change.
- `cyrius` pin bumped 5.8.64 → 5.11.4 — required for `: i64`
  return-type syntax (v5.10.x REAL TYPE SYSTEM).
- `dist/sankoch.cyr` regenerated via `cyrius distlib` at v2.2.5
  (4824 lines). Ready for next cyrius-side fold-in slot.

## [2.2.4] — 2026-05-05

### Changed

- `cyrius` pin bumped 5.7.48 → 5.8.64 ahead of the cyrius v5.8.65
  stdlib foldin. Sankoch is on the foldin manifest; this patch is
  the prerequisite for cyrius's `[deps].sankoch.tag` to point at
  2.2.4 in the foldin slot.
- `cyrius fmt` pass applied across `src/`, `programs/`, `tests/`,
  `fuzz/` to clear pre-existing fmt drift carried since the prior
  cyrius-fmt-update.

### Verified

- `cyrius test`: **1,029,338 / 1,029,338** asserts pass against
  cyrius 5.8.64 (full deflate/gzip fixture suite).
- `cyrius fmt --check`: clean across all 20 files.
- `dist/sankoch.cyr` rebuilt: 167,378 bytes (4824 lines).

## [2.2.3] — 2026-05-01

**P(-1) closeout for the 2.2.x line.** Audit pass over the surface
touched since 2.1.3 (the previous P(-1)): dict-init paths from
2.2.0, defensive-alloc wrapping from 2.2.1, aarch64 cross-build
gate from 2.2.2. **Zero HIGH/MEDIUM/LOW findings**; three INFO
observations documented; five test-coverage gaps closed. Full
audit at `docs/audit/2026-05-01-pre-2.3.0.md`.

### Tests — +57 assertions (2026-05-01)
- `test_alloc_fail_lz4f_xxh32` — fault-inject at offset 2 (the
  xxhash32_init alloc inside `lz4f_enc_init`, after ctx +
  block_buf). Closes a coverage gap from 2.2.1 — the third
  per-call helper alloc in lz4f's path was the only one without
  an explicit fault-injection test.
- `test_alloc_fail_gzip_crc32` — fault-inject at offset 4 (the
  crc32_init alloc inside `gzip_enc_init_dict`, after deflate's
  three allocs + gzip's own ctx). Same 2.2.1 coverage gap on the
  gzip side.
- `test_enc_dict_max_len_32768` — round-trip with the largest
  legal dict (= `DEFLATE_WINDOW_SIZE`); hash-seed loop runs
  32,766 iterations. The audit-driven write of this test
  surfaced INFO-B (see audit doc): `deflate_decompress_dict`
  requires `dst_cap >= dict_len` because the decoder stages the
  dict prefix into dst before decoding payload — the original
  test had `dst_cap=64` and was misreading the
  ERR_BUFFER_TOO_SMALL return as a round-trip correctness
  failure. Production code was always correct; test fixed to
  use `alloc(65536)` and the constraint documented.
- `test_enc_dict_min_match_len_3` — round-trip at exactly
  `LZ77_MIN_MATCH`; hash-seed loop runs once (j=0).
- `test_enc_dict_below_min_match_len_2` — round-trip at
  `dict_len=2` (below min match); hash-seed loop never enters,
  but dict bytes still copy to the window and round-trip works
  via byte-level transfers.

### Documented (INFO, not blocking)
- **INFO-A**: lazy-global allocs (35 sites — Huffman tables,
  LZ77 hash, DEFLATE workspace, etc.) still abort on first-call
  OOM. Carried forward from 2.2.1; deferred because failure here
  would need error propagation through many internal callers
  and the lazy globals are init-once-per-process. Realistic OOM
  victim is the per-call ctx alloc, which 2.2.1 hardened.
- **INFO-B**: `_deflate_decompress_dict` and
  `_zlib_decompress_dict` require `dst_cap >= dict_len`. Already
  enforced at runtime via the early
  `if (dict_len > dst_cap) return -ERR_BUFFER_TOO_SMALL` check
  — surfaced as an audit observation that the constraint could
  be more prominent in docstrings. Future docs-polish item.
- **INFO-C**: aarch64 LZ77 8-byte word-compare in
  `_lz77_find_match` uses unaligned `load64`. ARMv6+ permits
  unaligned 8-byte access but some implementations take a
  cycle-count penalty vs aligned. Flagged for future
  investigation if aarch64 perf benchmarks surface this section
  as hot. No consumer signal yet.

### Process — P(-1) outputs
- **Audit document**: `docs/audit/2026-05-01-pre-2.3.0.md`
  (full finding writeups, INFO observations, decision log,
  closeout checklist).
- **Test count**: sankoch.tcyr 1,029,281 → 1,029,338 (+57).
  git_object.tcyr unchanged at 346,583. **Total: 1,375,921
  assertions across the two suites.**
- **Benchmarks**: baseline captured at audit start; no source
  changes mean post-audit numbers are identical. Hot-path code
  unchanged from 2.2.2.
- **Cleared to open 2.3.0** — true incremental decompression
  (the streaming-decomp arc).

## [2.2.2] — 2026-05-01

**aarch64 cross-build now a hard CI/release gate.** Pulled forward
from the originally-planned 2.3.3 slot to set the portability floor
before the 2.3.x streaming-decomp arc opens — every `*_dec_*`
function added in 2.3.0+ will be aarch64-clean from day one rather
than retroactively. Pure CI/release YAML work; zero source changes.

### Added — aarch64 cross-build gate (2026-05-01)
- **`.github/workflows/ci.yml`** gains a "Cross-build aarch64"
  step after the kernel-safe tripwire. Builds `src/lib.cyr`,
  `programs/core_smoke.cyr`, and every `fuzz/*.fcyr` harness with
  `cyrius build --aarch64`, then verifies each output is an
  `ARM aarch64` ELF via `file`. Hard-fails if `cc5_aarch64` is
  missing from the toolchain or if any output is not an aarch64
  ELF. Stdlib syscall-arity warnings (`warning:N: syscall arity
  mismatch`) are cosmetic at this stage — they come from
  `lib/syscalls.cyr`'s arch-divergent paths and don't fail the
  build; sankoch's own `src/` is syscall-free pure-compute, so
  the warnings never originate from this tree.
- **`.github/workflows/release.yml`** gains the same cross-build
  step and ships the resulting binary as
  `sankoch-<tag>-aarch64-linux` alongside the existing
  `sankoch-<tag>-x86_64-linux` artifact in the release archive.
  SHA256SUMS now covers `sankoch-*-linux` ELFs in addition to the
  source tarball and the two distlib bundles.
- **cc5_aarch64 packaging workaround** in both workflows' install
  step: pre-5.7.48 tarballs ship `cc5_aarch64` under `bin/` (the
  existing `bin/*` copy already picks it up), 5.7.48+ moved it to
  the tarball top-level. The new defensive `[ -f "$CYRIUS_DIR/cc5_aarch64" ] && cp ...`
  step covers both layouts (same workaround yukti and sakshi
  carry).

### Verified — local cross-build pass
- `src/lib.cyr` → `build/sankoch-aarch64` (~180 KB, ARM aarch64 ELF)
- `programs/core_smoke.cyr` → `build/core_smoke-aarch64` (~64 KB)
- `fuzz/fuzz_deflate.fcyr` → ~226 KB ELF
- `fuzz/fuzz_lz4.fcyr` → ~204 KB ELF
- All four pass `file` ELF-magic verification. Cross-build runs in
  the same time order as x86 (no significant overhead).

### Roadmap cascade
- **2.2.2** = aarch64 cross-build (was 2.3.3) — keeps the 2.3.x
  line a clean streaming-decomp arc.
- 2.3.0 = true incremental decompression (unchanged headline).
- 2.3.1 = configurable LZ4F block-max size (unchanged).
- 2.3.2 = DEFLATE throughput round 2 (unchanged).
- No 2.3.3 — aarch64 absorbed into 2.2.2.

### `[lib.core]` — unchanged
- Zero source changes. `dist/sankoch.cyr` and
  `dist/sankoch-core.cyr` re-generated only to bump the embedded
  version stamp (`v2.2.1` → `v2.2.2`). Body byte-for-byte
  identical otherwise.

**Total assertions: 1,375,864** (sankoch.tcyr + git_object.tcyr,
unchanged from 2.2.1 — no test changes needed; the cross-build
binaries are gated by ELF-magic verification, not assertion
counts).

## [2.2.1] — 2026-05-01

**Defensive `alloc()` failure handling at the streaming-encoder
entry points (INFO-01 closeout).** Pure internal hardening; no
public API change. Promoted ahead of true-incremental-decompression
(now 2.3.0) because it ships in one session and unblocks the
`*_dec_init` work to follow the same defensive pattern.

### Changed — `*_enc_init` paths now release the mutex on alloc failure (2026-05-01)
- **Every alloc inside the four streaming-encoder entry points
  is now checked and unlocked-on-failure.** Pre-2.2.1 a failed
  alloc would either null-deref on the next field store
  (`store64(0, ...)`) or silently return a corrupt ctx, in either
  case with `_sankoch_mtx` still held — wedging the entire library
  for the calling thread. Affected functions:
  `deflate_enc_init_dict`, `zlib_enc_init_dict`,
  `gzip_enc_init_dict`, `lz4f_enc_init`, plus the per-call
  helpers they invoke (`bw_init`, `adler32_init`, `crc32_init`,
  `xxhash32_init`).
- The patched pattern is uniform — `if (x == 0) { _sankoch_unlock(); return 0; }`
  immediately after each `_sankoch_alloc(...)` site that runs
  while the mutex is held. Per-call helpers (`bw_init` and the
  three checksum-state constructors) propagate alloc failure as
  a 0 return; entry points check + unlock + return 0. Callers
  treat `ctx == 0` the same as before — that's the existing
  contract — but the lock is no longer leaked.
- For `zlib_enc_init_dict` and `gzip_enc_init_dict`, the lock is
  taken inside the inner `deflate_enc_init_dict` call. If the
  outer wrapper's own alloc (zlib/gzip ctx, or the
  adler32/crc32 state) fails AFTER the inner deflate has
  succeeded and is holding the lock, the outer wrapper releases
  it before returning. This is the new path tested by
  `test_alloc_fail_zlib_ctx` / `test_alloc_fail_zlib_adler` /
  `test_alloc_fail_gzip_ctx`.

### Added — `_sankoch_alloc` wrapper + fault-injection counter (2026-05-01)
- **`_sankoch_alloc(size)`** in `src/lib.cyr` is the seam every
  alloc-bearing constructor in the patched paths funnels through.
  In production it forwards straight to the stdlib `alloc(size)`
  call; the wrapper exists so the test suite can simulate OOM
  deterministically.
- **`_sankoch_alloc_set_fail_at(n)`** sets a one-shot counter:
  the Nth subsequent `_sankoch_alloc` call (0-indexed) returns 0
  once, then the counter resets to -1 (production / never fail).
  Tests warm up the lazy globals first, then inject failure at a
  known offset and verify the entry point returns 0 + the lock
  was released (proven by a second public-API call succeeding).

### Tests — +16 assertions (2026-05-01)
- `test_alloc_fail_deflate_ctx` / `_deflate_window` /
  `_deflate_bw` — fault inject at each of deflate's three allocs
  (DENC_CTX_SIZE, DENC_WINDOW_CAP, bw_init's 40-byte ctx).
- `test_alloc_fail_zlib_ctx` / `_zlib_adler` — zlib's own ctx
  alloc (offset 3) and adler32_init alloc (offset 4) — the new
  paths where a failure happens with the lock already held by
  the inner deflate.
- `test_alloc_fail_gzip_ctx` — same pattern as zlib for gzip.
- `test_alloc_fail_lz4f_ctx` / `_lz4f_block_buf` — lz4f's ctx
  and 64KB block buffer.
- Each test asserts (a) ctx == 0 after the targeted failure and
  (b) a second call succeeds, proving the mutex was released.

### Out of scope (deferred follow-up)
- **Lazy-global init helpers** (`_huff_alloc_tables`,
  `lz77_init`, `_lz4_htab` init, `_deflate_*_lookup`, `_dh_ws`,
  `_dyn_*` workspace, `crc32_table`) still abort on OOM rather
  than propagating an error. The same defensive pattern applies
  in principle, but failure here would need error propagation
  through many internal callers — a bigger surface than INFO-01
  asked for. The 41 alloc sites in `src/` break down as: 6
  patched in 2.2.1 (the entry-point + per-call constructors
  documented above) + 35 lazy-global / arena allocs left as-is.
  In practice the lazy globals allocate exactly once per process
  and are effectively never the OOM victim — the realistic
  failure mode is the per-call ctx alloc, which is now safe.
  Tracked as a future hardening item if a consumer surfaces a
  case.

### `[lib.core]` — unchanged
- `_sankoch_alloc` lives in `src/lib.cyr` (full profile only).
  `src/types.cyr`, `src/xxhash32.cyr`, `src/lz4_decode.cyr`
  (the kernel-safe profile) are unmodified at this release.
  `dist/sankoch-core.cyr` re-validated alloc/sys/mutex-free;
  `programs/core_smoke.cyr` tripwire green.

**Total assertions: 1,375,848 → 1,375,864** (sankoch.tcyr +16,
git_object.tcyr unchanged).

## [2.2.0] — 2026-05-01

**Preset dictionary in streaming encoders.** Three new public API
entry points — `deflate_enc_init_dict`, `zlib_enc_init_dict`,
`gzip_enc_init_dict` — mirror the existing `*_decompress_dict` paths
on the encode side. Minor bump (additive surface).

### Added — preset dictionary streaming-encoder APIs (2026-05-01)
- **`deflate_enc_init_dict(level, dst, dst_cap, dict, dict_len)`** —
  starts a streaming DEFLATE encoder with `dict[0..dict_len)`
  preloaded into the LZ77 sliding window. Hash chains are seeded for
  every 3-byte position in the dictionary, so back-references inside
  subsequent input can reach into dictionary territory. The
  dictionary itself is never emitted in the stream — caller's input
  is the only thing that produces output. Decoder must invoke
  `deflate_decompress_dict` with the same dictionary to recover the
  original bytes. Constraints: `dict_len ∈ [0, 32768]`, `dict != 0`
  if `dict_len > 0`. dict_len == 0 is equivalent to `deflate_enc_init`
  (no preload). Returns ctx pointer or 0 on error.
- **`zlib_enc_init_dict(level, dst, dst_cap, dict, dict_len)`** —
  same as zlib_enc_init but emits an FDICT-bearing zlib header
  (CMF=0x78, FLG=0x20 — FCHECK=0 satisfies `(0x78*256 + 0x20) % 31 == 0`)
  followed by a 4-byte big-endian DICTID = Adler-32(dict). Decoder
  validates DICTID against the dict it's been handed, returning
  `-ERR_CHECKSUM_MISMATCH` on mismatch (covered by
  `test_zlib_enc_dict_wrong_dict_rejected`). The encoder ctx layout
  grew from 24 to 32 bytes — `+24` now stores the header length
  (2 without FDICT, 6 with) so `zlib_enc_finish` puts the trailer
  at the right offset.
- **`gzip_enc_init_dict(level, dst, dst_cap, dict, dict_len)`** —
  preloads the inner DEFLATE encoder with the dict. **CAVEAT**:
  RFC 1952 has no FDICT equivalent, so the on-wire gzip header is
  byte-identical to the non-dict variant. Standard `gunzip` cannot
  decode the resulting stream — the consumer pair must agree on
  the dictionary out-of-band. Interoperates with zlib's
  `deflateInit2(..., 31, ...) + deflateSetDictionary` gzip-mode
  streams; testable in-tree by stripping the 10-byte gzip header
  and 8-byte trailer and feeding the inner DEFLATE to
  `deflate_decompress_dict` (see `test_gzip_enc_dict_roundtrip`).
  CRC-32 / ISIZE in the trailer cover only caller input bytes
  (the dict is not part of decompressed output).

### Changed — internal refactor (2026-05-01)
- **`deflate_enc_init` is now a thin shim over
  `deflate_enc_init_dict(level, dst, dst_cap, 0, 0)`.** Same for
  `zlib_enc_init` (calls `zlib_enc_init_dict(..., 0, 0)`) and
  `gzip_enc_init` (calls `gzip_enc_init_dict(..., 0, 0)`). The
  no-dict path is byte-identical to pre-2.2.0 — every existing
  assertion passes byte-for-byte (1,028,629 → 1,029,265 only from
  the new dict-path tests).
- Dict-validation errors return `0` (no ctx) **before** taking
  `_sankoch_mtx` — so a caller that passes a bogus `dict_len` no
  longer leaks the lock. The 2.2.2-scheduled defensive alloc-failure
  handling (INFO-01 from the 2026-04-19-pre-2.0.0 audit) still
  applies to the post-lock alloc path; this is a partial early
  improvement, not a substitute.

### Tests — +636 assertions (2026-05-01)
- `test_deflate_enc_dict_roundtrip` — round-trip via
  `deflate_decompress_dict`, byte-equal output.
- `test_deflate_enc_dict_levels` — same round-trip across levels
  1, 3, 6, 9 (covers fixed/dynamic and shallow/deep chain paths).
- `test_zlib_enc_dict_roundtrip` — verifies CMF/FLG/DICTID bytes
  in the on-wire header, then full round-trip via
  `zlib_decompress_dict`.
- `test_zlib_enc_dict_wrong_dict_rejected` — DICTID mismatch
  returns negative error.
- `test_gzip_enc_dict_roundtrip` — gzip header byte-identical to
  non-dict; inner DEFLATE round-trips via `deflate_decompress_dict`.
- `test_enc_dict_invalid_args` — `dict_len > 32768`, negative
  `dict_len`, null dict + non-zero len all return 0 across all
  three encoder families.
- `test_enc_dict_zero_len_equals_no_dict` — `dict_len == 0`
  produces a stream that round-trips via the non-dict
  `deflate_decompress`.

**Total assertions: 1,375,212 → 1,375,848** (sankoch.tcyr +636,
git_object.tcyr unchanged).

### `[lib.core]` — unchanged
- The kernel-safe profile bundle (`dist/sankoch-core.cyr`) is
  untouched at this release: dict-init code lives in
  `src/deflate.cyr` / `src/zlib.cyr` / `src/gzip.cyr`, none of
  which are part of `[lib.core]`. The kernel-safe tripwire
  (`programs/core_smoke.cyr`) re-validated clean.

## [2.1.3] — 2026-05-01

**P(-1) scaffold-hardening pass — closeout for the 2.1.x line, entry
door to the 2.2.x feature ladder.** Four parser-side findings fixed
(one HIGH, one MEDIUM, two LOW), four targeted regression tests
added, full audit at `docs/audit/2026-05-01-pre-2.2.0.md`. No public
API change; wire-format identical (every existing assertion passes
byte-for-byte). The `[lib.core]` kernel-safe profile re-validated
clean (zero alloc / sys / mutex references).

### Security — HIGH-01 fixed (2026-05-01)
- **DEFLATE stored-block raw-byte copy now bounds-checks against
  the bitreader's source length** before walking. Pre-2.1.3, a
  malformed input with `BFINAL=1`, `BTYPE=00`, valid `LEN^NLEN`
  one's-complement, and `LEN > (dlen - bpos)` would copy up to
  65,535 bytes past the source buffer. The direct-load path
  (`var data = load64(br); var bpos = load64(br + 8); … load8(data + bpos)`)
  bypassed `br_read`'s `bpos < dlen` check, so the existing valid-
  input bound (`dp + len > dst_cap`) only protected the destination.
  Adjacent process memory could leak through the decompressed
  output, or the load could fault if the source buffer ended at
  a page boundary. Reachable from `deflate_decompress`,
  `zlib_decompress`, `gzip_decompress`, and the streaming
  decompress wrapper. Fix: re-assert
  `bpos + len <= load64(br + 24)` immediately before the copy in
  both `_deflate_decompress_inner` and
  `_deflate_decompress_dict_inner`. Regression test:
  `test_err_deflate_stored_oob` — 5-byte stream, LEN=100, valid
  NLEN, expects negative error.

### Security — MEDIUM-01 fixed (2026-05-01)
- **DEFLATE dynamic-block parser caps HLIT at 286** per RFC 1951
  §3.2.7. The 5-bit HLIT field encodes 0..31 → count 257..288;
  the spec marks 287 and 288 as invalid. No exploit
  (the `all_lens[4672]` workspace has slack to absorb 320 entries),
  but the spec-invalid stream slipping through is the kind of
  thing that promotes a future correctness bug into a security one.
  Fix: `if (hlit > 286) return -ERR_CORRUPT_DATA;` immediately
  after the `+ 257` adjustment. HDIST and HCLEN don't share this
  problem — both have full-range encodings — and the patched code
  comments call this out so a mirror check doesn't get added by
  mistake. Regression test: `test_err_deflate_hlit_overflow`.

### Security — LOW fixes (2026-05-01)
- **LOW-01: zlib CINFO ≤ 7 enforced.** RFC 1950 §2.2 forbids
  CINFO > 7 (window > 32K). Pre-2.1.3 the parser checked CM but not
  CINFO; sankoch's 32K-fixed DEFLATE silently ignored oversized
  window claims. Fix: `if (((cmf >> 4) & 15) > 7) return -ERR_UNSUPPORTED_FORMAT;`
  in `_zlib_decompress_dict_inner`. Regression test:
  `test_err_zlib_cinfo_overflow`.
- **LOW-02: gzip reserved FLG bits 5-7 rejected.** RFC 1952 §2.3.1.2:
  "If any reserved bit is non-zero, a compliant decompressor must
  give an error." Fix: `if ((flg & 224) != 0) return -ERR_CORRUPT_DATA;`
  in `_gzip_decompress_member`. Regression test:
  `test_err_gzip_reserved_flg`.

### Backlogged — INFO-01
- **gzip FHCRC value not verified** when FHCRC bit is set. RFC 1952
  marks verification as a SHOULD; reference gunzip didn't enforce
  until 1.5+ and several modern impls (libdeflate, miniz, Go's
  `compress/gzip`) skip the CRC16 entirely. Implementing CRC16-IBM
  (polynomial 0xA001) is ~30 LoC; defer until a consumer actually
  generates FHCRC-bearing streams that mutate in transit.

### Process — P(-1) outputs
- **Audit document**: `docs/audit/2026-05-01-pre-2.2.0.md` (full
  finding writeups, fix rationale, test coverage, decision log).
- **Test count**: 1,028,625 → 1,028,629 (+4 audit-regression
  tests). git_object suite unchanged at 346,583. **Total: 1,375,212
  assertions across the two suites.**
- **Benchmarks**: pre/post comparison shows every patched check
  sits on a cold or error branch — hot-path deltas across the 25
  timed cases land within ±5% run-to-run noise. No regression.
- **`[lib.core]` re-validated**: `dist/sankoch-core.cyr` stays
  alloc/sys/mutex-free; kernel-safe tripwire
  (`programs/core_smoke.cyr`) green.

## [2.1.2] — 2026-05-01

**Multi-profile distlib — kernel-safe LZ4 decompress.** New
`[lib.core]` profile produces `dist/sankoch-core.cyr` (~300 lines,
10 KB) for AGNOS initrd consumption. Pure-compute LZ4 block + frame
decompress with zero alloc, zero syscalls, zero mutex. No public
API change in the full-`[lib]` profile; the extraction is file-level
only and source behavior is identical (1,375,208 assertions byte-
for-byte unchanged across the regression sweep).

### Added — kernel-safe distlib profile (2026-05-01)
- **`[lib.core]` profile in `cyrius.cyml`** lists three modules:
  `src/types.cyr`, `src/xxhash32.cyr`, `src/lz4_decode.cyr`.
  Mirrors yukti's `[lib.core]` pattern. Bundle ships as
  `dist/sankoch-core.cyr` (300 lines vs the full bundle's 4,615)
  and contains zero `alloc()`, `_sankoch_lock/unlock`, or `sys_*`
  references — verified by `grep -nE 'alloc\(|sys_|_sankoch_lock|mutex_'`
  on the bundle.
- **`src/xxhash32.cyr`** (new file, ~95 lines) — extracted batch
  xxHash32 (`xxhash32`, `_xxh32_round`, `_xxh32_rotl`, `XXH32`
  enum) from `src/checksum.cyr`. Alloc-using incremental state
  APIs (`xxhash32_init`/`_update`/`_final`) stay in checksum.cyr.
- **`src/lz4_decode.cyr`** (new file, ~165 lines) — extracted
  `lz4_decompress` and `lz4f_decompress` from `src/lz4.cyr`. The
  `LZ4F` enum (LZ4F_MAGIC, LZ4F_VERSION, LZ4F_BLOCK_MAX) moved
  here too so both halves see the constants through the include
  chain ordering.
- **`programs/core_smoke.cyr`** (new file, ~110 lines) — link-only
  invariant check. Includes ONLY the three kernel-safe modules,
  exercises `xxhash32` on three known vectors and `lz4_decompress`
  on a hand-crafted "Hello" fixture. Builds + runs in CI as the
  "Kernel-safe tripwire" gate; non-zero exit = something
  alloc/syscall-using leaked into the core subset.

### Changed — CI/release gates
- **`.github/workflows/ci.yml`** regenerates both bundles
  (`cyrius distlib && cyrius distlib core`) and fails on drift
  for either. Lint + `fmt --check` sweeps now include
  `programs/*.cyr`. New "Kernel-safe tripwire" step builds and
  runs `programs/core_smoke.cyr` after the main build.
- **`.github/workflows/release.yml`** regenerates both bundles,
  runs the kernel-safe tripwire, and ships
  `sankoch-<tag>-core.cyr` alongside `sankoch-<tag>.cyr` in the
  release archive (the existing `sankoch-*.cyr` upload glob
  matches both).

### Deferred — kernel-safe LZ4 *compress*
- The encoder's match-finder hash table is heap-allocated
  (`_lz4_htab = alloc(32768)`) and would need a caller-provided
  workspace refactor to be kernel-safe. AGNOS initrd is built
  userland-side (the kernel only decompresses), so the heap-using
  encoder stays in the full-`[lib]` profile. Revisit when a
  kernel-side compressor consumer appears — see the v2.x ladder
  in `docs/development/roadmap.md`.

## [2.1.1] — 2026-05-01

**Toolchain bump to Cyrius 5.7.48 (was 5.6.42).** Patch release —
zero source changes, wire-format identical, public API unchanged.

### Changed — toolchain pin to Cyrius 5.7.48 (2026-05-01)
- **`cyrius.cyml` pin updated to `cyrius = "5.7.48"`** (was 5.6.42).
  Skips the 5.7.0 stdlib refresh that introduced `sandhi` (HTTP /
  service-boundary stdlib) — sankoch's stdlib surface (`syscalls`,
  `string`, `alloc`, `fmt`, `vec`, `fnptr`, `thread`, `assert`) is
  unchanged across the jump and the modules involved did not gain
  any breaking API in the 5.6.x → 5.7.x transition. Full regression
  sweep on 5.7.48 is green: 1,028,625 + 346,583 = 1,375,208
  assertions; 1,649 fuzz iterations across 6 harnesses; lint clean;
  `cyrius fmt --check` clean across `src/`, `tests/tcyr/`,
  `tests/bcyr/`, `fuzz/`; distlib in sync (4574 lines, header
  bumped to v2.1.1). CI reads the toolchain pin from the manifest,
  so no workflow-yaml edits beyond the comment refresh.
- **Toolchain version sweep**: `CLAUDE.md`, `README.md`,
  `docs/development/cyrius-usage.md`, `docs/development/roadmap.md`,
  and `.github/workflows/ci.yml` reference 5.7.48. Historical entries
  in CHANGELOG and archived issue notes left as-is — they describe
  toolchain state at the time of those releases.

### Notes — yukti / sakshi CI parity
- The 5.7.x line shipped a packaging change at 5.7.48 that moved
  `cc5_aarch64` from `bin/` to the tarball top-level. Yukti's and
  sakshi's CI workflows added a defensive `[ -f "$CYRIUS_DIR/cc5_aarch64" ]`
  copy step to cover both layouts. Sankoch CI does **not** invoke
  `cc5_aarch64` — the library is built x86_64-only in CI and is
  arch-portable by virtue of being pure compression with no syscalls
  in `src/` (the security scan asserts this). No CI change required;
  if a future release adds an aarch64 cross-build lane, port the
  yukti pattern verbatim.
- Release tag policy unchanged: bare semver only (`2.1.1`, not
  `v2.1.1`). Yukti/vidya accept both shapes; sankoch does not — see
  CLAUDE.md "Do not add `v` prefix to version tags".

## [2.1.0] — 2026-04-25

**Toolchain refresh + DEFLATE compress perf — three stacked wins on
the throughput investigation surfaced by sit v0.6.4: pre-reversed
dynamic Huffman codes, 8-byte word-compare match extension, and
ring-buffer (absolute-position) match-finder. Plus a doc staleness
sweep aligning all live docs to current source/test/fuzz/distlib
counts. No public API change; wire-format identical (all SIZE lines
byte-for-byte unchanged across the bench matrix).**

### Optimized — ring-buffer match-finder, O(1) slide (2026-04-25)
- **`lz77_rebase` no longer walks the 65,536-entry hash table on every
  window slide.** The streaming encoder used to subtract `delta` from
  each entry in `_lz77_head` and `_lz77_prev` after sliding the window
  buffer — ~22% of streaming compress time on 128K text.

  Fix: hash table now stores ABSOLUTE stream-byte positions instead of
  window-relative ones. `_lz77_window_base` tracks the absolute byte
  offset of `window[0]`, advanced by O(1) on each slide. Stale entries
  (from before the most recent slide) are rejected lazily inside
  `_lz77_find_match` via a single extra `chain < base` check per chain
  iteration — no batch walk. Boundary safety: the new check guarantees
  `chain - base >= 0` before any byte access via the chain offset.

  Batch compress paths (`deflate_compress_*` etc.) never advance
  `_lz77_window_base` — `lz77_init` resets it to 0 — so abs_pos == win_pos
  in batch mode and behavior is unchanged. SIZE lines byte-for-byte
  identical to the previous baseline across the full bench matrix
  (1K/4K/16K/64K/128K/256K text + zeros + rand, DEFLATE/zlib/gzip,
  levels 1/3/6/9, batch + streaming).

### Metrics — streaming compress (50 iters/op, best of 3 stable runs)
- `stream deflate L1 text 128K`: 2,670,557 → 2,372,713 ns/op (**−11.2%**)
- `stream deflate L6 text 128K`: 2,724,857 → 2,385,036 ns/op (**−12.5%**)
- `stream zlib L6 text 128K`:    2,914,542 → 2,615,973 ns/op (**−10.2%**)
- `stream gzip L6 text 128K`:    3,087,046 → 2,756,579 ns/op (**−10.7%**)
- `deflate L6 text 4K` (batch):  157,672 → 155,884 ns/op (flat — batch
  path keeps window_base=0, no behavior change)

### Combined (all three Unreleased perf wins) vs pre-Unreleased baseline
- `stream zlib L6 text 128K` end-to-end ~−17-20% (bit-reverse + 8-byte
  match + ring-buffer stack)
- `deflate c rand 4K`: −16.2% (entirely from bit-reverse — random has
  no long matches and no window slides)
- `deflate L6 text 4K`: −9.7% (bit-reverse + 8-byte match — batch
  doesn't slide so ring-buffer doesn't apply)

### Roadmap
- Closes the **ring-buffer LZ77 match-finder** v2.x candidate. The
  rebase-walk-on-slide cost is now O(1) instead of O(HASH_SIZE).

**Prior wins on the same throughput investigation, still in this
Unreleased section:** pre-reversed dynamic Huffman codes (lower in this
section), 8-byte word-compare match extension (lower in this section).

### Changed — toolchain bump to Cyrius 5.6.42 (2026-04-25)
- **`cyrius.cyml` pin updated to `cyrius = "5.6.42"`** (was 5.6.34).
  No source changes required — sankoch's stdlib surface (`syscalls`,
  `string`, `alloc`, `fmt`, `vec`, `fnptr`, `thread`, `assert`) has the
  same public API across the jump. Full regression sweep on 5.6.42 is
  green: 1,028,625 + 346,583 = 1,375,208 assertions; 1,649 fuzz
  iterations across 6 harnesses; lint clean; `cyrius fmt --check`
  clean across `src/`, `tests/tcyr/`, `tests/bcyr/`, `fuzz/`; distlib
  in sync. CI reads the toolchain pin from the manifest, so no
  workflow-yaml edits beyond the comment refresh.
- **Toolchain version sweep**: `CLAUDE.md`, `README.md`,
  `docs/development/cyrius-usage.md`, and `.github/workflows/ci.yml`
  reference 5.6.42. Historical entries in CHANGELOG and archived issue
  notes left as-is — they describe toolchain state at the time of
  those releases.

### Docs — stale-data sweep (2026-04-25)
- **Source / test / fuzz / distlib counts updated to current truth**
  in `CLAUDE.md` (Current State block + bench-command comments),
  `README.md` (Architecture table + summary line + bench-command
  comments), `docs/development/roadmap.md` (File Summary table re-headed
  "current — 2.1.0", with current line
  counts and assertion totals), and `docs/development/cyrius-usage.md`
  (test command comment for `git_object.tcyr`). Previous figures still
  pointed at the v2.0.0 cut: 4,369 source lines, 1,028,759 assertions,
  1,564 fuzz iterations, 4,351 distlib lines. Current truth post-2.0.3
  + Unreleased perf wins: **4,574** source lines across 12 modules,
  **1,375,208** assertions (the git_object suite grew 134 → 13,929 →
  346,583 across the 2.0.2 / 2.0.3 cl-tree depth-cap regression
  fixtures), **1,649** fuzz iterations across 6 harnesses,
  **4,597**-line distlib bundle.
- **Status / distribution lines refreshed** in `CLAUDE.md`:
  "Status: 2.0.0 — shipping" → "Status: 2.0.3 (stable)";
  "Distribution: 2.0.0 lands in the next Cyrius lang release" →
  notes that 2.0.2 landed in cyrius 5.6.34, 2.0.3 in 5.6.35, and
  the current 5.6.42 toolchain ships 2.0.3 as `lib/sankoch.cyr`.
- **Roadmap header**: "Status: Stable (v2.0.0)" → "Status: Stable
  (v2.0.3)" (already done in the perf-fix commit).
- Historical CHANGELOG entries, audit reports, and archived issue
  docs intentionally left unchanged — they describe state at the
  time of writing and shouldn't be retconned.

### Optimized — 8-byte match extension in `_lz77_find_match` (2026-04-25)
- **Inner match-extend loop now compares 8 bytes per iteration via
  `load64` + word XOR, falling back to byte-at-a-time for the last
  partial chunk.** Previously every match-extension step was four ops
  per byte (two `load8`, compare, increment); now full 8-byte chunks
  cost the same four ops. ~8× speedup on the all-matching path; tail
  identical to the old code so wire-format and match length are
  unchanged. Boundary safety: the 8-byte loop only fires while
  `mlen + 8 <= max_len`, and `max_len = min(LZ77_MAX_MATCH, src_len -
  pos)` with `chain < pos`, so both `src + chain + mlen + 7` and
  `src + pos + mlen + 7` stay strictly inside the input buffer.

  Stacks cleanly on top of the bit-reversal fix below (independent
  hot-path component — Huffman emit vs LZ77 match-finder).

### Optimized — dynamic Huffman codes pre-reversed at build (2026-04-25)
- **Pre-reverse dynamic Huffman codes once at build time, not on every
  emit.** `_deflate_write_syms_dynamic` and `_deflate_write_dynamic_header`
  previously ran a per-bit reversal loop inside the per-symbol emit
  loop — every literal paid one, every match paid two (length code +
  distance code), every cl-stream symbol in the header paid one. The
  fixed-Huffman encoder already pre-reversed at build (`_deflate_build_enc_fixed`,
  matching `_deflate_build_enc_dist`); the dynamic path inherited
  unreversed canonical codes from `_huff_build` (which the decoder
  slow-path comparison still needs) and reversed on the fly.

  Fix: new `huff_build_enc_codes(lengths, num_symbols, out_codes_rev)`
  in `src/huffman.cyr` produces canonical codes pre-reversed for
  LSB-first emission. Three call sites in `src/deflate.cyr`
  (`_deflate_write_dynamic_header` cl-codes build, `_dyn_flush_subblock`
  litlen + dist code build) switch from `_huff_build` to the new
  helper. The three per-symbol reverse loops in
  `_deflate_write_syms_dynamic` and the cl-emit loop in
  `_deflate_write_dynamic_header` are gone — emit is one `bw_write` per
  code with a single load.

  Decoder paths untouched (still call `_huff_build`, `out_codes` stays
  unreversed for the slow-path acc-vs-code comparison in `_huff_decode`).

  Wire-format identical: all SIZE lines byte-for-byte unchanged across
  the bench matrix (1K/4K/16K/64K/128K/256K text + zeros + rand,
  DEFLATE/zlib/gzip/LZ4/LZ4F, levels 1/3/6/9, batch + streaming).
  Full regression suite (1,028,625 + 346,583 = 1,375,208 assertions),
  fuzz harnesses (1,564 round-trips across both files), and reference-CLI
  byte-equality tests stay green.

### Combined metrics vs pre-Unreleased baseline (50 iters/op)
- `deflate c rand 4K`: 511,901 → 428,786 ns/op (**−16.2%** — almost
  entirely from the bit-reverse fix; random has near-zero long matches)
- `deflate L6 text 4K`: 172,649 → 157,672 ns/op (**−8.7%** — both
  fixes contribute roughly evenly)
- `zlib c text 4K`: 179,226 → 165,366 ns/op (−7.7%)
- `deflate c text 4K`: 170,824 → 159,415 ns/op (−6.7%)
- `stream zlib L6 text 128K`: ~3.14 ms → ~2.91 ms (−7.1% — closest
  bench in the matrix to sit's 1MB workload shape)
- `stream gzip L6 text 128K`: ~3.31 ms → ~3.09 ms (−6.7%)
- `deflate L3 text 4K`: 162,330 → 156,273 ns/op (−3.7% — fixed-Huffman
  path benefits from the 8-byte match extend; bit-reverse fix doesn't
  apply to fixed path which was already pre-reversed)
- Decoder path: noise (untouched by both fixes)
- LZ4 / LZ4F: untouched (separate match-finder); within bench noise

### Roadmap
- Two foundational items on the **DEFLATE compress/decompress
  throughput investigation** (sit v0.6.4 perf review). Lower constant
  factor, no algorithm-shape change, wire-format identical.
- Still ahead, in roughly the order they're worth doing: `good_length`
  early-exit in the level-6+ chain walk (zlib's strategy: stop chasing
  the chain once the current best is already long enough); ring-buffer
  match-finder (drops `lz77_rebase` cost in streaming); PCLMULQDQ
  CRC-32 (already deferred separately).



### Optimized
- **Pre-reverse dynamic Huffman codes once at build time, not on every
  emit.** `_deflate_write_syms_dynamic` and `_deflate_write_dynamic_header`
  previously ran a per-bit reversal loop inside the per-symbol emit
  loop — every literal paid one, every match paid two (length code +
  distance code), every cl-stream symbol in the header paid one. The
  fixed-Huffman encoder already pre-reversed at build (`_deflate_build_enc_fixed`,
  matching `_deflate_build_enc_dist`); the dynamic path inherited
  unreversed canonical codes from `_huff_build` (which the decoder
  slow-path comparison still needs) and reversed on the fly.

  Fix: new `huff_build_enc_codes(lengths, num_symbols, out_codes_rev)`
  in `src/huffman.cyr` produces canonical codes pre-reversed for
  LSB-first emission. Three call sites in `src/deflate.cyr`
  (`_deflate_write_dynamic_header` cl-codes build, `_dyn_flush_subblock`
  litlen + dist code build) switch from `_huff_build` to the new
  helper. The three per-symbol reverse loops in
  `_deflate_write_syms_dynamic` and the cl-emit loop in
  `_deflate_write_dynamic_header` are gone — emit is one `bw_write` per
  code with a single load.

  Decoder paths untouched (still call `_huff_build`, `out_codes` stays
  unreversed for the slow-path acc-vs-code comparison in `_huff_decode`).

  Wire-format identical: all SIZE lines byte-for-byte unchanged across
  the bench matrix (1K/4K/16K/64K/128K/256K text + zeros + rand,
  DEFLATE/zlib/gzip/LZ4/LZ4F, levels 1/3/6/9, batch + streaming).
  Full regression suite (1,028,625 + 346,583 = 1,375,208 assertions),
  fuzz harnesses (1,564 round-trips across both files), and reference-CLI
  byte-equality tests stay green.

### Metrics (50 iters/op, 4KB text where not noted)
- `deflate c rand 4K`: 511,901 → 414,962 ns/op (**−19.0%** —
  literal-heavy input, no LZ77 matches eating the budget, so the
  reverse-loop savings dominate)
- `zlib c text 4K`: 179,226 → 167,443 ns/op (−6.6%)
- `zlib L9 text 4K`: 176,564 → 165,386 ns/op (−6.3%)
- `deflate L6 text 4K`: 172,649 → 166,064 ns/op (−3.8%)
- `gzip c text 4K`: 185,897 → 180,954 ns/op (−2.7%)
- `deflate L1 text 4K`: 152,265 → 152,011 ns/op (noise — fixed-Huffman
  path was already pre-reversed)
- Decoder path: untouched, throughput within noise (`deflate d text 4K`
  15,760 → 16,113 — change is decoder-side noise, not a regression)

### Roadmap
- Down-payment on the **DEFLATE compress/decompress throughput
  investigation** roadmap item (surfaced by sit v0.6.4 perf review).
  Foundational: lower constant factor without changing algorithm shape.
  The bigger structural wins still ahead — 8-byte match extension in
  `_lz77_find_match`, `good_length` chain early-exit at level ≥ 6,
  ring-buffer match-finder — each lands in its own change.

## [2.0.3] — 2026-04-24

**Critical fix to the 2.0.2 fix: code-length redistribution loop now
terminates on Kraft-sum, not on overflow-leaf-count.**

### Fixed
- **`zlib_compress` (and `deflate_compress` / `gzip_compress` at level
  ≥ 4) still produced non-decodable output for inputs whose cl-tree
  natural Huffman depth landed at `max_bits+2` or deeper.**
  Filed in `docs/development/issues/archived/2026-04-24-zlib-compress-2.0.2-partial-fix-2-remaining-inputs.md`.
  The 2.0.2 fix landed `_huff_redistribute` to cap code lengths at
  `max_bits` while preserving the Kraft inequality, but used zlib's
  `gen_bitlen` shortcut: `overflow -= 2` per iteration, looping until
  overflow == 0. That count-based termination is correct only when
  every overflow leaf came from depth `max_bits+1`. When the natural
  Huffman tree had any leaf at depth `max_bits+2` or deeper (e.g. on
  inputs with very skewed cl symbol frequencies — typical of larger
  sit tree objects with many singleton repeat-codes interleaved with
  one or two super-common code lengths), the loop ended one or more
  iterations short and left the cl tree silently over-subscribed. For
  the 1504-byte repro, post-redistribution Kraft was 33024 vs target
  32768 — off by exactly `2^(15-7) = 256`, one missed iteration. The
  encoder built a malformed code table from those lengths; the
  resulting bit-stream couldn't be decoded by either sankoch's own
  decoder (`-ERR_INVALID_HUFFMAN`) or reference Python `zlib.decompress`
  (`Error -3 invalid code lengths set`). 51/53 sit tree objects from
  the 100-commit fixture round-tripped on 2.0.2; 2 still failed.

  Fix: `_huff_redistribute` now loops on the Kraft sum directly,
  exiting when `kraft == 2^15`. Each iteration removes a known fixed
  amount (`2^(15-max_bits)`), and starting from a complete natural
  Huffman tree the post-clip Kraft is always a multiple of that
  amount, so the loop terminates with Kraft exactly at the target —
  unconditionally, regardless of how deep the over-long leaves were.
  The redistribution comment block now flags zlib's `overflow -= 2`
  shortcut as the trap and documents why Kraft-sum termination is
  correct.

  Wire-format identical for inputs that already round-tripped on
  2.0.2 (the post-clip Kraft already hit target, redistribution loop
  ran zero times). The 751-byte parent-issue input still produces a
  660-byte zlib stream byte-identically; the 1504/2021-byte
  partial-fix-issue inputs go from non-decodable to decodable at
  1243/1634 bytes (one extra byte each vs the broken 2.0.2 output —
  the cost of a correct cl tree).

### Added
- `tests/tcyr/git_object.tcyr`: four new regressions targeting the
  bug class. `test_tree_1504_byte_regression` /
  `test_tree_2021_byte_regression` use the synthetic `_build_tree`
  helper (now upgraded with a seed parameter and a stronger LCG hash
  generator) to cover the 32-entry / 43-entry shapes through every
  dynamic level. `test_real_sit_tree_1504_byte_roundtrip` /
  `test_real_sit_tree_2021_byte_roundtrip` are the load-bearing
  tests: they read the actual sit tree-object bytes from the
  archived issue repros via a small `_read_repro` syscall helper
  (SYS_OPEN + SYS_READ + SYS_CLOSE) and verify roundtrip across all
  six dynamic levels. The synthetic `_build_tree` does NOT trigger
  the natural-depth-≥-max_bits+2 case across any seed sweep we
  tried — only real SHA-hash-derived byte distributions push the
  cl tree past the count-based redistribution's blind spot, so the
  file-read tests are the regression that would actually fail on
  pre-2.0.3 code (verified by stashing the fix and re-running:
  every byte-match assertion in those two tests fires). Suite now
  reports 346,583 assertions (was 13,929 on 2.0.2).
- `tests/tcyr/git_object.tcyr` `test_tree_shape_sweep_roundtrip`
  extended from 1..20 entries with one seed to 1..50 entries with
  five seeds — broad coverage even though the synthetic builder
  doesn't reach the deep-natural-depth case in the file-read tests.
- `fuzz/fuzz_deflate.fcyr` `tree_entries` table now includes 32 and
  43 (the 1504/2021-byte points), 75, and continues to 120 — 55
  outer iterations × 9 levels = 495 sub-runs of the tree-shape
  round-trip harness per fuzz invocation.

### Downstream
- **cyrius v5.6.35** can now bump its `cyrius.cyml` `[release]` pin
  from sankoch 2.0.1 to 2.0.3 and flip
  `tests/regression-sit-status.sh`'s `CYRIUS_V5635_SHIPPED` guard.
- **sit**: post-commit `read_object` verify in `cmd_commit` is now
  safe to revert; `fl_alloc` swap stays as the cyrius v5.6.34
  alloc-grow mitigation.

## [2.0.2] — 2026-04-24

**Critical fix: dynamic-block code-length-tree depth limit.**

### Fixed
- **`zlib_compress` (and `deflate_compress` / `gzip_compress` at level
  ≥ 4) produced non-decodable output for inputs whose code-length
  alphabet's natural Huffman depth exceeded 7 bits.**
  Reported in `docs/development/issues/2026-04-24-zlib-compress-non-roundtrip-on-tree-shaped-input.md`,
  discovered during cyrius v5.6.35 triage of sit's "symptom 2 of 2"
  memory anomaly at scale. Affected any input whose dynamic block
  produced a cl-symbol frequency distribution skewed enough that the
  natural Huffman tree on the 19-symbol code-length alphabet pushed
  past 7 bits (e.g. one super-common literal-length plus rare
  repeat-codes). Tree-shaped inputs from sit's git tree objects hit
  this regularly: 50/300 tree objects in sit's 100-commit fixture
  failed standalone roundtrip; the smallest minimal repro was a
  484-byte truncation of one such tree. RFC 1951 §3.2.7 caps the
  code-length alphabet at 7 bits, and sankoch wrote each cl_len in a
  3-bit header field — so any cl length above 7 aliased on the
  decoder side, leaving the cl tree malformed and the lit/dist
  length stream unreadable. Reference Python `zlib.decompress`
  rejected the same byte streams with `Error -3 invalid code lengths
  set`, matching sankoch's own decoder return of `-ERR_INVALID_HUFFMAN`.

  The root cause was `huff_compute_lengths` having no notion of an
  alphabet-specific max code length: it clamped each individual leaf
  at `HUFF_MAX_BITS=15`, but that clamp (a) could not enforce the
  cl alphabet's 7-bit ceiling, and (b) when it did fire on the lit/
  dist alphabets at depth > 15, broke the Kraft inequality by
  shortening individual codes without redistributing the saved code
  space.

  Fix: `huff_compute_lengths` gains a fifth `max_bits` parameter, the
  buggy individual-leaf clamp is removed, and a new helper
  `_huff_redistribute` runs after the natural-Huffman DFS. It applies
  zlib's iterative `gen_bitlen` algorithm (zlib `trees.c`): every
  leaf at depth > max_bits is moved down to max_bits, then pairs of
  overflow leaves are paid for by extending one shorter leaf by one
  bit (its slot splits into two at length+1) — keeping
  Σ 2^(-len_i) = 1 exactly. Lengths are then reassigned to symbols
  in descending-frequency order so optimality up to the cap is
  preserved. Three call sites updated: cl tree at max_bits=7,
  litlen and dist trees at max_bits=15.

  Wire-format identical for inputs that already roundtripped on
  2.0.1 (the natural-depth tree was already ≤ max_bits, so the
  redistribution short-circuits). Compression ratio unchanged: the
  751-byte issue input still produces a 660-byte zlib stream at
  level 6, byte-identical to what 2.0.1 emitted — but now decodable.

### Added
- `tests/tcyr/git_object.tcyr`: three regressions covering the bug
  class — `test_tree_shape_sweep_roundtrip` sweeps 1..20 entries
  through the failing band; `test_tree_751_byte_regression` pins the
  exact 16-entry tree from the issue (asserts `n == 751`);
  `test_tree_513_byte_regression` cycles every level on an 11-entry
  tree from inside the 507-520 failing band. The `_build_tree`
  helper produces deterministic tree objects mimicking real git
  format. Suite now reports 13929 assertions (was 134).
- `fuzz/fuzz_deflate.fcyr`: two new harnesses targeting the bug
  class. `fuzz_tree_shape_roundtrip` (5 seeds × 8 entry counts × 9
  levels) generates random-but-tree-shaped inputs straddling the
  484/507/520/740/751 failing bands. `fuzz_skewed_freq_roundtrip` (6
  seeds × 5 sizes × 6 levels) emits Fibonacci-ish literal frequency
  distributions to drive `_huff_redistribute` past its short-circuit.
  Adds 70 outer iterations on top of the existing 1564 — but exposes
  the bug class that uniform-random fuzz inputs cannot reach.

### Changed
- **Toolchain pin**: `cyrius.cyml` updated to `cyrius = "5.6.34"`.
  This is the toolchain release that bundles sankoch 2.0.2 into the
  Cyrius stdlib as `lib/sankoch.cyr`, and the version the in-flight
  cyrius v5.6.35 picks up to retire sit's post-commit `read_object`
  verify mitigation.
- Docs sweep: README, CLAUDE.md, `docs/development/cyrius-usage.md`,
  and `.github/workflows/ci.yml` reference 5.6.34. Roadmap and
  CHANGELOG history references to 5.5.22 are left as-is — they
  describe the toolchain at the time of those releases.

### Downstream
- **cyrius v5.6.35** (in-flight): pins this sankoch tag in
  `cyrius.cyml`, and adds a `tests/regression-sit-status.sh` gate
  that runs sit's 100-commit fixture and asserts `sit fsck`
  reports 0 bad.
- **sit**: the post-commit `read_object` verify added as a
  mitigation for this bug can be reverted once cyrius v5.6.35 ships
  with sankoch 2.0.2.

## [2.0.1] — 2026-04-21

**Toolchain refresh + Adler-32 streaming perf. No API or wire-format
change.**

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

## [2.0.0] — 2026-04-19

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
