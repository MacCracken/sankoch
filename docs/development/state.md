---
name: Sankoch State
description: Living state of the sankoch repo — version, sizes, test totals, in-flight slots, consumers. Refreshed every release.
type: state
---

# Sankoch State

> **Last refresh**: 2026-07-20 (v2.7.1 cut — **xz encoder: BT4 binary-tree match finder (real-source speedup)**. 2.7.0 closed the repetitive half of the xz-encode gap; 2.7.1 closes part of the real-source half. The 2.7.0 "78 % match finder" profiling figure counted *operations, not time* — the hash-chain nodes are cheap quick-rejects, so an HC4 (4-byte-hash) attempt gave only +4 % while regressing repetitive −25 %, and was rejected. BT4 is the genuine fix: it finds the longest match + every shorter length in O(match_len + tree_depth), never re-comparing bytes across candidates. On **xz-private tables** (65536-slot son[] tree + hash heads, +1.75 MiB) so DEFLATE's shared 3-byte lz77 stays byte-identical (proven by the deflate/gzip/zlib suites). The greedy-covered skip range uses a **seed-only O(1) insert** so BT4's per-insert cost never touches repetitive data. Result: real-source corpus **0.60 → 0.73 MB/s (+21 %)** *and* smaller (58872 → 58704 B), speed gap to `xz -6` 7.1× → 5.8×, text/zeros unchanged. Design research + adversarial review (3 verifiers, all *sound*) ran as a workflow before any tree code. Also dropped `lz77_init()` from the xz encode path (BT4 is xz-private). Toolchain pin 6.4.68 → 6.4.69. The residual +7 % ratio (32 KB window vs xz's 8 MB dict) is the 2.7.2 dictionary item. Previously — v2.7.0 cut — **xz encoder: optimal-parse greedy shortcut (repetitive-data speedup)**. The .xz encoder was the largest measured perf gap in the tree. Profiling ([`docs/benchmarks/2026-07-20-2.7.0-baseline.md`](../benchmarks/2026-07-20-2.7.0-baseline.md)) split it into two regimes: on **repetitive** data (300–750× slower than `xz -6`) the cost is the windowed optimal parse pricing a ~273-length match at every one of the 4096 window positions; on **real source** (7.3× slower) the HC3 hash-chain walk dominates. 2.7.0 ships the repetitive fix — a **rep-only `nice_len` greedy shortcut** (take a *saturated* rep as one op instead of a full DP window) + an **interior DP cut** (end a window when a rep covers the whole remainder). Rep-only + saturated-gated is the ratio-safe subset an adversarial design review isolated (a normal-match greedy regresses real-source ratio — the longest recorded match sits at the largest distance). Result: text 256K **0.15 → 44.6 MB/s (~290×)**, zeros **0.07 → 31.7 MB/s (~473×)**, each *smaller* (240→216, 192→172); corpus exactly neutral (74132, unchanged speed). Reference `xz -t`/`xz -dc` round-trip holds on all fixtures; 43 gated SIZE lines byte-identical. Toolchain pin 6.4.67 → 6.4.68. HC4 match finder for the real-source gap → 2.7.1. Previously — v2.6.4 cut — **P(-1) hardening: first security audit of the ZIP surface** ([`docs/audit/2026-07-20-zip-container.md`](../audit/2026-07-20-zip-container.md), 0 HIGH · 3 MEDIUM · 1 LOW confirmed, all fixed): i64 additive-overflow defeated four Zip64 bounds checks (SIGSEGV from `zip_open`/`zip_extract` on 42–117-byte crafted archives) → rewritten subtraction-form; a streamed DEFLATE member abandoned before `deflate_enc_finish` leaked `_sankoch_mtx` process-wide → `_zip_abandon` releases it on every abort path; `zip_add` mid-stream produced an overlapped archive → rejected; name > 65535 bytes silently truncated → rejected. One HIGH symlink claim rebased to LOW — the ZIP surface is memory-only (zero filesystem ops), so the tar-style on-disk traversal has no reachable analogue; the archive-global symlink ledger is kept as defense-in-depth. New `fuzz/fuzz_zip.fcyr` (six strategies incl. Zip64 injection; reliably SIGSEGV'd the pre-fix path). `zip.tcyr` 175 → 206 assertions. Previously — v2.6.3 cut — **ZIP streaming write + per-entry metadata**: `zip_enc_begin/write/end` (bit-3 + data descriptors) and mode/mtime/symlink accessors + `zip_add_meta`, giving tar-parity extraction. **The 2.6.x ZIP arc is complete.** Previously — v2.6.2 cut — **ZIP Zip64, read + write**: EOCD record + locator and the extended-information extra field on both sides; >65,535 members and >4 GB directories/entries. Also fixed a latent 2.6.0 bug — the writer ALIASED caller-supplied member names instead of copying them, so a reusable name buffer silently produced an archive where every entry had the last name, clean by every external check. Previously — v2.6.1 cut — **ZIP: every method sankoch owns** — 12 (bzip2) / 93 (zstd) / 95 (xz) read + write via new `src/zip_methods.cyr` (174), joining 0/8. `zip.cyr` still references only deflate+crc32, so `[lib.zip]` stays lean for agnosai (4,969) while the new `[lib.zipall]` (10,698) carries every method — ten bundles. Reference parity both ways via bsdtar + Python `zipfile`; `zip.tcyr` 15 tests / 98 assertions. Previously — v2.6.0 cut — **ZIP archive container**: new `src/zip.cyr` (487 lines) — in-memory PKZIP reader + writer, methods 0/8, CRC-verified, zip-slip guards, per-member ratio cap; the whole agnosai `.agpkg` filing. New `[lib.zip]` profile (9 bundles), `tests/tcyr/zip.tcyr` (22nd suite), `scripts/zip-smoke.sh` reference parity 5/5 via `unzip`/Python `zipfile`. Previously — v2.5.10 cut — **P(-1) audit remainder**: closes the deferred half of the 2026-07-19 audit — zstd decode/encode arena leaks (349 KB + 90 KB per call → **0**), tar retry-ladder DoS (1030 MB → 38 MB), multi-frame `.zst` truncation, multi-member `.tar.gz` rejection, L-2/L-3/L-4/R-1, and the L-5/I-1 testability work (zstd/tar/stream now on the fault seam; zstd in the OOM sweep; `fuzz_xz_truncate`). **Every confirmed audit finding is now resolved — 2.6.0 is cleared to open.** Previously — v2.5.9 cut — **P(-1) security hardening**: first audit of the never-audited 2.4.x/2.5.x surface [xz/bzip2/tar/zstd-encoder] found 1 HIGH + 13 MEDIUM + 5 LOW; 2.5.9 lands the security-critical subset — H-1 tar symlink-chain traversal, M-3 tar NULL-write, M-5/M-6/M-7 xz OOB-read/DoS-hang/sha256-fail-closed, M-8+L-1 OOM-latch crash class, M-12 zstd concurrency lock, M-13 stream allocs; resource-leak/interop/zstd-decode-OOM cluster deferred to 2.5.10. Audit: `docs/audit/2026-07-19-pre-2.6.0.md`) | **Refresh cadence**: every release; bumped by the release post-hook or by hand if the hook misses.
>
> Per [first-party-documentation.md § Development Docs](https://github.com/MacCracken/agnosticos/blob/main/docs/development/first-party/first-party-documentation.md#development-docs-docsdevelopment), this file holds the **volatile** state. Durable rules live in [`../../CLAUDE.md`](../../CLAUDE.md); release narrative lives in [`../../CHANGELOG.md`](../../CHANGELOG.md); forward ladder lives in [`roadmap.md`](roadmap.md).

---

## Version

- **`VERSION`**: `2.7.1` — single source of truth (2.7.1 = **xz encoder BT4 match finder** [binary-tree finder on xz-private tables, seed-only O(1) skip; real-source corpus +21 % and better ratio, gap to `xz -6` 7.1×→5.8×, repetitive neutral; HC4 tried+rejected first; pin → 6.4.69; residual ratio gap → 2.7.2 dict]; 2.7.0 = **xz encoder repetitive-data speedup** [rep-only `nice_len` greedy shortcut + interior DP cut; text/zeros encode ~290–473× faster and smaller, corpus neutral; pin → 6.4.68; HC4 match finder for the real-source 7.3× gap deferred to 2.7.1]; 2.6.4 = **P(-1) ZIP-surface hardening** [first security audit of the 2.6.x ZIP code — i64-overflow-safe Zip64 bounds (subtraction form, 4 sites), streaming-abandon lock release, mid-stream-add rejection, name-length limit; `fuzz_zip.fcyr`; 0 HIGH · 3 MED · 1 LOW]; 2.6.3 = **ZIP streaming write + metadata** [`zip_enc_*` data descriptors; mode/mtime/symlink read + write — completes the ZIP arc]; 2.6.2 = **ZIP Zip64** [EOCD record + locator + extended-information extra field, read + write; entry cap 65,535 → 16,777,216; latent name-aliasing fix]; 2.6.1 = **ZIP: every method sankoch owns** [12 bzip2 / 93 zstd / 95 xz, read + write, via `zip_methods.cyr`; `[lib.zipall]` profile; lean `[lib.zip]` unchanged]; 2.6.0 = **ZIP archive container** [`zip.cyr` in-memory reader + writer, store + DEFLATE, zip-slip guards, per-member ratio cap, `[lib.zip]` profile — the agnosai `.agpkg` core]; 2.5.10 = **P(-1) audit remainder** [zstd memory-lifetime pooling → 0 B/call leaks; tar ladder DoS; multi-frame zstd; multi-member gzip; L-2/L-3/L-4/R-1; fault-seam routing + zstd OOM sweep + xz truncation fuzz — clears 2.6.0]; 2.5.9 = **P(-1) security hardening** [1 HIGH tar symlink-chain traversal + xz OOB-read/DoS/sha256 + OOM-latch crash class + zstd concurrency lock + stream allocs; first audit of the 2.4.x/2.5.x surface]; 2.5.8 = **zstd encoder priced parse** [`_ze_mvalue` bit-cost match selection + repcode candidates at the lookahead; corpus −9.9 %, zero regressions, beats `zstd -3` everywhere]; 2.5.7 = **zstd encoder parse quality** [repcode-aware match finding + adaptive FSE sequence tables; now beats `zstd -3` on real code/text/binary]; 2.5.6 = **zstd encoder competitiveness + decoder hardening** [FSE literal weights + repeat-offset codes + lazy parse + 1..9 level knob; decoder closed against 36 verified OOB/DoS paths + `fuzz_zstd.fcyr`]; 2.5.5 = **sovereign zstd encoder** `zstd_compress` [LZ77 + FSE sequences + Huffman literals; completes the codec, decode shipped 2.5.0]; 2.5.4 = xz / bzip2 encoder throughput [output byte-identical]; 2.5.3 = xz / bzip2 ratio cap; 2.5.2 = toolchain pin refresh to Cyrius 6.4.66; 2.5.1 = per-codec distlib profiles; 2.5.0 = sovereign `zstd.cyr` decoder + shared `tar.cyr` cursor)
- **`cyrius.cyml [package].cyrius`**: `6.4.69` — toolchain pin (6.4.67 → 6.4.68 at 2.7.0, → 6.4.69 at 2.7.1, tracking the active toolchain; 2.7.1 built + tested on it. `cyrius deps` re-resolved, clean rebuild + all gates green — no source / API / wire-format change from the pin)
- **Tag**: `2.7.1` (bare semver, no `v` prefix)
- **Released**: 2026-07-20

## Distribution

- **Cyrius stdlib**: shipping as `lib/sankoch.cyr` in Cyrius 6.4.x toolchain releases (full profile).
- **Kernel-safe subset**: `lib/sankoch-core.cyr` ships alongside since the 2.1.2 cut (LZ4 batch decompress only; no alloc / no syscalls / no mutex).
- **Consumers import via**: `include "lib/sankoch.cyr"` — no separate `[deps]` declaration in their `cyrius.cyml`.
- **Stdlib fold-in**: folded into the Cyrius stdlib since 2.0.2 (Cyrius 5.6.34); tracks the toolchain pin in `cyrius.cyml`. Per-version fold-in chronology lives in `CHANGELOG.md`.

## Source

- **Source**: **15,064 lines** across **21** domain modules (`src/*.cyr`) — 2.7.1 grew `xz.cyr` **1,939 → 2,104** (the BT4 binary-tree match finder: `_xzbt_hash4`, the shared tree-walk `_xze_get_matches`, the seed-only `_xzbt_skip`, the son[]/head tables + M-8 alloc + per-encode reset). Previously 2.7.0 grew `xz.cyr` **1,836 → 1,939** (the rep-only `nice_len` greedy shortcut in `_xze_lzma2_emit` + the interior DP cut in `_xze_dp_fill` with its O(1) last-byte quick-reject). Previously 2.6.4 grew `zip.cyr` **1,013 → 1,206** (P(-1) hardening: subtraction-form Zip64 bounds at 4 sites, `_zip_abandon` streaming lock release, mid-stream-add + name-length guards, the archive-global symlink ledger) and `zip_methods.cyr` **148 → 150** (matching streaming/name guards). Previously 2.6.3 grew `zip.cyr` **730 → 1,013** (MS-DOS/Unix time conversion, metadata read + write, the `zip_enc_*` streaming writer). Previously 2.6.2 grew `zip.cyr` **521 → 730** (Zip64 read + write, shared `_zip_emit_local` / `_zip_record`) and shrank `zip_methods.cyr` **174 → 143** (its duplicated header emission folded into the shared helpers). Previously 2.6.1 added `src/zip_methods.cyr` (**174**, the extra ZIP methods, kept out of the lean profile) and grew `zip.cyr` **487 → 521** (shared `_zip_prepare` / `_zip_verify` plumbing + method constants); 2.6.0 added `src/zip.cyr`, the first new module since 2.5.0. Previously the 2.5.10 audit-remainder arc grew `zstd.cyr` **2,083 → 2,384** (+301 — pooled decode/encode FSE + Huffman + reader slots, the multi-frame loop, `zstd_content_size`, and the OOM null-check sweep), `tar.cyr` **701 → 710**, `gzip.cyr` **638 → 650**, `lib.cyr` **254 → 265**. Previously the 2.5.9 security-hardening arc grew `tar.cyr` **513 → 701** (+188 — the cross-entry symlink ledger for H-1 + parse-path OOM guards for M-3), `zstd.cyr` **2,058 → 2,083** (+25 — M-12 lock wrappers), `xz.cyr` **1,819 → 1,836** (M-5/M-6/M-7 + M-8 flag), `bzip2.cyr` **1,316 → 1,323** (M-8/L-1 flags), `stream.cyr` **250 → 256** (M-13), `lz77.cyr` **181 → 184** (M-8), `lib.cyr` **246 → 254** (I-1 reset + M-12 dispatch). Largest modules: `deflate.cyr` **2,545**, `zstd.cyr` **2,384**, `xz.cyr` **1,939**, `bzip2.cyr` **1,323**, `lz4.cyr` **935**, `tar.cyr` **710**, `huffman.cyr` **683**, `gzip.cyr` **650**, `zip.cyr` **1,206**, `zip_methods.cyr` **150**; `runtime.cyr` **73**, `lib.cyr` **266**, `types.cyr` **43**. (`xz.cyr` now **2,104**.)
- **Per-file breakdown** lives in [`roadmap.md` § File Summary](roadmap.md#file-summary-at-230). Re-bump there alongside this file on every release.

## Test totals

The suite is split into **21 per-codec × direction / container suites** plus the
cross-cutting `ratio_cap` and `detect_error` suites under
`tests/tcyr/`, sharing `_harness.tcyr` (includes + 4 MB heap setup +
cross-cutting helpers).

| Suite group                                   | Functions | Assertions |
|-----------------------------------------------|----------:|-----------:|
| `tests/tcyr/*.tcyr` (21 split suites)         |       283 |  4,137,910 |
| `tests/tcyr/git_object.tcyr`                  |        10 |    346,583 |
| **Total**                                     |   **293** | **4,484,493** |

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
(2.6.0 → 2.6.4 — **26 tests / 206 assertions**: round-trip, empty archive/member, all six
zip-slip shapes, ratio cap, CRC-32 on a flipped *stored* byte, malformed/truncated input,
index bounds, writer overrun, Zip64 read+write, streaming write, per-entry metadata; plus
the 2.6.4 P(-1) adversarial set — byte-built hostile Zip64-overflow archives (42/98-byte),
the streaming-abandon deadlock paths, mid-stream-add rejection, cross-entry symlink escape,
and long-name refusal; reference `unzip` / bsdtar / Python `zipfile` parity is
`scripts/zip-smoke.sh`). Run one
with `cyrius test tests/tcyr/<name>.tcyr`, or all with bare `cyrius test`.

> **Counting correction (2.5.8)**: totals through 2.5.7 were tallied with a pattern that
> silently dropped one suite (the only one whose summary line omits the `(N total)`
> suffix), so every historical figure in this row was **21 assertions low**. The 2.5.7
> total was really 4,484,010, not 4,483,989. Figures from 2.5.8 onward are the full tally
> across all 21 suite runs.

The assertion total is heavily inflated by per-byte content-loop checks on streaming round-trips (a single 128 KB round-trip contributes 131,072 assertions through one `while (i < N) assert(load8(d+i) == load8(s+i))` loop). Read as a coverage-**density** number, not a coverage-**breadth** number. See [`guides/cyrius-usage.md`](../guides/cyrius-usage.md#what-assertions-means-here-and-why-the-number-is-so-large) for the full explanation.

## Fuzz totals

- **6,999 iterations** across 35 harness functions in 6 files:
  - `fuzz/fuzz_lz4.fcyr`: 700 (round-trip 500 + malformed 200)
  - `fuzz/fuzz_deflate.fcyr`: 1,629 (deflate batch 340 + zlib 160 + gzip 160 + 4 streaming variants 204 + tree-shape 55 + skewed-freq 30 + ratio-cap 240 + ratio-cap malformed 100 + **streaming ratio-cap 240 + streaming malformed 100**)
  - `fuzz/fuzz_xz.fcyr`: 1,000 (random-input 300 + corruption 200 + encode→decode round-trip 300 + ratio-cap 100 + **truncation 100 + an exhaustive prefix sweep of the fixture**, 2.5.10 L-5 — the class that reaches the M-5 check-field OOB site)
  - `fuzz/fuzz_bzip2.fcyr`: 900 (random-input 300 + corruption 200 + encode→decode round-trip 300 + **ratio-cap 100**)
  - `fuzz/fuzz_zstd.fcyr`: 1,150 (2.5.6 — decode-survival on random input 400 + encode→decode round-trip across 5 distributions 600 + corruption of valid streams 150; found the decoder-hardening SIGSEGVs)
  - `fuzz/fuzz_zip.fcyr`: 1,620 (**2.6.4** — random 300 + truncation prefix-sweep 120 + corruption 300 + hostile-field 300 [incl. Zip64 injection] + writer round-trip 200 + streaming round-trip 200 + Zip64 hostile-offset 200; reliably SIGSEGV'd the pre-fix i64-overflow path, green post-fix — doubles as the overflow-class regression gate)

## Dist bundles

| Bundle                       | Lines | Role |
|------------------------------|------:|------|
| `dist/sankoch.cyr`           | 14,843 | Full library — LZ4 / LZ4F / DEFLATE / zlib / gzip / xz / bzip2 de/compress + zstd de/compress (encode 2.5.5, competitive 2.5.6–2.5.8) + tar cursor, batch + streaming, + ratio-capped decompress (DEFLATE family batch + streaming; xz + bzip2 batch, 2.5.3) |
| `dist/sankoch-core.cyr`      |   332 | **[lib.core]** kernel-safe LZ4 batch decompress only (types + xxhash32 + lz4_decode); no alloc / syscalls / mutex (AGNOS initrd) |
| `dist/sankoch-zlib.cyr`      | 4,933 | **[lib.zlib]** (2.4.9) — DEFLATE/zlib only (`zlib_compress`/`zlib_decompress` + closure); drops LZ4/gzip/xz/bzip2/zstd/tar/streaming. Keeps the initialised-global footprint low so a consumer stays under its `max 1024 globals` budget while tracking current sankoch (sit's git read path / thoth's git producer). Runtime helpers via the extracted `src/runtime.cyr` |
| `dist/sankoch-gzip.cyr`      | 5,098 | **[lib.gzip]** (2.5.1) — gzip/DEFLATE decode closure + CRC-32 (the zlib profile with the gzip envelope) |
| `dist/sankoch-xz.cyr`        | 2,799 | **[lib.xz]** (2.5.1) — `.xz` (LZMA2) decode: lz77 match model + CRC-32 / CRC-64; + `xz_decompress_with_ratio_cap` (2.5.3, self-contained closure) |
| `dist/sankoch-bzip2.cyr`     | 2,099 | **[lib.bzip2]** (2.5.1) — bzip2 decode (BWT + Huffman + MTF) + CRC-32/BZIP2 + runtime; + `bzip2_decompress_with_ratio_cap` (2.5.3, self-contained closure) |
| `dist/sankoch-zstd.cyr`      | 2,514 | **[lib.zstd]** (2.5.1) — RFC-8878 zstd **de + compress** (decode 2.5.0, hardened 2.5.6; sovereign `zstd_compress` encoder 2.5.5, competitive 2.5.6–2.5.8 — now beats `zstd -3`, zstd's own default, on every fixture — with a 1..9 `zstd_compress_level`), own bit reader / FSE / Huffman; carries `runtime.cyr` since 2.5.9 for the API lock (M-12) and, since 2.5.10, for the `_sankoch_alloc` fault seam (L-5). Multi-frame `.zst` decode + `zstd_content_size` since 2.5.10 (M-2); zero per-call arena growth (M-9/M-10). agnova `base-system.tar.zst` + takumi zstd tarballs; the ZIP method-93 write path (2.6.x) |
| `dist/sankoch-zip.cyr`       | 5,654 | **[lib.zip]** (2.6.0) — PKZIP `.zip` container: in-memory reader + writer, methods 0 (store) / 8 (DEFLATE), CRC-verified, zip-slip guards, per-member ratio cap, 2.6.4 i64-overflow-safe Zip64 bounds. The DEFLATE closure + crc32 + `zip.cyr`; excludes `tar.cyr`. agnosai's `.agpkg` profile |
| `dist/sankoch-zipall.cyr`    | 11,359 | **[lib.zipall]** (2.6.1) — ZIP with EVERY method sankoch owns: 0 / 8 / 12 (bzip2) / 93 (zstd) / 95 (xz), read + write. Adds `zip_methods.cyr` + the xz/bzip2/zstd codecs to the `[lib.zip]` closure. Use `[lib.zip]` when only store + DEFLATE are needed — it is less than half the size |
| `dist/sankoch-tar.cyr`       | 11,363 | **[lib.tar]** (2.5.1) — sovereign tar cursor + every envelope `tar_open_auto` dispatches to (gzip / xz / bzip2 / zstd); the "extract any tarball" profile (takumi source tarballs, agnova rootfs) |

All zero deps. Regenerated at every release via `cyrius distlib` (full) plus the seven named profiles — `cyrius distlib core` / `zlib` / `gzip` / `xz` / `bzip2` / `zstd` / `zip` / `zipall` / `tar` (ten bundles total). CI gates on drift across all ten.

## In-flight slots

**2.7.1 shipped — the xz-encode BT4 match finder.** 2.7.0 closed the repetitive half of the
xz-encode gap; 2.7.1 closes part of the real-source half. The 2.7.0 profiling's "78 % match
finder" figure counted *operations, not time* — the HC3 chain nodes are cheap quick-rejects, so
an **HC4** (4-byte-hash chain) attempt gave only +4 % corpus while regressing repetitive −25 %,
and was rejected. **BT4** (a binary-tree finder, LzFind.c-style) is the genuine fix: it finds the
longest match + every shorter length in O(match_len + tree_depth), never re-comparing bytes across
candidates. On **xz-private** tables (65536-slot son[] tree + hash heads, +1.75 MiB) so DEFLATE's
shared 3-byte lz77 stays byte-identical. The greedy-covered skip range uses a **seed-only O(1)
insert** so BT4's per-insert cost never touches repetitive data. Result: real-source corpus
**0.60 → 0.73 MB/s (+21 %)** *and* smaller (58872 → 58704 B), speed gap to `xz -6` 7.1× → 5.8×,
text/zeros neutral, every stream round-trips via `xz -d`. Research + adversarial design (3
verifiers, all *sound*) ran as a workflow before any tree code.

**Forward: the 2.7.x ladder** (forward detail in
[`roadmap.md`](roadmap.md#-scheduled--the-27x-performance--ratio-ladder)):

- **2.7.2 — xz encoder dictionary / window growth.** The residual +7 % ratio vs `xz -6` on real
  source is mostly the 32 KB match window (`LZ77_WINDOW`) vs xz's 8 MB dict. Fix = raise
  `XZE_DICT_CODE` first (advertised dict ≥ max emitted distance, always) then widen the BT4
  window on **private** wider tables (DEFLATE's 32 KB frozen). A ratio play; a speed gap to xz's
  optimized C + 8 MB dict will persist.
- **2.7.3 — zstd optimal / 2-pass parse.** The residue on very-regular record data. A working DP
  probe (preserved at `/home/macro/Repos/sankoch-deferred-dp-2.5.8.diff`) reached −3.6 % on real
  source/binary vs the 2.5.8 priced parse's −0.5 %, at ~400 lines / ~224 KiB DP arrays / 4–74×
  encode time — worth doing gated behind levels 7–9.
- **Conditional (schedule on a consumer profile):** SIMD CRC-32 via `PCLMULQDQ` (slice-by-8
  already banks ~2× wire-identical; PMULL/scalar-fallback + silent-corruption risk gate the
  x86 win) and a wire-identical DEFLATE match-finder speedup (the byte-for-byte-parity
  mandate blocks the obvious knobs). Both slot into 2.7.x if a hot-path profile surfaces.

Not scheduled (unchanged): the Future codec bucket in [`roadmap.md`](roadmap.md) — Brotli,
GPU texture compression.

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

- **Cleanliness**: `cyrius build` 0 warnings on library path; `cyrius lint` 0 warnings per source file; `cyrfmt --check` clean across all `src/` + `programs/` + `tests/` + `fuzz/`; `cyrius vet src/lib.cyr` clean (27 deps, 0 untrusted, 0 missing).
- **Tests**: all tcyr suites green (split codec×direction suites incl. `zstd_compress` + `zip` + `ratio_cap` + `git_object`, auto-discovered by the CI Test loop; `detect_error` carries the 2.5.9 OOM-latch retry sweep across deflate/xz/bzip2); all fuzz harnesses green (6 files — lz4 / deflate / xz / bzip2 / zstd / zip, auto-discovered via `fuzz/*.fcyr`). **Note (2.5.9)**: `cyrius test` does not propagate a child suite's SIGSEGV as a non-zero exit — a crashing suite reports no failure line; verify a suspect suite by building + running its binary directly.
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
| 2.7.1  | 2026-07-20 | **xz encoder BT4 match finder** — binary-tree finder (LzFind.c-style) on xz-private tables with a seed-only O(1) skip; real-source corpus **0.60 → 0.73 MB/s (+21 %) and smaller** (58872 → 58704 B), gap to `xz -6` 7.1× → 5.8×, repetitive neutral, reference `xz -d` preserved, DEFLATE lz77 byte-identical. HC4 tried + rejected first (the "78 % match finder" was operation-count, not time). Pin → 6.4.69. Residual +7 % ratio → 2.7.2 dict |
| 2.7.0  | 2026-07-20 | **xz encoder repetitive-data speedup** — rep-only `nice_len` greedy shortcut + interior DP cut; text/zeros encode **~290–473× faster and smaller** (0.15→44.6 / 0.07→31.7 MB/s), real-source corpus exactly neutral; reference `xz -d` round-trip preserved. Design research + adversarial review ran as a workflow first. Pin → 6.4.68. HC4 match finder (real-source 7.3× gap) → 2.7.1 |
| 2.6.4  | 2026-07-20 | **P(-1) hardening — first security audit of the ZIP surface** (0 HIGH · 3 MED · 1 LOW). i64 additive-overflow defeated four Zip64 bounds checks (SIGSEGV from `zip_open`/`zip_extract`) → subtraction-form; streaming-abandon `_sankoch_mtx` leak → `_zip_abandon`; mid-stream `zip_add` overlap + name > 65535 truncation → rejected. HIGH symlink claim rebased LOW (ZIP is memory-only). New `fuzz_zip.fcyr`; `zip.tcyr` → 206 assertions |
| 2.6.3  | 2026-07-19 | **ZIP streaming write + per-entry metadata** — `zip_enc_begin/write/end` (bit-3 + data descriptors) and mode/mtime/symlink read + write (`zip_add_meta`), giving tar-parity extraction; bsdtar restores real symlinks and modes from sankoch's output. **Completes the 2.6.x ZIP arc** |
| 2.6.2  | 2026-07-19 | **ZIP Zip64** — EOCD record + locator + extended-information extra field, read + write (>65,535 members, >4 GB directories/entries); entry cap 65,535 → 16,777,216. Fixed a latent 2.6.0 writer bug that aliased caller name buffers (every entry got the last name, invisible to every external check) |
| 2.6.1  | 2026-07-19 | **ZIP: every method sankoch owns** — 12 (bzip2) / 93 (zstd) / 95 (xz) read + write via `zip_methods.cyr`, kept out of the lean `[lib.zip]` so agnosai's profile stays 4,969 lines; new `[lib.zipall]` (10 bundles). Reference parity both ways via bsdtar + Python `zipfile` |
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

The **2.6.4 P(-1) ZIP-surface audit** ([`docs/audit/2026-07-20-zip-container.md`](../audit/2026-07-20-zip-container.md))
is fully remediated: 0 HIGH + 3 MEDIUM + 1 LOW confirmed, all fixed and regression-tested;
no INFOs carried forward from it (the one deferred-style note — hardening `zip-smoke.sh` to
per-run `mktemp` paths — is a test-harness nicety, not a library finding). The
**2.5.9/2.5.10 P(-1) audit** ([`docs/audit/2026-07-19-pre-2.6.0.md`](../audit/2026-07-19-pre-2.6.0.md))
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
