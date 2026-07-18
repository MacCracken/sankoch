---
name: Sankoch State
description: Living state of the sankoch repo — version, sizes, test totals, in-flight slots, consumers. Refreshed every release.
type: state
---

# Sankoch State

> **Last refresh**: 2026-07-18 (v2.5.2 cut — toolchain pin refresh to Cyrius 6.4.66; no source/API/wire-format change) | **Refresh cadence**: every release; bumped by the release post-hook or by hand if the hook misses.
>
> Per [first-party-documentation.md § Development Docs](https://github.com/MacCracken/agnosticos/blob/main/docs/development/first-party/first-party-documentation.md#development-docs-docsdevelopment), this file holds the **volatile** state. Durable rules live in [`../../CLAUDE.md`](../../CLAUDE.md); release narrative lives in [`../../CHANGELOG.md`](../../CHANGELOG.md); forward ladder lives in [`roadmap.md`](roadmap.md).

---

## Version

- **`VERSION`**: `2.5.2` — single source of truth (2.5.2 = toolchain pin refresh to Cyrius 6.4.66, no source/API/wire-format change; 2.5.1 = per-codec distlib profiles: `[lib.zstd]` / `[lib.bzip2]` / `[lib.xz]` / `[lib.gzip]` / `[lib.tar]`, so a consumer pulls one codec's closure not the whole lib; 2.5.0 = sovereign `zstd.cyr` decoder [40/40 vs reference zstd v1.5.7] + shared `tar.cyr` cursor)
- **`cyrius.cyml [package].cyrius`**: `6.4.66` — toolchain pin (bumped from 6.4.43 at 2.5.2; clears the pin-vs-`cycc` drift warning, re-resolves the current stdlib snapshot)
- **Tag**: `2.5.2` (bare semver, no `v` prefix)
- **Released**: 2026-07-18

## Distribution

- **Cyrius stdlib**: shipping as `lib/sankoch.cyr` in Cyrius 6.4.x toolchain releases (full profile).
- **Kernel-safe subset**: `lib/sankoch-core.cyr` ships alongside since the 2.1.2 cut (LZ4 batch decompress only; no alloc / no syscalls / no mutex).
- **Consumers import via**: `include "lib/sankoch.cyr"` — no separate `[deps]` declaration in their `cyrius.cyml`.
- **Stdlib fold-in**: folded into the Cyrius stdlib since 2.0.2 (Cyrius 5.6.34); tracks the toolchain pin in `cyrius.cyml`. Per-version fold-in chronology lives in `CHANGELOG.md`.

## Source

- **Source**: **11,351 lines** across 19 domain modules (`src/*.cyr`) — up from 16 as the 2.4.9 → 2.5.0 arc added three files: `runtime.cyr` (**73** — the lock + alloc seam, extracted from `lib.cyr` at 2.4.9, which dropped `lib.cyr` to **239**), then `zstd.cyr` (**729** — sovereign RFC-8878 decoder) and `tar.cyr` (**513** — POSIX ustar/v7 pull-cursor) at 2.5.0. Largest modules: `deflate.cyr` **2,540**, `xz.cyr` **1,738**, `bzip2.cyr` **1,239**, `lz4.cyr` **935**, `zstd.cyr` **729**, `huffman.cyr` **683**, `gzip.cyr` **638**; `types.cyr` **42**.
- **Per-file breakdown** lives in [`roadmap.md` § File Summary](roadmap.md#file-summary-at-230). Re-bump there alongside this file on every release.

## Test totals

The suite is split into **18 per-codec × direction suites** plus the
cross-cutting `ratio_cap` and `detect_error` suites under
`tests/tcyr/`, sharing `_harness.tcyr` (includes + 4 MB heap setup +
cross-cutting helpers).

| Suite group                                   | Functions | Assertions |
|-----------------------------------------------|----------:|-----------:|
| `tests/tcyr/*.tcyr` (18 split suites)         |       224 |  4,137,251 |
| `tests/tcyr/git_object.tcyr`                  |        10 |    346,583 |
| **Total**                                     |   **234** | **4,483,834** |

Split suites: `checksum`, `lz4_{compress,decompress}`,
`lz4f_{compress,decompress}`, `deflate_{compress,decompress}`,
`zlib_{compress,decompress}`, `gzip_{compress,decompress}`,
`xz_{compress,decompress}`, `bzip2_{compress,decompress}`, `stream`,
`detect_error`, **`ratio_cap`** (2.4.5 batch + 2.4.6 streaming — 16 tests,
66 assertions). Run one with `cyrius test tests/tcyr/<name>.tcyr`, or all
with bare `cyrius test`.

The assertion total is heavily inflated by per-byte content-loop checks on streaming round-trips (a single 128 KB round-trip contributes 131,072 assertions through one `while (i < N) assert(load8(d+i) == load8(s+i))` loop). Read as a coverage-**density** number, not a coverage-**breadth** number. See [`guides/cyrius-usage.md`](../guides/cyrius-usage.md#what-assertions-means-here-and-why-the-number-is-so-large) for the full explanation.

## Fuzz totals

- **3,929 iterations** across 21 harness functions in 4 files:
  - `fuzz/fuzz_lz4.fcyr`: 700 (round-trip 500 + malformed 200)
  - `fuzz/fuzz_deflate.fcyr`: 1,629 (deflate batch 340 + zlib 160 + gzip 160 + 4 streaming variants 204 + tree-shape 55 + skewed-freq 30 + ratio-cap 240 + ratio-cap malformed 100 + **streaming ratio-cap 240 + streaming malformed 100**)
  - `fuzz/fuzz_xz.fcyr`: 800 (random-input 300 + corruption 200 + encode→decode round-trip 300)
  - `fuzz/fuzz_bzip2.fcyr`: 800 (random-input 300 + corruption 200 + encode→decode round-trip 300)

## Dist bundles

| Bundle                       | Lines | Role |
|------------------------------|------:|------|
| `dist/sankoch.cyr`           | 11,394 | Full library — LZ4 / LZ4F / DEFLATE / zlib / gzip / xz / bzip2 de/compress + zstd decode + tar cursor, batch + streaming, + ratio-capped decompress (batch + streaming) |
| `dist/sankoch-core.cyr`      |   331 | **[lib.core]** kernel-safe LZ4 batch decompress only (types + xxhash32 + lz4_decode); no alloc / syscalls / mutex (AGNOS initrd) |
| `dist/sankoch-zlib.cyr`      | 4,924 | **[lib.zlib]** (2.4.9) — DEFLATE/zlib only (`zlib_compress`/`zlib_decompress` + closure); drops LZ4/gzip/xz/bzip2/zstd/tar/streaming. Keeps the initialised-global footprint low so a consumer stays under its `max 1024 globals` budget while tracking current sankoch (sit's git read path / thoth's git producer). Runtime helpers via the extracted `src/runtime.cyr` |
| `dist/sankoch-gzip.cyr`      | 5,077 | **[lib.gzip]** (2.5.1) — gzip/DEFLATE decode closure + CRC-32 (the zlib profile with the gzip envelope) |
| `dist/sankoch-xz.cyr`        | 2,697 | **[lib.xz]** (2.5.1) — `.xz` (LZMA2) decode: lz77 match model + CRC-32 / CRC-64 |
| `dist/sankoch-bzip2.cyr`     | 2,014 | **[lib.bzip2]** (2.5.1) — bzip2 decode (BWT + Huffman + MTF) + CRC-32/BZIP2 + runtime |
| `dist/sankoch-zstd.cyr`      |   782 | **[lib.zstd]** (2.5.1) — RFC-8878 zstd decode, fully self-contained (own bit reader / FSE / Huffman). Smallest useful profile — the agnova `base-system.tar.zst` installer path + takumi's zstd tarballs |
| `dist/sankoch-tar.cyr`       | 9,308 | **[lib.tar]** (2.5.1) — sovereign tar cursor + every envelope `tar_open_auto` dispatches to (gzip / xz / bzip2 / zstd); the "extract any tarball" profile (takumi source tarballs, agnova rootfs) |

All zero deps. Regenerated at every release via `cyrius distlib` (full) plus the seven named profiles — `cyrius distlib core` / `zlib` / `gzip` / `xz` / `bzip2` / `zstd` / `tar` (eight bundles total). CI gates on drift across all eight.

## In-flight slots

**None committed.** The 2.4.5 cut closed the sit ratio-cap backlog item
(batch `*_with_ratio_cap`); 2.4.6 extended it to the streaming decode path
(`*_dec_init_capped` for zlib / deflate / gzip). Candidate follow-ons,
none scheduled:

- **xz / bzip2 ratio cap** — extend `*_with_ratio_cap` to xz and bzip2
  decode (both funnel through localized output chokepoints — `_xz_put` /
  `_xz_copy_match`, the bzip2 RLE1 run-emit — so the same incremental
  guard applies). Not needed by sit (zlib only); pick up if a consumer
  inflates untrusted `.xz` / `.bz2`.
- xz / bzip2 **encoder throughput** passes (the optimal-parse DP and the
  BWT block-sort dominate their encode time).
- The deferred markers in [`roadmap.md`](roadmap.md) — SIMD CRC-32
  (`PCLMULQDQ`) and a wire-identical DEFLATE match-finder speedup.
- The Future bucket (Zstandard, Brotli, GPU texture) per
  [`roadmap.md`](roadmap.md).

## Consumers

| Consumer           | Uses             | Why                                  |
|--------------------|------------------|--------------------------------------|
| Future git impl    | DEFLATE, zlib    | Git objects are zlib-compressed      |
| ark                | LZ4 or DEFLATE   | Package compression                  |
| AGNOS kernel       | LZ4              | initrd, snapshots                    |
| shravan / tarang   | DEFLATE, gzip    | Embedded compressed streams          |
| sit                | zlib             | Git-object reads (post-v2.0.3); **ratio-capped decompress** for untrusted wire objects — batch (2.4.5) + streaming (2.4.6) |
| kii                | DEFLATE (agnos)  | PNG IDAT inflate; first agnos consumer (drove the 2.4.4 agnos-lock no-op) |
| takumi             | gzip, **xz**, **bzip2** | `.tar.gz` + `.tar.xz` (2.4.0) + `.tar.bz2` (2.4.2) extraction; xz encode (2.4.1) + bzip2 encode (2.4.3) also available |
| Any crate          | All              | Replaces zlib FFI / shelling to gzip |

## CI / release gates

- **Cleanliness**: `cyrius build` 0 warnings on library path; `cyrius lint` 0 warnings per source file; `cyrfmt --check` clean across all `src/` + `programs/` + `tests/` + `fuzz/`; `cyrius vet src/lib.cyr` clean (25 deps, 0 untrusted, 0 missing).
- **Tests**: all tcyr suites green (18 split codec×direction suites + `ratio_cap` + `git_object`, auto-discovered by the CI Test loop); all 21 fuzz harness functions green.
- **Wire-format gate**: 43 SIZE lines in `cyrius bench` output must remain byte-for-byte identical across patch / minor releases unless explicitly broken with a CHANGELOG `Breaking` entry. (2.3.3 added the four `lz4f_bm{4,5,6,7}` block-max-sweep lines; pre-existing lines unchanged.) The **xz and bzip2 encoders** (2.4.1 / 2.4.3) are **deliberately excluded** from this gate — they ship informational ratio lines in `bench` instead, as does the 2.4.5 ratio-cap section.
- **Bundle gate**: `cyrius distlib` + `cyrius distlib core` regenerate `dist/sankoch.cyr` + `dist/sankoch-core.cyr`; CI fails on drift.
- **Kernel-safe tripwire**: `programs/core_smoke.cyr` links ONLY the `[lib.core]` modules and exercises LZ4 batch decompress on known fixtures. Any alloc / syscall / mutex leak into the core subset fails the build.
- **aarch64 cross-build**: hard gate in both ci.yml and release.yml; `cyrius build --aarch64 src/lib.cyr` must succeed and produce a valid ARM aarch64 ELF. Workflows expect `cycc_aarch64` in the Cyrius bundle (renamed from `cc5_aarch64` at Cyrius 6.0).
- **Tag filter**: release workflow triggers on bare semver tags only (`2.4.5`, not `v2.4.5`).
- **Version-verify**: release asserts `VERSION == git tag` before building.

## Recent releases

Most recent first. Full per-release notes in [`../../CHANGELOG.md`](../../CHANGELOG.md).

| Tag    | Date       | Headline                                              |
|--------|------------|-------------------------------------------------------|
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
- **INFO-F** — the ratio cap (2.4.5 batch + 2.4.6 streaming) covers the DEFLATE family only; xz / bzip2 decode have analogous chokepoints but are not yet capped (see [In-flight slots](#in-flight-slots)). Not a defect — sit (the driving consumer) inflates zlib only.

---

*This file is the canonical source for live-state claims. CLAUDE.md must reference, never inline. Refresh in place at every release.*
