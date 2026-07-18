# Sankoch Development Roadmap

> **Status**: Stable (v2.5.4) | **Last Updated**: 2026-07-18

Shipped history lives in `CHANGELOG.md`; this file is the **forward**
ladder — the committed next-release ladder, deferred items, known
limitations, and the longer-horizon Future bucket. The codec set through
2.5.4 is complete — LZ4 / LZ4F / DEFLATE / zlib / gzip / xz / bzip2
(de + compress, batch + streaming) + zstd decode + a shared tar cursor —
with ratio-capped decompression across the DEFLATE family + xz + bzip2
(2.5.3) and a retuned xz / bzip2 encoder (2.5.4, ~5× faster xz on text,
output-identical). The scheduled ladder below continues that (2.5.5 zstd
encode — completing the zstd codec) and opens a full-feature ZIP archive
container arc (2.6.x — agnosai's `.agpkg` need first at 2.6.0, then the
rest of the surface across 2.6.1+).

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

### 2.5.5 — zstd encode

The sovereign Zstandard **encoder** (RFC 8878, compress side) — completes
the codec that shipped decode-only at 2.5.0, and lands **before** the
2.6.x ZIP arc so ZIP method 93 can be written, not just read. Reuses the
in-tree LZ77 match-finder for sequence generation; adds the FSE + Huffman
*encoders* (the decoder's predefined tables run in reverse) + block/frame
construction (Raw / RLE / Compressed blocks, the recent-offset model).
**Reference-CLI parity is the bar**: output must round-trip through
reference `zstd -d` (v1.5.7 — the same text / random / repetitive /
multi-block fixture set the 2.5.0 decoder was validated against, 40/40).
One practical compression level to start (not the full `--ultra` parse);
higher levels + dictionary training can follow. No wire-format SIZE gate
(zstd output isn't bit-reproducible across encoder versions) — ships an
informational ratio line in `bench` like the xz / bzip2 encoders.
Primitive reference: Duda, "Asymmetric Numeral Systems" (arXiv:1311.2540);
shravan's Opus range encoder (`opus.cyr:175-284`) is the entropy-coding
cousin. Sequenced as small bites:

- **Bite 1 — frame + Raw/RLE blocks (store mode) — ✅ committed.**
  `zstd_compress` emits valid single_segment RFC-8878 frames with Raw
  (verbatim) + RLE (single repeated byte) blocks, 128 KiB block chunking,
  frame-content-size flag arithmetic mirrored from the decoder. Wired into
  `compress`/`_compress_inner`. Lock-free + self-contained (no runtime dep —
  `[lib.zstd]` profile still closes). Verified: `tests/tcyr/zstd_compress.tcyr`
  + `scripts/zstd-encode-smoke.sh` (reference `zstd -d` v1.5.7).
- **Bite 2 — Compressed block, single-stream Huffman literals (0 sequences) — 🟡 done, uncommitted.**
  Length-limited (≤ 11-bit) canonical Huffman whose assignment matches the
  decoder's `_z_huff_build`; direct weight table + backward single-stream
  bitstream (symbols emitted in reverse, marker-topped) + `sizefmt`-0
  literals header + 0-sequences byte. Applied to non-constant blocks ≤ 1023
  bytes when it beats raw; larger blocks still store. First real entropy
  compression — text ~30-50 % smaller. **Verified**: extended tcyr round-trip
  (incl. a Fibonacci input that forces the length-limiter) + reference `zstd
  -d` on the smoke battery **and an 80/80 random-skewed fuzz**, all
  byte-identical. (Found + fixed a length-limiter overshoot: the Kraft repair
  must be the exact zlib `gen_bitlen` demotion, or reference zstd rejects the
  incomplete code — sankoch's own decoder was too lenient to catch it.)
- **Bite 3a — 4-stream Huffman literals (regen > 1023) — 🟡 done, uncommitted.**
  Full 128 KiB blocks Huffman-compress their literals via 4 streams (jump
  table) sharing one table (`sizefmt` 2/3), plus a cheap size pre-estimate
  that skips the build when Huffman can't beat raw. ASCII text now compresses
  at any size (~42-58 % of original). Direct weights cap the alphabet at
  maxsym ≤ 128, so wide-alphabet / high-byte / binary blocks store for now
  (FSE weights = bite 4). **Verified**: tcyr round-trip (8 KB / 128 KiB / wide
  alphabet) + reference `zstd -d` on large text **and a 60/60 fuzz** across
  sizes 100 B–180 KB and alphabets 2–250, all byte-identical. (Caught + fixed:
  the direct-weight header byte `127 + maxsym` overflows for maxsym > 128 —
  reference rejected a source file containing a UTF-8 byte; guard added.)
- **Bite 3b-1 — self-contained LZ77 match finder → sequences — 🟡 done, uncommitted (scaffolding, unwired).**
  A greedy hash-chain matcher (own hash + chain in `zstd.cyr`, since `[lib.zstd]`
  can't pull in `lz77.cyr`) parses input into zstd sequences (`_zs_ll` / `_zs_ml`
  / `_zs_off` + concatenated literals `_zs_lit`), offsets emitted as literal
  offsets (`offset_value = offset + 3`). **Verified in isolation** by
  `_ze_lz_reconstruct` (byte-exact reconstruction: 97-99 % matched on periodic
  text, 0 % on random). Not yet wired into `zstd_compress` — it feeds the FSE
  emitter below.
- **Bite 3b-2 — FSE sequence encoder + framing — 🟡 done, uncommitted.**
  FSE **encoding** tables (`_ze_fse_ctable`, mirroring `FSE_buildCTable`,
  reusing the decoder's spread) for LL/OF/ML in Predefined mode; the 3
  interleaved states encoded **backward** (init LL/OF/ML → per-seq OF/ML/LL
  state + LL/ML/OF extra → flush ML/OF/LL, derived by reversing the decoder's
  read order); sequences-section header (nbSeq + modes) + bitstream; Raw
  literals for now. Wired into the block loop (sequences → Huffman → raw).
  **Verified**: tcyr round-trip + reference `zstd -d` **and a 70/70 mixed-content
  fuzz**, all byte-identical. Real LZ77 + entropy compression now (text 2 KB →
  3 %, 50 KB → 0.1 %). Currently **~10-20 % behind `zstd -1`** — the gap is the
  Raw literals (see 3b-3). (Caught + fixed: `_ze_try_seq_block` redirected the
  writer to `_ze_tmp` without allocating it — null-pointer SIGSEGV on the first
  block.)
- **Bite 3b-3 — Huffman literals *inside* the sequences block.** Replace the
  Raw literals section of the sequences block with the 4-stream Huffman coder
  (for ASCII/maxsym ≤ 128), closing most of the gap to `zstd -1`. **2.5.5 is
  release-able here** (competitive LZ77 + entropy).
- **Bite 4 — FSE-compressed literal weights (wide alphabets) + custom seq
  tables + a level knob + `bench` ratio line + CI wiring** (add the
  encode-smoke to CI).

No wire-format SIZE gate (zstd output isn't bit-reproducible across encoder
versions). **Not shipped as a release until Bite 3b lands** — through Bite 3a
the encoder is entropy-only (Huffman literals, no LZ77 matches) and stores
wide-alphabet data.

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
> Current as of **2.5.0** — the tree grew from 16 to 19 modules: `runtime.cyr`
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
| lz77.cyr         |  181 | Sliding window match-finder, 8-byte word-compare match extend, `lz77_rebase`, ring-buffer slide | full |
| lz4_decode.cyr   |  181 | LZ4 block + frame decompress (incl. per-block checksum) + LZ4F enum (kernel-safe) | core |
| lz4.cyr          |  935 | LZ4 block + frame compress + `lz4f_enc_*` (configurable block-max + checksum) + `lz4f_dec_*` streaming | full |
| deflate.cyr      | 2540 | DEFLATE de/compress, adaptive blocks, `deflate_enc_*` + `deflate_dec_*` streaming (+ `deflate_dec_reset` / `deflate_dec_init_dict` / `deflate_dec_init_capped`), dict, OOM-propagating table inits, `deflate_decompress_with_ratio_cap` + shared `_deflate_ratio_ceiling` | full |
| zlib.cyr         |  485 | RFC 1950 wrapper + FDICT batch + streaming (`zlib_dec_init_dict` / `zlib_dec_init_capped`) + `zlib_enc_*` + `zlib_dec_*` + `zlib_decompress_with_ratio_cap` | full |
| gzip.cyr         |  638 | RFC 1952 wrapper + concatenated batch/streaming + FHCRC verify + `gzip_enc_*` + `gzip_dec_*` streaming (+ `gzip_dec_init_capped`) + `gzip_decompress_with_ratio_cap` (cumulative cap) | full |
| xz.cyr           | 1819 | `.xz` de/compress: container + LZMA2 framing + LZMA range decoder/encoder, optimal-parse (`xz_decompress` / `xz_compress`) + `xz_decompress_with_ratio_cap` (2.5.3) | full |
| bzip2.cyr        | 1316 | `.bz2` de/compress: bit reader/writer + Huffman + MTF/RLE2 + inverse/forward BWT + RLE1 (`bzip2_decompress` / `bzip2_compress`) + `bzip2_decompress_with_ratio_cap` (2.5.3) | full |
| zstd.cyr         |  729 | `.zst` decode (RFC 8878): frames + Raw/RLE/Compressed blocks + FSE/Huffman literals + sequences + recent-offsets (`zstd_decompress`); self-contained bit reader / FSE / Huffman — decode only (2.5.0) | full |
| tar.cyr          |  513 | Sovereign POSIX ustar + pre-POSIX v7 tar pull-cursor (`tar_open_auto` sniffs gzip/xz/bzip2/zstd); PAX/GNU long-name + path-traversal guards (2.5.0) | full |
| stream.cyr       |  250 | Streaming dispatch (`stream_compress_*`, legacy buffered `stream_decompress_*`, incremental `stream_decompress_init_inc` / `_finish_inc`) | full |
| runtime.cyr      |   73 | Shared runtime seam: `_sankoch_mtx` + two-tier lock (agnos no-op since 2.4.4) + `_sankoch_alloc` arena + fault injection — extracted from `lib.cyr` (2.4.9) so lean profiles pull it without the format-dispatch API | full |
| lib.cyr          |  239 | Include chain + public API + format dispatch + `_sankoch_reset_tables` (references every codec's lazy globals) | full |
| **Total**        | **11509** | | |

`core` modules (types + xxhash32 + lz4_decode = 317 source lines)
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

Distlib: `dist/sankoch.cyr` at 11,394 lines (full) +
`dist/sankoch-core.cyr` at 331 lines (kernel-safe), plus six lean
single-purpose profiles from the 2.4.9 → 2.5.1 reorg —
`sankoch-zlib.cyr` (4,924), `sankoch-gzip.cyr` (5,077),
`sankoch-xz.cyr` (2,697), `sankoch-bzip2.cyr` (2,014),
`sankoch-zstd.cyr` (782), `sankoch-tar.cyr` (9,308). Eight profiles
total; per-bundle roles in [`state.md` § Dist bundles](state.md#dist-bundles).

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

*Last Updated: 2026-07-18 (2.5.4 xz/bzip2 encoder throughput shipped [output-identical, xz ~5× on text]; 2.5.3 ratio cap shipped [INFO-F closed]. Remaining ladder 2.5.5 zstd encode → 2.6.x full-feature ZIP archive container arc, agnosai `.agpkg` core first at 2.6.0. Zstandard moved out of Future — all codecs live here, modular by profile. Deferred unchanged.)*
