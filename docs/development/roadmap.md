# Sankoch Development Roadmap

> **Status**: Stable (v2.3.3) | **Last Updated**: 2026-06-16

Shipped history lives in `CHANGELOG.md`; this file is the forward
ladder. Items are ordered by release; scope per item is the working
contract — adjust if a P(-1) pass surfaces something that has to slot
in. Items further down can be re-ordered against new information.

> **Numbering note.** 2.3.1 and 2.3.2 shipped as cyrius pin-bump
> releases (→ 6.2.1, → 6.2.14) with no source change, consuming the
> two patch slots the feature ladder originally planned. The feature
> items were renumbered to 2.3.3+ accordingly; 2.3.3 (configurable
> LZ4F block-max + per-block checksum) has now shipped — see
> `CHANGELOG.md`. xz/bzip2 decode (takumi-driven) opens the 2.4.x
> line — additive `FORMAT_*` APIs are a minor bump.

---

## v2.3.x ladder (sequenced, post-2.3.3)

The 2.3.x line continues from the streaming-decompression cut (2.3.0)
through two pin-bump patches (2.3.1, 2.3.2) and the configurable-
block-max cut (2.3.3). The remaining pre-2.3.0 item (DEFLATE
throughput round 2) keeps its slot; the follow-on item rolls up the
deferred work from the 2.3.0 bite ladder plus carried INFOs from the
2.1.3 / 2.2.3 audits. P(-1) closes the line before 2.4.0 opens.

### 🎯 2.3.4 — DEFLATE throughput round 2

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

### 🎯 2.3.5 — streaming-decode hardening (deferred 2.3.0 items + carried INFOs)

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

### 🎯 2.3.6 — P(-1) closeout for the 2.3.x line

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
  questions surfaced during 2.3.0 / 2.3.3 / 2.3.4 / 2.3.5 work that
  didn't rise to a release on their own.
- External research — RFC errata sweep, zlib / reference `lz4` /
  reference gzip changes since the 2.2.3-era audit.
- Security audit — `docs/audit/2026-MM-DD-pre-2.4.0.md`. Specifically
  re-checks: the new `*_dec_*` state-machine paths for source-bounds
  bypasses (mirror of the HIGH-01 fix from 2.1.3); the
  bit-accumulator overpull rewind in zlib/gzip wrappers; the
  streaming-LZ4F block-buffer sizing under varied BD values
  (post-2.3.3); the new alloc-fail propagation paths (post-2.3.5).
- Follow-up on the three INFO observations carried into 2.3.x —
  most should be closed by 2.3.5 (lazy-global alloc-fail, FHCRC
  verify). Document remaining INFOs.
- Additional tests / benchmarks from findings.
- Documentation audit — CLAUDE.md, roadmap, CHANGELOG, README,
  cyrius-usage.md.

**Sizing:** medium. Mostly process; no API or source change
expected unless the audit surfaces something. If a finding wants
a non-trivial fix, P(-1) calls it out and 2.3.7 picks it up
before 2.4.0 starts.

---

## ⏸ Deferred — SIMD CRC-32 via `PCLMULQDQ`

Folded into the 2.3.4 scope above. Kept here as an explicit marker
in case 2.3.4 splits the L≥6 chain-walk work out from the SIMD
work (then PCLMULQDQ lands in 2.3.4 and the chain-walk retry moves
to its own slot).

---

## v2.4.x ladder — decode-only xz / bzip2 (takumi-driven)

Opens after the 2.3.x line closes (P(-1) at 2.3.6). Driven by
**takumi** source extraction: `extract_archive` in takumi handles
`.tar` and `.tar.gz` today (via `gzip_decompress`), but `.tar.xz`
and `.tar.bz2` are rejected because sankoch has no LZMA or bzip2
path. Many upstream source releases ship `.tar.xz`, so this is the
practical gap.

Scope is **decompression only** (extracting downloaded tarballs) —
the encoder side is *not* required and stays in the full-codec
Future bucket below. Decode-only is a much smaller effort than a
complete codec. Each new `FORMAT_*` + public `*_decompress` entry
point is additive API → **minor bump** (hence 2.4.x, not patch).

Consumer/conformance reference: takumi `src/source.cyr`
(`extract_archive` sniff + dispatch) and [takumi ADR 0002](https://github.com/MacCracken/takumi)
(`docs/adr/0002-source-extraction-safety.md`). Once each lands,
takumi adds the matching `FORMAT_*` sniff branch and lifts the
corresponding `.tar.xz` / `.tar.bz2` rejection.

### 🎯 2.4.0 — xz / LZMA decode

**Priority** (xz is the common modern source-tarball format; this is
what unblocks takumi). Adds `xz_decompress` / `lzma_decompress` +
`FORMAT_XZ`. Promotes the entropy/prediction stages noted under LZMA
in Future to a concrete decode-only deliverable.

**Scope:**
- `.xz` container parse (stream header magic `FD 37 7A 58 5A 00`,
  block headers, index, stream footer) + the LZMA2 chunk framing
  inside. CRC-32 / CRC-64 check fields validated against the inline
  checksums (CRC-64 is new — ~30 LoC table primitive alongside the
  existing CRC-32).
- LZMA decode core: range decoder (entropy stage) + LZ77-style
  match/literal model with the position/state context bits.
  Primitive starting points per the table below — Opus range coder
  for entropy, FLAC LPC for prediction scaffolding.
- Decode-only: no encoder, no `.lzma` (legacy alone-format) unless a
  consumer surfaces it.
- Conformance: round-trip reference `.tar.xz` source tarballs against
  `xz -dc`; takumi adds the `FORMAT_XZ` sniff branch.

**Sizing:** large. The range decoder + LZMA state model is the bulk;
take it in bites (container parse → range decoder → LZMA core →
takumi wiring), per CLAUDE.md large-task discipline.

### 🎯 2.4.1 — bzip2 decode

Lower priority (legacy; rare for new releases, but still in the wild).
Adds `bzip2_decompress` + `FORMAT_BZIP2`.

**Scope:**
- `.bz2` stream parse (magic `BZh` + block magic
  `31 41 59 26 53 59`) + per-block CRC validation.
- Decode pipeline: Huffman decode → MTF (move-to-front) inverse →
  RLE2 → inverse BWT (Burrows-Wheeler) → RLE1. The inverse BWT is the
  non-obvious piece (build the transform vector, walk it).
- Decode-only; no encoder.
- Conformance: round-trip reference `.tar.bz2` against `bzip2 -dc`;
  takumi adds the `FORMAT_BZIP2` sniff branch.

**Sizing:** medium-large. Inverse BWT + the MTF/RLE chain is
self-contained but spec-dense.

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

> Heading anchor kept stable (`#file-summary-at-230`) for the CLAUDE.md
> and state.md cross-links; figures below are refreshed every release.
> Current as of **2.3.3**.

| File | Lines | Role | Profile |
|------|-------|------|---------|
| types.cyr        |   37 | Enums: formats (incl. FORMAT_LZ4F), errors, limits | core |
| xxhash32.cyr     |   94 | xxHash32 batch + helpers + XXH32 enum (kernel-safe) | core |
| checksum.cyr     |  424 | Adler-32 / CRC-32 + incremental state APIs (alloc-using) | full |
| bitreader.cyr    |   99 | LSB-first bit-stream reader | full |
| bitwriter.cyr    |  145 | LSB-first bit-stream writer | full |
| huffman.cyr      |  661 | Huffman build/decode, fixed + optimal trees, encoder pre-reversed codes | full |
| lz77.cyr         |  179 | Sliding window match-finder, 8-byte word-compare match extend, `lz77_rebase`, ring-buffer slide | full |
| lz4_decode.cyr   |  181 | LZ4 block + frame decompress (incl. per-block checksum) + LZ4F enum (kernel-safe) | core |
| lz4.cyr          |  932 | LZ4 block + frame compress + `lz4f_enc_*` (configurable block-max + checksum) + `lz4f_dec_*` streaming | full |
| deflate.cyr      | 2276 | DEFLATE de/compress, adaptive blocks, `deflate_enc_*` + `deflate_dec_*` streaming, dict | full |
| zlib.cyr         |  406 | RFC 1950 wrapper + FDICT batch + `zlib_enc_*` + `zlib_dec_*` streaming | full |
| gzip.cyr         |  531 | RFC 1952 wrapper + concatenated batch + `gzip_enc_*` + `gzip_dec_*` streaming | full |
| lib.cyr          |  193 | Public API, `_sankoch_mtx`, two-tier lock dispatch | full |
| stream.cyr       |  250 | Streaming dispatch (`stream_compress_*`, legacy buffered `stream_decompress_*`, incremental `stream_decompress_init_inc` / `_finish_inc`) | full |
| **Total**        | **6408** | | |

`core` modules (types + xxhash32 + lz4_decode = 312 source lines)
form `[lib.core]` → `dist/sankoch-core.cyr`. They contain no
`alloc()`, no syscalls, no mutex usage — verified by the CI
"Kernel-safe tripwire" gate (`programs/core_smoke.cyr`).

Tests: **177 distinct test functions** (167 sankoch.tcyr + 10
git_object.tcyr) producing **4,208,566 assertions** total
(3,861,983 + 346,583). Most of the assertion count comes from
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

Distlib: `dist/sankoch.cyr` at 6,388 lines (full) +
`dist/sankoch-core.cyr` at 312 lines (kernel-safe) — at 2.3.3.

## Dependencies

**Zero external.** Checksums (Adler-32, CRC-32, xxHash32 — batch and
incremental) are inline. No sigil dependency. Stdlib-only: `syscalls`,
`string`, `alloc`, `fmt`, `vec`, `fnptr`, `thread`, `assert` (all
ship with Cyrius ≥ 6.0.1; pin is 6.2.14).

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

*Last Updated: 2026-06-16 (2.3.3 cut — configurable LZ4F block-max + per-block checksum)*
