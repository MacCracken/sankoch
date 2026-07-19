---
name: Sankoch State
description: Living state of the sankoch repo — version, sizes, test totals, in-flight slots, consumers. Refreshed every release.
type: state
---

# Sankoch State

> **Last refresh**: 2026-07-18 (v2.5.7 cut — **zstd encoder parse quality**: repcode-aware matching + adaptive FSE sequence tables [per-block RLE/FSE_Compressed/Predefined], now *beats* `zstd -3` — the default level — by 4–11 % on real code/text/binary; structured/tabular +106 %→−6 % vs `zstd -1`; optional optimal parse deferred to 2.5.8) | **Refresh cadence**: every release; bumped by the release post-hook or by hand if the hook misses.
>
> Per [first-party-documentation.md § Development Docs](https://github.com/MacCracken/agnosticos/blob/main/docs/development/first-party/first-party-documentation.md#development-docs-docsdevelopment), this file holds the **volatile** state. Durable rules live in [`../../CLAUDE.md`](../../CLAUDE.md); release narrative lives in [`../../CHANGELOG.md`](../../CHANGELOG.md); forward ladder lives in [`roadmap.md`](roadmap.md).

---

## Version

- **`VERSION`**: `2.5.7` — single source of truth (2.5.7 = **zstd encoder parse quality** [repcode-aware match finding + adaptive FSE sequence tables; now beats `zstd -3` on real code/text/binary]; 2.5.6 = **zstd encoder competitiveness + decoder hardening** [FSE literal weights + repeat-offset codes + lazy parse + 1..9 level knob; decoder closed against 36 verified OOB/DoS paths + `fuzz_zstd.fcyr`]; 2.5.5 = **sovereign zstd encoder** `zstd_compress` [LZ77 + FSE sequences + Huffman literals; completes the codec, decode shipped 2.5.0]; 2.5.4 = xz / bzip2 encoder throughput [output byte-identical]; 2.5.3 = xz / bzip2 ratio cap; 2.5.2 = toolchain pin refresh to Cyrius 6.4.66; 2.5.1 = per-codec distlib profiles; 2.5.0 = sovereign `zstd.cyr` decoder + shared `tar.cyr` cursor)
- **`cyrius.cyml [package].cyrius`**: `6.4.67` — toolchain pin (bumped from 6.4.66 during the 2.5.6 arc; 2.5.5 shipped on 6.4.66. `cyrius deps` re-resolved, all gates green)
- **Tag**: `2.5.7` (bare semver, no `v` prefix)
- **Released**: 2026-07-18

## Distribution

- **Cyrius stdlib**: shipping as `lib/sankoch.cyr` in Cyrius 6.4.x toolchain releases (full profile).
- **Kernel-safe subset**: `lib/sankoch-core.cyr` ships alongside since the 2.1.2 cut (LZ4 batch decompress only; no alloc / no syscalls / no mutex).
- **Consumers import via**: `include "lib/sankoch.cyr"` — no separate `[deps]` declaration in their `cyrius.cyml`.
- **Stdlib fold-in**: folded into the Cyrius stdlib since 2.0.2 (Cyrius 5.6.34); tracks the toolchain pin in `cyrius.cyml`. Per-version fold-in chronology lives in `CHANGELOG.md`.

## Source

- **Source**: **12,779 lines** across 19 domain modules (`src/*.cyr`). The 2.5.7 arc grew `zstd.cyr` **1,798 → 1,992** (+194 — repcode-aware match finding [`_ze_pr*` model + `_ze_rep_search`] and adaptive FSE sequence tables [`_ze_seq_plan` histogram + cost decision, `_ze_ncount_size`, per-stream RLE/FSE_Compressed/Predefined encode]). Largest modules: `deflate.cyr` **2,540**, `zstd.cyr` **1,992**, `xz.cyr` **1,819**, `bzip2.cyr` **1,316**, `lz4.cyr` **935**, `huffman.cyr` **683**, `gzip.cyr` **638**, `tar.cyr` **513**; `runtime.cyr` **73**, `lib.cyr` **244**, `types.cyr` **42**.
- **Per-file breakdown** lives in [`roadmap.md` § File Summary](roadmap.md#file-summary-at-230). Re-bump there alongside this file on every release.

## Test totals

The suite is split into **19 per-codec × direction suites** plus the
cross-cutting `ratio_cap` and `detect_error` suites under
`tests/tcyr/`, sharing `_harness.tcyr` (includes + 4 MB heap setup +
cross-cutting helpers).

| Suite group                                   | Functions | Assertions |
|-----------------------------------------------|----------:|-----------:|
| `tests/tcyr/*.tcyr` (19 split suites)         |       255 |  4,137,406 |
| `tests/tcyr/git_object.tcyr`                  |        10 |    346,583 |
| **Total**                                     |   **265** | **4,483,989** |

Split suites: `checksum`, `lz4_{compress,decompress}`,
`lz4f_{compress,decompress}`, `deflate_{compress,decompress}`,
`zlib_{compress,decompress}`, `gzip_{compress,decompress}`,
`xz_{compress,decompress}`, `bzip2_{compress,decompress}`,
**`zstd_compress`** (2.5.5 store / RLE / Huffman / LZ77+FSE + 2.5.6 FSE literal
weights / repeat offsets / level knob / **malformed-input decode-survival** [the
34-byte raw-overflow repro + truncations]; zstd reference-`zstd -d` interop is
`scripts/zstd-encode-smoke.sh`, and decode robustness is fuzzed by
`fuzz/fuzz_zstd.fcyr`), `stream`, `detect_error`, **`ratio_cap`** (2.4.5
batch + 2.4.6 streaming + 2.5.3 xz/bzip2 — 26 tests, 98 assertions). Run one
with `cyrius test tests/tcyr/<name>.tcyr`, or all with bare `cyrius test`.

The assertion total is heavily inflated by per-byte content-loop checks on streaming round-trips (a single 128 KB round-trip contributes 131,072 assertions through one `while (i < N) assert(load8(d+i) == load8(s+i))` loop). Read as a coverage-**density** number, not a coverage-**breadth** number. See [`guides/cyrius-usage.md`](../guides/cyrius-usage.md#what-assertions-means-here-and-why-the-number-is-so-large) for the full explanation.

## Fuzz totals

- **5,279 iterations** across 26 harness functions in 5 files:
  - `fuzz/fuzz_lz4.fcyr`: 700 (round-trip 500 + malformed 200)
  - `fuzz/fuzz_deflate.fcyr`: 1,629 (deflate batch 340 + zlib 160 + gzip 160 + 4 streaming variants 204 + tree-shape 55 + skewed-freq 30 + ratio-cap 240 + ratio-cap malformed 100 + **streaming ratio-cap 240 + streaming malformed 100**)
  - `fuzz/fuzz_xz.fcyr`: 900 (random-input 300 + corruption 200 + encode→decode round-trip 300 + **ratio-cap 100**)
  - `fuzz/fuzz_bzip2.fcyr`: 900 (random-input 300 + corruption 200 + encode→decode round-trip 300 + **ratio-cap 100**)
  - `fuzz/fuzz_zstd.fcyr`: 1,150 (2.5.6 — decode-survival on random input 400 + encode→decode round-trip across 5 distributions 600 + corruption of valid streams 150; found the decoder-hardening SIGSEGVs)

## Dist bundles

| Bundle                       | Lines | Role |
|------------------------------|------:|------|
| `dist/sankoch.cyr`           | 12,761 | Full library — LZ4 / LZ4F / DEFLATE / zlib / gzip / xz / bzip2 de/compress + zstd de/compress (encode 2.5.5, competitive 2.5.6–2.5.7) + tar cursor, batch + streaming, + ratio-capped decompress (DEFLATE family batch + streaming; xz + bzip2 batch, 2.5.3) |
| `dist/sankoch-core.cyr`      |   317 | **[lib.core]** kernel-safe LZ4 batch decompress only (types + xxhash32 + lz4_decode); no alloc / syscalls / mutex (AGNOS initrd) |
| `dist/sankoch-zlib.cyr`      | 4,889 | **[lib.zlib]** (2.4.9) — DEFLATE/zlib only (`zlib_compress`/`zlib_decompress` + closure); drops LZ4/gzip/xz/bzip2/zstd/tar/streaming. Keeps the initialised-global footprint low so a consumer stays under its `max 1024 globals` budget while tracking current sankoch (sit's git read path / thoth's git producer). Runtime helpers via the extracted `src/runtime.cyr` |
| `dist/sankoch-gzip.cyr`      | 5,042 | **[lib.gzip]** (2.5.1) — gzip/DEFLATE decode closure + CRC-32 (the zlib profile with the gzip envelope) |
| `dist/sankoch-xz.cyr`        | 2,755 | **[lib.xz]** (2.5.1) — `.xz` (LZMA2) decode: lz77 match model + CRC-32 / CRC-64; + `xz_decompress_with_ratio_cap` (2.5.3, self-contained closure) |
| `dist/sankoch-bzip2.cyr`     | 2,071 | **[lib.bzip2]** (2.5.1) — bzip2 decode (BWT + Huffman + MTF) + CRC-32/BZIP2 + runtime; + `bzip2_decompress_with_ratio_cap` (2.5.3, self-contained closure) |
| `dist/sankoch-zstd.cyr`      | 2,034 | **[lib.zstd]** (2.5.1) — RFC-8878 zstd **de + compress** (decode 2.5.0, hardened 2.5.6; sovereign `zstd_compress` encoder 2.5.5, competitive 2.5.6–2.5.7 — now beats `zstd -3` — with a 1..9 `zstd_compress_level`), fully self-contained (own bit reader / FSE / Huffman, no runtime/mutex). agnova `base-system.tar.zst` + takumi zstd tarballs; the ZIP method-93 write path (2.6.x) |
| `dist/sankoch-tar.cyr`       | 10,682 | **[lib.tar]** (2.5.1) — sovereign tar cursor + every envelope `tar_open_auto` dispatches to (gzip / xz / bzip2 / zstd); the "extract any tarball" profile (takumi source tarballs, agnova rootfs) |

All zero deps. Regenerated at every release via `cyrius distlib` (full) plus the seven named profiles — `cyrius distlib core` / `zlib` / `gzip` / `xz` / `bzip2` / `zstd` / `tar` (eight bundles total). CI gates on drift across all eight.

## In-flight slots

**Ladder committed; 2.5.7 shipped (2026-07-18), 2.5.8 optional / 2.6.x next.** 2.5.7
landed the last parse-quality items: **repcode-aware match finding** (bias the matcher
toward recent offsets) and **adaptive FSE sequence tables** (per-block RLE /
FSE_Compressed / Predefined selection fitted to the block histogram — the dominant win).
The encoder now *beats* `zstd -3` (the default level) by 4–11 % on real code / text /
binary, and structured/tabular data went from +106 % to −6 % vs `zstd -1` — ratios in
[`docs/benchmarks/2026-07-18-2.5.7-parse-quality.md`](../benchmarks/2026-07-18-2.5.7-parse-quality.md).
Reference `zstd -d` v1.5.7 (108/108 files × sizes + the 13-case smoke) is the correctness
bar. Remaining forward ladder in
[`roadmap.md`](roadmap.md#-scheduled--the-committed-next-release-ladder):

- **2.5.8 (optional) — zstd optimal / 2-pass parse.** The niche residue after
  2.5.7: very regular record data (synthetic csv +45 %, log lines +104 % — tiny
  in absolute terms) where zstd's optimal parse finds longer cross-record matches
  than a greedy+lazy+repcode hash chain. Price each candidate under the current
  FSE tables and pick the globally cheaper path. Reference `zstd -d` stays the
  correctness bar. Schedule only if a consumer needs the last few percent.
- **2.6.x — ZIP archive container arc** (`zip.cyr` alongside `tar.cyr`),
  full-feature but **agnosai-first**:
  - **2.6.0** — agnosai `.agpkg` core: store + DEFLATE, read **and**
    write, in-memory byte buffers, per-entry uncompressed cap (folds into
    `ERR_RATIO_LIMIT`), zip-slip guards. ~250 lines reusing deflate +
    crc32. The whole agnosai filing; **not blocking agnosai v2.0.0**
    (behind its non-default `definitions` feature, post-v2.0.0).
  - **2.6.1** — other methods, all both ways (12 bzip2 / 95 xz / 93 zstd — all
    writable now that 2.5.5 landed); **2.6.2** — zip64; **2.6.3** —
    streaming + per-entry metadata. Parity build-out; does not block
    agnosai. Encryption /
    multi-disk / Deflate64 are non-goals.

Not scheduled (unchanged): the deferred markers in
[`roadmap.md`](roadmap.md) — SIMD CRC-32 (`PCLMULQDQ`) and a wire-identical
DEFLATE match-finder speedup — and the Future bucket (Brotli, GPU texture — Zstandard
encode shipped 2.5.5).

## Consumers

| Consumer           | Uses             | Why                                  |
|--------------------|------------------|--------------------------------------|
| Future git impl    | DEFLATE, zlib    | Git objects are zlib-compressed      |
| ark                | LZ4 or DEFLATE   | Package compression                  |
| AGNOS kernel       | LZ4              | initrd, snapshots                    |
| shravan / tarang   | DEFLATE, gzip    | Embedded compressed streams          |
| sit                | zlib             | Git-object reads (post-v2.0.3); **ratio-capped decompress** for untrusted wire objects — batch (2.4.5) + streaming (2.4.6) |
| kii                | DEFLATE (agnos)  | PNG IDAT inflate; first agnos consumer (drove the 2.4.4 agnos-lock no-op) |
| takumi             | gzip, **xz**, **bzip2**, **zstd** | `.tar.{gz,xz,bz2,zst}` extraction; xz/bzip2 encode (2.4.1/2.4.3) + **zstd encode (2.5.5)** available |
| agnosai            | ZIP read+write *(pending 2.6.0)* | `.agpkg` definition bundles (`definitions/packaging.rs` export/import; DEFLATE) — drives the scheduled `zip.cyr` container |
| Any crate          | All              | Replaces zlib FFI / shelling to gzip |

## CI / release gates

- **Cleanliness**: `cyrius build` 0 warnings on library path; `cyrius lint` 0 warnings per source file; `cyrfmt --check` clean across all `src/` + `programs/` + `tests/` + `fuzz/`; `cyrius vet src/lib.cyr` clean (25 deps, 0 untrusted, 0 missing).
- **Tests**: all tcyr suites green (19 split codec×direction suites incl. `zstd_compress` + `ratio_cap` + `git_object`, auto-discovered by the CI Test loop); all fuzz harnesses green (5 files — lz4 / deflate / xz / bzip2 / zstd, auto-discovered via `fuzz/*.fcyr`).
- **Wire-format gate**: 43 SIZE lines in `cyrius bench` output must remain byte-for-byte identical across patch / minor releases unless explicitly broken with a CHANGELOG `Breaking` entry. (2.3.3 added the four `lz4f_bm{4,5,6,7}` block-max-sweep lines; pre-existing lines unchanged.) The **xz and bzip2 encoders** (2.4.1 / 2.4.3) and the **zstd encoder** (`SIZE zstd6_*`, 2.5.6) are **deliberately excluded** from this gate — their output is not bit-reproducible across encoder versions, so they ship informational ratio lines in `bench` instead, as does the 2.4.5 ratio-cap section.
- **Bundle gate**: `cyrius distlib` + `cyrius distlib core` regenerate `dist/sankoch.cyr` + `dist/sankoch-core.cyr`; CI fails on drift.
- **Kernel-safe tripwire**: `programs/core_smoke.cyr` links ONLY the `[lib.core]` modules and exercises LZ4 batch decompress on known fixtures. Any alloc / syscall / mutex leak into the core subset fails the build.
- **aarch64 cross-build**: hard gate in both ci.yml and release.yml; `cyrius build --aarch64 src/lib.cyr` must succeed and produce a valid ARM aarch64 ELF. Workflows expect `cycc_aarch64` in the Cyrius bundle (renamed from `cc5_aarch64` at Cyrius 6.0).
- **Tag filter**: release workflow triggers on bare semver tags only (`2.4.5`, not `v2.4.5`).
- **Version-verify**: release asserts `VERSION == git tag` before building.

## Recent releases

Most recent first. Full per-release notes in [`../../CHANGELOG.md`](../../CHANGELOG.md).

| Tag    | Date       | Headline                                              |
|--------|------------|-------------------------------------------------------|
| 2.5.7  | 2026-07-18 | **zstd encoder parse quality** — repcode-aware match finding + adaptive FSE sequence tables (per-block RLE/FSE_Compressed/Predefined); now *beats* `zstd -3` (the default level) by 4–11 % on real code/text/binary; structured/tabular +106 %→−6 % vs `zstd -1` |
| 2.5.6  | 2026-07-18 | **zstd encoder competitiveness + decoder hardening** — FSE literal weights + repeat offsets + lazy parse + 1..9 level knob (now *beats* `zstd -1` on source/binary/repetitive); decoder closed against 36 verified OOB/DoS paths + new `fuzz_zstd.fcyr` |
| 2.5.5  | 2026-07-18 | **Sovereign zstd encoder** `zstd_compress` (LZ77 + FSE sequences + Huffman literals) — completes the zstd codec; reference-`zstd -d`-validated, ~2-17 % behind `zstd -1` |
| 2.5.4  | 2026-07-18 | xz / bzip2 encoder throughput — output-byte-identical speedups (xz optimal-parse ~5× text / ~2.5× repetitive; bzip2 ~5% random) |
| 2.5.3  | 2026-07-18 | xz / bzip2 ratio cap (`*_decompress_with_ratio_cap`; `ERR_RATIO_LIMIT`) — DEFLATE-family zip-bomb defense extended to the last two batch decoders; closes INFO-F |
| 2.5.2  | 2026-07-18 | Toolchain pin refresh → Cyrius 6.4.66 (maintenance; no source/API/wire-format change) |
| 2.5.1  | 2026-07-10 | Per-codec distlib profiles (`[lib.zstd]` / `[lib.bzip2]` / `[lib.xz]` / `[lib.gzip]` / `[lib.tar]`) — pull one codec's closure, not the whole lib |
| 2.5.0  | 2026-07-10 | Sovereign zstd decode (`zstd.cyr`, 40/40 vs reference zstd v1.5.7) + shared `tar.cyr` cursor + pin → 6.4.43 |
| 2.4.9  | 2026-07-03 | `[lib.zlib]` distlib profile (`dist/sankoch-zlib.cyr`) + shared `runtime.cyr` seam extraction |
| 2.4.8  | 2026-07-01 | Undersized-array stack-smash sweep (cyrius 6.3.13+ stack-allocated locals) + pin → 6.3.18 |
| 2.4.7  | 2026-06-30 | bzip2 undersized-array stack-smash fix (cyrius 6.3.13+ stack-allocated locals) |
| 2.4.6  | 2026-06-25 | Streaming ratio cap (`*_dec_init_capped`) — incremental zip-bomb defense extending 2.4.5 to the streaming decode path |
| 2.4.5  | 2026-06-25 | Ratio-capped decompression (`*_with_ratio_cap`; `ERR_RATIO_LIMIT`; sit zip-bomb defense) + cyrius pin → 6.2.44 |
| 2.4.4  | 2026-06-18 | AGNOS-compatible lock primitives (`_sankoch_lock` / `_unlock` no-op under `CYRIUS_TARGET_AGNOS`; surfaced by kii) |
| 2.4.3  | 2026-06-17 | bzip2 encode (`bzip2_compress`; forward BWT block-sort; byte-identical to `bzip2 -9`) |
| 2.4.2  | 2026-06-17 | bzip2 decode (`bzip2_decompress` + `FORMAT_BZIP2` + CRC-32/BZIP2; BWT pipeline) |
| 2.4.1  | 2026-06-16 | xz / LZMA encode (`xz_compress`, optimal parse; `xz -d` round-trips) |
| 2.4.0  | 2026-06-16 | xz / LZMA decode (`FORMAT_XZ` + `xz_decompress` + CRC-64/XZ; decode-only) |
| 2.3.8  | 2026-06-16 | P(-1) closeout — 2.3.x line complete (zero audit findings) |

## Open INFOs carried forward

Minor tracked items for the next P(-1) / audit pass to resolve or rebase. From the most recent audit ([`docs/audit/2026-06-16-pre-2.4.0.md`](../audit/2026-06-16-pre-2.4.0.md), zero HIGH/MED/LOW findings). Closed items live in `CHANGELOG.md`.

- **INFO-B** — batch `_deflate_decompress_dict` / `_zlib_decompress_dict` require `dst_cap >= dict_len` (dict staged in `dst`). The 2.3.6 *streaming* FDICT path removed this for the streaming variant (dict in scratch); the batch constraint stands. Already enforced at runtime; docstring-polish item.
- **INFO-C** — aarch64 LZ77 / FDICT match-copy use unaligned `load64`. Permitted by ARMv6+ but some implementations pay a cycle penalty. Flagged for future investigation if aarch64 perf benchmarks surface this as hot.
- **INFO-D** — on a *retried* OOM, partially-allocated lazy tables orphan their bump-allocated memory (`_sankoch_alloc` arena does not free). OOM-path only; minor.
- **INFO-E** — the xz and bzip2 encoders allocate large working buffers (xz prob/DP ~0.6 MB; bzip2 BWT + Huffman ~44 MB at level 9) as lazy singletons. Acceptable for userspace encode, but a future audit should confirm the OOM-propagation paths on first-call failure.
- ~~**INFO-F**~~ — **CLOSED in 2.5.3.** The ratio cap now covers xz and bzip2 decode too (`xz_decompress_with_ratio_cap` / `bzip2_decompress_with_ratio_cap`, batch). The DEFLATE-family-only gap is closed.

---

*This file is the canonical source for live-state claims. CLAUDE.md must reference, never inline. Refresh in place at every release.*
