# Sankoch Development Roadmap

> **Status**: Stable (v2.4.1 — xz codec complete: decode + optimal-parse encode; 2.4.2 bzip2 decode next) | **Last Updated**: 2026-06-16

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

## v2.4.x ladder — full xz / bzip2 codecs

The arc opened decode-first (takumi-driven) and now closes the loop to
**full codecs** — own the whole stack, encode + decode, per the project
principle. Ladder:

| Slot      | Theme                         | Status            |
|-----------|-------------------------------|-------------------|
| 2.4.0     | xz / LZMA **decode**          | ✅ shipped 2026-06-16 |
| 2.4.1     | xz / LZMA **encode**          | ✅ shipped 2026-06-16 |
| **2.4.2** | bzip2 **decode**              | ← next            |
| 2.4.3     | bzip2 **encode**              | planned           |

**Decode** was the takumi gap: `extract_archive` handles `.tar` /
`.tar.gz` today (via `gzip_decompress`) but rejected `.tar.xz` /
`.tar.bz2` for lack of an LZMA / bzip2 path; 2.4.0 closed the xz half.
**Encode** is not required by takumi — it lands for stack ownership
(zero-FFI parity with the DEFLATE / zlib / gzip / LZ4 encoders this
library already ships) and to make `compress(FORMAT_XZ, …)` a real
round-trip partner to `decompress(FORMAT_XZ, …)`.

Each new `FORMAT_*` entry point and each new `*_compress` /
`*_decompress` is additive API → **minor bump** (hence 2.4.x, not
patch).

Consumer/conformance reference: takumi `src/source.cyr`
(`extract_archive` sniff + dispatch) and [takumi ADR 0002](https://github.com/MacCracken/takumi)
(`docs/adr/0002-source-extraction-safety.md`). Decode cuts let takumi
add the matching `FORMAT_*` sniff branch and lift the corresponding
rejection; encode cuts are validated against the reference CLIs
(`xz -d` / `bzip2 -d` must decode our output, and our decoder must
round-trip it).

### ✅ 2.4.0 — xz / LZMA decode — SHIPPED (2026-06-16)

Adds `xz_decompress` + `FORMAT_XZ` (= 6) and CRC-64/XZ. New module
[`src/xz.cyr`](../../src/xz.cyr) (~730 lines): `.xz` container parse
(stream header `FD 37 7A 58 5A 00` / block headers / index / stream
footer, all CRCs validated) → LZMA2 chunk framing (uncompressed +
LZMA chunks, dict/state/props resets) → LZMA core (range decoder +
literal/match state machine with rep-distance history). Concatenated
streams + stream padding + multi-block + `xz -T` threaded streams
decode; per-block check verified for CRC-32 / CRC-64 (SHA-256 / none
parsed, not hashed). Wired into `decompress()` + `detect_format()`.

Validated out-of-band: 700+ `xz`-vs-sankoch round-trips (sizes 1 B –
200 KB, random/zero/text/seq content, all four check types, levels
0–9e) + a real multi-file `.tar.xz`; in-suite: 9 `.tcyr` tests +
[`fuzz/fuzz_xz.fcyr`](../../fuzz/fuzz_xz.fcyr) (300 random + 200
corruption). Per-cut detail in [`CHANGELOG.md`](../../CHANGELOG.md).
**takumi** can now add the `FORMAT_XZ` sniff branch and lift its
`.tar.xz` rejection.

Two scope calls retained from the plan: **decode-only** (no encoder,
no legacy `.lzma` alone-format), and SHA-256 check fields are parsed
but not hashed (CRC-32 / CRC-64 only — SHA-256 isn't in this crate).

### ✅ 2.4.1 — xz / LZMA encode — SHIPPED (2026-06-16)

`xz_compress` + `compress(FORMAT_XZ, …)` — sankoch emits valid `.xz`
that `xz -d` decodes and our own `xz_decompress` round-trips. From-
scratch LZMA encoder in [`src/xz.cyr`](../../src/xz.cyr) (encode side
~1,000 lines) reusing the `lz77.cyr` match finder. Shipped in four
bites per the large-task discipline:

1. **Range encoder** — carry-propagating `ShiftLow`, `encode_bit`,
   `encode_direct`, bit-tree / reverse-bit-tree encoders, flush;
   verified bit-exact against the 2.4.0 decoder.
2. **Greedy scaffold** — symbol emit (literal / length / distance) +
   LZMA2 framing + xz container writer; first end-to-end `xz -d`
   round-trip.
3. **Optimal parse** — the user-chosen deliverable: a bounded forward
   DP (window `XZE_OPT_W`) minimizing modeled bit-price over literal /
   normal-match / rep-match / short-rep, rep history per path, prices
   from a `ProbPrices` table read against the live model, with a
   per-window length-price cache for the hot loops.
4. **Wiring** — public API, tcyr round-trip tests, encode→decode fuzz,
   a `bench` ratio/throughput section, docs.

**Numbers** (vs `xz -6`): within ~1–5 % on text/code, wider on
pathological repetition — stated, not claimed at parity (different
parse heuristics). The default check is **CRC-64** (matches `xz`).
Per-cut detail in [`CHANGELOG.md`](../../CHANGELOG.md). **Not** in the
wire-format SIZE gate (the encoder will keep being tuned). A throughput
pass on the optimal-parse DP is a candidate follow-on.

### 🎯 2.4.2 — bzip2 decode

Lower priority (legacy; rare for new releases, but still in the wild).
Adds `bzip2_decompress` + `FORMAT_BZIP2`.

**Scope:**
- `.bz2` stream parse (magic `BZh` + block magic
  `31 41 59 26 53 59`) + per-block CRC validation.
- Decode pipeline: Huffman decode → MTF (move-to-front) inverse →
  RLE2 → inverse BWT (Burrows-Wheeler) → RLE1. The inverse BWT is the
  non-obvious piece (build the transform vector, walk it).
- Conformance: round-trip reference `.tar.bz2` against `bzip2 -dc`;
  takumi adds the `FORMAT_BZIP2` sniff branch.

**Sizing:** medium-large. Inverse BWT + the MTF/RLE chain is
self-contained but spec-dense.

### 🎯 2.4.3 — bzip2 encode

Closes the bzip2 codec. Adds `bzip2_compress` + wires
`compress(FORMAT_BZIP2, …)`.

**Scope:**
- Encode pipeline (inverse of 2.4.2): RLE1 → **forward BWT** (suffix-
  array / block-sort — the hard, compute-heavy piece) → MTF → RLE2 →
  Huffman encode with the multi-table selector, per-block CRC.
- `.bz2` stream writer (`BZh` + level digit, block magic, stream
  footer magic `17 72 45 38 50 90` + combined CRC).
- Conformance: `bzip2 -d` decodes our output; our own
  `bzip2_decompress` round-trips.

**Sizing:** large. The forward BWT block-sort dominates; the rest is
the 2.4.2 chain run backwards.

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
> Current as of **2.4.1** (xz/LZMA encode — `src/xz.cyr` grew the encoder;
> lib dispatch touched).

| File | Lines | Role | Profile |
|------|-------|------|---------|
| types.cyr        |   39 | Enums: formats (incl. FORMAT_LZ4F, FORMAT_XZ), errors (incl. ERR_OOM), limits | core |
| xxhash32.cyr     |   94 | xxHash32 batch + helpers + XXH32 enum (kernel-safe) | core |
| checksum.cyr     |  502 | Adler-32 / CRC-32 (slice-by-8) / CRC-64-XZ + incremental state APIs (alloc-using) | full |
| bitreader.cyr    |  100 | LSB-first bit-stream reader | full |
| bitwriter.cyr    |  145 | LSB-first bit-stream writer | full |
| huffman.cyr      |  683 | Huffman build/decode, fixed + optimal trees, encoder pre-reversed codes (OOM-propagating allocs) | full |
| lz77.cyr         |  181 | Sliding window match-finder, 8-byte word-compare match extend, `lz77_rebase`, ring-buffer slide | full |
| lz4_decode.cyr   |  181 | LZ4 block + frame decompress (incl. per-block checksum) + LZ4F enum (kernel-safe) | core |
| lz4.cyr          |  935 | LZ4 block + frame compress + `lz4f_enc_*` (configurable block-max + checksum) + `lz4f_dec_*` streaming | full |
| deflate.cyr      | 2425 | DEFLATE de/compress, adaptive blocks, `deflate_enc_*` + `deflate_dec_*` streaming (+ `deflate_dec_reset` / `deflate_dec_init_dict`), dict, OOM-propagating table inits | full |
| zlib.cyr         |  451 | RFC 1950 wrapper + FDICT batch + streaming (`zlib_dec_init_dict`) + `zlib_enc_*` + `zlib_dec_*` | full |
| gzip.cyr         |  596 | RFC 1952 wrapper + concatenated batch/streaming + FHCRC verify + `gzip_enc_*` + `gzip_dec_*` streaming | full |
| xz.cyr           | 1738 | `.xz` de/compress: container + LZMA2 framing + LZMA range decoder/encoder, optimal-parse (`xz_decompress` / `xz_compress`) | full |
| lib.cyr          |  242 | Public API, `_sankoch_mtx`, two-tier lock dispatch, `_sankoch_alloc` + fault-injection + `_sankoch_reset_tables` | full |
| stream.cyr       |  250 | Streaming dispatch (`stream_compress_*`, legacy buffered `stream_decompress_*`, incremental `stream_decompress_init_inc` / `_finish_inc`) | full |
| **Total**        | **8562** | | |

`core` modules (types + xxhash32 + lz4_decode = 314 source lines)
form `[lib.core]` → `dist/sankoch-core.cyr`. They contain no
`alloc()`, no syscalls, no mutex usage — verified by the CI
"Kernel-safe tripwire" gate (`programs/core_smoke.cyr`).

Tests: **200 distinct test functions** (190 sankoch.tcyr + 10
git_object.tcyr) producing **4,326,194 assertions** total
(3,979,611 + 346,583). Most of the assertion count comes from
per-byte round-trip loops on the streaming suites — a single 200 KB
round-trip contributes 200,000 assertions through one
`while (i < N) assert(byte_eq)` loop; the headline number measures
coverage *density*, not coverage *breadth*. See
[`../cyrius-usage.md`](../cyrius-usage.md#what-assertions-means-here-and-why-the-number-is-so-large)
for the full explanation.

Fuzz: 2,449 iterations across 3 files (`fuzz_lz4` 700, `fuzz_deflate`
949 — batch 340 / zlib 160 / gzip 160 / four streaming variants /
tree-shape / skewed-freq, `fuzz_xz` 800 — 300 random-input + 200
corruption + 300 encode→decode round-trip).

Distlib: `dist/sankoch.cyr` at 8,541 lines (full) +
`dist/sankoch-core.cyr` at 314 lines (kernel-safe) — at 2.4.1
(+xz encoder in the full bundle; core unchanged).

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
- The .xz File Format v1.1.0 — tukaani.org/xz/xz-file-format.txt
- LZMA SDK `LzmaDec.c` / xz-embedded `xz_dec_lzma2.c` — LZMA decoder reference shape
- Feldspar, "An Explanation of the Deflate Algorithm" — clearest DEFLATE walkthrough
- Intel, "Fast CRC Computation for Generic Polynomials Using PCLMULQDQ Instruction" (whitepaper, Dec 2009)
- Duda, "Asymmetric Numeral Systems" (arXiv:1311.2540) — for future Zstandard work

---

*Last Updated: 2026-06-16 (2.4.1 cut — xz/LZMA optimal-parse encode shipped; xz codec complete. Next: 2.4.2 bzip2 decode, 2.4.3 bzip2 encode)*
