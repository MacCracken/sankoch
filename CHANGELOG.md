# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

**Toolchain refresh + DEFLATE compress perf — three stacked wins on
the throughput investigation surfaced by sit v0.6.4: pre-reversed
dynamic Huffman codes, 8-byte word-compare match extension, and
ring-buffer (absolute-position) match-finder.**

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
  "current — Unreleased / next 2.x point release", with current line
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
