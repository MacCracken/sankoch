# Sankoch Development Roadmap

> **Status**: Stable (v2.2.6) | **Last Updated**: 2026-05-20

---

## v2.0.0 — shipped 2026-04-19

Four-item v2.0.0 track landed as incremental minor bumps, then cut to
2.0.0 after a P(-1) pass. Declares the LZ4 + DEFLATE + zlib + gzip
surface stable. No API changes in 2.0.0 itself — just a closeout pass
(two LOW audit findings fixed, dead accessors removed, docs swept).
See `docs/audit/2026-04-19-pre-2.0.0.md`.

### ✅ v1.5.0 — Adaptive DEFLATE block splitting (shipped 2026-04-19)

Dynamic-Huffman path now emits multiple adaptive sub-blocks per caller
chunk, flushing when the shared symbol buffer fills. Each sub-block
ships its own optimal tree tuned to its own frequencies. Replaces the
1.4.0- fallback-to-fixed downgrade.

**Impact shipped:** 64K random −4.8%; 256K random went from
`-ERR_BUFFER_TOO_SMALL` to valid output. No regression on the 26
high-locality text bench sizes.

### ✅ v1.6.0 — LZ4 multi-block frames (shipped 2026-04-19)

`lz4f_compress` now chunks inputs into ≤64KB blocks per the BD byte
instead of emitting a single oversized block. Each chunk compresses
independently (B.Indep=1) and falls back to an uncompressed block
per-chunk when needed. `lz4f_decompress` needed no change — its
block-size loop already handled multi-block frames.

**Impact shipped:** 128K text = 647B (2 blocks), 256K text = 1279B
(4 blocks), 128K random = 131095B (2 uncompressed blocks — validates
the per-chunk fallback path). Reference `lz4` CLI now accepts our
output.

### ✅ v1.6.1 — xxHash32 spec compliance + P(-1) hardening (shipped 2026-04-19)

P(-1) audit before v1.7.0 uncovered that our `xxhash32` was the
short-length variant only and used PRIME2 instead of PRIME4 in the
4-byte tail. Compressor and decompressor were self-consistent but
reference `lz4` CLI rejected our output. Fixed the hash, added 9
known-vector tests (from `xxh32sum`), validated end-to-end against
`lz4 -dc`. Breaking wire-format change; no shipping downstream
consumers yet. See `docs/audit/2026-04-19.md`.

**Tracked for v1.7.0:** direct-entry APIs (`lz4f_compress`,
`zlib_*_dict`, `deflate_*_dict`, `stream_*`) bypass the public mutex
— fix lands alongside the streaming refactor that release needs
anyway.

### ✅ v1.7.0 — True incremental streaming + MED-01 (shipped 2026-04-19)

Today's `stream_compress_finish` buffers the whole input then
compresses in one shot. True incremental streaming means the
compressor emits output bytes as each `stream_write` chunk arrives.
Scope for 1.7.0 is **all four formats**: DEFLATE (foundation),
zlib/gzip (thin wrappers over DEFLATE with incremental Adler-32 /
CRC-32 trailers), and LZ4F (multi-block frame with per-block emit,
leveraging B.Indep=1).

**Design decisions locked (2026-04-19):**
- Per-format incremental API: `<fmt>_enc_init(level, dst, dst_cap)` →
  `<fmt>_enc_write(ctx, chunk, len)` → `<fmt>_enc_finish(ctx)` →
  `total_bytes_written`. `deflate_enc_*` is the foundation; zlib/gzip
  wrap it; `lz4f_enc_*` wraps `lz4_compress` per 64KB block.
- Encoder owns a 64 KB sliding window; slides every 32 KB of new
  input; rebases `_lz77_head`/`_lz77_prev` on each slide (accept
  ~16 B/input-byte rebase cost for first cut; ring-buffer rewrite of
  match-finder deferred to 1.7.x if benchmarks justify).
- Lazy matching disabled in streaming fixed path (levels ≤3 — greedy
  only). Level ≥4 dynamic path is already greedy; no change there.
- BFINAL choreography: `enc_write` always emits BFINAL=0; `enc_finish`
  always emits one final sub-block with BFINAL=1 (even if the symbol
  buffer is empty — trivial BFINAL=1 stored block with LEN=0).
- Dynamic-path block emit refactored into three primitives
  (`_dyn_reset`, `_dyn_collect_at`, `_dyn_flush_subblock`) so the
  batch path and streaming path share the sub-block code.
- Incremental xxhash32 API added (`xxhash32_init` / `_update` /
  `_final`) for LZ4F content-checksum streaming; batch `xxhash32`
  stays for callers who have the full input.
- **Bundles MED-01 fix**: public direct-entry APIs (`lz4f_*`,
  `zlib_*`, `gzip_*`, `deflate_*`, `stream_*`) get the two-tier
  public/internal split so they can safely take `_sankoch_mtx`
  without recursing through batch `compress()`. Single mutex held
  from `enc_init` to `enc_finish`; concurrent encoders serialize.
  Single-threaded contract: a live encoder precludes other
  `compress`/`decompress` calls on the same thread until `finish`.

**Impact**: required for compressing data larger than available
memory; also unblocks network-streaming consumers and closes the
MED-01 thread-safety gap from the 2026-04-19 audit.

### ⏸ Deferred — SIMD CRC-32 via `PCLMULQDQ`

4–10× CRC-32 speedup on x86_64 via the `PCLMULQDQ` carry-less multiply
instruction. Cyrius 5.5.22 exposes raw `asm { byte; byte; … }` blocks
(see `lib/thread.cyr` `_thread_spawn`), so the toolchain gate is
cleared. Not prioritized yet because current table-driven CRC-32 runs
at ~278 MB/s on 4KB, which is fine for the consumers we have today —
revisit if a consumer actually pushes CRC-32 onto the hot path.

---

## v2.x release ladder (sequenced, post-2.2.0)

Each item below is a planned release with a target version. Order
holds for now; scope per item is the working contract — adjust if a
P(-1) pass surfaces something that has to slot in. Items further down
the ladder can be re-ordered against new information; the dependency
direction is roughly top → bottom (the streaming-decomp work in
2.3.0 leans on patterns from the kernel-safe refactor in 2.1.2 and
the lock-aware alloc handling from 2.2.1; the aarch64 cross-build
gate in 2.2.2 sets the portability floor before new public surface
lands; the perf retry in 2.3.2 wants the throughput baseline to be
steady, which means after the API surface settles).

### ✅ 2.1.2 — multi-profile distlib (kernel-safe LZ4 decompress) — shipped 2026-05-01

Mirrors yukti's `dist/yukti-core.cyr` pattern. AGNOS initrd consumer
needs LZ4 decompress with no alloc, no syscalls, no mutex. Decompress
in `src/lz4.cyr` is already alloc-free at the function-call level —
the work is file-level extraction so `cyrius distlib core` produces a
clean bundle with no kernel-unsafe code in scope.

**Scope (decompress-only — block + frame):**
- Extract `_xxh32_rotl`, `_xxh32_round`, `xxhash32` (batch) and the
  `XXH32` enum from `src/checksum.cyr` into a new
  `src/xxhash32.cyr`. Alloc-using incremental state APIs
  (`xxhash32_init`/`_update`/`_final`) stay in checksum.cyr.
- Extract `lz4_decompress` and `lz4f_decompress` from `src/lz4.cyr`
  into a new `src/lz4_decode.cyr`. Encode side stays in lz4.cyr.
- Add `[lib.core]` profile in `cyrius.cyml`:
  `types.cyr` + `xxhash32.cyr` + `lz4_decode.cyr`.
- Add `programs/core_smoke.cyr` link-only invariant check (calls
  block + frame decompress on small known fixtures; any alloc /
  syscall / mutex leak into the core subset fails the build).
- New CI step: `cyrius distlib core` + drift check, mirroring the
  full-bundle gate.
- New release artifact: `sankoch-<tag>-core.cyr` alongside the full
  bundle.

**Out of scope (deferred until a consumer asks):**
- Kernel-safe LZ4 *compress*. Match-finder hash table is heap-
  allocated and would need a caller-provided workspace refactor.
  No kernel consumer is asking for compress yet (initrd is built
  userland-side; the kernel only decompresses), so the heap-using
  encoder stays in the full-`[lib]` profile.
- Kernel-safe DEFLATE / zlib / gzip. Same pattern would apply but
  no consumer signal yet.

**Sizing:** small-medium. Two file-level extractions, an `[lib.core]`
config block, a smoke program, and CI/release wiring. No source
behavior change — extraction is cut/paste with the include chain
re-ordered.

### ✅ 2.1.3 — P(-1) scaffold-hardening pass — shipped 2026-05-01

CLAUDE.md's P(-1) pre-feature checklist run before opening 2.2.0+
work. Closeout for the 2.1.x line; entry door to the 2.2.x feature
work that follows.

**Scope (per CLAUDE.md "P(-1): Scaffold Hardening"):**
- Cleanliness gates: `cyrius build` 0 warnings on the library path,
  `cyrius lint` 0 warnings, `cyrius fmt --check` clean,
  `cyrius vet src/lib.cyr` clean.
- Test sweep: both tcyr suites green, all fuzz harnesses green.
- Benchmark baseline: full `cyrius bench tests/bcyr/sankoch.bcyr`
  run, CSV archived to `docs/benchmarks/`.
- Internal deep review — gaps, optimization candidates, correctness
  questions surfaced during 2.1.0 / 2.1.1 / 2.1.2 work that didn't
  rise to a release on their own.
- External research — RFC errata sweep (1950 / 1951 / 1952), zlib
  + reference `lz4` CLI changes since the last audit.
- Security audit — `docs/audit/2026-MM-DD.md`, follow-up on any
  open INFO from the 2026-04-19-pre-2.0.0 audit. Specifically
  re-checks: stack-buffer sizes, `var buf[N]` static-data
  warnings, sys_ usage in src/, dead public-API list.
- Additional tests / benchmarks from findings.
- Post-review benchmarks — prove any wins.
- Documentation audit — CLAUDE.md, roadmap, CHANGELOG, README.

**Sizing:** medium. Mostly process; no API or source change
expected unless the audit surfaces something. If a finding wants a
non-trivial fix, P(-1) calls it out and 2.1.4 picks it up before
2.2.0 starts.

**Outcome (2026-05-01)**: parser-side audit surfaced 1 HIGH (DEFLATE
stored-block source-bounds bypass), 1 MEDIUM (HLIT spec compliance),
2 LOW (zlib CINFO, gzip reserved FLG bits). All four fixed in 2.1.3
with targeted regression tests; one INFO (gzip FHCRC verify)
backlogged. Full writeup at `docs/audit/2026-05-01-pre-2.2.0.md`.
Test count: 1,375,208 → 1,375,212. Cleared to open 2.2.0.

### ✅ 2.2.0 — preset dictionary in streaming encoders — shipped 2026-05-01

Adds public API → minor bump. Matches existing
`deflate_decompress_dict` / `zlib_decompress_dict` semantics on the
encode side.

**Scope:**
- `deflate_enc_init_dict(level, dst, dst_cap, dict, dict_len)` —
  preload sliding window with `dict` bytes, hash table seeded.
- `zlib_enc_init_dict` — same, plus FDICT flag set in zlib header
  (RFC 1950 §2.2) and Adler-32 of dict written before stream body.
- `gzip_enc_init_dict` — gzip has no FDICT in the spec; this is
  identical-format to non-dict but with the encoder's window
  pre-warmed (callers who decompress with the same dict get the
  improved ratio).
- LZ4F has no dict concept in the frame format — out of scope.
- Round-trip tests against existing `*_decompress_dict` paths
  (compress with dict, decompress with same dict, byte-equal input).

**Sizing:** small-medium. Encoder dict plumbing is mostly a
window-preload + Adler-32 prelude; the test matrix is the bulk.

**Outcome (2026-05-01)**: three new public API entry points
(`deflate_enc_init_dict`, `zlib_enc_init_dict`, `gzip_enc_init_dict`).
Existing `*_enc_init` functions refactored to thin shims calling the
dict variant with `dict=0, dict_len=0` — no behavior change for
existing callers. zlib ctx grew from 24 to 32 bytes (header_len
field added). gzip support documented with the "no FDICT in spec"
caveat — round-trips inside the gzip wrapper via
`deflate_decompress_dict` on the stripped DEFLATE payload.
Tests +636 assertions. `[lib.core]` unchanged.

### ✅ 2.2.1 — defensive `alloc()` failure handling — shipped 2026-05-01

INFO-01 from the 2026-04-19-pre-2.0.0 audit. Promoted ahead of
true-incremental-decomp (2.3.0) because it's small, mechanical, and
ships a tag the same session — momentum win with no scope risk.
Pure internal hardening, no public API change.

**Scope:**
- Wrap every `alloc()` call in `*_enc_init` (and `*_dec_init` when
  those land in 2.3.0) with an unlock-on-failure check so a failed
  alloc returns 0 (no ctx) with `_sankoch_mtx` released, instead of
  leaving the lock held + null-deref'ing on the next field access.
- Per-call helpers invoked from those entry points (`bw_init`,
  `adler32_init`, `crc32_init`, `xxhash32_init`) propagate alloc
  failure as a 0 return; the entry point checks and unlocks.
- Add a fault-injection test harness — `_sankoch_alloc(size)`
  wrapper around the stdlib alloc with a caller-set
  `_sankoch_alloc_fail_at` counter; tcyr tests use it to inject
  failure at the first alloc of each `*_enc_init`, verify the
  call returns 0, and verify the lock was released by making a
  second public-API call succeed.
- **Out of scope (deferred)**: lazy-global init helpers
  (`_huff_alloc_tables`, `_lz77_init`, `_lz4_htab` init,
  `_deflate_*_lookup`, `_dh_ws`, `_dyn_*`, `crc32_table`). Same
  pattern, but failure here would need error propagation through
  many internal callers — bigger surface than INFO-01 calls for.
  Tracked as a future hardening item; the 2.2.1 audit appendix
  notes which sites remain.

**Sizing:** small. Mostly mechanical; the test harness is the
deliberate part.

**Outcome (2026-05-01)**: 6 alloc sites patched in the four
`*_enc_init` entry points + their per-call constructors
(`bw_init`, `adler32_init`, `crc32_init`, `xxhash32_init`). New
`_sankoch_alloc(size)` wrapper + `_sankoch_alloc_set_fail_at(n)`
one-shot counter in `src/lib.cyr`. 8 fault-injection tests
(+16 assertions) covering each patched path: ctx alloc fails,
window alloc fails, bw_init fails, zlib ctx fails (after
inner deflate took the lock), zlib adler init fails, gzip ctx
fails, lz4f ctx fails, lz4f block_buf fails. Each test asserts
the entry point returned 0 AND the lock was released by
verifying a follow-up call succeeds. Lazy-global allocs
(35 of the 41 total sites) deferred to a future hardening
item — they're effectively never the OOM victim and would need
error propagation through internal callers.

### ✅ 2.2.2 — aarch64 cross-build in CI/release — shipped 2026-05-01

Closes the long-standing aarch64 parity gap before the 2.3.x
streaming-decomp arc opens, so every `*_dec_*` function added in
2.3.0+ is aarch64-clean from day one rather than retroactively.
Pulled forward from 2.3.3 to keep the 2.3.x line a clean
streaming-decomp narrative.

Yukti has shipped aarch64 cross-builds since 2.1.3 on cyrius
5.7.43+; we're on 5.7.48, so the toolchain is ready and
`cc5_aarch64` is in the bundle. Local cross-build sanity-checks
already pass (sankoch's `src/` is syscall-free pure-compute).

**Scope:**
- Add aarch64 cross-build step to `.github/workflows/ci.yml` —
  build `src/lib.cyr`, `programs/core_smoke.cyr`, and all fuzz
  harnesses with `--aarch64`. Verify each output is an
  ARM aarch64 ELF via `file`.
- Pick up the `cc5_aarch64` packaging workaround yukti and sakshi
  carry (covers pre-5.7.48 `bin/` layout plus 5.7.48+ tarball
  top-level).
- Mirror in `.github/workflows/release.yml`: cross-build
  `src/lib.cyr`, archive alongside x86_64, ship
  `sankoch-<tag>-aarch64-linux` next to the existing x86
  artifact.
- No `src/` changes expected — sankoch is pure-compute (no direct
  syscalls; the security scan asserts this). Stdlib syscall-arity
  warnings on the aarch64 build are cosmetic and don't fail the
  gate.

**Sizing:** small. Pure CI/release YAML work + bundle
regeneration with the new version stamp.

**Outcome (2026-05-01)**: aarch64 cross-build step added to both
ci.yml and release.yml; cc5_aarch64 packaging workaround landed
to cover the 5.7.48+ tarball layout. Local sweep verifies
`src/lib.cyr` (180 KB), `programs/core_smoke.cyr` (64 KB), and
both fuzz harnesses (~200-226 KB each) produce valid ARM aarch64
ELFs. Release archive now ships `sankoch-<tag>-aarch64-linux`
alongside the x86_64 artifact. Zero source changes; both bundles
regen'd only for the version stamp bump (body byte-identical).

### ✅ 2.2.3 — P(-1) closeout for the 2.2.x line — shipped 2026-05-01

Audit pass over the surface touched since 2.1.3 (dict-init paths,
defensive-alloc wrapping, aarch64 cross-build gate). Pure process
+ test-coverage release; no source changes.

**Outcome (2026-05-01)**: zero HIGH/MEDIUM/LOW findings; three
INFO observations documented (lazy-global alloc-fail still
deferred; `*_decompress_dict` requires `dst_cap >= dict_len`;
aarch64 LZ77 word-compare uses unaligned loads). Five new tests
close the coverage gaps surfaced during the review: two missed
alloc-fail paths from 2.2.1 (gzip crc32_init, lz4f xxhash32_init)
plus three dict-boundary cases (max=32768, min-match=3,
below-min=2). Total assertions: 1,375,864 → 1,375,921. Audit at
`docs/audit/2026-05-01-pre-2.3.0.md`. Cleared to open 2.3.0.

### ✅ 2.2.4 — Cyrius 5.8.64 toolchain bump — shipped 2026-05-05

Patch release. Pin bumped 5.7.48 → 5.8.64 ahead of the cyrius
v5.8.65 stdlib foldin slot (sankoch is on the foldin manifest;
this patch is the prerequisite for cyrius's `[deps].sankoch.tag`
to point at 2.2.4 in the foldin slot). Pre-existing `cyrius fmt`
drift cleared across `src/`, `programs/`, `tests/`, `fuzz/`. Zero
behavior change — full regression sweep green on 5.8.64
(1,029,338 / 1,029,338 in sankoch.tcyr; fmt clean across all 20
files). `dist/sankoch.cyr` regenerated.

### ✅ 2.2.5 — stdlib `: i64` annotation pass — shipped 2026-05-11

Patch release. Cyrius 5.10.x landed the REAL TYPE SYSTEM and the
5.11.x annotation arc required every public fn in stdlib-tracked
trees to carry an explicit `: i64` return-type annotation. Pure
mechanical pass across `src/*.cyr` — parse-only, zero runtime /
codegen change. Pin bumped 5.8.64 → 5.11.4 (required for the new
syntax). `dist/sankoch.cyr` regenerated at 4824 lines.

### ✅ 2.2.6 — Cyrius 6.0.1 + `cycc_aarch64` rename — shipped 2026-05-20

Patch release. Pin bumped 5.11.4 → **6.0.1** — Cyrius's first
major-version cut. Build, both tcyr suites (1,029,338 + 346,583
= 1,375,921 assertions), `cyrius lint`, `cyrius vet`, and the CI
fmt sweep all clean against 6.0.1 — the pin-drift warning is
gone. Stale `5.7.48` references in `README.md`,
`docs/development/cyrius-usage.md`, and `CLAUDE.md` (carried since
the 2.2.4 / 2.2.5 bumps) refreshed at the same time. CI/release
gate updated: Cyrius 6.0 renamed the aarch64 cross-compiler binary
from `cc5_aarch64` to `cycc_aarch64`; both workflows were looking
for the old name and erroring out (`cc5_aarch64 missing from
Cyrius`). Local `cyrius build --aarch64 src/lib.cyr` confirmed
clean against the renamed binary. `dist/sankoch.cyr` regenerated.

### 🎯 2.2.7 — P(-1) closeout against cyrius 6.0.1

Re-runs the P(-1) scaffold-hardening checklist after three
patch-level toolchain-tracking releases (2.2.4 / 2.2.5 / 2.2.6)
collectively jumped the Cyrius pin two minor lines and one major
(5.7.48 → 6.0.1). Pure process; expected outcome is zero source
changes. Locks in a fresh throughput baseline immediately before
2.3.0's `*_dec_*` streaming-decomp arc lands new hot-path code.

**Scope (per CLAUDE.md "P(-1): Scaffold Hardening"):**
- Cleanliness gates against cyrius 6.0.1: `cyrius build` 0
  warnings on the library path, `cyrius lint` 0 warnings,
  `cyrius fmt --check` clean, `cyrius vet src/lib.cyr` clean.
- Test sweep: both tcyr suites green at 1,375,921 assertions.
  All six fuzz harnesses green.
- Benchmark baseline: full `cyrius bench tests/bcyr/sankoch.bcyr`
  archived as `docs/benchmarks/2026-MM-DD-pre-2.3.0.csv` — the
  reference 2.3.0 will defend against.
- Internal deep review — anything the cyrius 6.0.x type-system
  + annotation refresh perturbed in `src/`.
- External research — cyrius 5.7 → 6.0 stdlib API drift sweep
  (syscalls / string / alloc / fmt / vec / fnptr / thread /
  assert) for surface sankoch depends on.
- Security audit — `docs/audit/2026-MM-DD-pre-2.3.0-redux.md`,
  fresh sweep of stack-buffer sizes, sys_ usage in src/, dead
  public-API list. Follow-up on the three INFO observations
  carried from 2026-05-01 (lazy-global alloc-fail, dict
  `dst_cap >= dict_len` docstring polish, aarch64 unaligned
  word-compare).
- Additional tests / benchmarks from findings, if any.
- Documentation audit — CLAUDE.md, roadmap, CHANGELOG, README,
  cyrius-usage.md.

**Sizing:** medium. Mostly process; no API or source change
expected unless the audit surfaces something. If a finding wants
a non-trivial fix, P(-1) calls it out and 2.2.8 picks it up
before 2.3.0 starts.

### 🚧 2.3.0 — true incremental decompression (bites 1-4 of 6 done)

Mirrors the 1.7.0 streaming-encoder work on the decode side. Minor
bump because the new APIs are additive (`<fmt>_dec_init / write /
finish`); the existing buffered `stream_decompress_*` path stays
as-is for callers that don't need byte-streaming output.

**Scope:**
- `<fmt>_dec_init / write / finish` for DEFLATE, zlib, gzip, LZ4F —
  emits decompressed output bytes as compressed input chunks
  arrive, instead of buffering then batch-decompressing.
- Two-tier mutex split mirroring the encoder side: single mutex
  held from `dec_init` to `dec_finish`.
- DEFLATE state machine has to suspend/resume across `write` calls
  (block header parse, Huffman code-length state, literal/length
  decode, distance decode — each may straddle a chunk boundary).
- zlib/gzip wrap with incremental Adler-32 / CRC-32 trailers and
  header parsing that may straddle chunks.
- LZ4F multi-block frame: per-block emit at block boundaries.
- Update `stream.cyr` dispatch to route to `*_dec_*` when
  `stream_decompress_init` is called in incremental mode.

**Sizing:** large — DEFLATE state-machine suspension is the hard
part. Broken into 6 small bites; each ships verified before the next
opens.

**Bite ladder:**
- ✅ **Bite 1 (2026-05-23)** — `deflate_dec_init / write / finish` API
  surface + 88-byte ctx + hold/bits bit accumulator + state machine
  for **stored blocks only** (BTYPE=00). BTYPE=01/10 return
  `-ERR_UNSUPPORTED_FORMAT` until bites 2 & 3. 13 new hand-crafted
  tests (+57 assertions, total 1,375,978); wire format byte-identical
  to 2.2.7. Mutex held `dec_init` → `dec_finish` mirroring encoder.
- ✅ **Bite 2 (2026-05-23)** — fixed-Huffman block decode (BTYPE=01).
  `_ddec_decode_huff` bridge helper (stack-only 4-byte buffer +
  32-byte br struct; reuses the existing `_huff_decode`). Four new
  state-machine arms (`DECODE_SYM` / `LEN_EXTRA` / `DECODE_DIST` /
  `DIST_EXTRA`) drive literal emit, length+extra, distance+extra,
  and overlap-safe match-copy. Phantom-decode guard
  (`consumed > ctx.bits` → need-more) rejects spurious matches on
  zero-padded partial bytes. 7 new tests (+1,105 assertions); first
  bite to round-trip against the batch compressor's level-1 output.
  ctx grew 88 → 112 bytes.
- ✅ **Bite 3 (2026-05-23)** — dynamic-Huffman block decode (BTYPE=10).
  Six new state-machine arms slice `_deflate_read_dynamic` into
  chunk-suspendable pieces: `DYN_HLIT` / `DYN_HDIST` / `DYN_HCLEN`
  / `DYN_CL_LENS` (loop over hclen × 3-bit cl_order reads) /
  `DYN_AL_SYM` (decode cl symbol → literal/repeat) / `DYN_AL_EXTRA`
  (read 2/3/7 extras + emit repeat). Lazy-global workspaces
  (`_ddec_cl_order` / `_ddec_cl_lens` / `_ddec_all_lens`) persist
  partial trees across chunks. MED-01 (HLIT > 286) reject preserved
  in the new state. 6 new tests (+1,342 assertions); after this
  bite the streaming decoder accepts all 3 DEFLATE block types and
  round-trips against every encoder level 1-9. ctx grew 112 → 160
  bytes.
- ✅ **Bite 4 (2026-05-23)** — streaming zlib + gzip wrappers.
  `zlib_dec_init / write / finish` (no FDICT yet) and
  `gzip_dec_init / write / finish` (single-member only) wrap the
  bite-1/2/3 DEFLATE decoder. 4-state zlib machine; 9-state gzip
  machine covering the full RFC 1952 optional-field surface
  (FEXTRA / FNAME / FCOMMENT / FHCRC) with the LOW-02
  reserved-FLG reject preserved. `deflate_dec_write` contract
  evolved to return bytes-consumed so the wrappers can split each
  chunk between DEFLATE body and trailer. Bit-accumulator
  overpull fixed in both wrappers via a `cp -= (ctx.bits >> 3)`
  rewind when the inner transitions to DONE. 15 new tests
  (+2,233 assertions). FDICT zlib + concatenated-member gzip
  scoped to a follow-on 2.3.x patch.
- 🎯 **Bite 5** — LZ4F multi-block frame; per-block emit.
- 🎯 **Bite 6** — `stream.cyr` dispatch routes `stream_decompress_init`
  to the appropriate `*_dec_*` for incremental-mode callers.

### 🎯 2.3.1 — configurable LZ4F block-max size

Adds public API → minor bump. BD byte spec (LZ4 Block Format §1.2)
defines four block-max values: 64K (4), 256K (5), 1M (6), 4M (7).
Sankoch hardcodes 64K today.

**Scope:**
- New API: `lz4f_compress_block_max(input, in_len, dst, dst_cap, block_max)`
  or extend `lz4f_enc_init` with a block-max parameter (decide
  during P(-1)).
- BD byte encoding: bits 4-6 carry block-max ID; update header
  emit + HC checksum.
- Decoder already reads the BD byte and sizes its block buffer
  accordingly — verify with a round-trip test against reference
  `lz4` CLI at each of the four sizes.
- New benchmarks: same input, four block sizes, ratio + throughput
  per size.

**Sizing:** small-medium. Encoder plumbing is well-scoped; the
verification matrix against reference `lz4` is the bulk.

### 🎯 2.3.2 — DEFLATE throughput round 2

Continues the throughput investigation surfaced by sit v0.6.4
(2026-04-25). The two foundational down-payments landed in 2.1.0
(see "Landed in 2.1.0" below); this release picks up what was
deferred or reverted.

**Scope:**
- Retry `good_length` early-exit in the chain walk at level ≥ 6.
  First attempt 2026-04-25 was reverted because sankoch's L6 chain
  depth of 64 was too shallow for the cut to bite on benchmarkable
  inputs. Retry options: (a) widen the bench input set with
  long-locality inputs that push deeper chain walks, (b) raise L6
  chain depth to 128 first and re-bench, (c) drop the early-exit and
  pick a different micro-optimization (e.g. tighter inner-loop
  scheduling). Decision lives in the P(-1) writeup.
- PCLMULQDQ CRC-32 via Cyrius inline asm (5.5.22+ exposes raw
  `asm { byte; … }` blocks; toolchain gate clear since 5.6.x).
  Reference: Intel "Fast CRC Computation for Generic Polynomials
  Using PCLMULQDQ Instruction" (whitepaper, Dec 2009).
- Wire-format identical — every change has to pass the
  byte-for-byte SIZE-line gate against the previous baseline.

**Target:** sit's `add-1MB` (currently ~150ms in `zlib_compress(1MB)`
out of 208ms total) wants a 5× zlib speedup to put `sit add` of a
1MB file under 100ms. Round 1 (2.1.0 down-payments) bought
~7-12% on the streaming path; round 2 + PCLMULQDQ together should
double that.

**Sizing:** medium. PCLMULQDQ is contained; the L≥6 retry is a
think-first job.

---

### Landed in 2.1.0 (record, not roadmap)

Two down-payments on the DEFLATE throughput investigation shipped
2026-04-25, plus the ring-buffer match-finder. Wire-format identical
across all three.

1. **Pre-reverse dynamic Huffman codes** at build time so the
   symbol-emit hot loop drops three per-symbol bit-reversal
   sub-loops.
2. **8-byte word-compare match extension** in `_lz77_find_match`
   (replaces byte-at-a-time inner loop with `load64` + word XOR
   on full 8-byte chunks plus a byte tail).
3. **Ring-buffer match-finder, O(1) slide.** Hash table now stores
   absolute stream-byte positions; `_lz77_window_base` tracks the
   absolute offset of `window[0]` and is bumped O(1) on each
   slide. Stale entries are rejected lazily inside
   `_lz77_find_match` via a single `chain < base` check per chain
   iteration — no batch walk. ~10-12% on streaming compress 128K
   text; batch path unchanged.

Combined vs the pre-Unreleased baseline: `deflate c rand 4K`
−16.2%, `deflate L6 text 4K` −8.7%, `zlib c text 4K` −7.7%,
`stream zlib L6 text 128K` ~−7%.

Also closed in earlier 2.x: **Adler-32 16-byte unroll in
`adler32_update`** (2.0.1, INFO-02 from the 2026-04-19-pre-2.0.0
audit) — streaming zlib ~6% closer to streaming DEFLATE on 128 KB.

---

## Scaffold follow-ups (independent of codec work)

### ✅ `cyrfmt` in-place mode — shipped in Cyrius 5.5.22

`cyrfmt --write <file.cyr>` (or `-w`, gofmt convention) reformats in
place. Idempotent — a clean file short-circuits before the write
syscall so mtime doesn't churn. Truncate-and-overwrite (not atomic
temp+rename; Cyrius doesn't expose `sys_rename` yet). Replaces the
prior `cyrfmt x.cyr > x.new && mv x.new x` shell one-liner. The
`cyrius fmt` frontend banner still shows only `[--check]` in 5.5.22
but passes `--write` / `-w` through to the underlying `cyrfmt`
binary — use the direct `cyrfmt` invocation or pass the flag
through `cyrius fmt` either way.

### 🔀 Multi-profile distlib & aarch64 cross-build — on the ladder

Multi-profile distlib (kernel-safe LZ4 decompress subset) shipped in
**2.1.2** (2026-05-01); aarch64 cross-build in CI/release is **2.2.2**.
See the "v2.x release ladder" section above for the latter's scope.

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

## File Summary (at 2.2.6)

| File | Lines | Role | Profile |
|------|-------|------|---------|
| types.cyr        |   37 | Enums: formats (incl. FORMAT_LZ4F), errors, limits | core |
| xxhash32.cyr     |   94 | xxHash32 batch + helpers + XXH32 enum (kernel-safe) | core |
| checksum.cyr     |  424 | Adler-32 / CRC-32 + incremental state APIs (alloc-using) | full |
| bitreader.cyr    |   99 | LSB-first bit-stream reader | full |
| bitwriter.cyr    |  145 | LSB-first bit-stream writer | full |
| huffman.cyr      |  661 | Huffman build/decode, fixed + optimal trees, encoder pre-reversed codes | full |
| lz77.cyr         |  179 | Sliding window match-finder, 8-byte word-compare match extend, `lz77_rebase`, ring-buffer slide | full |
| lz4_decode.cyr   |  169 | LZ4 block + frame decompress + LZ4F enum (kernel-safe) | core |
| lz4.cyr          |  513 | LZ4 block + frame compress + `lz4f_enc_*` streaming | full |
| deflate.cyr      | 1676 | DEFLATE de/compress, adaptive blocks, `deflate_enc_*` streaming, dict | full |
| zlib.cyr         |  222 | RFC 1950 wrapper + FDICT + `zlib_enc_*` streaming | full |
| gzip.cyr         |  270 | RFC 1952 wrapper + concatenated members + `gzip_enc_*` streaming | full |
| lib.cyr          |  193 | Public API, `_sankoch_mtx`, two-tier lock dispatch | full |
| stream.cyr       |  162 | Streaming dispatch (`stream_compress_init/write/finish` → per-format `_enc_*`) | full |
| **Total**        | **4844** | | |

`core` modules (types + xxhash32 + lz4_decode = 300 source lines)
form `[lib.core]` → `dist/sankoch-core.cyr`. They contain no
`alloc()`, no syscalls, no mutex usage — verified by the CI
"Kernel-safe tripwire" gate (`programs/core_smoke.cyr`).

Tests: **116 distinct test functions** (106 sankoch.tcyr + 10
git_object.tcyr) producing **1,375,921 assertions** total
(1,029,338 + 346,583). Most of the assertion count comes from
per-byte round-trip loops on the streaming suites — a single 200 KB
round-trip contributes 200,000 assertions through one
`while (i < N) assert(byte_eq)` loop; the headline number measures
coverage *density*, not coverage *breadth*. See
[`../cyrius-usage.md`](../cyrius-usage.md#what-assertions-means-here-and-why-the-number-is-so-large)
for the full explanation.

The git_object suite grew massively in 2.0.2 / 2.0.3 when the
cl-tree depth-cap regression fixtures landed (134 → 13,929 →
346,583 across the two patches); the +4 in sankoch.tcyr at 2.1.3
covers the four P(-1) audit-finding regressions, the +636 at
2.2.0 covers the streaming-encoder dict round-trip + invalid-args
matrix, the +16 at 2.2.1 covers the eight fault-injection tests
for INFO-01 alloc-failure handling, and the +57 at 2.2.3 covers
the five P(-1) coverage-gap tests (two missed alloc-fail paths
plus three dict-boundary cases).

Fuzz: 1,649 iterations across 6 harnesses
(`fuzz_lz4` 700, `fuzz_deflate` batch 340, `fuzz_zlib` 160, `fuzz_gzip`
160, plus the four streaming variants and the 2.0.2 tree-shape /
skewed-freq harnesses).

Distlib: `dist/sankoch.cyr` at 4,871 lines (full) +
`dist/sankoch-core.cyr` at 315 lines (kernel-safe).

## Dependencies

**Zero external.** Checksums (Adler-32, CRC-32, xxHash32 — batch and
incremental) are inline. No sigil dependency. Stdlib-only: `syscalls`,
`string`, `alloc`, `fmt`, `vec`, `fnptr`, `thread`, `assert` (all
ship with Cyrius ≥ 6.0.1, which is the current pin).

## Key References

- RFC 1951 — DEFLATE Compressed Data Format Specification
- RFC 1950 — ZLIB Compressed Data Format Specification
- RFC 1952 — GZIP File Format Specification
- LZ4 Block Format — github.com/lz4/lz4/blob/dev/doc/lz4_Block_format.md
- Feldspar, "An Explanation of the Deflate Algorithm" — clearest DEFLATE walkthrough
- Duda, "Asymmetric Numeral Systems" (arXiv:1311.2540) — for future Zstandard work

---

*Last Updated: 2026-05-20 (2.2.6 toolchain bump to Cyrius 6.0.1)*
