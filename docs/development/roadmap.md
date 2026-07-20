# Sankoch Development Roadmap

> **Status**: Stable (v2.6.3) | **Last Updated**: 2026-07-19

Shipped history lives in `CHANGELOG.md`; this file is the **forward**
ladder — the committed next-release ladder, deferred items, known
limitations, and the longer-horizon Future bucket. **Every codec now
de+compresses** — LZ4 / LZ4F / DEFLATE / zlib / gzip / xz / bzip2 / **zstd**
(the sovereign zstd encoder completed the last codec at 2.5.5) — plus a
shared tar cursor and ratio-capped decompression across the DEFLATE family
+ xz + bzip2. zstd-encode competitiveness landed across 2.5.6–2.5.8 — the
encoder now **beats `zstd -3` (zstd's own default level) on every fixture in
the benchmark corpus**, and the decoder is hardened against hostile input. The
The ZIP archive container opened at **2.6.0** — `zip.cyr` is an in-memory PKZIP
reader + writer for methods 0/8, the whole agnosai `.agpkg` filing. The forward
ladder is the rest of that arc (2.6.1 other methods → 2.6.2 zip64 → 2.6.3
streaming + metadata), with the zstd optimal/2-pass parse and xz encoder
throughput deferred to their own unscheduled arcs.

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

> **2.5.10 — P(-1) audit remainder — ✅ shipped 2026-07-19**
> (see CHANGELOG + [`docs/audit/2026-07-19-pre-2.6.0.md`](../audit/2026-07-19-pre-2.6.0.md)).
>
> Closes the deferred half of the audit: **M-9/M-10** zstd decode/encode arena leaks
> (349 KB + 90 KB per call → **0**, via pooled FSE/Huffman tables, reader slots and encoder
> coding tables; encoder output byte-identical), **M-1** tar retry-ladder DoS
> (1030 MB → 38 MB of arena on a 51-byte bomb), **M-2** multi-frame `.zst` silent truncation
> (+ `zstd_content_size`), **M-4** multi-member `.tar.gz` rejection, **M-11** + the zstd half
> of **M-8** (decode/encode OOM null-checks), **L-2/L-3/L-4/R-1**, and the **L-5/I-1**
> testability work (zstd/tar/stream routed through the `_sankoch_alloc` fault seam — viable
> only because 2.5.9 added `runtime.cyr` to `[lib.zstd]` — zstd added to the OOM sweep, and
> `fuzz_xz_truncate` + an exhaustive prefix sweep). The seam routing immediately caught a
> sticky-`_ze_oom` bug that would have poisoned every `zstd_compress` after one OOM.
>
> **Every confirmed audit finding is now resolved. 2.6.0 is cleared to open.**

## ⏸ Deferred — xz encoder throughput

The 2.5.9 P(-1) baseline measured xz encode at **~0.07–0.16 MB/s — roughly 400–900× slower
than reference `xz -6`** for equal-or-better ratio (1 MB of zeros: 14.8 s vs ~16 ms;
1 MB of text: 6.4 s). Scaling is *linear*, so this is a constant factor, not an algorithmic
blowup: reference xz uses a BT4 binary-tree match finder with hash-chain skipping, while
sankoch walks a plain chain and prices every position. This is the largest measured
performance gap in the tree and `takumi` is an xz-encode consumer (a 4 MB tarball takes
25–57 s). It survived the 2.5.4 throughput pass, so closing it means a new match finder,
not micro-optimisation. Numbers in
[`docs/benchmarks/2026-07-19-2.5.9-p1-baseline.md`](../benchmarks/2026-07-19-2.5.9-p1-baseline.md).

> **2.6.0 — ZIP archive container: agnosai `.agpkg` core — ✅ shipped 2026-07-19**
> (see CHANGELOG).
>
> New `src/zip.cyr` (487 lines): the PKZIP `.zip` container as an in-memory **reader and
> writer** for methods 0 (store) and 8 (DEFLATE) — EOCD + central directory index,
> extract-by-index with the member's **CRC-32 always verified**, local headers + central
> directory + EOCD on write, DEFLATE falling back to STORE when it would not shrink.
> Zip-slip guards mirror `tar.cyr` (absolute / `..` / empty interior components /
> control bytes / **backslash**), enforced on both write and read, with a new shared
> `ERR_UNSAFE_PATH`; a per-member expansion cap folds into `ERR_RATIO_LIMIT`. New
> `[lib.zip]` distlib profile (nine bundles total), `tests/tcyr/zip.tcyr` (11 tests /
> 59 assertions — the 22nd suite), and `scripts/zip-smoke.sh` proving reference parity
> **both ways** across five archive shapes: Python `zipfile` writes → sankoch reads →
> sankoch re-packs → `unzip -t` + Python `zipfile` accept it byte-identically, 5/5.

> **2.6.1 — ZIP: every method sankoch owns — ✅ shipped 2026-07-19** (see CHANGELOG).
>
> Methods **12 (bzip2)**, **93 (Zstandard)** and **95 (xz)** on read *and* write, via new
> `src/zip_methods.cyr` (174 lines). For each, the ZIP payload is the codec's own
> standalone stream, so a member can be handed straight to the reference CLI. Method 14
> (LZMA alone-format) stays unsupported — same non-goal as the codec.
>
> `zip.cyr` still references only deflate + crc32, so **`[lib.zip]` stays lean for
> agnosai (4,969 lines, methods 0/8)** while the new **`[lib.zipall]` (10,698)** carries
> every method — ten bundles, each verified to compile standalone. That split is what
> keeps the *Modular by profile* promise; a function-pointer seam was considered and
> rejected (fnptr availability in a lean profile depends on the consumer's stdlib list,
> and it carries per-target ABI caveats).
>
> Parity verified **both directions**: bsdtar extracts all five methods from a sankoch
> archive byte-identically, and sankoch reads Python-written 12/93 plus a bsdtar-written
> 95. `zip-smoke.sh` now covers seven archive shapes; `zip.tcyr` is 15 tests / 98 assertions.

> **2.6.2 — ZIP: Zip64 — ✅ shipped 2026-07-19** (see CHANGELOG).
>
> Zip64 on both sides: the **EOCD record + locator** (archive-level) and the
> **extended-information extra field, header ID 0x0001** (per-member), lifting the
> 65,535-member and 4 GB ceilings. `ZIP_MAX_ENTRIES` 65,535 → 16,777,216. The extra-field
> parse is driven by *which* sentinels were seen — each field is present only if its base
> field overflowed, so the record's length alone does not say what is in it.
>
> Verified against real Zip64: a Python `force_zip64` member, a 70,000-entry Python
> archive (EOCD count `0xFFFF`), and sankoch's own 70,000-entry output — **6,230,098
> bytes, byte-for-byte the size Python produces** — accepted by `unzip -t`, `bsdtar` and
> Python `zipfile`.
>
> Also fixed a **latent 2.6.0 defect this work surfaced**: the writer aliased
> caller-supplied member names rather than copying them, so a reusable name buffer
> produced an archive where every entry carried the last name — with valid CRCs and a
> correct member count, accepted by every external tool. Only the duplicate names showed
> it. `test_zip_name_not_aliased` now scribbles the caller's buffer before `finish`;
> reverting the fix fails it.

> **2.6.3 — ZIP: streaming write + per-entry metadata — ✅ shipped 2026-07-19**
> (see CHANGELOG).
>
> **Per-entry Unix metadata**: `zip_entry_mode` / `zip_entry_mtime` /
> `zip_entry_is_symlink` and `zip_add_meta` / `zip_add_any_meta`, with MS-DOS <-> Unix time
> conversion over the proleptic-Gregorian day count (integer only; pre-1980 clamps to the
> format floor, and that floor reads back as *absent*). Mode is only reported when
> "version made by" says Unix, so a DOS/NTFS writer's attribute bits are never mistaken
> for one. Symlinks follow the bsdtar/Info-ZIP convention (S_IFLNK + target as content) —
> **bsdtar restores a real symlink and mode 0754 from sankoch's output**.
>
> **Streaming write**: `zip_enc_begin` / `zip_enc_write` / `zip_enc_end` using
> general-purpose bit 3 + a trailing data descriptor, mirroring the codec `*_enc_*` shape;
> DEFLATE streams through `deflate_enc_*`. Misuse (nested begin, write before begin,
> finishing with a member still open) is refused rather than emitting a corrupt archive.
> The READ half already worked — the reader takes sizes from the central directory — and
> now carries a regression fixture.
>
> **This completes the 2.6.x ZIP arc.**

### ZIP — what is deliberately NOT there

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
| deflate.cyr      | 2545 | DEFLATE de/compress, adaptive blocks, `deflate_enc_*` + `deflate_dec_*` streaming (+ `deflate_dec_reset` / `deflate_dec_init_dict` / `deflate_dec_init_capped`), dict, OOM-propagating table inits, `deflate_decompress_with_ratio_cap` + shared `_deflate_ratio_ceiling` | full |
| zlib.cyr         |  485 | RFC 1950 wrapper + FDICT batch + streaming (`zlib_dec_init_dict` / `zlib_dec_init_capped`) + `zlib_enc_*` + `zlib_dec_*` + `zlib_decompress_with_ratio_cap` | full |
| gzip.cyr         |  650 | RFC 1952 wrapper + concatenated batch/streaming + FHCRC verify + `gzip_enc_*` + `gzip_dec_*` streaming (+ `gzip_dec_init_capped`) + `gzip_decompress_with_ratio_cap` (cumulative cap) | full |
| xz.cyr           | 1836 | `.xz` de/compress: container + LZMA2 framing + LZMA range decoder/encoder, optimal-parse (`xz_decompress` / `xz_compress`) + `xz_decompress_with_ratio_cap` (2.5.3) | full |
| bzip2.cyr        | 1323 | `.bz2` de/compress: bit reader/writer + Huffman + MTF/RLE2 + inverse/forward BWT + RLE1 (`bzip2_decompress` / `bzip2_compress`) + `bzip2_decompress_with_ratio_cap` (2.5.3) | full |
| zstd.cyr         | 2384 | `.zst` de+compress (RFC 8878): decoder (2.5.0, hardened 2.5.6) + sovereign `zstd_compress` encoder (2.5.5 — LZ77 hash-chain matcher + FSE sequence encoder + length-limited Huffman literals, single/4-stream; adaptive FSE sequence tables 2.5.7; **priced match selection `_ze_mvalue` 2.5.8**); self-contained bit reader / FSE / Huffman, no runtime | full |
| zip.cyr          | 1013 | PKZIP `.zip` container (2.6.0): in-memory reader (EOCD + central directory index, extract-by-index, CRC-32 verified) + writer (local headers + central directory + EOCD), methods 0/8, zip-slip guards, per-member ratio cap | full |
| zip_methods.cyr  |  148 | The rest of ZIP's methods (2.6.1): 12 (bzip2) / 93 (zstd) / 95 (xz), read + write. Kept OUT of `[lib.zip]` so the lean profile never pulls those codecs | full |
| tar.cyr          |  710 | Sovereign POSIX ustar + pre-POSIX v7 tar pull-cursor (`tar_open_auto` sniffs gzip/xz/bzip2/zstd); PAX/GNU long-name + two-layer path-traversal guards incl. the 2.5.9 cross-entry symlink ledger (H-1) + parse-path OOM guards (M-3) | full |
| stream.cyr       |  256 | Streaming dispatch (`stream_compress_*`, legacy buffered `stream_decompress_*`, incremental `stream_decompress_init_inc` / `_finish_inc`) | full |
| runtime.cyr      |   73 | Shared runtime seam: `_sankoch_mtx` + two-tier lock (agnos no-op since 2.4.4) + `_sankoch_alloc` arena + fault injection — extracted from `lib.cyr` (2.4.9) so lean profiles pull it without the format-dispatch API | full |
| lib.cyr          |  265 | Include chain + public API + format dispatch + `_sankoch_reset_tables` (references every codec's lazy globals) | full |
| **Total**        | **14601** | | |

`core` modules (types + xxhash32 + lz4_decode = 317 source lines)
form `[lib.core]` → `dist/sankoch-core.cyr`. They contain no
`alloc()`, no syscalls, no mutex usage — verified by the CI
"Kernel-safe tripwire" gate (`programs/core_smoke.cyr`).

Tests: **267 distinct test functions** (257 across the 20 split
codec×direction suites + 10 in git_object.tcyr) producing
**4,484,462 assertions** total (4,137,879 + 346,583). Most comes from
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

*Last Updated: 2026-07-19 (2.6.3 shipped — ZIP streaming write + per-entry metadata.
**The 2.6.x ZIP archive-container arc is complete**: reader + writer, every method sankoch
owns, Zip64, streaming, and tar-parity metadata, all reference-verified against unzip /
bsdtar / Python zipfile. Nothing further is scheduled; the natural next step is a P(-1)
hardening pass over the ~1,900 lines of zip.cyr + zip_methods.cyr the arc added, which has
not been security-audited. Deferred: zstd optimal parse, xz encoder throughput, SIMD
CRC-32, the wire-identical DEFLATE match-finder speedup; Future bucket unchanged.)*
