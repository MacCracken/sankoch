# Sankoch Development Roadmap

> **Status**: Stable (v2.6.4) — ZIP surface P(-1)-audited and cleared | **Last Updated**: 2026-07-20

This file is the **forward** ladder — what is in progress, the committed
next-release ladder, and the longer-horizon Future bucket. **Shipped history
lives in [`CHANGELOG.md`](../../CHANGELOG.md); the live per-release snapshot
lives in [`state.md`](state.md).** This file does not re-list what shipped.

**Where the library stands.** Every lossless codec de+compresses — LZ4 / LZ4F /
DEFLATE / zlib / gzip / xz / bzip2 / zstd — with ratio-capped decompression
across the DEFLATE family + xz + bzip2, a shared tar cursor, and a full PKZIP
`.zip` container (reader + writer, every method sankoch owns, Zip64, streaming,
tar-parity metadata). The zstd encoder beats `zstd -3` on every benchmark
fixture; the zstd decoder is hardened against hostile input. Two P(-1) security
audits have run — the pre-2.6.0 pass over the 2.4.x/2.5.x codec surface, and the
2.6.4 pass over the ZIP surface (0 HIGH · 3 MEDIUM · 1 LOW confirmed, all fixed;
dossier: [`docs/audit/2026-07-20-zip-container.md`](../audit/2026-07-20-zip-container.md)).

**What remains is performance and ratio polish**, promoted below into a committed
**2.7.x ladder** — no new formats are needed for any current consumer.

---

## ▶ Scheduled — the 2.7.x performance & ratio ladder

The 2.6.x line completes the feature surface. 2.7.x is the deferred
performance/ratio work, promoted into a committed ladder, **highest-value
first**. Each is a measured gap, not a guess.

### 2.7.0 — xz encoder match finder (the largest measured gap)

The 2.5.9 P(-1) baseline measured xz encode at **~0.07–0.16 MB/s — roughly
400–900× slower than reference `xz -6`** for equal-or-better ratio (1 MB of
zeros: 14.8 s vs ~16 ms; 1 MB of text: 6.4 s). Scaling is *linear*, so it is a
constant factor, not an algorithmic blow-up: reference xz uses a BT4 binary-tree
match finder with hash-chain skipping, while sankoch walks a plain chain and
prices every position. This is the **largest measured performance gap in the
tree**, and `takumi` is an xz-encode consumer (a 4 MB source tarball takes
25–57 s). It survived the 2.5.4 throughput pass, so closing it means a **new
match finder** (BT4 or a hash-chain with skip/`good_length` cutoffs), not
micro-optimisation. Output need not stay bit-identical (xz encode already isn't,
and is excluded from the wire-format SIZE gate) — only `xz -d`-decodable and
within the current ~1–5 % ratio band. Numbers:
[`docs/benchmarks/2026-07-19-2.5.9-p1-baseline.md`](../benchmarks/2026-07-19-2.5.9-p1-baseline.md).
Likely several bites (match finder → optimal-parse integration → tuning).

### 2.7.1 — zstd optimal / 2-pass parse

The residue after the 2.5.8 priced parse: on *very regular record* data
(synthetic csv, log lines) zstd's optimal parse finds longer cross-record
matches than sankoch's greedy+lazy+repcode hash chain. This was the original
2.5.8 slot; a **working DP probe was built and measured** before being deferred —
it reached 251,733 B on the 7-fixture corpus (vs the shipped priced parse's
251,333 B, i.e. *worse on total*) but **−3.6 % on real source/binary
specifically** (vs the priced parse's −0.5 %), at ~400 added lines, ~224 KiB of
DP arrays, and 4–74× encode time. So it is a real win on real data at a real
cost — worth doing as its own release, gated behind the higher levels
(`zstd_compress_level` 7–9) so the default stays fast. The probe implementation
is preserved at `/home/macro/Repos/sankoch-deferred-dp-2.5.8.diff` as the
starting point. Reference `zstd -d` stays the correctness bar. The DP prices each
candidate under the current FSE tables and picks the globally cheaper path;
per-DP-node rep state and a 2-pass statistics refit are the known-hard parts (see
the 2.5.8 dossier).

### Conditional — scheduled only when a consumer profile surfaces it

Both of these have a *sound reason to wait*: the cheap win is already banked, and
the expensive version carries a correctness or portability risk that only a real
hot-path profile justifies. They slot into the 2.7.x ladder if that profile
appears; until then, scheduling them would be dishonest.

- **SIMD CRC-32 via `PCLMULQDQ`.** 2.3.4 already covered the CRC-32 throughput
  goal with a portable **slice-by-8** table fold (~2×, x86_64 + aarch64,
  wire-identical), so PCLMULQDQ is off the critical path. It remains an x86-only
  further optimisation: the aarch64 gate would need a parallel PMULL path or a
  scalar fallback, and hand-assembled CRC-folding carries a silent-corruption
  risk that must clear a high bar over the slice-by-8 baseline. Revisit only if a
  consumer's profile shows CRC-32 back on the hot path. Ref: Intel "Fast CRC
  Computation … Using PCLMULQDQ" (whitepaper, Dec 2009).
- **DEFLATE match-finder throughput.** The wire-identical mandate (zlib
  byte-for-byte parity is load-bearing) blocks the obvious speedups —
  `good_match` and friends are speed/ratio trade-offs that change output. A
  genuine win needs an optimisation that finds the *same* matches faster (tighter
  chain-walk scheduling, a better hash, or a provably output-preserving
  lazy-match restructure). Open-ended; pick up if sit's `zlib_compress(1 MB)`
  target resurfaces as a priority.

---

## ZIP container — deliberately not there

**Non-goals** (like the codec non-goals): **encryption** — ZipCrypto is
cryptographically broken, and AES-in-ZIP needs a real AES primitive sankoch
deliberately doesn't carry (zero-crypto-dep, cf. xz's unverified SHA-256);
**multi-disk / spanned** archives (obsolete); **Deflate64** (method 9 — a
separate codec, not RFC 1951).

---

## Known limitations / non-goals

- **xz**: `--check=sha256` streams are **rejected** (`ERR_UNSUPPORTED_FORMAT`)
  since 2.5.9 — sankoch carries no SHA-256 primitive, so it fails closed rather
  than accept an unverified payload (CRC-32 / CRC-64 checks are verified). The
  legacy `.lzma` alone-format is not handled. xz encode is within ~1–5 % of
  `xz -6` (optimal parse, not bit-identical to `xz`) but ~400–900× slower — the
  2.7.0 target above; bzip2 encode is byte-identical to `bzip2 -9`. Neither
  encoder is in the wire-format SIZE gate — both ship informational ratio lines
  in `bench`.

---

## Future — additional codecs (in-scope, unscheduled)

Because the per-codec distlib profiles let a consumer pull only the
closure it needs (see *Modular by profile* in [`CLAUDE.md`](../../CLAUDE.md)),
sankoch is the home for **every** lossless-compression codec — new formats
never bloat consumers that don't use them, so nothing here is "a separate
crate." These are simply not yet implemented:

- **Brotli** — DEFLATE-family with a static dictionary + context modeling;
  land it when a web-serving / font consumer needs it.
- **GPU texture compression** (BC1-BC7, ASTC) — the one genuinely
  different beast (lossy, GPU-format-specific); mabda has generic compute
  dispatch (`compute.cyr`) and the texture format enums, but no codecs
  yet. May instead live with mabda — decide when a consumer surfaces.

(Zstandard is no longer here — decode shipped 2.5.0, the sovereign encoder
shipped 2.5.5, and it now beats `zstd -3` on every benchmark fixture. Its one
remaining ratio residue is the 2.7.1 optimal-parse item above, not a new codec.)

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
> Current as of **2.5.8** — the tree grew from 16 to 19 modules: `runtime.cyr`
> (the lock + alloc seam, extracted from `lib.cyr` at 2.4.9) plus `zstd.cyr`
> (sovereign RFC-8878 decoder) and `tar.cyr` (POSIX ustar/v7 cursor) at 2.5.0.

| File | Lines | Role | Profile |
|------|-------|------|---------|
| types.cyr        |   42 | Enums: formats (incl. FORMAT_XZ, FORMAT_BZIP2, FORMAT_ZSTD), errors (incl. ERR_OOM, ERR_RATIO_LIMIT), limits | core |
| xxhash32.cyr     |   94 | xxHash32 batch + helpers + XXH32 enum (kernel-safe) | core |
| checksum.cyr     |  546 | Adler-32 / CRC-32 (slice-by-8) / CRC-64-XZ / CRC-32-BZIP2 + incremental state APIs (alloc-using) | full |
| bitreader.cyr    |  100 | LSB-first bit-stream reader | full |
| bitwriter.cyr    |  145 | LSB-first bit-stream writer | full |
| huffman.cyr      |  683 | Huffman build/decode, fixed + optimal trees, encoder pre-reversed codes (OOM-propagating allocs) | full |
| lz77.cyr         |  184 | Sliding window match-finder, 8-byte word-compare match extend, `lz77_rebase`, ring-buffer slide | full |
| lz4_decode.cyr   |  181 | LZ4 block + frame decompress (incl. per-block checksum) + LZ4F enum (kernel-safe) | core |
| lz4.cyr          |  935 | LZ4 block + frame compress + `lz4f_enc_*` (configurable block-max + checksum) + `lz4f_dec_*` streaming | full |
| deflate.cyr      | 2545 | DEFLATE de/compress, adaptive blocks, `deflate_enc_*` + `deflate_dec_*` streaming (+ `deflate_dec_reset` / `deflate_dec_init_dict` / `deflate_dec_init_capped`), dict, OOM-propagating table inits, `deflate_decompress_with_ratio_cap` + shared `_deflate_ratio_ceiling` | full |
| zlib.cyr         |  485 | RFC 1950 wrapper + FDICT batch + streaming (`zlib_dec_init_dict` / `zlib_dec_init_capped`) + `zlib_enc_*` + `zlib_dec_*` + `zlib_decompress_with_ratio_cap` | full |
| gzip.cyr         |  650 | RFC 1952 wrapper + concatenated batch/streaming + FHCRC verify + `gzip_enc_*` + `gzip_dec_*` streaming (+ `gzip_dec_init_capped`) + `gzip_decompress_with_ratio_cap` (cumulative cap) | full |
| xz.cyr           | 1836 | `.xz` de/compress: container + LZMA2 framing + LZMA range decoder/encoder, optimal-parse (`xz_decompress` / `xz_compress`) + `xz_decompress_with_ratio_cap` (2.5.3) | full |
| bzip2.cyr        | 1323 | `.bz2` de/compress: bit reader/writer + Huffman + MTF/RLE2 + inverse/forward BWT + RLE1 (`bzip2_decompress` / `bzip2_compress`) + `bzip2_decompress_with_ratio_cap` (2.5.3) | full |
| zstd.cyr         | 2384 | `.zst` de+compress (RFC 8878): decoder (2.5.0, hardened 2.5.6) + sovereign `zstd_compress` encoder (2.5.5 — LZ77 hash-chain matcher + FSE sequence encoder + length-limited Huffman literals, single/4-stream; adaptive FSE sequence tables 2.5.7; **priced match selection `_ze_mvalue` 2.5.8**); self-contained bit reader / FSE / Huffman, no runtime | full |
| zip.cyr          | 1206 | PKZIP `.zip` container: in-memory reader + writer, methods 0/8, Zip64 (2.6.2), streaming write + data descriptors + Unix metadata/symlinks (2.6.3), CRC-32 verified, per-member ratio cap; 2.6.4 P(-1) hardening — i64-overflow-safe Zip64 bounds (subtraction form), streaming-abandon lock release, mid-stream-add rejection, name-length limit, cross-entry symlink ledger | full |
| zip_methods.cyr  |  150 | The rest of ZIP's methods (2.6.1): 12 (bzip2) / 93 (zstd) / 95 (xz), read + write. Kept OUT of `[lib.zip]` so the lean profile never pulls those codecs | full |
| tar.cyr          |  710 | Sovereign POSIX ustar + pre-POSIX v7 tar pull-cursor (`tar_open_auto` sniffs gzip/xz/bzip2/zstd); PAX/GNU long-name + two-layer path-traversal guards incl. the 2.5.9 cross-entry symlink ledger (H-1) + parse-path OOM guards (M-3) | full |
| stream.cyr       |  256 | Streaming dispatch (`stream_compress_*`, legacy buffered `stream_decompress_*`, incremental `stream_decompress_init_inc` / `_finish_inc`) | full |
| runtime.cyr      |   73 | Shared runtime seam: `_sankoch_mtx` + two-tier lock (agnos no-op since 2.4.4) + `_sankoch_alloc` arena + fault injection — extracted from `lib.cyr` (2.4.9) so lean profiles pull it without the format-dispatch API | full |
| lib.cyr          |  265 | Include chain + public API + format dispatch + `_sankoch_reset_tables` (references every codec's lazy globals) | full |
| **Total**        | **14796** | | |

`core` modules (types + xxhash32 + lz4_decode = 317 source lines)
form `[lib.core]` → `dist/sankoch-core.cyr`. They contain no
`alloc()`, no syscalls, no mutex usage — verified by the CI
"Kernel-safe tripwire" gate (`programs/core_smoke.cyr`).

Tests: **293 distinct test functions** (283 across the 20 split
codec×direction suites + 10 in git_object.tcyr) producing
**4,484,493 assertions** total (4,137,910 + 346,583). Most comes from
per-byte round-trip loops on the streaming suites — a single 200 KB
round-trip contributes 200,000 assertions through one
`while (i < N) assert(byte_eq)` loop; the headline number measures
coverage *density*, not coverage *breadth*. See
[`../cyrius-usage.md`](../cyrius-usage.md#what-assertions-means-here-and-why-the-number-is-so-large)
for the full explanation.

Fuzz: 6,999 iterations across 6 files (`fuzz_lz4` 700, `fuzz_deflate`
1,629, `fuzz_xz` 1,000, `fuzz_bzip2` 900, `fuzz_zstd` 1,150, `fuzz_zip`
1,620 — 300 random + 120 truncation + 300 corruption + 300 hostile-field
+ 200 writer + 200 streaming + 200 Zip64 hostile-offset). Per-file
breakdown in [`state.md` § Fuzz totals](state.md#fuzz-totals).

Distlib: `dist/sankoch.cyr` at 14,843 lines (full) +
`dist/sankoch-core.cyr` at 332 lines (kernel-safe), plus eight lean
single-purpose profiles — `sankoch-zlib.cyr` (4,933),
`sankoch-gzip.cyr` (5,098), `sankoch-xz.cyr` (2,799),
`sankoch-bzip2.cyr` (2,099), `sankoch-zstd.cyr` (2,514),
`sankoch-tar.cyr` (11,363), `sankoch-zip.cyr` (5,654, methods 0/8) and
`sankoch-zipall.cyr` (11,359, every method). Ten profiles total;
per-bundle roles in [`state.md` § Dist bundles](state.md#dist-bundles).

## Dependencies

**Zero external.** Checksums (Adler-32, CRC-32, xxHash32 — batch and
incremental) are inline. No sigil dependency. Stdlib-only: `syscalls`,
`string`, `alloc`, `fmt`, `vec`, `fnptr`, `thread`, `assert` (all
ship with Cyrius ≥ 6.0.1; pin is 6.4.67).

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

*Last Updated: 2026-07-20 (2.6.4 shipped — the P(-1) ZIP-surface audit closed and its
in-progress block removed; the forward ladder is now the committed **2.7.x
performance/ratio ladder**. Shipped history lives in CHANGELOG.md and the per-release
snapshot in state.md. The four formerly-scattered deferred items are promoted into that
ladder: 2.7.0 xz encoder match finder (the ~400–900× gap) and 2.7.1 zstd optimal/2-pass
parse are committed; SIMD CRC-32 and the DEFLATE match-finder stay conditional (schedule on
a consumer profile) inside the same arc. Future codec bucket [Brotli, GPU texture]
unchanged.)*
