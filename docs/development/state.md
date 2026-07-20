---
name: Sankoch State
description: Living state of the sankoch repo — version, sizes, test totals, in-flight slots, consumers. Refreshed every release.
type: state
---

# Sankoch State

> **Last refresh**: 2026-07-19 (v2.6.0 cut — **ZIP archive container**: new `src/zip.cyr` (487 lines) — in-memory PKZIP reader + writer, methods 0/8, CRC-verified, zip-slip guards, per-member ratio cap; the whole agnosai `.agpkg` filing. New `[lib.zip]` profile (9 bundles), `tests/tcyr/zip.tcyr` (22nd suite), `scripts/zip-smoke.sh` reference parity 5/5 via `unzip`/Python `zipfile`. Previously — v2.5.10 cut — **P(-1) audit remainder**: closes the deferred half of the 2026-07-19 audit — zstd decode/encode arena leaks (349 KB + 90 KB per call → **0**), tar retry-ladder DoS (1030 MB → 38 MB), multi-frame `.zst` truncation, multi-member `.tar.gz` rejection, L-2/L-3/L-4/R-1, and the L-5/I-1 testability work (zstd/tar/stream now on the fault seam; zstd in the OOM sweep; `fuzz_xz_truncate`). **Every confirmed audit finding is now resolved — 2.6.0 is cleared to open.** Previously — v2.5.9 cut — **P(-1) security hardening**: first audit of the never-audited 2.4.x/2.5.x surface [xz/bzip2/tar/zstd-encoder] found 1 HIGH + 13 MEDIUM + 5 LOW; 2.5.9 lands the security-critical subset — H-1 tar symlink-chain traversal, M-3 tar NULL-write, M-5/M-6/M-7 xz OOB-read/DoS-hang/sha256-fail-closed, M-8+L-1 OOM-latch crash class, M-12 zstd concurrency lock, M-13 stream allocs; resource-leak/interop/zstd-decode-OOM cluster deferred to 2.5.10. Audit: `docs/audit/2026-07-19-pre-2.6.0.md`) | **Refresh cadence**: every release; bumped by the release post-hook or by hand if the hook misses.
>
> Per [first-party-documentation.md § Development Docs](https://github.com/MacCracken/agnosticos/blob/main/docs/development/first-party/first-party-documentation.md#development-docs-docsdevelopment), this file holds the **volatile** state. Durable rules live in [`../../CLAUDE.md`](../../CLAUDE.md); release narrative lives in [`../../CHANGELOG.md`](../../CHANGELOG.md); forward ladder lives in [`roadmap.md`](roadmap.md).

---

## Version

- **`VERSION`**: `2.6.0` — single source of truth (2.6.0 = **ZIP archive container** [`zip.cyr` in-memory reader + writer, store + DEFLATE, zip-slip guards, per-member ratio cap, `[lib.zip]` profile — the agnosai `.agpkg` core]; 2.5.10 = **P(-1) audit remainder** [zstd memory-lifetime pooling → 0 B/call leaks; tar ladder DoS; multi-frame zstd; multi-member gzip; L-2/L-3/L-4/R-1; fault-seam routing + zstd OOM sweep + xz truncation fuzz — clears 2.6.0]; 2.5.9 = **P(-1) security hardening** [1 HIGH tar symlink-chain traversal + xz OOB-read/DoS/sha256 + OOM-latch crash class + zstd concurrency lock + stream allocs; first audit of the 2.4.x/2.5.x surface]; 2.5.8 = **zstd encoder priced parse** [`_ze_mvalue` bit-cost match selection + repcode candidates at the lookahead; corpus −9.9 %, zero regressions, beats `zstd -3` everywhere]; 2.5.7 = **zstd encoder parse quality** [repcode-aware match finding + adaptive FSE sequence tables; now beats `zstd -3` on real code/text/binary]; 2.5.6 = **zstd encoder competitiveness + decoder hardening** [FSE literal weights + repeat-offset codes + lazy parse + 1..9 level knob; decoder closed against 36 verified OOB/DoS paths + `fuzz_zstd.fcyr`]; 2.5.5 = **sovereign zstd encoder** `zstd_compress` [LZ77 + FSE sequences + Huffman literals; completes the codec, decode shipped 2.5.0]; 2.5.4 = xz / bzip2 encoder throughput [output byte-identical]; 2.5.3 = xz / bzip2 ratio cap; 2.5.2 = toolchain pin refresh to Cyrius 6.4.66; 2.5.1 = per-codec distlib profiles; 2.5.0 = sovereign `zstd.cyr` decoder + shared `tar.cyr` cursor)
- **`cyrius.cyml [package].cyrius`**: `6.4.67` — toolchain pin (bumped from 6.4.66 during the 2.5.6 arc; 2.5.5 shipped on 6.4.66. `cyrius deps` re-resolved, all gates green)
- **Tag**: `2.6.0` (bare semver, no `v` prefix)
- **Released**: 2026-07-19

## Distribution

- **Cyrius stdlib**: shipping as `lib/sankoch.cyr` in Cyrius 6.4.x toolchain releases (full profile).
- **Kernel-safe subset**: `lib/sankoch-core.cyr` ships alongside since the 2.1.2 cut (LZ4 batch decompress only; no alloc / no syscalls / no mutex).
- **Consumers import via**: `include "lib/sankoch.cyr"` — no separate `[deps]` declaration in their `cyrius.cyml`.
- **Stdlib fold-in**: folded into the Cyrius stdlib since 2.0.2 (Cyrius 5.6.34); tracks the toolchain pin in `cyrius.cyml`. Per-version fold-in chronology lives in `CHANGELOG.md`.

## Source

- **Source**: **13,926 lines** across **20** domain modules (`src/*.cyr`) — 2.6.0 added `src/zip.cyr` (**487**), the first new module since 2.5.0. Previously the 2.5.10 audit-remainder arc grew `zstd.cyr` **2,083 → 2,384** (+301 — pooled decode/encode FSE + Huffman + reader slots, the multi-frame loop, `zstd_content_size`, and the OOM null-check sweep), `tar.cyr` **701 → 710**, `gzip.cyr` **638 → 650**, `lib.cyr` **254 → 265**. Previously the 2.5.9 security-hardening arc grew `tar.cyr` **513 → 701** (+188 — the cross-entry symlink ledger for H-1 + parse-path OOM guards for M-3), `zstd.cyr` **2,058 → 2,083** (+25 — M-12 lock wrappers), `xz.cyr` **1,819 → 1,836** (M-5/M-6/M-7 + M-8 flag), `bzip2.cyr` **1,316 → 1,323** (M-8/L-1 flags), `stream.cyr` **250 → 256** (M-13), `lz77.cyr` **181 → 184** (M-8), `lib.cyr` **246 → 254** (I-1 reset + M-12 dispatch). Largest modules: `deflate.cyr` **2,545**, `zstd.cyr` **2,384**, `xz.cyr` **1,836**, `bzip2.cyr` **1,323**, `lz4.cyr` **935**, `tar.cyr` **710**, `huffman.cyr` **683**, `gzip.cyr` **650**, `zip.cyr` **487**; `runtime.cyr` **73**, `lib.cyr` **266**, `types.cyr` **43**.
- **Per-file breakdown** lives in [`roadmap.md` § File Summary](roadmap.md#file-summary-at-230). Re-bump there alongside this file on every release.

## Test totals

The suite is split into **21 per-codec × direction / container suites** plus the
cross-cutting `ratio_cap` and `detect_error` suites under
`tests/tcyr/`, sharing `_harness.tcyr` (includes + 4 MB heap setup +
cross-cutting helpers).

| Suite group                                   | Functions | Assertions |
|-----------------------------------------------|----------:|-----------:|
| `tests/tcyr/*.tcyr` (21 split suites)         |       268 |  4,137,763 |
| `tests/tcyr/git_object.tcyr`                  |        10 |    346,583 |
| **Total**                                     |   **278** | **4,484,346** |

Split suites: `checksum`, `lz4_{compress,decompress}`,
`lz4f_{compress,decompress}`, `deflate_{compress,decompress}`,
`zlib_{compress,decompress}`, `gzip_{compress,decompress}`,
`xz_{compress,decompress}`, `bzip2_{compress,decompress}`,
**`zstd_compress`** (2.5.5 store / RLE / Huffman / LZ77+FSE + 2.5.6 FSE literal
weights / repeat offsets / level knob / **malformed-input decode-survival** [the
34-byte raw-overflow repro + truncations] + **2.5.8 priced parse** [
`test_zc_lazy_beats_greedy` — the lazy levels may never lose to greedy level 1 on
ascending-integer text, which 2.5.7 fails 35,710 B vs 21,337 B — and
`test_zc_record_parse` on drifting-offset records]; zstd reference-`zstd -d` interop
is `scripts/zstd-encode-smoke.sh` (15 cases, incl. the 2.5.8 `hjsonrec` / `hasc`
fixtures), and decode robustness is fuzzed by `fuzz/fuzz_zstd.fcyr`), `stream`, `detect_error`, **`ratio_cap`** (2.4.5
batch + 2.4.6 streaming + 2.5.3 xz/bzip2 — 26 tests, 98 assertions), and **`zip`**
(2.6.0 — 11 tests / 59 assertions: round-trip, empty archive/member, all six zip-slip
shapes, ratio cap, CRC-32 on a flipped *stored* byte, malformed/truncated input, index
bounds, writer overrun; reference `unzip` / Python `zipfile` parity is
`scripts/zip-smoke.sh`). Run one
with `cyrius test tests/tcyr/<name>.tcyr`, or all with bare `cyrius test`.

> **Counting correction (2.5.8)**: totals through 2.5.7 were tallied with a pattern that
> silently dropped one suite (the only one whose summary line omits the `(N total)`
> suffix), so every historical figure in this row was **21 assertions low**. The 2.5.7
> total was really 4,484,010, not 4,483,989. Figures from 2.5.8 onward are the full tally
> across all 21 suite runs.

The assertion total is heavily inflated by per-byte content-loop checks on streaming round-trips (a single 128 KB round-trip contributes 131,072 assertions through one `while (i < N) assert(load8(d+i) == load8(s+i))` loop). Read as a coverage-**density** number, not a coverage-**breadth** number. See [`guides/cyrius-usage.md`](../guides/cyrius-usage.md#what-assertions-means-here-and-why-the-number-is-so-large) for the full explanation.

## Fuzz totals

- **5,379 iterations** across 28 harness functions in 5 files:
  - `fuzz/fuzz_lz4.fcyr`: 700 (round-trip 500 + malformed 200)
  - `fuzz/fuzz_deflate.fcyr`: 1,629 (deflate batch 340 + zlib 160 + gzip 160 + 4 streaming variants 204 + tree-shape 55 + skewed-freq 30 + ratio-cap 240 + ratio-cap malformed 100 + **streaming ratio-cap 240 + streaming malformed 100**)
  - `fuzz/fuzz_xz.fcyr`: 1,000 (random-input 300 + corruption 200 + encode→decode round-trip 300 + ratio-cap 100 + **truncation 100 + an exhaustive prefix sweep of the fixture**, 2.5.10 L-5 — the class that reaches the M-5 check-field OOB site)
  - `fuzz/fuzz_bzip2.fcyr`: 900 (random-input 300 + corruption 200 + encode→decode round-trip 300 + **ratio-cap 100**)
  - `fuzz/fuzz_zstd.fcyr`: 1,150 (2.5.6 — decode-survival on random input 400 + encode→decode round-trip across 5 distributions 600 + corruption of valid streams 150; found the decoder-hardening SIGSEGVs)

## Dist bundles

| Bundle                       | Lines | Role |
|------------------------------|------:|------|
| `dist/sankoch.cyr`           | 13,971 | Full library — LZ4 / LZ4F / DEFLATE / zlib / gzip / xz / bzip2 de/compress + zstd de/compress (encode 2.5.5, competitive 2.5.6–2.5.8) + tar cursor, batch + streaming, + ratio-capped decompress (DEFLATE family batch + streaming; xz + bzip2 batch, 2.5.3) |
| `dist/sankoch-core.cyr`      |   332 | **[lib.core]** kernel-safe LZ4 batch decompress only (types + xxhash32 + lz4_decode); no alloc / syscalls / mutex (AGNOS initrd) |
| `dist/sankoch-zlib.cyr`      | 4,933 | **[lib.zlib]** (2.4.9) — DEFLATE/zlib only (`zlib_compress`/`zlib_decompress` + closure); drops LZ4/gzip/xz/bzip2/zstd/tar/streaming. Keeps the initialised-global footprint low so a consumer stays under its `max 1024 globals` budget while tracking current sankoch (sit's git read path / thoth's git producer). Runtime helpers via the extracted `src/runtime.cyr` |
| `dist/sankoch-gzip.cyr`      | 5,098 | **[lib.gzip]** (2.5.1) — gzip/DEFLATE decode closure + CRC-32 (the zlib profile with the gzip envelope) |
| `dist/sankoch-xz.cyr`        | 2,799 | **[lib.xz]** (2.5.1) — `.xz` (LZMA2) decode: lz77 match model + CRC-32 / CRC-64; + `xz_decompress_with_ratio_cap` (2.5.3, self-contained closure) |
| `dist/sankoch-bzip2.cyr`     | 2,099 | **[lib.bzip2]** (2.5.1) — bzip2 decode (BWT + Huffman + MTF) + CRC-32/BZIP2 + runtime; + `bzip2_decompress_with_ratio_cap` (2.5.3, self-contained closure) |
| `dist/sankoch-zstd.cyr`      | 2,514 | **[lib.zstd]** (2.5.1) — RFC-8878 zstd **de + compress** (decode 2.5.0, hardened 2.5.6; sovereign `zstd_compress` encoder 2.5.5, competitive 2.5.6–2.5.8 — now beats `zstd -3`, zstd's own default, on every fixture — with a 1..9 `zstd_compress_level`), own bit reader / FSE / Huffman; carries `runtime.cyr` since 2.5.9 for the API lock (M-12) and, since 2.5.10, for the `_sankoch_alloc` fault seam (L-5). Multi-frame `.zst` decode + `zstd_content_size` since 2.5.10 (M-2); zero per-call arena growth (M-9/M-10). agnova `base-system.tar.zst` + takumi zstd tarballs; the ZIP method-93 write path (2.6.x) |
| `dist/sankoch-zip.cyr`       | 4,935 | **[lib.zip]** (2.6.0) — PKZIP `.zip` container: in-memory reader + writer, methods 0 (store) / 8 (DEFLATE), CRC-verified, zip-slip guards, per-member ratio cap. The DEFLATE closure + crc32 + `zip.cyr`; excludes `tar.cyr`. agnosai's `.agpkg` profile |
| `dist/sankoch-tar.cyr`       | 11,363 | **[lib.tar]** (2.5.1) — sovereign tar cursor + every envelope `tar_open_auto` dispatches to (gzip / xz / bzip2 / zstd); the "extract any tarball" profile (takumi source tarballs, agnova rootfs) |

All zero deps. Regenerated at every release via `cyrius distlib` (full) plus the seven named profiles — `cyrius distlib core` / `zlib` / `gzip` / `xz` / `bzip2` / `zstd` / `zip` / `tar` (nine bundles total). CI gates on drift across all nine.

## In-flight slots

**2.6.0 shipped (2026-07-19) — the ZIP arc is open.** The pre-2.6.0 P(-1) pass (2.5.9 +
2.5.10) closed every confirmed audit finding, and 2.6.0 landed the container: `zip.cyr`
as an in-memory PKZIP reader + writer for methods 0/8, CRC-verified, with zip-slip guards
and a per-member ratio cap — **the whole agnosai `.agpkg` filing**. Reference parity
(`unzip` + Python `zipfile`) verified both directions across five archive shapes.

- **2.6.1 — the other methods.** Wire the codecs sankoch owns into ZIP's method field,
  both ways: **12 (bzip2)**, **95 (xz)**, **93 (zstd)**. Method 14 (raw LZMA
  alone-format) stays unsupported — the same non-goal as the codec, which handles the
  `.xz` container, not `.lzma`. Does not block agnosai.
- **2.6.2 — zip64.** >4 GB entries and >65,535-entry / >4 GB archives: the Zip64 EOCD
  record + locator + the Zip64 extended-information extra field, read and write. The
  current writer caps at 65,535 entries (`ZIP_MAX_ENTRIES`) and 4 GB fields by design.
- **2.6.3 — streaming + metadata.** Streaming read + streaming write (data descriptors,
  bit-3 sizes-after-data) mirroring the codec `*_enc_*` / `*_dec_*` shape, plus per-entry
  metadata (mtime, mode, symlink) for tar-parity extraction. 2.6.0 writes a fixed
  1980-01-01 MS-DOS date and no external attributes.

- **Deferred — zstd optimal / 2-pass parse (its own arc, unscheduled).** Was the 2.5.8
  slot; built and measured side by side against the priced parse before being deferred.
  A verified DP probe reached 251,733 B on the seven-fixture corpus against 2.5.8's
  251,333 B — i.e. **worse on total** — while costing ~400 lines, ~224 KiB of DP arrays
  and 4–74× encode time. It is genuinely better on real source/binary specifically
  (−3.6 % vs 2.5.8's −0.5 %), so it stays on the ladder rather than being dropped, but it
  is an arc, not a point release. Schedule if a consumer needs that last few percent on
  source/binary.
- **Deferred — xz encoder throughput.** The 2.5.9 baseline measured xz encode at
  ~0.07–0.16 MB/s, **~400–900× slower than reference `xz -6`** for equal-or-better ratio
  (1 MB of zeros: 14.8 s vs ~16 ms). Scaling is linear, so this is a constant factor, not
  an algorithmic blowup — reference xz uses a BT4 binary-tree match finder where sankoch
  walks a plain chain and prices every position. Largest measured performance gap in the
  tree; `takumi` is an xz-encode consumer. See
  [`docs/benchmarks/2026-07-19-2.5.9-p1-baseline.md`](../benchmarks/2026-07-19-2.5.9-p1-baseline.md).
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
| agnosai            | ZIP read+write   | `.agpkg` definition bundles (`definitions/packaging.rs` export/import; DEFLATE) — **shipped 2.6.0** (`zip_open`/`zip_extract_capped` + `zip_writer_*`, `[lib.zip]` profile) |
| Any crate          | All              | Replaces zlib FFI / shelling to gzip |

## CI / release gates

- **Cleanliness**: `cyrius build` 0 warnings on library path; `cyrius lint` 0 warnings per source file; `cyrfmt --check` clean across all `src/` + `programs/` + `tests/` + `fuzz/`; `cyrius vet src/lib.cyr` clean (25 deps, 0 untrusted, 0 missing).
- **Tests**: all tcyr suites green (19 split codec×direction suites incl. `zstd_compress` + `ratio_cap` + `git_object`, auto-discovered by the CI Test loop; `detect_error` carries the 2.5.9 OOM-latch retry sweep across deflate/xz/bzip2); all fuzz harnesses green (5 files — lz4 / deflate / xz / bzip2 / zstd, auto-discovered via `fuzz/*.fcyr`). **Note (2.5.9)**: `cyrius test` does not propagate a child suite's SIGSEGV as a non-zero exit — a crashing suite reports no failure line; verify a suspect suite by building + running its binary directly.
- **Wire-format gate**: 43 SIZE lines in `cyrius bench` output must remain byte-for-byte identical across patch / minor releases unless explicitly broken with a CHANGELOG `Breaking` entry. (2.3.3 added the four `lz4f_bm{4,5,6,7}` block-max-sweep lines; 2.5.8 added `SIZE zstd6_rec_256K`, a record-structured parse-quality canary — the three `zstd6_text_*` lines use a periodic filler that is one long match at any level, so they did not move a byte across either the 2.5.7 or 2.5.8 parse rewrite; pre-existing lines unchanged.) The **xz and bzip2 encoders** (2.4.1 / 2.4.3) and the **zstd encoder** (`SIZE zstd6_*`, 2.5.6) are **deliberately excluded** from this gate — their output is not bit-reproducible across encoder versions, so they ship informational ratio lines in `bench` instead, as does the 2.4.5 ratio-cap section.
- **Bundle gate**: `cyrius distlib` + `cyrius distlib core` regenerate `dist/sankoch.cyr` + `dist/sankoch-core.cyr`; CI fails on drift.
- **Kernel-safe tripwire**: `programs/core_smoke.cyr` links ONLY the `[lib.core]` modules and exercises LZ4 batch decompress on known fixtures. Any alloc / syscall / mutex leak into the core subset fails the build.
- **aarch64 cross-build**: hard gate in both ci.yml and release.yml; `cyrius build --aarch64 src/lib.cyr` must succeed and produce a valid ARM aarch64 ELF. Workflows expect `cycc_aarch64` in the Cyrius bundle (renamed from `cc5_aarch64` at Cyrius 6.0).
- **Tag filter**: release workflow triggers on bare semver tags only (`2.4.5`, not `v2.4.5`).
- **Version-verify**: release asserts `VERSION == git tag` before building.

## Recent releases

Most recent first. Full per-release notes in [`../../CHANGELOG.md`](../../CHANGELOG.md).

| Tag    | Date       | Headline                                              |
|--------|------------|-------------------------------------------------------|
| 2.6.0  | 2026-07-19 | **ZIP archive container** — new `zip.cyr`: in-memory PKZIP reader + writer (store + DEFLATE), CRC-verified, zip-slip guards, per-member ratio cap; `[lib.zip]` profile (9 bundles); `zip.tcyr` (22nd suite) + `zip-smoke.sh` reference parity via `unzip` / Python `zipfile`. The agnosai `.agpkg` core |
| 2.5.10 | 2026-07-19 | **P(-1) audit remainder** — zstd decode/encode arena leaks 349 KB + 90 KB per call → **0** (pooled tables/readers); tar retry-ladder DoS 1030 MB → 38 MB; multi-frame `.zst` truncation + `zstd_content_size`; multi-member `.tar.gz` rejection; L-2/L-3/L-4/R-1; zstd/tar/stream on the fault seam + zstd OOM sweep + `fuzz_xz_truncate`. **Clears 2.6.0** |
| 2.5.9  | 2026-07-19 | **P(-1) security hardening** — first audit of the never-audited 2.4.x/2.5.x surface (1 HIGH + 13 MED + 5 LOW); landed the security-critical subset: H-1 tar symlink-chain traversal, M-3 tar NULL-write, M-5/M-6/M-7 xz OOB-read/DoS-hang/sha256-fail-closed, M-8+L-1 OOM-latch crash class (INFO-E), M-12 zstd concurrency lock, M-13 stream allocs; remainder → 2.5.10 |
| 2.5.8  | 2026-07-19 | **zstd encoder priced parse** — `_ze_mvalue` bit-cost match selection replaces raw length compares; repcode candidates at the lookahead position; corpus −9.9 %, no regression on any of 11 fixtures, beats `zstd -3` (zstd's default) on every fixture; fixes a 2.5.7 defect where the lazy lookahead inflated regular data 67 % |
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

The **2.5.9/2.5.10 P(-1) audit** ([`docs/audit/2026-07-19-pre-2.6.0.md`](../audit/2026-07-19-pre-2.6.0.md))
is fully remediated: 1 HIGH + 13 MEDIUM + 5 LOW, all resolved. Closed items live in
`CHANGELOG.md`. What remains tracked:

- **INFO-B** — batch `_deflate_decompress_dict` / `_zlib_decompress_dict` require `dst_cap >= dict_len` (dict staged in `dst`). Carried unchanged (not re-derived by the audit). Already enforced at runtime; docstring-polish item.
- **INFO-C** — aarch64 LZ77 / FDICT unaligned `load64`. The audit confirmed only one such site repo-wide; aarch64 cross-build green. Carried, narrowed — revisit only if aarch64 perf surfaces it.
- **INFO-D** — **the never-freeing bump arena**, now the last structural memory item. 2.5.10 removed every *per-call* growth path (zstd decode/encode 0 B/call; the tar ladder 1030 MB → 38 MB), so no public API leaks unboundedly with repeated use. What remains is the design property itself: the arena never returns memory, so a partially-completed lazy init on a retried OOM still orphans its successful allocations. Accepted as the cost of the M-8 completion-flag fix; a future arena-with-reset would close it.
- ~~**INFO-E**~~ — **RESOLVED (negative) in 2.5.9**, encoder half completed in 2.5.10. First-call/partial OOM propagation *was* broken on the encode path; fixed with completion-flag guards + a partial-OOM-then-retry fault sweep across deflate/xz/bzip2/zstd.
- ~~**INFO-F**~~ — **CLOSED in 2.5.3.** Ratio cap extended to xz and bzip2 decode.
- ~~**INFO-I1**~~ — **CLOSED in 2.5.10.** `_sankoch_reset_tables()` now clears the xz/bzip2/crc64 *and* zstd lazy globals, and zstd/tar/stream allocations route through the `_sankoch_alloc` fault seam (74 sites), so their OOM paths are sweepable. zstd is in the OOM sweep; `fuzz_xz_truncate` added. The routing immediately caught a sticky-`_ze_oom` bug that would have poisoned every `zstd_compress` after one OOM.

---

*This file is the canonical source for live-state claims. CLAUDE.md must reference, never inline. Refresh in place at every release.*
