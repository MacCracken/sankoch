---
name: Sankoch State
description: Living state of the sankoch repo — version, sizes, test totals, in-flight slots, consumers. Refreshed every release.
type: state
---

# Sankoch State

> **Last refresh**: 2026-06-16 (v2.4.1 cut — xz/LZMA optimal-parse encode shipped; xz codec complete) | **Refresh cadence**: every release; bumped by the release post-hook or by hand if the hook misses.
>
> Per [first-party-documentation.md § Development Docs](https://github.com/MacCracken/agnosticos/blob/main/docs/development/first-party/first-party-documentation.md#development-docs-docsdevelopment), this file holds the **volatile** state. Durable rules live in [`../../CLAUDE.md`](../../CLAUDE.md); release narrative lives in [`../../CHANGELOG.md`](../../CHANGELOG.md); forward ladder lives in [`roadmap.md`](roadmap.md).

---

## Version

- **`VERSION`**: `2.4.1` — single source of truth
- **`cyrius.cyml [package].cyrius`**: `6.2.15` — toolchain pin
- **Tag**: `2.4.1` (bare semver, no `v` prefix)
- **Released**: 2026-06-16

## Distribution

- **Cyrius stdlib**: shipping as `lib/sankoch.cyr` in Cyrius 6.2.x toolchain releases (full profile).
- **Kernel-safe subset**: `lib/sankoch-core.cyr` ships alongside since the 2.1.2 cut (LZ4 batch decompress only; no alloc / no syscalls / no mutex).
- **Consumers import via**: `include "lib/sankoch.cyr"` — no separate `[deps]` declaration in their `cyrius.cyml`.
- **Stdlib fold-in history**: 2.0.2 in Cyrius 5.6.34; 2.0.3 in 5.6.35; 2.1.0 in the 5.6.42 era; 2.1.1 / 2.1.2 in 5.7.x; 2.2.4 in 5.8.65 (foldin manifest pre-req); 2.2.5 in the 5.11.x line; 2.2.6 / 2.3.0 in the 6.0.x line.

## Source

- **Source**: **8,562 lines** across 15 domain modules (`src/*.cyr`) — `src/xz.cyr` is **1,738** (de/compress) after the 2.4.1 encoder.
- **Per-file breakdown** lives in [`roadmap.md` § File Summary](roadmap.md#file-summary-at-230). Re-bump there alongside this file on every release.

## Test totals

The monolithic `sankoch.tcyr` was split (2.4.1 post-ship) into **15
per-codec × direction suites** under `tests/tcyr/`, sharing
`_harness.tcyr` (includes + 4 MB heap setup + cross-cutting helpers).
Function/assertion totals are unchanged by the split.

| Suite group                                   | Functions | Assertions |
|-----------------------------------------------|----------:|-----------:|
| `tests/tcyr/*.tcyr` (15 split suites)         |       190 |  3,979,611 |
| `tests/tcyr/git_object.tcyr`                  |        10 |    346,583 |
| **Total**                                     |   **200** | **4,326,194** |

Split suites: `checksum`, `lz4_{compress,decompress}`,
`lz4f_{compress,decompress}`, `deflate_{compress,decompress}`,
`zlib_{compress,decompress}`, `gzip_{compress,decompress}`,
`xz_{compress,decompress}`, `stream`, `detect_error`. Run one with
`cyrius test tests/tcyr/<name>.tcyr`, or all with bare `cyrius test`.

The assertion total is heavily inflated by per-byte content-loop checks on streaming round-trips (a single 128 KB round-trip contributes 131,072 assertions through one `while (i < N) assert(load8(d+i) == load8(s+i))` loop). Read as a coverage-**density** number, not a coverage-**breadth** number. See [`guides/cyrius-usage.md`](../guides/cyrius-usage.md#what-assertions-means-here-and-why-the-number-is-so-large) for the full explanation.

## Fuzz totals

- **2,449 iterations** across 14 harness functions in 3 files:
  - `fuzz/fuzz_lz4.fcyr`: 700 (round-trip 500 + malformed 200)
  - `fuzz/fuzz_deflate.fcyr`: 949 (deflate batch 340 + zlib 160 + gzip 160 + 4 streaming variants 204 + tree-shape 55 + skewed-freq 30)
  - `fuzz/fuzz_xz.fcyr`: 800 (random-input 300 + corruption 200 + encode→decode round-trip 300) — encode added at 2.4.1

## Dist bundles

| Bundle                       | Lines | Role |
|------------------------------|------:|------|
| `dist/sankoch.cyr`           | 8,541 | Full library — DEFLATE / zlib / gzip / LZ4 + LZ4F + xz de/compress, batch + streaming |
| `dist/sankoch-core.cyr`      |   314 | Kernel-safe LZ4 batch decompress only (AGNOS initrd) |

Both zero deps. Regenerated via `cyrius distlib` and `cyrius distlib core` at every release. CI gates on drift.

## In-flight slots

**2.4.1 (xz / LZMA optimal-parse encode) shipped** 2026-06-16 — the xz
codec is now complete (decode + encode). `xz_compress` /
`compress(FORMAT_XZ, …)` emit valid `.xz` that `xz -d` decodes and our
own decoder round-trips; within ~1–5 % of `xz -6` on text/code. The
2.4.x arc continues with bzip2 per [`roadmap.md`](roadmap.md):

| Slot       | Theme                                                                           | Sizing       |
|------------|---------------------------------------------------------------------------------|--------------|
| ✅ 2.4.0   | xz / LZMA decode (`FORMAT_XZ`) — **shipped**; unblocks takumi `.tar.xz`          | large        |
| ✅ 2.4.1   | xz / LZMA **encode** (`xz_compress`, optimal parse) — **shipped**               | large        |
| **2.4.2**  | bzip2 decode (`FORMAT_BZIP2`) — takumi `.tar.bz2` extraction ← next             | medium-large |
| 2.4.3      | bzip2 encode (`bzip2_compress`) — forward BWT block-sort                         | large        |

DEFLATE throughput round 2 (the old 2.3.4 slot) partially delivered as
CRC-32 slice-by-8; `good_match` dropped and PCLMULQDQ deferred — see the
two deferred markers in [`roadmap.md`](roadmap.md).

## Consumers

| Consumer           | Uses             | Why                                  |
|--------------------|------------------|--------------------------------------|
| Future git impl    | DEFLATE, zlib    | Git objects are zlib-compressed      |
| ark                | LZ4 or DEFLATE   | Package compression                  |
| AGNOS kernel       | LZ4              | initrd, snapshots                    |
| shravan / tarang   | DEFLATE, gzip    | Embedded compressed streams          |
| sit                | zlib             | Git-object reads (post-v2.0.3)       |
| takumi             | gzip, **xz**     | `.tar.gz` + (post-2.4.0) `.tar.xz` source extraction (decode); xz encode available post-2.4.1 |
| Any crate          | All              | Replaces zlib FFI / shelling to gzip |

## CI / release gates

- **Cleanliness**: `cyrius build` 0 warnings on library path; `cyrius lint` 0 warnings per source file; `cyrfmt --check` clean across all `src/` + `programs/` + `tests/` + `fuzz/`; `cyrius vet src/lib.cyr` clean (21 deps, 0 untrusted, 0 missing).
- **Tests**: all tcyr suites green (15 split codec×direction suites + `git_object`, auto-discovered by the CI Test loop); all 14 fuzz harness functions green.
- **Wire-format gate**: 43 SIZE lines in `cyrius bench` output must remain byte-for-byte identical across patch / minor releases unless explicitly broken with a CHANGELOG `Breaking` entry. (2.3.3 added the four `lz4f_bm{4,5,6,7}` block-max-sweep lines; pre-existing lines unchanged.) The 2.4.1 xz encoder is **deliberately excluded** from this gate — its output will keep being tuned, so it ships an informational ratio line in `bench` instead.
- **Bundle gate**: `cyrius distlib` + `cyrius distlib core` regenerate `dist/sankoch.cyr` + `dist/sankoch-core.cyr`; CI fails on drift.
- **Kernel-safe tripwire**: `programs/core_smoke.cyr` links ONLY the `[lib.core]` modules and exercises LZ4 batch decompress on known fixtures. Any alloc / syscall / mutex leak into the core subset fails the build.
- **aarch64 cross-build**: hard gate in both ci.yml and release.yml; `cyrius build --aarch64 src/lib.cyr` must succeed and produce a valid ARM aarch64 ELF. Workflows expect `cycc_aarch64` in the Cyrius bundle (renamed from `cc5_aarch64` at Cyrius 6.0).
- **Tag filter**: release workflow triggers on bare semver tags only (`2.3.0`, not `v2.3.0`).
- **Version-verify**: release asserts `VERSION == git tag` before building.

## Recent releases

Most recent first. Full per-release notes in [`../../CHANGELOG.md`](../../CHANGELOG.md).

| Tag    | Date       | Headline                                              |
|--------|------------|-------------------------------------------------------|
| 2.4.1  | 2026-06-16 | xz / LZMA encode (`xz_compress`, optimal parse; `xz -d` round-trips) |
| 2.4.0  | 2026-06-16 | xz / LZMA decode (`FORMAT_XZ` + `xz_decompress` + CRC-64/XZ; decode-only) |
| 2.3.8  | 2026-06-16 | P(-1) closeout — 2.3.x line complete (zero audit findings) |
| 2.3.7  | 2026-06-16 | Lazy-global alloc-fail propagation (INFO-A; `ERR_OOM`, OOM sweep, batch-encoder bw-OOM fix) |
| 2.3.6  | 2026-06-16 | Streaming FDICT zlib (`zlib_dec_init_dict`; dict-scratch match-copy) |
| 2.3.5  | 2026-06-16 | gzip streaming hardening — FHCRC verify + concatenated-member decode |
| 2.3.4  | 2026-06-16 | CRC-32 slice-by-8 (~2×, wire-identical) + cyrius pin → 6.2.15 |
| 2.3.3  | 2026-06-16 | Configurable LZ4F block-max (64K/256K/1M/4M) + per-block checksum (`lz4f_enc_init_ex`) |

## Open INFOs carried forward

Tracked items the next P(-1) (the 2.4.x closeout) should resolve or rebase. From the most recent audit ([`docs/audit/2026-06-16-pre-2.4.0.md`](../audit/2026-06-16-pre-2.4.0.md), zero HIGH/MED/LOW findings):

- **INFO-01** — gzip FHCRC validation. **CLOSED at 2.3.5** (batch + streaming validate the low-16-of-CRC-32 header checksum; verified vs `gunzip`).
- **INFO-A** — lazy-global alloc sites aborting on first-call OOM. Carried from 2.2.1 / 2.2.3. **CLOSED at 2.3.7** (~33 sites route through `_sankoch_alloc` + propagate `ERR_OOM`; OOM fault-injection sweep added; a pre-existing batch-encoder bitwriter-OOM segfault was fixed in the process).
- **INFO-B** — batch `_deflate_decompress_dict` / `_zlib_decompress_dict` require `dst_cap >= dict_len` (dict staged in `dst`). The 2.3.6 *streaming* FDICT path removed this for the streaming variant (dict in scratch); the batch constraint stands. Already enforced at runtime; docstring-polish item.
- **INFO-C** — aarch64 LZ77 / FDICT match-copy use unaligned `load64`. Permitted by ARMv6+ but some implementations pay a cycle penalty. Flagged for future investigation if aarch64 perf benchmarks surface this as hot.
- **INFO-D** (new, 2026-06-16) — on a *retried* OOM, partially-allocated lazy tables orphan their bump-allocated memory (`_sankoch_alloc` arena does not free). OOM-path only; minor.

---

*This file is the canonical source for live-state claims. CLAUDE.md must reference, never inline. Refresh in place at every release.*
