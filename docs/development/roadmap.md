# Sankoch Development Roadmap

> **Status**: Stable (v2.3.0) | **Last Updated**: 2026-05-23

Shipped history lives in `CHANGELOG.md`; this file is the forward
ladder. Items are ordered by release; scope per item is the working
contract — adjust if a P(-1) pass surfaces something that has to slot
in. Items further down can be re-ordered against new information.

---

## v2.3.x ladder (sequenced, post-2.3.0)

The 2.3.x line continues from the streaming-decompression cut. The
two pre-2.3.0 items (configurable LZ4F block-max, DEFLATE throughput
round 2) keep their slots; the new follow-on item rolls up the
deferred work from the 2.3.0 bite ladder plus carried INFOs from
the 2.1.3 / 2.2.3 audits. P(-1) closes the line before 2.4.0 opens.

### 🎯 2.3.1 — configurable LZ4F block-max + streaming per-block checksum

Adds public API → minor bump. BD byte spec (LZ4 Block Format §1.2)
defines four block-max values: 64K (4), 256K (5), 1M (6), 4M (7).
Sankoch hardcodes 64K today on both encoder and streaming decoder.
While this release is touching the BD plumbing it also lifts the
two FLG-bit-4 (per-block checksum) restrictions the 2.3.0 streaming
decoder shipped with.

**Scope:**
- Extend `lz4f_enc_init` with a block-max parameter (decide signature
  during P(-1) — extension vs new `lz4f_enc_init_block_max` overload).
  BD byte encoding: bits 4-6 carry block-max ID; update header emit
  + HC checksum + block buffer sizing in the encoder.
- Streaming decoder side: parse BD bits 4-6 and size the per-frame
  block buffer accordingly (currently hardcoded to LZ4F_BLOCK_MAX).
  Drop the `bms != 4 → -ERR_UNSUPPORTED_FORMAT` reject in
  `lz4f_dec_write`'s BD-state arm.
- Streaming LZ4F per-block checksum (FLG bit 4): add a new
  `LDEC_STATE_BLOCK_CHECKSUM` between BLOCK_DATA and the next
  BLOCK_SIZE; consume 4 bytes LE, validate against
  `xxhash32(block_buf, block_size)`. Drop the `(fb >> 4) & 1 →
  -ERR_UNSUPPORTED_FORMAT` reject in `lz4f_dec_write`'s FLG-state arm.
  Encoder companion: add a corresponding emit option (gated by a new
  `lz4f_enc_init_*` parameter or a separate API).
- New benchmarks: same input, four block sizes, ratio + throughput
  per size. Verify each size's output against reference `lz4` CLI.

**Sizing:** medium. Encoder/decoder symmetry needs careful state-
machine work for the per-block checksum; the BD parameter plumbing
is well-scoped.

### 🎯 2.3.2 — DEFLATE throughput round 2

Continues the throughput investigation surfaced by sit v0.6.4
(2026-04-25). The three foundational down-payments landed in 2.1.0
(pre-reversed dynamic Huffman codes, 8-byte word-compare match
extension, ring-buffer match-finder); this release picks up what
was deferred or reverted.

**Scope:**
- Retry `good_length` early-exit in the chain walk at level ≥ 6.
  First attempt 2026-04-25 was reverted because sankoch's L6 chain
  depth of 64 was too shallow for the cut to bite on benchmarkable
  inputs. Retry options: (a) widen the bench input set with
  long-locality inputs that push deeper chain walks, (b) raise L6
  chain depth to 128 first and re-bench, (c) drop the early-exit and
  pick a different micro-optimization (e.g. tighter inner-loop
  scheduling). Decision lives in the P(-1) writeup.
- PCLMULQDQ CRC-32 via Cyrius inline asm. Cyrius 5.5.22+ exposes raw
  `asm { byte; byte; … }` blocks (see `lib/thread.cyr`
  `_thread_spawn`), so the toolchain gate has been clear since the
  5.6.x line. Reference: Intel "Fast CRC Computation for Generic
  Polynomials Using PCLMULQDQ Instruction" (whitepaper, Dec 2009).
  4–10× CRC-32 speedup on x86_64 expected.
- Wire-format identical — every change has to pass the byte-for-byte
  SIZE-line gate against the previous baseline.

**Target:** sit's `add-1MB` (currently ~150ms in `zlib_compress(1MB)`
out of 208ms total) wants a 5× zlib speedup to put `sit add` of a
1MB file under 100ms. Round 1 (2.1.0 down-payments) bought ~7-12%
on the streaming path; round 2 + PCLMULQDQ together should double
that.

**Sizing:** medium. PCLMULQDQ is contained; the L≥6 retry is a
think-first job.

### 🎯 2.3.3 — streaming-decode hardening (deferred 2.3.0 items + carried INFOs)

Rolls up the items the 2.3.0 bite ladder deferred plus three INFO
observations carried across the 2.1.3 / 2.2.3 audits. No single item
is large enough to justify its own minor; bundling them keeps the
2.3.x line moving.

**Scope:**
- **Streaming FDICT zlib.** Bite 4 (2.3.0) rejects FDICT-bearing
  zlib streams with `-ERR_UNSUPPORTED_FORMAT`. Full support needs a
  `deflate_dec_init_dict(dst, dst_cap, dict, dict_len)` companion
  to the bite-1 `deflate_dec_init` — preload the dict into a
  separate scratch region that back-references can reach (the
  existing batch `_deflate_decompress_dict_inner` stages dict at
  the start of dst and adjusts distances; the streaming variant
  needs an equivalent layout that survives chunk-boundary state
  saves). zlib wrapper extends to accept the dict + validate the
  4-byte DICTID against `adler32(dict)`.
- **Concatenated-member gzip streaming.** Bite 4 ships single-member
  only; batch `gzip_decompress` already handles concatenated streams.
  Streaming variant needs a per-member inner-DEFLATE reset (or
  fresh `deflate_dec_init` on each member) and a new
  `GDEC_STATE_AFTER_TRAILER` that probes for the next magic-or-EOF.
  Concatenated `gunzip` files from the wild (e.g. log rotators)
  motivate this.
- **gzip FHCRC verify** (INFO-01, carried from 2.1.3). Bite 4
  consumes the 2-byte FHCRC field but doesn't validate it; batch
  side has the same posture. Implement CRC-16-IBM (polynomial
  0xA001, ~30 LoC) and validate against the bytes from ID1 through
  the byte before FHCRC. Mirror in batch `_gzip_decompress_member`.
  Reference behavior: zlib's gunzip 1.5+ enforces; libdeflate, miniz,
  Go's `compress/gzip` skip — sankoch joins the "enforce" camp once
  a consumer surfaces FHCRC-bearing streams.
- **Lazy-global alloc-failure propagation** (INFO-A, carried from
  2.2.1 / 2.2.3). The defensive `_sankoch_alloc` wrapper currently
  covers 6 of the 41 alloc sites — the 35 lazy-global / arena allocs
  (Huffman tables, LZ77 hash, DEFLATE workspace, `_dyn_*` slabs,
  crc32_table, etc.) still abort on first-call OOM. Extend the
  pattern through internal callers: each lazy-init helper returns
  0 on alloc failure, propagated up to public API entry points
  which release the mutex + return 0. New fault-injection tests
  parallel to the existing 8 from 2.2.1, one per lazy-init site.
  Big surface-area change because error-return plumbing threads
  through many internal callers — that's why it was deferred from
  2.2.1.

**Sizing:** medium-large. FDICT streaming is the biggest piece;
multi-member gzip is medium; FHCRC verify and lazy-global hardening
are small individually but the test matrix for the alloc-fail
expansion is substantial.

### 🎯 2.3.4 — P(-1) closeout for the 2.3.x line

CLAUDE.md's P(-1) pre-feature checklist; closes the 2.3.x line and
is the entry door to 2.4.0+ work. Same template as the 2.1.3 / 2.2.3
/ 2.2.7 closeouts.

**Scope (per CLAUDE.md "P(-1): Scaffold Hardening"):**
- Cleanliness gates: `cyrius build` 0 warnings on the library path,
  `cyrius lint` 0 warnings, `cyrfmt --check` clean,
  `cyrius vet src/lib.cyr` clean.
- Test sweep: both tcyr suites green, all fuzz harnesses green.
- Benchmark baseline: full `cyrius bench tests/bcyr/sankoch.bcyr`
  CSV archived to `docs/benchmarks/` — reference for 2.4.0+.
- Internal deep review — gaps, optimization candidates, correctness
  questions surfaced during 2.3.0 / 2.3.1 / 2.3.2 / 2.3.3 work that
  didn't rise to a release on their own.
- External research — RFC errata sweep, zlib / reference `lz4` /
  reference gzip changes since the 2.2.3-era audit.
- Security audit — `docs/audit/2026-MM-DD-pre-2.4.0.md`. Specifically
  re-checks: the new `*_dec_*` state-machine paths for source-bounds
  bypasses (mirror of the HIGH-01 fix from 2.1.3); the
  bit-accumulator overpull rewind in zlib/gzip wrappers; the
  streaming-LZ4F block-buffer sizing under varied BD values
  (post-2.3.1); the new alloc-fail propagation paths (post-2.3.3).
- Follow-up on the three INFO observations carried into 2.3.x —
  most should be closed by 2.3.3 (lazy-global alloc-fail, FHCRC
  verify). Document remaining INFOs.
- Additional tests / benchmarks from findings.
- Documentation audit — CLAUDE.md, roadmap, CHANGELOG, README,
  cyrius-usage.md.

**Sizing:** medium. Mostly process; no API or source change
expected unless the audit surfaces something. If a finding wants
a non-trivial fix, P(-1) calls it out and 2.3.5 picks it up
before 2.4.0 starts.

---

## ⏸ Deferred — SIMD CRC-32 via `PCLMULQDQ`

Folded into the 2.3.2 scope above. Kept here as an explicit marker
in case 2.3.2 splits the L≥6 chain-walk work out from the SIMD
work (then PCLMULQDQ lands in 2.3.2 and the chain-walk retry moves
to its own slot).

---

## Future (separate crate or major version)

- **Zstandard** — tANS + LZ77. Shravan's Opus range encoder
  (`opus.cyr:175-284`) is the entropy-coding primitive tANS
  generalizes from. ~30K lines in the reference impl. Research
  Duda's ANS paper (arXiv:1311.2540) first.
- **LZMA** — LZ77 + range coding + LPC prediction. Shravan's FLAC
  LPC decoder (`flac.cyr:517-580`) is the prediction stage. The
  range coder from Opus covers the entropy stage.
- **Brotli** — if web serving needs arise.
- **GPU texture compression** (BC1-BC7, ASTC) — mabda has generic
  compute dispatch (`compute.cyr`). Texture format enums are
  defined but codecs not yet implemented.

### Primitive sources for future codecs

| Primitive | Home | File | Lines |
|-----------|------|------|-------|
| Rice/Golomb coding | shravan/FLAC | flac.cyr | 367-437 |
| Range encoder | shravan/Opus | opus.cyr | 175-284 |
| LPC prediction | shravan/FLAC | flac.cyr | 517-580 |
| GPU compute dispatch | mabda | compute.cyr | 142 lines |

---

## File Summary (at 2.3.0)

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
| lz4.cyr          |  835 | LZ4 block + frame compress + `lz4f_enc_*` + `lz4f_dec_*` streaming | full |
| deflate.cyr      | 2276 | DEFLATE de/compress, adaptive blocks, `deflate_enc_*` + `deflate_dec_*` streaming, dict | full |
| zlib.cyr         |  406 | RFC 1950 wrapper + FDICT batch + `zlib_enc_*` + `zlib_dec_*` streaming | full |
| gzip.cyr         |  531 | RFC 1952 wrapper + concatenated batch + `gzip_enc_*` + `gzip_dec_*` streaming | full |
| lib.cyr          |  193 | Public API, `_sankoch_mtx`, two-tier lock dispatch | full |
| stream.cyr       |  250 | Streaming dispatch (`stream_compress_*`, legacy buffered `stream_decompress_*`, incremental `stream_decompress_init_inc` / `_finish_inc`) | full |
| **Total**        | **6299** | | |

`core` modules (types + xxhash32 + lz4_decode = 300 source lines)
form `[lib.core]` → `dist/sankoch-core.cyr`. They contain no
`alloc()`, no syscalls, no mutex usage — verified by the CI
"Kernel-safe tripwire" gate (`programs/core_smoke.cyr`).

Tests: **156 distinct test functions** (146 sankoch.tcyr + 10
git_object.tcyr) producing **1,708,518 assertions** total
(1,361,935 + 346,583). Most of the assertion count comes from
per-byte round-trip loops on the streaming suites — a single 200 KB
round-trip contributes 200,000 assertions through one
`while (i < N) assert(byte_eq)` loop; the headline number measures
coverage *density*, not coverage *breadth*. See
[`../cyrius-usage.md`](../cyrius-usage.md#what-assertions-means-here-and-why-the-number-is-so-large)
for the full explanation.

Fuzz: 1,649 iterations across 6 harnesses (`fuzz_lz4` 700,
`fuzz_deflate` batch 340, `fuzz_zlib` 160, `fuzz_gzip` 160, plus
the four streaming variants and the tree-shape / skewed-freq
harnesses).

Distlib: `dist/sankoch.cyr` at 6,326 lines (full) +
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
- LZ4 Frame Format — github.com/lz4/lz4/blob/dev/doc/lz4_Frame_format.md
- Feldspar, "An Explanation of the Deflate Algorithm" — clearest DEFLATE walkthrough
- Intel, "Fast CRC Computation for Generic Polynomials Using PCLMULQDQ Instruction" (whitepaper, Dec 2009)
- Duda, "Asymmetric Numeral Systems" (arXiv:1311.2540) — for future Zstandard work

---

*Last Updated: 2026-05-23 (2.3.0 cut — true incremental decompression)*
