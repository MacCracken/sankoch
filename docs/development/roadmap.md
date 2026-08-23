# Sankoch Development Roadmap

> **Status**: Stable (**v2.7.8**); no open Critical — 2.7.6 shipped the batch-deflate
> block-boundary corruption fix, 2.7.7 the ZIP sizing/reclaim work, 2.7.8 the
> toolchain catch-up. Next: **2.8.x** (SIMD CRC-32 → GPU texture → P(-1) closeout).
> ⚠ The **DEFLATE match-finder** backlog item is no longer speculative — sit has
> measured it as its single worst benchmark row; see Backlog. | **Last Updated**: 2026-08-20

This file is the **forward** ladder — the committed next releases
(**▶ Scheduled**) and an unscheduled **Backlog** to be re-organised when the
next arc opens. **Shipped history lives in [`CHANGELOG.md`](../../CHANGELOG.md);
the live per-release snapshot lives in [`state.md`](state.md).** This file does
not re-list what shipped.

**Where the library stands.** Every lossless codec de+compresses — LZ4 / LZ4F /
DEFLATE / zlib / gzip / xz / bzip2 / zstd — with ratio-capped decompression
across the DEFLATE family + xz + bzip2, a shared tar cursor, and a full PKZIP
`.zip` container (reader + writer, every method sankoch owns, Zip64, streaming,
tar-parity metadata). The zstd encoder beats `zstd -3` on every benchmark
fixture; the zstd decoder is hardened against hostile input. Two P(-1) security
audits have run — the pre-2.6.0 pass over the 2.4.x/2.5.x codec surface, and the
2.6.4 pass over the ZIP surface (0 HIGH · 3 MEDIUM · 1 LOW confirmed, all fixed;
dossier: [`docs/audit/2026-07-20-zip-container.md`](../audit/2026-07-20-zip-container.md)).

The 2.4.x–2.7.x encoder work closed the largest measured gaps in the tree: the
xz-encode arc (2.7.0 repetitive speed, 2.7.1 BT4 match finder, 2.7.2 256 KB window),
then the zstd encoder (2.7.3 DP optimal parse, 2.7.4 cross-block match window —
which now **beats `zstd -19` on record data** — 2.7.5 repetitive-record chain-cutoff
refinement). The encoder ladder is complete.

The **2.8.x line** takes down the two most-ready **Backlog** items as a fresh
ladder (see **▶ Scheduled** below): **2.8.0 = SIMD CRC-32 (`PCLMULQDQ`)**, then
**2.8.1 = GPU texture compression**, then a **P(-1) hardening pass** closes out the
line. It opens **straight into the feature** — no P(-1) pass *leads* 2.8.0
(deliberate); the P(-1) closeout at the end of 2.8.x audits the un-audited 2.7.x
encoder surface together with the 2.8.x additions before the next minor opens. The
remaining Backlog items (DEFLATE match-finder, Brotli) stay parked pending a
consumer profile.

---

## ▶ Next — 2.7.6 (patch, preempts 2.8.x)

### One-shot DEFLATE compress re-encodes bytes at every 1 MiB block boundary

**Critical, open, reproduced on `main` @ `68052c1`.** Filed 2026-07-26 by stiva:
[`docs/development/issues/2026-07-26-deflate-one-shot-multi-block-reencodes-boundary-bytes.md`](issues/2026-07-26-deflate-one-shot-multi-block-reencodes-boundary-bytes.md).

`_deflate_compress_level_inner` (`src/deflate.cyr:1869`) resumes each block at `sp = block_end`
(`:1891`), but the per-block encoders match against the full `src` and can overshoot `sp_end` by
up to 257 bytes without reporting it. The overshot bytes are then emitted a second time as the
head of the next block, so the stream decodes **longer than the input** — ~257 bytes per
boundary, i.e. per `DEFLATE_BLOCK_SIZE` (1 MiB, `:1847`). Levels 1–9, both the fixed
(`:1900`) and dynamic (`:2155`) paths. `deflate_compress` returns the wrong bytes with **no
error** (no container checksum); `zlib`/`gzip` produce streams that sankoch's own decoder and
zlib both reject. The **streaming `*_enc_*` path is correct** and is the consumer workaround.

Why it survived to 2.7.5: no one-shot fixture in `tests/tcyr/` or `fuzz/` crosses 1 MiB (largest
~424 KB against a 4 MiB harness heap), so every one-shot compress test has run as a single block.
`fuzz_deflate.fcyr` does go bigger, but through the streaming path.

Scope for the patch:
1. Clamp matches at `sp_end` (minimal — leaves the outer loop and `bfinal` untouched), or resume
   at the true stop position (better ratio, but `bfinal` is decided before the block runs, so an
   overshoot that consumes the tail would emit no final block at all).
2. Multi-block regression fixtures — 1 048 576 / 1 048 577 / 2 097 152 / 3 145 728 of compressible
   input, round-trip length asserted for deflate/zlib/gzip at levels 1, 3, 6, 9.
3. Consider raising the one-shot ceiling in the fuzz corpus so the boundary is in range.

---

## ▶ Scheduled — 2.8.x

The committed forward ladder: the two most-ready Backlog items, taken down in
order, then a **P(-1) hardening pass closes out the 2.8.x line**. 2.8.0 opens
**straight into the feature** — no P(-1) hardening pass *leads* it (deliberate);
instead the un-audited 2.7.x encoder surface — BT4 `son[]`, the 4 MiB frame-global
chain, the DP-optimal arrays, the window/cutoff math — is audited together with the
2.8.0/2.8.1 additions in the **2.8.x-closeout P(-1) pass** (below), before the next
minor opens.

### 2.8.0 — SIMD CRC-32 via `PCLMULQDQ`

A carryless-multiply (fold-based) CRC-32 on x86_64, beyond the portable
**slice-by-8** table fold 2.3.4 already banked (~2×, wire-identical, x86_64 +
aarch64). PCLMULQDQ was off the critical path *because* slice-by-8 covered the
goal, so this is a further optimisation, not a correctness need — its bar is that
it must not regress and must be provably bit-exact.

Approach (mirrors the prior arcs' "verify each bite" cadence):
1. **x86_64 fold** — the 4-way PCLMULQDQ fold from the Intel whitepaper (folding
   constants per the CRC-32 polynomial), behind a runtime/compile-time gate; keep
   slice-by-8 as the unconditional fallback so no target loses a working path.
2. **aarch64** — either a PMULL (crypto-extension) parallel fold or an explicit
   **fall back to slice-by-8** (no regression on the aarch64 gate — never a scalar
   byte loop).
3. **Wire-identical proof** — every gated CRC-32 output must equal the slice-by-8
   table result **byte-for-byte** across the test corpus, plus a differential fuzz
   (`fold(x) == table(x)` on random buffers). Hand-assembled CRC-folding carries a
   silent-corruption risk; this gate is the whole point. `PCLMULQDQ`-off restores
   the table path.
- Ref: Intel, "Fast CRC Computation … Using PCLMULQDQ" (whitepaper, 2009).

### 2.8.1 — GPU texture compression (BC1–BC7 / ASTC)

The one genuinely different codec: **lossy** and GPU-format-specific, so it does
not fit sankoch's "lossless" identity the way every prior codec did.

- **First sub-step is a home decision, not code.** sankoch is the home for *every
  lossless* codec (modular-by-profile), but a lossy texture codec may instead belong
  with **mabda** — which already has generic compute dispatch (`compute.cyr`) and the
  texture-format enums, but no codecs yet. Resolve this before writing a block encoder;
  it decides the repo, the API shape, and whether the "lossless" framing in `CLAUDE.md`
  needs qualifying.
- **Then a first format** — a CPU reference block encoder (BC1/BC7 for desktop or ASTC
  for mobile, driven by whichever consumer surfaces), block-based, validated against a
  reference decoder.
- Needs a consumer to pin *which* formats matter; scheduled as the direction, with the
  home decision as its gating bite.

### 2.8.x closeout — P(-1) hardening pass

The P(-1) scaffold-hardening pass, run at the **end of the 2.8.x line** (before the next
minor opens), per [`CLAUDE.md` § P(-1)](../../CLAUDE.md). It ships as its own release, as
the 2.6.4 ZIP-surface and 2.5.9/2.5.10 audits did. Deferring it to the closeout (rather than
leading 2.8.0) is the one deviation from "P(-1) before each minor" — recorded deliberately.

Scope — the surface accrued since the last audit (2.6.4, ZIP), audited together:
- **The un-audited 2.7.x encoder surface** — the BT4 binary-tree finder's `son[]` indexing,
  the 4 MiB frame-global hash chain (`_ze_prev` + snapshot/restore/fill), the DP-optimal
  arrays (`_zo_*`, the 4200-entry bounds), and the window / saturation-cutoff math. ~1,000
  lines of new indexing / OOM / integer-range surface never security-reviewed.
- **The 2.8.0/2.8.1 additions** — the hand-assembled `PCLMULQDQ` CRC fold (silent-corruption
  risk is the whole reason it needs the wire-identical gate + an audit), and the new GPU
  texture codec's block encoder.
- Plus the standard closeout gates (cleanliness / dead-code / stale-comment sweeps, a fresh
  benchmark baseline, the security-audit dossier under [`docs/audit/`](../audit/), and a
  doc-health pass).

Primitive sources for the codec items (Rice/Golomb, range encoder, LPC, GPU
dispatch) are tabulated under [§ Primitive sources](#primitive-sources-for-future-codecs) below.

---

## Backlog — unscheduled (to be re-organised)

Parked items with no committed release. Each has a *sound reason to wait* — the
payoff needs a real consumer profile to justify the cost/risk. **To be triaged
into a fresh ladder** when a consumer surfaces.

- **DEFLATE match-finder throughput.** ⚠ **The trigger has fired — this is no
  longer speculative.** The entry used to end "pick up if sit's
  `zlib_compress(1 MB)` target resurfaces as a priority". It has, repeatedly, and
  sit has measured it.

  **Evidence (sit v1.4.8–1.5.x, `docs/benchmarks/2026-08-19-v1.4.8.md`):**

  | measurement | value |
  |---|---:|
  | `add-1MB`, sit vs git | **6.37×** (104.27 ms vs 16.38 ms) |
  | of which `zlib_compress` | **~100 ms — the dominant term** |
  | `blob-hash-1048576B` (sigil SHA-256, same 1 MB) | 4.73 ms |
  | `zlib-compress-65536B` | 1.067 ms |
  | `zlib-compress-1024B` | 123.7 µs |

  **`add-1MB` is sit's single worst benchmark row**, and compression is
  essentially all of it — hashing the same megabyte costs 4.7 ms against
  compression's ~100 ms, a 21× gap. sit has driven every other row it controls
  to parity or better (`init` 0.64×, `commit` 0.59×, `fetch` 0.24×, `status`
  1.38×), so this is the largest remaining gap that is *not* sit's own code.

  **The constraint stands and is the hard part.** zlib byte-for-byte parity is
  load-bearing for sankoch's consumers, so `good_match` and friends are off the
  table — they are speed/ratio trade-offs that change output. A genuine win has
  to find the *same* matches faster: tighter chain-walk scheduling, a better
  hash, or a provably output-preserving lazy-match restructure. **Any candidate
  must be gated on a byte-identical-output test across a real corpus before a
  benchmark number is quoted.**

  Open-ended and large. Pairs naturally with the 2.8.0 SIMD work already
  scheduled, but note that CRC-32 via `PCLMULQDQ` does **not** touch this — the
  cost here is match finding in `lz77.cyr`, not checksumming.
- **Brotli** (new codec) — DEFLATE-family with a static dictionary + context
  modeling; land it when a web-serving / font consumer needs it.

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
  `xz -6` (optimal parse, not bit-identical to `xz`). Since 2.7.0 the *repetitive*
  regime is within ~1.5× of `xz -6` (the `nice_len` greedy shortcut); since 2.7.1
  the *real-source* regime is ~5.8× slower (0.73 vs 4.2 MB/s, BT4 match finder); since
  2.7.2 its **ratio is within ~0.2 % of `xz -6`** on inputs that fit the 256 KB window
  (was +7 %). A speed gap to xz's optimized C persists, and inputs larger than 256 KB
  keep a small ratio residue (a one-line window bump closes it, at more memory). bzip2
  encode is byte-identical to `bzip2 -9`. Neither encoder is in the wire-format SIZE gate
  — both ship informational ratio lines in `bench`.

---

## New-codec context (for the Backlog codec items)

Because the per-codec distlib profiles let a consumer pull only the closure it
needs (see *Modular by profile* in [`CLAUDE.md`](../../CLAUDE.md)), sankoch is the
home for **every** lossless-compression codec — new formats never bloat consumers
that don't use them, so nothing is "a separate crate." The **Brotli** and **GPU
texture compression** backlog items above are the two not-yet-implemented codecs;
Zstandard is done (decode 2.5.0, sovereign encoder 2.5.5, beats `zstd -3`, optimal
parse 2.7.3 — its remaining record-data ratio residue is the 2.7.4 window item, not
a new codec).

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
> Current as of **2.7.5** — the tree is **21 modules**: `runtime.cyr`
> (the lock + alloc seam, extracted from `lib.cyr` at 2.4.9), `zstd.cyr`
> (sovereign RFC-8878 codec) and `tar.cyr` (POSIX ustar/v7 cursor) at 2.5.0,
> then `zip.cyr` (2.6.0) and `zip_methods.cyr` (2.6.1) for the PKZIP container.

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
| xz.cyr           | 2111 | `.xz` de/compress: container + LZMA2 framing + LZMA range decoder/encoder, optimal-parse (`xz_decompress` / `xz_compress`) + `xz_decompress_with_ratio_cap` (2.5.3) + 2.7.0 rep-only `nice_len` greedy shortcut + interior DP cut (repetitive encode ~290–473× faster) + 2.7.1 BT4 binary-tree match finder, xz-private, seed-only skip + 2.7.2 xz-private 256 KB window (real-source ratio now within ~0.2 % of `xz -6`) | full |
| bzip2.cyr        | 1323 | `.bz2` de/compress: bit reader/writer + Huffman + MTF/RLE2 + inverse/forward BWT + RLE1 (`bzip2_decompress` / `bzip2_compress`) + `bzip2_decompress_with_ratio_cap` (2.5.3) | full |
| zstd.cyr         | 3058 | `.zst` de+compress (RFC 8878): decoder (2.5.0, hardened 2.5.6) + sovereign `zstd_compress` encoder (2.5.5 — LZ77 hash-chain matcher + FSE sequence encoder + length-limited Huffman literals, single/4-stream; adaptive FSE sequence tables 2.5.7; priced match selection `_ze_mvalue` 2.5.8; DP optimal parser at levels 7–9 with per-block best-of, 2.7.3; **cross-block frame-global match window (512 KiB), 2.7.4 — beats `zstd -19` on record data**; L9 hash-chain saturation cutoff for repetitive record data, 2.7.5); self-contained bit reader / FSE / Huffman, no runtime | full |
| zip.cyr          | 1206 | PKZIP `.zip` container: in-memory reader + writer, methods 0/8, Zip64 (2.6.2), streaming write + data descriptors + Unix metadata/symlinks (2.6.3), CRC-32 verified, per-member ratio cap; 2.6.4 P(-1) hardening — i64-overflow-safe Zip64 bounds (subtraction form), streaming-abandon lock release, mid-stream-add rejection, name-length limit, cross-entry symlink ledger | full |
| zip_methods.cyr  |  150 | The rest of ZIP's methods (2.6.1): 12 (bzip2) / 93 (zstd) / 95 (xz), read + write. Kept OUT of `[lib.zip]` so the lean profile never pulls those codecs | full |
| tar.cyr          |  710 | Sovereign POSIX ustar + pre-POSIX v7 tar pull-cursor (`tar_open_auto` sniffs gzip/xz/bzip2/zstd); PAX/GNU long-name + two-layer path-traversal guards incl. the 2.5.9 cross-entry symlink ledger (H-1) + parse-path OOM guards (M-3) | full |
| stream.cyr       |  256 | Streaming dispatch (`stream_compress_*`, legacy buffered `stream_decompress_*`, incremental `stream_decompress_init_inc` / `_finish_inc`) | full |
| runtime.cyr      |   73 | Shared runtime seam: `_sankoch_mtx` + two-tier lock (agnos no-op since 2.4.4) + `_sankoch_alloc` arena + fault injection — extracted from `lib.cyr` (2.4.9) so lean profiles pull it without the format-dispatch API | full |
| lib.cyr          |  265 | Include chain + public API + format dispatch + `_sankoch_reset_tables` (references every codec's lazy globals) | full |
| **Total**        | **15745** | | |

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

Fuzz: 7,529 iterations across 6 files (`fuzz_lz4` 700, `fuzz_deflate`
1,629, `fuzz_xz` 1,000, `fuzz_bzip2` 900, `fuzz_zstd` 1,680 — +500
DP-optimal (2.7.3) + 30 cross-block (2.7.4/2.7.5), `fuzz_zip`
1,620 — 300 random + 120 truncation + 300 corruption + 300 hostile-field
+ 200 writer + 200 streaming + 200 Zip64 hostile-offset). Per-file
breakdown in [`state.md` § Fuzz totals](state.md#fuzz-totals).

Distlib: `dist/sankoch.cyr` at 15,792 lines (full) +
`dist/sankoch-core.cyr` at 332 lines (kernel-safe), plus eight lean
single-purpose profiles — `sankoch-zlib.cyr` (4,933),
`sankoch-gzip.cyr` (5,098), `sankoch-xz.cyr` (3,074),
`sankoch-bzip2.cyr` (2,099), `sankoch-zstd.cyr` (3,188),
`sankoch-tar.cyr` (12,312), `sankoch-zip.cyr` (5,654, methods 0/8) and
`sankoch-zipall.cyr` (12,308, every method). Ten profiles total;
per-bundle roles in [`state.md` § Dist bundles](state.md#dist-bundles).

## Dependencies

**Zero external.** Checksums (Adler-32, CRC-32, xxHash32 — batch and
incremental) are inline. No sigil dependency. Stdlib-only: `syscalls`,
`string`, `alloc`, `fmt`, `vec`, `fnptr`, `thread`, `assert` (all
ship with Cyrius ≥ 6.0.1; pin is 6.4.69).

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

*Last Updated: 2026-07-21 (**2.8.x prep + doc sweep**. The encoder ladder is complete — 2.7.5 shipped
the zstd L9 hash-chain saturation cutoff (reclaims the repetitive-record cost the 2.7.4 frame-global
chain had introduced: record L9 2.76 → 1.86 s, ratio Δ ≤ +0.043 %; arch note 001). The **▶ Scheduled**
section is re-opened for the **2.8.x line** — **2.8.0 SIMD CRC-32 (`PCLMULQDQ`)**, **2.8.1 GPU texture
compression** — taken down from the Backlog, which now retains DEFLATE match-finder + Brotli. 2.8.x
opens straight into the feature (no P(-1) lead); a **P(-1) hardening pass closes out the 2.8.x line**
instead — auditing the un-audited 2.7.x encoder surface + the 2.8.x additions before the next minor. File Summary / fuzz / distlib figures re-counted at the 2.7.5 cut (source 15,745;
full bundle 15,792; fuzz 7,529). Recap of the shipped ladder: 2.7.0 xz repetitive speed, 2.7.1 xz BT4
(an HC4 attempt was rejected — the "78 % match finder" was operation-count, not time), 2.7.2 xz 256 KB
window, 2.7.3 zstd optimal parse, 2.7.4 zstd cross-block window, 2.7.5 zstd chain cutoff. Toolchain pin
6.4.69 since 2.7.1.)*
