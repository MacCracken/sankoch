# Sankoch Development Roadmap

> **Status**: Stable (v2.5.9) | **Last Updated**: 2026-07-19

Shipped history lives in `CHANGELOG.md`; this file is the **forward**
ladder — the committed next-release ladder, deferred items, known
limitations, and the longer-horizon Future bucket. **Every codec now
de+compresses** — LZ4 / LZ4F / DEFLATE / zlib / gzip / xz / bzip2 / **zstd**
(the sovereign zstd encoder completed the last codec at 2.5.5) — plus a
shared tar cursor and ratio-capped decompression across the DEFLATE family
+ xz + bzip2. zstd-encode competitiveness landed across 2.5.6–2.5.8 — the
encoder now **beats `zstd -3` (zstd's own default level) on every fixture in
the benchmark corpus**, and the decoder is hardened against hostile input. The
forward ladder is the full-feature ZIP archive container arc (2.6.x — agnosai's
`.agpkg` need first at 2.6.0, then the rest across 2.6.1+), with the zstd
optimal/2-pass parse deferred to its own unscheduled arc.

---

## ▶ Scheduled — the committed next-release ladder

> **2.5.3 — xz / bzip2 ratio cap — ✅ shipped 2026-07-18** (see CHANGELOG).
> `xz_decompress_with_ratio_cap` / `bzip2_decompress_with_ratio_cap` extended
> the DEFLATE-family `ERR_RATIO_LIMIT` zip-bomb defense to the last two batch
> decoders. Closed the INFO-F gap.

> **2.5.4 — xz / bzip2 encoder throughput — ✅ shipped 2026-07-18** (see
> CHANGELOG + [`docs/benchmarks/2026-07-18-2.5.4-encoder-throughput.md`](../benchmarks/2026-07-18-2.5.4-encoder-throughput.md)).
> Output-byte-identical speedups: xz optimal-parse ~5× on text / ~2.5× on
> repetitive input (hoisted distance-price + inlined `_xze_relax` + match-finder
> `best` pre-check); bzip2 ~5% on random (`% n` → conditional subtract in the
> BWT sort + scalarized 6-group Huffman-cost accumulator).

> **2.5.5 — sovereign zstd encoder — ✅ shipped 2026-07-18** (see CHANGELOG +
> [`docs/benchmarks/2026-07-18-2.5.5-zstd-encode.md`](../benchmarks/2026-07-18-2.5.5-zstd-encode.md)).
> `zstd_compress` — LZ77 (a self-contained hash-chain matcher, since `[lib.zstd]`
> can't pull in `lz77.cyr`) + FSE sequences (Predefined tables; 3 interleaved
> states encoded backward, order derived by reversing the decoder's read order)
> + Huffman literals (length-limited canonical, single/4-stream) — completing
> the codec that shipped decode-only at 2.5.0. Reference-`zstd -d`-validated
> across hundreds of fuzz cases; ~2-17 % behind `zstd -1` (it *beats* `-1` on
> repetitive / incompressible data). Built as bites 1 → 4a; **three spec bugs
> caught by the reference decoder** (Huffman length-limiter overshoot fixed with
> the exact zlib `gen_bitlen` repair; the direct-weight header-byte overflow for
> maxsym > 128; a null-scratch SIGSEGV) — each a case where sankoch's own decoder
> was lenient enough to round-trip an invalid stream.

> **2.5.6 — zstd encode competitiveness + decoder hardening — ✅ shipped 2026-07-18**
> (see CHANGELOG + [`docs/benchmarks/2026-07-18-2.5.6-zstd-competitiveness.md`](../benchmarks/2026-07-18-2.5.6-zstd-competitiveness.md)
> + [`docs/audit/2026-07-18-zstd-decoder-hardening.md`](../audit/2026-07-18-zstd-decoder-hardening.md)).
>
> Shipped as five bites: **FSE-compressed literal weights** (wide/UTF-8/binary
> literals now Huffman-compress), **zstd decoder hardening** (36 verified OOB/DoS
> paths closed; new `fuzz/fuzz_zstd.fcyr`), **repeat-offset codes**, a **one-step
> lazy parse**, and a **1..9 compression-level knob** (`zstd_compress_level`) + a
> `bench` ratio line. The encoder now **beats `zstd -1`** on source / binary /
> repetitive / incompressible data, trailing only on UTF-8-heavy text (+7.5 %).
> Reference `zstd -d` v1.5.7 was the correctness bar throughout.

> **2.5.7 — zstd encoder parse quality — ✅ shipped 2026-07-18**
> (see CHANGELOG + [`docs/benchmarks/2026-07-18-2.5.7-parse-quality.md`](../benchmarks/2026-07-18-2.5.7-parse-quality.md)).
>
> Two bites: **repcode-aware match finding** (bias the matcher toward recent offsets)
> and **adaptive FSE sequence tables** (per-block RLE / FSE_Compressed / Predefined
> selection for LL/OF/ML, fitted to the block histogram — the dominant win). The
> encoder now **beats `zstd -1` by 6–16 % and `zstd -3` (the default) by 4–11 %** on
> real code / text / binary; structured/tabular data went from +106 % to −6 % vs
> `zstd -1`. Reference `zstd -d` v1.5.7 was the correctness bar throughout.

> **2.5.8 — zstd encoder priced parse — ✅ shipped 2026-07-19**
> (see CHANGELOG + [`docs/benchmarks/2026-07-19-2.5.8-priced-parse.md`](../benchmarks/2026-07-19-2.5.8-priced-parse.md)).
>
> The slot was scheduled as an optimal / 2-pass parse. Diagnosis found the residue was not
> missing search depth but the parser comparing raw match **lengths** where it should have
> compared encoded **cost**. Six bites: the **priced lazy accept test** (`_ze_mvalue`, 65 %
> of the release), **repcode candidates at the lookahead position** (the largest real-data
> contributor), deleting the hand-tuned `+2` rep slack, the **rep0−1 probe** (RFC 8878
> parity), a **Huffman tree-description race**, and a **rep-locked lookahead**. Corpus
> **278,970 → 251,333 B (−9.9 %)** with **no regression on any of eleven fixtures**;
> ~100 lines and **zero new allocation**. Also fixed a 2.5.7 defect where merely enabling
> the lazy lookahead inflated ascending-integer text by **67 %** — now covered by
> `test_zc_lazy_beats_greedy`. Reference `zstd -d` v1.5.7 was the correctness bar throughout.

> **2.5.9 — P(-1) security hardening — ✅ shipped 2026-07-19**
> (see CHANGELOG + [`docs/audit/2026-07-19-pre-2.6.0.md`](../audit/2026-07-19-pre-2.6.0.md)
> + [`docs/benchmarks/2026-07-19-2.5.9-p1-baseline.md`](../benchmarks/2026-07-19-2.5.9-p1-baseline.md)).
>
> The pre-2.6.0 P(-1) scaffold-hardening pass. First security audit of the never-audited
> 2.4.x/2.5.x surface (xz / bzip2 / tar / zstd-encoder): **1 HIGH + 13 MEDIUM + 5 LOW**
> (post adversarial verification; 11 refuted or rebased). Landed the **security-critical
> subset**: **H-1** tar symlink-chain traversal (arbitrary file write outside the root —
> cross-entry symlink ledger, 5,000-archive differential, GNU-tar contract matched),
> **M-3** tar NULL-write, **M-5/M-6/M-7** xz OOB-read / DoS-hang / sha256-fail-closed,
> **M-8+L-1** the OOM-latch crash class (INFO-E answered, negative), **M-12** zstd
> concurrency lock, **M-13** stream allocs. Each reproduced pre-fix, verified post-fix.

### 2.5.10 — the audit remainder (gates 2.6.0)

The resource-leak / interop / zstd-decode-OOM cluster deferred from 2.5.9 because it all
touches `zstd.cyr` memory lifetime + `tar_open_auto` sizing and lands coherently: **M-1**
(tar retry-ladder ~1 GiB arena DoS), **M-2** (multi-frame `.zst` truncation), **M-4**
(multi-member `.tar.gz` rejection), **M-9** (zstd decode ~262 KB/call leak), **M-10** (zstd
encoder FSE-ctable leak), **M-11** (zstd decode OOM null-checks), the **zstd-encoder half of
M-8**, and the LOW/INFO tail (**L-2** gzip ratio 1-byte overshoot, **L-3** DEFLATE
stored-block ceiling, **L-4** zstd errata-7297 guard, **L-5 / I-1** route zstd/tar/stream
allocs through the fault seam + `fuzz_xz_truncate`). Verified fixes are sketched in the
audit record's remediation list. **2.6.0 opens after this lands.**

## ⏸ Deferred — zstd optimal / 2-pass parse

Was the 2.5.8 slot. It was **built and measured** against the priced parse that shipped
instead, rather than deferred on speculation:

| metric | 2.5.7 | 2.5.8 (shipped) | verified DP probe |
|--------|------:|----------------:|------------------:|
| 7-fixture corpus | 278,970 | **251,333** | 251,733 |
| deflate + bash | 168,309 | 167,291 | **164,055** |
| encode cost | 1.0× | 1.1–1.4× | 4–74× |
| new allocation | — | 0 bytes | ~224 KiB |
| source added | — | ~100 lines | ~400 lines |

The DP is **worse on total corpus size** than what shipped, at 3–60× the cost. It is
genuinely better on real source/binary specifically (−3.6 % against 2.5.8's −0.5 %), which
is why it stays on the ladder — as its own arc, not a point release. The design is fully
specified (stretch-DP over a match ladder from the hash chain, integer 1/256-bit prices,
per-DP-node recent-offset triple, 2-pass statistics refit; the `with1literal` rescue must
land *before* the per-node rep triple or the corpus regresses). Schedule if a consumer
needs that last few percent on source/binary.

A smaller known limitation rides along: deeper levels are still slightly non-monotonic on
some inputs (csv is best at level 6, not 9; spread under 2 %). That is inherent to
greedy+lazy parsing and is what the DP would fix properly.

### 2.6.x — ZIP archive container arc  (full-feature, agnosai-first)

A new `zip.cyr` archive module built out to the same completeness the
codecs carry — read + write, every method sankoch owns, zip64, streaming
— but delivered **across the 2.6.x arc so agnosai's lean `.agpkg` need
lands first (2.6.0) and unblocks the port before the rest fills in**. The
PKZIP `.zip` container throughout: local file headers + central directory
+ end-of-central-directory record, per-entry CRC-32 (all already in-tree,
reusing the DEFLATE codec). **Reference-CLI parity is the bar** — every
round-trip must decode via `unzip` / Python `zipfile`, the same load-
bearing rule the codecs hold. Bites may merge/split per the usual sizing
rule; the ordering is the commitment, not the exact boundaries.

- **2.6.0 — agnosai core: store + DEFLATE, read + write.** Scoped
  directly from the consumer, not guessed: agnosai's
  `src/definitions/packaging.rs` round-trips an `.agpkg` bundle (a ZIP of
  `manifest.json` + one JSON per agent definition) — `ZipWriter` with
  `CompressionMethod::Deflated` on `export()`, `ZipArchive` on
  `import(&[u8])`, proven by `test_export_import_round_trip`. In-memory
  reader (enumerate the central directory, pull each entry by name) +
  store/DEFLATE writer (local headers + central directory), both over byte
  buffers — agnosai's `export_to_file` / `import_from_file` stay thin
  `std::fs` wrappers on its side. A per-entry **uncompressed-size cap** is
  built in (agnosai hand-rolls a 1 MiB/file + entry-count zip-bomb guard;
  sankoch's `ERR_RATIO_LIMIT` ratio-cap absorbs it natively). Zip-slip /
  path-traversal guards mirror `tar.cyr`. **This is the whole agnosai
  filing** (~250 lines, deflate + crc32); everything below is parity
  build-out that **does not block agnosai** — its ZIP need is behind the
  non-default `definitions` feature, excluded from agnosai v2.0.0 parity
  (the `sankoch` row in
  [`agnosai/docs/development/cyrius-port-plan.md`](https://github.com/MacCracken/agnosai/blob/main/docs/development/cyrius-port-plan.md)).
- **2.6.1 — the other methods.** Wire the codecs sankoch owns into ZIP's
  method field, all **both ways**: **12 (bzip2)**, **95 (xz)**, and
  **93 (zstd)** — the last is full round-trip because 2.5.5 zstd encode
  lands before this arc. Method 14 (raw LZMA alone-format) stays
  unsupported — same non-goal as the codec, which handles the `.xz`
  container, not `.lzma`.
- **2.6.2 — zip64.** >4 GB entries and >65 535-entry / >4 GB archives: the
  Zip64 end-of-central-directory record + locator + the Zip64 extended-
  information extra field, on read and write.
- **2.6.3 — streaming + metadata.** Streaming read + streaming write (data
  descriptors — bit-3 sizes-after-data) mirroring the codec `*_enc_*` /
  `*_dec_*` shape, plus per-entry metadata (mtime, mode, symlink) for
  tar-parity extraction.

**Non-goals** (like the codec non-goals): **encryption** — ZipCrypto is
cryptographically broken, and AES-in-ZIP needs a real AES primitive
sankoch deliberately doesn't carry (zero-crypto-dep, cf. xz's unverified
SHA-256); **multi-disk / spanned** archives (obsolete); **Deflate64**
(method 9 — a separate codec, not RFC 1951).

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

(Zstandard is no longer here — decode shipped 2.5.0, encode is scheduled
at 2.5.5.)

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
| deflate.cyr      | 2540 | DEFLATE de/compress, adaptive blocks, `deflate_enc_*` + `deflate_dec_*` streaming (+ `deflate_dec_reset` / `deflate_dec_init_dict` / `deflate_dec_init_capped`), dict, OOM-propagating table inits, `deflate_decompress_with_ratio_cap` + shared `_deflate_ratio_ceiling` | full |
| zlib.cyr         |  485 | RFC 1950 wrapper + FDICT batch + streaming (`zlib_dec_init_dict` / `zlib_dec_init_capped`) + `zlib_enc_*` + `zlib_dec_*` + `zlib_decompress_with_ratio_cap` | full |
| gzip.cyr         |  638 | RFC 1952 wrapper + concatenated batch/streaming + FHCRC verify + `gzip_enc_*` + `gzip_dec_*` streaming (+ `gzip_dec_init_capped`) + `gzip_decompress_with_ratio_cap` (cumulative cap) | full |
| xz.cyr           | 1836 | `.xz` de/compress: container + LZMA2 framing + LZMA range decoder/encoder, optimal-parse (`xz_decompress` / `xz_compress`) + `xz_decompress_with_ratio_cap` (2.5.3) | full |
| bzip2.cyr        | 1323 | `.bz2` de/compress: bit reader/writer + Huffman + MTF/RLE2 + inverse/forward BWT + RLE1 (`bzip2_decompress` / `bzip2_compress`) + `bzip2_decompress_with_ratio_cap` (2.5.3) | full |
| zstd.cyr         | 2083 | `.zst` de+compress (RFC 8878): decoder (2.5.0, hardened 2.5.6) + sovereign `zstd_compress` encoder (2.5.5 — LZ77 hash-chain matcher + FSE sequence encoder + length-limited Huffman literals, single/4-stream; adaptive FSE sequence tables 2.5.7; **priced match selection `_ze_mvalue` 2.5.8**); self-contained bit reader / FSE / Huffman, no runtime | full |
| tar.cyr          |  701 | Sovereign POSIX ustar + pre-POSIX v7 tar pull-cursor (`tar_open_auto` sniffs gzip/xz/bzip2/zstd); PAX/GNU long-name + two-layer path-traversal guards incl. the 2.5.9 cross-entry symlink ledger (H-1) + parse-path OOM guards (M-3) | full |
| stream.cyr       |  256 | Streaming dispatch (`stream_compress_*`, legacy buffered `stream_decompress_*`, incremental `stream_decompress_init_inc` / `_finish_inc`) | full |
| runtime.cyr      |   73 | Shared runtime seam: `_sankoch_mtx` + two-tier lock (agnos no-op since 2.4.4) + `_sankoch_alloc` arena + fault injection — extracted from `lib.cyr` (2.4.9) so lean profiles pull it without the format-dispatch API | full |
| lib.cyr          |  254 | Include chain + public API + format dispatch + `_sankoch_reset_tables` (references every codec's lazy globals) | full |
| **Total**        | **13099** | | |

`core` modules (types + xxhash32 + lz4_decode = 317 source lines)
form `[lib.core]` → `dist/sankoch-core.cyr`. They contain no
`alloc()`, no syscalls, no mutex usage — verified by the CI
"Kernel-safe tripwire" gate (`programs/core_smoke.cyr`).

Tests: **267 distinct test functions** (257 across the 20 split
codec×direction suites + 10 in git_object.tcyr) producing
**4,484,226 assertions** total (4,137,643 + 346,583). Most comes from
per-byte round-trip loops on the streaming suites — a single 200 KB
round-trip contributes 200,000 assertions through one
`while (i < N) assert(byte_eq)` loop; the headline number measures
coverage *density*, not coverage *breadth*. See
[`../cyrius-usage.md`](../cyrius-usage.md#what-assertions-means-here-and-why-the-number-is-so-large)
for the full explanation.

Fuzz: 5,279 iterations across 5 files (`fuzz_lz4` 700, `fuzz_deflate`
1,629, `fuzz_xz` 900, `fuzz_bzip2` 900, `fuzz_zstd` 1,150 — 400 random
+ 600 encode→decode round-trip + 150 corruption). Per-file breakdown in
[`state.md` § Fuzz totals](state.md#fuzz-totals).

Distlib: `dist/sankoch.cyr` at 12,827 lines (full) +
`dist/sankoch-core.cyr` at 317 lines (kernel-safe), plus six lean
single-purpose profiles from the 2.4.9 → 2.5.1 reorg —
`sankoch-zlib.cyr` (4,889), `sankoch-gzip.cyr` (5,042),
`sankoch-xz.cyr` (2,755), `sankoch-bzip2.cyr` (2,071),
`sankoch-zstd.cyr` (2,100), `sankoch-tar.cyr` (10,748). Eight profiles
total; per-bundle roles in [`state.md` § Dist bundles](state.md#dist-bundles).

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

*Last Updated: 2026-07-19 (2.5.9 P(-1) security-hardening pass — first audit of the
never-audited 2.4.x/2.5.x surface [xz/bzip2/tar/zstd-encoder], 1 HIGH + 13 MEDIUM + 5 LOW;
landed the security-critical subset [H-1 tar symlink-chain traversal, M-3 tar NULL-write,
M-5/M-6/M-7 xz OOB/DoS/sha256, M-8+L-1 OOM-latch class, M-12 zstd concurrency lock, M-13
stream allocs]; remainder [resource leaks / interop / zstd decode-OOM] → 2.5.10, which
gates 2.6.0. Audit: docs/audit/2026-07-19-pre-2.6.0.md. Deferred zstd optimal parse + the
2.6.x ZIP arc unchanged.)*
