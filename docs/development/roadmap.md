# Sankoch Development Roadmap

> **Status**: Stable (v2.5.2) | **Last Updated**: 2026-07-18

Shipped history lives in `CHANGELOG.md`; this file is the **forward**
ladder — backlog, deferred items, known limitations, and the
longer-horizon Future bucket. **No release is currently committed.** The
codec set is complete — LZ4 / LZ4F / DEFLATE / zlib / gzip / xz / bzip2,
de + compress, batch + streaming — with ratio-capped decompression for
the DEFLATE family (batch + streaming).

---

## ▢ Backlog — candidate follow-ons (none scheduled)

- **xz / bzip2 ratio cap** — extend the DEFLATE-family ratio cap (2.4.5
  batch `*_with_ratio_cap` + 2.4.6 streaming `*_dec_init_capped`) to xz
  and bzip2 decode. Both funnel output through localized chokepoints
  (`_xz_put` / `_xz_copy_match`; the bzip2 RLE1 run-emit), so the same
  incremental `ERR_RATIO_LIMIT` guard applies. Not needed by sit (zlib
  only); pick up if a consumer inflates untrusted `.xz` / `.bz2`.
- **xz / bzip2 encoder throughput** — the optimal-parse DP (xz) and the
  BWT block-sort (bzip2) dominate encode time. Fine for the
  archival / one-shot use they target; revisit if encode latency
  surfaces as a consumer priority.

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

## Known limitations / non-goals

- **xz**: SHA-256 check fields are parsed but not verified (CRC-32 /
  CRC-64 only — SHA-256 isn't in this crate); the legacy `.lzma`
  alone-format is not handled. xz encode is within ~1–5 % of `xz -6`
  (optimal parse, not bit-identical to `xz`); bzip2 encode is
  byte-identical to `bzip2 -9`. Neither encoder is in the wire-format
  SIZE gate — both ship informational ratio lines in `bench`.
- **Zstandard** is intentionally out of scope for this crate — it
  warrants its own crate / major version (see Future).

---

## Future (separate crate or major version)

- **Zstandard** — tANS + LZ77. Shravan's Opus range encoder
  (`opus.cyr:175-284`) is the entropy-coding primitive tANS
  generalizes from. ~30K lines in the reference impl. Research
  Duda's ANS paper (arXiv:1311.2540) first.
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
> Current as of **2.4.6** (streaming ratio cap — `deflate.cyr` / `zlib.cyr`
> / `gzip.cyr` grew the `*_dec_init_capped` plumbing atop the 2.4.5 batch
> `*_with_ratio_cap`; `lib.cyr` reflects the 2.4.4 agnos lock no-op).

| File | Lines | Role | Profile |
|------|-------|------|---------|
| types.cyr        |   41 | Enums: formats (incl. FORMAT_XZ, FORMAT_BZIP2), errors (incl. ERR_OOM, ERR_RATIO_LIMIT), limits | core |
| xxhash32.cyr     |   94 | xxHash32 batch + helpers + XXH32 enum (kernel-safe) | core |
| checksum.cyr     |  546 | Adler-32 / CRC-32 (slice-by-8) / CRC-64-XZ / CRC-32-BZIP2 + incremental state APIs (alloc-using) | full |
| bitreader.cyr    |  100 | LSB-first bit-stream reader | full |
| bitwriter.cyr    |  145 | LSB-first bit-stream writer | full |
| huffman.cyr      |  683 | Huffman build/decode, fixed + optimal trees, encoder pre-reversed codes (OOM-propagating allocs) | full |
| lz77.cyr         |  181 | Sliding window match-finder, 8-byte word-compare match extend, `lz77_rebase`, ring-buffer slide | full |
| lz4_decode.cyr   |  181 | LZ4 block + frame decompress (incl. per-block checksum) + LZ4F enum (kernel-safe) | core |
| lz4.cyr          |  935 | LZ4 block + frame compress + `lz4f_enc_*` (configurable block-max + checksum) + `lz4f_dec_*` streaming | full |
| deflate.cyr      | 2540 | DEFLATE de/compress, adaptive blocks, `deflate_enc_*` + `deflate_dec_*` streaming (+ `deflate_dec_reset` / `deflate_dec_init_dict` / `deflate_dec_init_capped`), dict, OOM-propagating table inits, `deflate_decompress_with_ratio_cap` + shared `_deflate_ratio_ceiling` | full |
| zlib.cyr         |  485 | RFC 1950 wrapper + FDICT batch + streaming (`zlib_dec_init_dict` / `zlib_dec_init_capped`) + `zlib_enc_*` + `zlib_dec_*` + `zlib_decompress_with_ratio_cap` | full |
| gzip.cyr         |  638 | RFC 1952 wrapper + concatenated batch/streaming + FHCRC verify + `gzip_enc_*` + `gzip_dec_*` streaming (+ `gzip_dec_init_capped`) + `gzip_decompress_with_ratio_cap` (cumulative cap) | full |
| xz.cyr           | 1738 | `.xz` de/compress: container + LZMA2 framing + LZMA range decoder/encoder, optimal-parse (`xz_decompress` / `xz_compress`) | full |
| bzip2.cyr        | 1239 | `.bz2` de/compress: bit reader/writer + Huffman + MTF/RLE2 + inverse/forward BWT + RLE1 (`bzip2_decompress` / `bzip2_compress`) | full |
| lib.cyr          |  282 | Public API, `_sankoch_mtx`, two-tier lock dispatch (agnos no-op since 2.4.4), `_sankoch_alloc` + fault-injection + `_sankoch_reset_tables` | full |
| stream.cyr       |  250 | Streaming dispatch (`stream_compress_*`, legacy buffered `stream_decompress_*`, incremental `stream_decompress_init_inc` / `_finish_inc`) | full |
| **Total**        | **10078** | | |

`core` modules (types + xxhash32 + lz4_decode = 316 source lines)
form `[lib.core]` → `dist/sankoch-core.cyr`. They contain no
`alloc()`, no syscalls, no mutex usage — verified by the CI
"Kernel-safe tripwire" gate (`programs/core_smoke.cyr`).

Tests: **234 distinct test functions** (224 across the 18 split
codec×direction suites + 10 in git_object.tcyr) producing
**4,483,834 assertions** total (4,137,251 + 346,583). Most comes from
per-byte round-trip loops on the streaming suites — a single 200 KB
round-trip contributes 200,000 assertions through one
`while (i < N) assert(byte_eq)` loop; the headline number measures
coverage *density*, not coverage *breadth*. See
[`../cyrius-usage.md`](../cyrius-usage.md#what-assertions-means-here-and-why-the-number-is-so-large)
for the full explanation.

Fuzz: 3,929 iterations across 4 files (`fuzz_lz4` 700, `fuzz_deflate`
1,629 — incl. batch ratio-cap 240 + malformed 100 + streaming ratio-cap
240 + streaming malformed 100, `fuzz_xz` 800 — 300 random + 200
corruption + 300 encode→decode, `fuzz_bzip2` 800 — 300 random + 200
corruption + 300 encode→decode).

Distlib: `dist/sankoch.cyr` at 10,056 lines (full) +
`dist/sankoch-core.cyr` at 316 lines (kernel-safe) — at 2.4.6
(streaming-cap plumbing added to the full bundle; core unchanged at 316,
the +1 `ERR_RATIO_LIMIT` enum line having landed at 2.4.5).

## Dependencies

**Zero external.** Checksums (Adler-32, CRC-32, xxHash32 — batch and
incremental) are inline. No sigil dependency. Stdlib-only: `syscalls`,
`string`, `alloc`, `fmt`, `vec`, `fnptr`, `thread`, `assert` (all
ship with Cyrius ≥ 6.0.1; pin is 6.4.66).

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

*Last Updated: 2026-07-18 (2.5.2 cut — toolchain pin refresh to Cyrius 6.4.66; no source change. Next: xz/bzip2 ratio-cap follow-on, or the Future bucket.)*
