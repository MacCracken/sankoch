---
name: Sankoch State
description: Living state of the sankoch repo — version, sizes, test totals, in-flight slots, consumers. Refreshed every release.
type: state
---

# Sankoch State

> **Last refresh**: 2026-06-17 (v2.4.3 cut — bzip2 encode shipped; bzip2 codec + v2.4.x arc complete) | **Refresh cadence**: every release; bumped by the release post-hook or by hand if the hook misses.
>
> Per [first-party-documentation.md § Development Docs](https://github.com/MacCracken/agnosticos/blob/main/docs/development/first-party/first-party-documentation.md#development-docs-docsdevelopment), this file holds the **volatile** state. Durable rules live in [`../../CLAUDE.md`](../../CLAUDE.md); release narrative lives in [`../../CHANGELOG.md`](../../CHANGELOG.md); forward ladder lives in [`roadmap.md`](roadmap.md).

---

## Version

- **`VERSION`**: `2.4.3` — single source of truth
- **`cyrius.cyml [package].cyrius`**: `6.2.15` — toolchain pin
- **Tag**: `2.4.3` (bare semver, no `v` prefix)
- **Released**: 2026-06-17

## Distribution

- **Cyrius stdlib**: shipping as `lib/sankoch.cyr` in Cyrius 6.2.x toolchain releases (full profile).
- **Kernel-safe subset**: `lib/sankoch-core.cyr` ships alongside since the 2.1.2 cut (LZ4 batch decompress only; no alloc / no syscalls / no mutex).
- **Consumers import via**: `include "lib/sankoch.cyr"` — no separate `[deps]` declaration in their `cyrius.cyml`.
- **Stdlib fold-in**: folded into the Cyrius stdlib since 2.0.2 (Cyrius 5.6.34); tracks the toolchain pin in `cyrius.cyml`. Per-version fold-in chronology lives in `CHANGELOG.md`.

## Source

- **Source**: **9,866 lines** across 16 domain modules (`src/*.cyr`) — `src/bzip2.cyr` is **1,239** (de/compress) after the 2.4.3 encoder.
- **Per-file breakdown** lives in [`roadmap.md` § File Summary](roadmap.md#file-summary-at-230). Re-bump there alongside this file on every release.

## Test totals

The suite is split into **17 per-codec × direction suites** under
`tests/tcyr/`, sharing `_harness.tcyr` (includes + 4 MB heap setup +
cross-cutting helpers).

| Suite group                                   | Functions | Assertions |
|-----------------------------------------------|----------:|-----------:|
| `tests/tcyr/*.tcyr` (17 split suites)         |       208 |  4,137,185 |
| `tests/tcyr/git_object.tcyr`                  |        10 |    346,583 |
| **Total**                                     |   **218** | **4,483,768** |

Split suites: `checksum`, `lz4_{compress,decompress}`,
`lz4f_{compress,decompress}`, `deflate_{compress,decompress}`,
`zlib_{compress,decompress}`, `gzip_{compress,decompress}`,
`xz_{compress,decompress}`, `bzip2_{compress,decompress}`, `stream`,
`detect_error`. Run one with `cyrius test tests/tcyr/<name>.tcyr`, or
all with bare `cyrius test`.

The assertion total is heavily inflated by per-byte content-loop checks on streaming round-trips (a single 128 KB round-trip contributes 131,072 assertions through one `while (i < N) assert(load8(d+i) == load8(s+i))` loop). Read as a coverage-**density** number, not a coverage-**breadth** number. See [`guides/cyrius-usage.md`](../guides/cyrius-usage.md#what-assertions-means-here-and-why-the-number-is-so-large) for the full explanation.

## Fuzz totals

- **3,249 iterations** across 17 harness functions in 4 files:
  - `fuzz/fuzz_lz4.fcyr`: 700 (round-trip 500 + malformed 200)
  - `fuzz/fuzz_deflate.fcyr`: 949 (deflate batch 340 + zlib 160 + gzip 160 + 4 streaming variants 204 + tree-shape 55 + skewed-freq 30)
  - `fuzz/fuzz_xz.fcyr`: 800 (random-input 300 + corruption 200 + encode→decode round-trip 300)
  - `fuzz/fuzz_bzip2.fcyr`: 800 (random-input 300 + corruption 200 + encode→decode round-trip 300)

## Dist bundles

| Bundle                       | Lines | Role |
|------------------------------|------:|------|
| `dist/sankoch.cyr`           | 9,844 | Full library — DEFLATE / zlib / gzip / LZ4 + LZ4F + xz de/compress + bzip2 de/compress, batch + streaming |
| `dist/sankoch-core.cyr`      |   315 | Kernel-safe LZ4 batch decompress only (AGNOS initrd) |

Both zero deps. Regenerated via `cyrius distlib` and `cyrius distlib core` at every release. CI gates on drift.

## In-flight slots

**None committed.** The v2.4.x arc (xz + bzip2, both directions) is
complete as of 2.4.3 — see [Recent releases](#recent-releases). Candidate
follow-ons, none scheduled:

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
| sit                | zlib             | Git-object reads (post-v2.0.3)       |
| takumi             | gzip, **xz**, **bzip2** | `.tar.gz` + `.tar.xz` (2.4.0) + `.tar.bz2` (2.4.2) extraction; xz encode (2.4.1) + bzip2 encode (2.4.3) also available |
| Any crate          | All              | Replaces zlib FFI / shelling to gzip |

## CI / release gates

- **Cleanliness**: `cyrius build` 0 warnings on library path; `cyrius lint` 0 warnings per source file; `cyrfmt --check` clean across all `src/` + `programs/` + `tests/` + `fuzz/`; `cyrius vet src/lib.cyr` clean (22 deps, 0 untrusted, 0 missing).
- **Tests**: all tcyr suites green (17 split codec×direction suites + `git_object`, auto-discovered by the CI Test loop); all 17 fuzz harness functions green.
- **Wire-format gate**: 43 SIZE lines in `cyrius bench` output must remain byte-for-byte identical across patch / minor releases unless explicitly broken with a CHANGELOG `Breaking` entry. (2.3.3 added the four `lz4f_bm{4,5,6,7}` block-max-sweep lines; pre-existing lines unchanged.) The **xz and bzip2 encoders** (2.4.1 / 2.4.3) are **deliberately excluded** from this gate — they ship informational ratio lines in `bench` instead.
- **Bundle gate**: `cyrius distlib` + `cyrius distlib core` regenerate `dist/sankoch.cyr` + `dist/sankoch-core.cyr`; CI fails on drift.
- **Kernel-safe tripwire**: `programs/core_smoke.cyr` links ONLY the `[lib.core]` modules and exercises LZ4 batch decompress on known fixtures. Any alloc / syscall / mutex leak into the core subset fails the build.
- **aarch64 cross-build**: hard gate in both ci.yml and release.yml; `cyrius build --aarch64 src/lib.cyr` must succeed and produce a valid ARM aarch64 ELF. Workflows expect `cycc_aarch64` in the Cyrius bundle (renamed from `cc5_aarch64` at Cyrius 6.0).
- **Tag filter**: release workflow triggers on bare semver tags only (`2.3.0`, not `v2.3.0`).
- **Version-verify**: release asserts `VERSION == git tag` before building.

## Recent releases

Most recent first. Full per-release notes in [`../../CHANGELOG.md`](../../CHANGELOG.md).

| Tag    | Date       | Headline                                              |
|--------|------------|-------------------------------------------------------|
| 2.4.3  | 2026-06-17 | bzip2 encode (`bzip2_compress`; forward BWT block-sort; byte-identical to `bzip2 -9`) |
| 2.4.2  | 2026-06-17 | bzip2 decode (`bzip2_decompress` + `FORMAT_BZIP2` + CRC-32/BZIP2; BWT pipeline) |
| 2.4.1  | 2026-06-16 | xz / LZMA encode (`xz_compress`, optimal parse; `xz -d` round-trips) |
| 2.4.0  | 2026-06-16 | xz / LZMA decode (`FORMAT_XZ` + `xz_decompress` + CRC-64/XZ; decode-only) |
| 2.3.8  | 2026-06-16 | P(-1) closeout — 2.3.x line complete (zero audit findings) |
| 2.3.7  | 2026-06-16 | Lazy-global alloc-fail propagation (INFO-A; `ERR_OOM`, OOM sweep, batch-encoder bw-OOM fix) |
| 2.3.6  | 2026-06-16 | Streaming FDICT zlib (`zlib_dec_init_dict`; dict-scratch match-copy) |
| 2.3.5  | 2026-06-16 | gzip streaming hardening — FHCRC verify + concatenated-member decode |
| 2.3.4  | 2026-06-16 | CRC-32 slice-by-8 (~2×, wire-identical) + cyrius pin → 6.2.15 |
| 2.3.3  | 2026-06-16 | Configurable LZ4F block-max (64K/256K/1M/4M) + per-block checksum (`lz4f_enc_init_ex`) |

## Open INFOs carried forward

Minor tracked items for the next P(-1) / audit pass to resolve or rebase. From the most recent audit ([`docs/audit/2026-06-16-pre-2.4.0.md`](../audit/2026-06-16-pre-2.4.0.md), zero HIGH/MED/LOW findings). Closed items live in `CHANGELOG.md`.

- **INFO-B** — batch `_deflate_decompress_dict` / `_zlib_decompress_dict` require `dst_cap >= dict_len` (dict staged in `dst`). The 2.3.6 *streaming* FDICT path removed this for the streaming variant (dict in scratch); the batch constraint stands. Already enforced at runtime; docstring-polish item.
- **INFO-C** — aarch64 LZ77 / FDICT match-copy use unaligned `load64`. Permitted by ARMv6+ but some implementations pay a cycle penalty. Flagged for future investigation if aarch64 perf benchmarks surface this as hot.
- **INFO-D** — on a *retried* OOM, partially-allocated lazy tables orphan their bump-allocated memory (`_sankoch_alloc` arena does not free). OOM-path only; minor.
- **INFO-E** — the xz and bzip2 encoders allocate large working buffers (xz prob/DP ~0.6 MB; bzip2 BWT + Huffman ~44 MB at level 9) as lazy singletons. Acceptable for userspace encode, but a future audit should confirm the OOM-propagation paths on first-call failure.

---

*This file is the canonical source for live-state claims. CLAUDE.md must reference, never inline. Refresh in place at every release.*
