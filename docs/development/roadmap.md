# Sankoch Development Roadmap

> **Status**: Stable (v2.3.8 — 2.3.x line closed) | **Last Updated**: 2026-06-16

Shipped history lives in `CHANGELOG.md`; this file is the forward
ladder. Items are ordered by release; scope per item is the working
contract — adjust if a P(-1) pass surfaces something that has to slot
in. Items further down can be re-ordered against new information.

> **Numbering note.** 2.3.1 and 2.3.2 shipped as cyrius pin-bump
> releases (→ 6.2.1, → 6.2.14) with no source change, consuming the
> two patch slots the feature ladder originally planned. The feature
> items were renumbered to 2.3.3+ accordingly. Shipped since:
> **2.3.3** (configurable LZ4F block-max + per-block checksum),
> **2.3.4** (CRC-32 slice-by-8 + cyrius pin → 6.2.15), **2.3.5** (gzip
> streaming hardening — FHCRC verify + concatenated members), **2.3.6**
> (streaming FDICT zlib), **2.3.7** (lazy-global alloc-fail propagation,
> INFO-A), **2.3.8** (P(-1) closeout — 2.3.x line closed) — see
> `CHANGELOG.md`. **The 2.3.x line is complete.** Next is the 2.4.x
> decode-only xz/bzip2 (takumi-driven) arc — additive `FORMAT_*` APIs,
> a minor bump.

---

## ✅ v2.3.x line — COMPLETE

Shipped, in order: **2.3.0** streaming decompression · **2.3.1 / 2.3.2**
cyrius pin bumps (6.2.1, 6.2.14) · **2.3.3** configurable LZ4F block-max
+ per-block checksum · **2.3.4** CRC-32 slice-by-8 + pin 6.2.15 ·
**2.3.5** gzip FHCRC verify + concatenated-member streaming · **2.3.6**
streaming FDICT zlib · **2.3.7** lazy-global alloc-fail propagation
(INFO-A closed) · **2.3.8** P(-1) closeout. Per-cut detail is in
`CHANGELOG.md`; the 2.3.8 audit + benchmark baseline are in
[`docs/audit/2026-06-16-pre-2.4.0.md`](../audit/2026-06-16-pre-2.4.0.md)
and [`docs/benchmarks/2026-06-16-pre-2.4.0.md`](../benchmarks/2026-06-16-pre-2.4.0.md).

Two scope calls worth remembering when the relevant work resurfaces:

- **2.3.4 "DEFLATE throughput round 2" was partially delivered.** CRC-32
  throughput landed as a portable **slice-by-8** rewrite (~2×, wire-
  identical) rather than PCLMULQDQ. The `good_match` chain-walk early-
  exit was implemented, measured, and **dropped** — it is wire-safe only
  where it gives no speedup and faster only where it changes the selected
  matches (breaking the SIZE gate). The deeper DEFLATE match-finder
  throughput question (and PCLMULQDQ) carries to the deferred markers
  below.
- The original bundled "2.3.5 streaming hardening" slot was unwound
  across 2.3.5 / 2.3.6 / 2.3.7 (small-bites rule) rather than shipped as
  one large release.

---

## ⏸ Deferred — SIMD CRC-32 via `PCLMULQDQ`

2.3.4 covered the CRC-32 throughput goal with a portable **slice-by-8**
table fold (~2×, x86_64 + aarch64, wire-identical), so PCLMULQDQ is no
longer on the critical path. It stays deferred as an x86-only further
optimization: the aarch64 cross-build gate would need a parallel PMULL
path or a scalar fallback, and hand-assembled CRC-folding bytes carry a
silent-corruption risk that has to clear a high bar to be worth it over
the slice-by-8 baseline. Revisit only if a consumer's profile shows
CRC-32 back on the hot path. Reference: Intel "Fast CRC Computation …
Using PCLMULQDQ" (whitepaper, Dec 2009).

## ⏸ Deferred — DEFLATE match-finder throughput

The wire-identical mandate blocks the obvious match-finder speedups
(`good_match` and friends are speed/ratio tradeoffs that change output).
A genuine win here needs an optimization that finds the *same* matches
faster — e.g. tighter chain-walk scheduling, a better hash, or a
lazy-match restructure that provably preserves output. Open-ended;
pick up if sit's `zlib_compress(1MB)` target resurfaces as a priority.

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
> Current as of **2.3.8** (P(-1) closeout — no source change vs 2.3.7).

| File | Lines | Role | Profile |
|------|-------|------|---------|
| types.cyr        |   38 | Enums: formats (incl. FORMAT_LZ4F), errors (incl. ERR_OOM), limits | core |
| xxhash32.cyr     |   94 | xxHash32 batch + helpers + XXH32 enum (kernel-safe) | core |
| checksum.cyr     |  427 | Adler-32 / CRC-32 (slice-by-8) + incremental state APIs (alloc-using) | full |
| bitreader.cyr    |  100 | LSB-first bit-stream reader | full |
| bitwriter.cyr    |  145 | LSB-first bit-stream writer | full |
| huffman.cyr      |  683 | Huffman build/decode, fixed + optimal trees, encoder pre-reversed codes (OOM-propagating allocs) | full |
| lz77.cyr         |  181 | Sliding window match-finder, 8-byte word-compare match extend, `lz77_rebase`, ring-buffer slide | full |
| lz4_decode.cyr   |  181 | LZ4 block + frame decompress (incl. per-block checksum) + LZ4F enum (kernel-safe) | core |
| lz4.cyr          |  935 | LZ4 block + frame compress + `lz4f_enc_*` (configurable block-max + checksum) + `lz4f_dec_*` streaming | full |
| deflate.cyr      | 2425 | DEFLATE de/compress, adaptive blocks, `deflate_enc_*` + `deflate_dec_*` streaming (+ `deflate_dec_reset` / `deflate_dec_init_dict`), dict, OOM-propagating table inits | full |
| zlib.cyr         |  451 | RFC 1950 wrapper + FDICT batch + streaming (`zlib_dec_init_dict`) + `zlib_enc_*` + `zlib_dec_*` | full |
| gzip.cyr         |  596 | RFC 1952 wrapper + concatenated batch/streaming + FHCRC verify + `gzip_enc_*` + `gzip_dec_*` streaming | full |
| lib.cyr          |  223 | Public API, `_sankoch_mtx`, two-tier lock dispatch, `_sankoch_alloc` + fault-injection + `_sankoch_reset_tables` | full |
| stream.cyr       |  250 | Streaming dispatch (`stream_compress_*`, legacy buffered `stream_decompress_*`, incremental `stream_decompress_init_inc` / `_finish_inc`) | full |
| **Total**        | **6729** | | |

`core` modules (types + xxhash32 + lz4_decode = 313 source lines)
form `[lib.core]` → `dist/sankoch-core.cyr`. They contain no
`alloc()`, no syscalls, no mutex usage — verified by the CI
"Kernel-safe tripwire" gate (`programs/core_smoke.cyr`).

Tests: **182 distinct test functions** (172 sankoch.tcyr + 10
git_object.tcyr) producing **4,209,075 assertions** total
(3,862,492 + 346,583). Most of the assertion count comes from
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

Distlib: `dist/sankoch.cyr` at 6,709 lines (full) +
`dist/sankoch-core.cyr` at 313 lines (kernel-safe) — at 2.3.8
(version-line only vs 2.3.7).

## Dependencies

**Zero external.** Checksums (Adler-32, CRC-32, xxHash32 — batch and
incremental) are inline. No sigil dependency. Stdlib-only: `syscalls`,
`string`, `alloc`, `fmt`, `vec`, `fnptr`, `thread`, `assert` (all
ship with Cyrius ≥ 6.0.1; pin is 6.2.15).

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

*Last Updated: 2026-06-16 (2.3.8 cut — P(-1) closeout; 2.3.x line complete, 2.4.0 next)*
