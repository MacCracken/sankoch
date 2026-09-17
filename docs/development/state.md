---
name: Sankoch State
description: Living state of the sankoch repo — version, sizes, test totals, in-flight slots, consumers. Refreshed every release.
type: state
---

# Sankoch State

> **Last refresh**: 2026-09-16 (**v2.8.0 cut — Brotli decoder + per-profile arena-reset fix.** Every alloc-bearing profile bundle had been unlinkable since 2.7.10 (rekha filing). Fixing it surfaced memoized globals the full bundle's reset also missed: xz BT4 229,370 caller words overwritten after `alloc_reset()`, zstd L9 712, zstd L6 14. It also surfaced unguarded unlocked builders, a stranded canary, and a reset that was dead code on AGNOS. All are fixed, and `scripts/profile-link-gate.sh` now proves every bundle links and runs. Brotli decode (RFC 7932) ships in the full bundle + `[lib.brotli]` + `[lib.woff]` for rekha's WOFF2. Toolchain 6.6.2 → 6.6.4. Source **16,471 → 18,503**; tests **4,500,520 across 27 suites**; fuzz +`fuzz_brotli` (5,013 inputs); **12 bundles**. The pre-release review (0 H · 4 M · 15 L · 4 I) was all fixed. Earlier refresh narratives live in CHANGELOG.)
>
> Per [first-party-documentation.md § Development Docs](https://github.com/MacCracken/agnosticos/blob/main/docs/development/first-party/first-party-documentation.md#development-docs-docsdevelopment), this file holds the **volatile** state. Durable rules live in [`../../CLAUDE.md`](../../CLAUDE.md); release narrative lives in [`../../CHANGELOG.md`](../../CHANGELOG.md); forward ladder lives in [`roadmap.md`](roadmap.md).

---

## Version

- **`VERSION`**: `2.8.0` — single source of truth. 2.8.0 = **Brotli decoder (RFC 7932, decode only) + the per-profile arena-reset fix + profile link gate**; see CHANGELOG.
- **`cyrius.cyml [package].cyrius`**: `6.6.4` — toolchain pin. It was 6.6.2 at 2.7.15; 6.6.4 adds `SYS_FLOCK` and `O_DIRECT` / `O_LARGEFILE` / `O_DIRECTORY` / `O_NOFOLLOW` to the stdlib syscall peers, and `lib/` was re-vendored. Historic: 6.6.0 at 2.7.11 → 6.6.2 at 2.7.15 → 6.6.4 at 2.8.0. ⚠ `cyrius --version` inside the repo echoes the pin; `~/.cyrius/current` is the active binary.
- **Tag**: `2.8.0` (bare semver, no `v` prefix)
- **Released**: 2026-09-16

## Distribution

- **Cyrius stdlib**: shipping as `lib/sankoch.cyr` in Cyrius 6.4.x toolchain releases (full profile).
- **Kernel-safe subset**: `dist/sankoch-core.cyr` (LZ4 batch decompress only; no alloc / no syscalls / no mutex), available since the 2.1.2 cut. ⚠ Unlike the full bundle it is **consumed as a direct dep, not folded into the Cyrius stdlib** — a consumer (the AGNOS initrd loader) declares it and pulls this repo's `dist/` artifact. It is therefore *correct* that `~/.cyrius/lib/` carries `sankoch.cyr` but no `sankoch-core.cyr`; its absence there is not drift and not a packaging gap. Only the full profile folds into the stdlib.
- **Consumers import via**: `include "lib/sankoch.cyr"` — no separate `[deps]` declaration in their `cyrius.cyml`.
- **Stdlib fold-in**: folded into the Cyrius stdlib since 2.0.2 (Cyrius 5.6.34); tracks the toolchain pin in `cyrius.cyml`. Per-version fold-in chronology lives in `CHANGELOG.md`.

## Source

- **Source**: **18,503 lines** across **33** files in `src/`: **23** domain modules + **10** `reset_<profile>.cyr` dispatchers (179 lines). 2.8.0 added `brotli.cyr` (1,460) and the generated `brotli_dict.cyr` (82 lines, one 122,784-byte literal). It grew `runtime.cyr` 155 → 275 (the stranded-canary predicate, failed-arm handling, and the registration rule) and moved each module's reset into the module (`lib.cyr` 273 → 252).
- **Per-file breakdown** lives in [`roadmap.md` § File Summary](roadmap.md#file-summary-at-230). Re-bump there alongside this file on every release.

## Test totals

`tests/tcyr/` holds **28 files**: **27 runnable suites** — per-codec ×
direction, the `zip` container, and the cross-cutting `checksum`, `ratio_cap`,
`detect_error`, `stream`, `git_object`, `arena_reset`, `output_cap` and `deep_huffman` suites — plus the shared
`_harness.tcyr`, which is not itself a suite. 2.8.0 added `brotli_decompress.tcyr`
(4,554 assertions: tables, dictionary, prefix codes, the manifest corpus with guard-page
exact-cap decodes, prefixes, bit flips, caps, transforms, adversarial IMTF), and grew
`arena_reset.tcyr` to 107 (builder guards, stranded canary in both directions, failed arm).
It reads `tests/data/brotli/` at runtime, so run it from the repo root.

| Suite group                                   | Functions | Assertions |
|-----------------------------------------------|----------:|-----------:|
| `tests/tcyr/*.tcyr` (26 suites)               |       366 |  4,153,937 |
| `tests/tcyr/git_object.tcyr`                  |        10 |    346,583 |
| **Total** (27 runnable suites)                |   **376** | **4,500,520** |

⚠ **Counting basis (corrected at 2.7.12).** Sum only the summary lines carrying a
`(N total)` suffix — one per runnable suite (27 at 2.8.0). The runner
then prints its own `N passed, 0 failed` line, which counts **files** (the
suites plus `_harness.tcyr`), not assertions; folding it into the sum is what
made every figure through 2.7.11 read **25 high** (`4,495,243` for a true
`4,495,218`). This is the mirror of the error the 2.7.9 sweep fixed, where the
same tally ran 21 *low* by dropping a suite whose line omits the suffix.

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

- **12,722 iterations** across **7 files**: the 7,709 across 40 harness functions in the six
  pre-2.8.0 files (per-file: xz 1,000 · deflate 1,809 · bzip2 900 · zip 1,620 · lz4 700 · zstd 1,680;
  `fuzz_xz_truncate` and `fuzz_xz_truncate_sweep` share one printed line, and `fuzz_z_roundtrip` prints two),
  plus 2.8.0's `fuzz_brotli` at 5,013:
  - `fuzz/fuzz_brotli.fcyr`: 5,013 (2.8.0 — 13 seeds decoded to their manifest CRC-32 + 1,500 random + 2,000 seed mutations + 750 truncations + 750 splices; src flush against a PROT_NONE page on every decode, and accepted inputs re-decoded at exact cap into a guard-paged dst; ~0.2 s)
  - `fuzz/fuzz_lz4.fcyr`: 700 (round-trip 500 + malformed 200)
  - `fuzz/fuzz_deflate.fcyr`: 1,689 (deflate batch 340 + zlib 160 + gzip 160 + 4 streaming variants 204 + tree-shape 55 + skewed-freq 30 + ratio-cap 240 + ratio-cap malformed 100 + streaming ratio-cap 240 + streaming malformed 100 + **2.7.9 sync-flush round-trips 36** [random flush points and context resets, levels 1/6/9] **+ RFC 7692 framing 24** [per-message flush, trailer stripped and re-appended, replayed through one never-terminated decoder ctx with `deflate_dec_produced` asserted per frame])
  - `fuzz/fuzz_xz.fcyr`: 1,000 (random-input 300 + corruption 200 + encode→decode round-trip 300 + ratio-cap 100 + **truncation 100 + an exhaustive prefix sweep of the fixture**, 2.5.10 L-5 — the class that reaches the M-5 check-field OOB site)
  - `fuzz/fuzz_bzip2.fcyr`: 900 (random-input 300 + corruption 200 + encode→decode round-trip 300 + **ratio-cap 100**)
  - `fuzz/fuzz_zstd.fcyr`: 1,680 (2.5.6 — decode-survival on random input 400 + encode→decode round-trip across 5 distributions 600 + corruption of valid streams 150; found the decoder-hardening SIGSEGVs; **2.7.3 — +500 DP-optimal-parse (levels 7–9) round-trips**, each distribution × level; **+30 cross-block round-trips** — 20 L6 greedy + 10 L9 optimal — 2.7.4; **2.7.5 restored the L9 half 3 → 10 calls** after the chain-cutoff cut L9 record cost ~2.6 s → ~1.1 s per 2-block input)
  - `fuzz/fuzz_zip.fcyr`: 1,620 (**2.6.4** — random 300 + truncation prefix-sweep 120 + corruption 300 + hostile-field 300 [incl. Zip64 injection] + writer round-trip 200 + streaming round-trip 200 + Zip64 hostile-offset 200; reliably SIGSEGV'd the pre-fix i64-overflow path, green post-fix — doubles as the overflow-class regression gate)

## Dist bundles

| Bundle                       | Lines | Role |
|------------------------------|------:|------|
| `dist/sankoch.cyr`           | 18,375 | Full library — LZ4 / LZ4F / DEFLATE / zlib / gzip / xz / bzip2 de/compress + zstd de/compress (encode 2.5.5, competitive 2.5.6–2.5.8) + **Brotli decode (2.8.0)** + tar cursor, batch + streaming, + ratio-capped decompress (DEFLATE family batch + streaming; xz + bzip2 batch, 2.5.3) |
| `dist/sankoch-core.cyr`      |    333 | **[lib.core]** kernel-safe LZ4 batch decompress only (types + xxhash32 + lz4_decode); no alloc / syscalls / mutex (AGNOS initrd) |
| `dist/sankoch-zlib.cyr`      |  5,707 | **[lib.zlib]** (2.4.9) — DEFLATE/zlib only (`zlib_compress`/`zlib_decompress` + closure); drops LZ4/gzip/xz/bzip2/zstd/tar/streaming. Keeps the initialised-global footprint low so a consumer stays under its `max 1024 globals` budget while tracking current sankoch (sit's git read path / thoth's git producer). Runtime helpers via the extracted `src/runtime.cyr` |
| `dist/sankoch-gzip.cyr`      |  5,815 | **[lib.gzip]** (2.5.1) — gzip/DEFLATE decode closure + CRC-32 (the zlib profile with the gzip envelope) |
| `dist/sankoch-xz.cyr`        |  3,358 | **[lib.xz]** (2.5.1) — `.xz` (LZMA2) decode: lz77 match model + CRC-32 / CRC-64; + `xz_decompress_with_ratio_cap` (2.5.3, self-contained closure) |
| `dist/sankoch-bzip2.cyr`     |  2,366 | **[lib.bzip2]** (2.5.1) — bzip2 decode (BWT + Huffman + MTF) + CRC-32/BZIP2 + runtime; + `bzip2_decompress_with_ratio_cap` (2.5.3, self-contained closure) |
| `dist/sankoch-zstd.cyr`      |  3,465 | **[lib.zstd]** (2.5.1) — RFC-8878 zstd **de + compress** (decode 2.5.0, hardened 2.5.6; sovereign `zstd_compress` encoder 2.5.5, competitive 2.5.6–2.5.8 — now beats `zstd -3`, zstd's own default, on every fixture — with a 1..9 `zstd_compress_level`), own bit reader / FSE / Huffman; carries `runtime.cyr` since 2.5.9 for the API lock (M-12) and, since 2.5.10, for the `_sankoch_alloc` fault seam (L-5). Multi-frame `.zst` decode + `zstd_content_size` since 2.5.10 (M-2); zero per-call arena growth (M-9/M-10). agnova `base-system.tar.zst` + takumi zstd tarballs; the ZIP method-93 write path (2.6.x) |
| `dist/sankoch-zip.cyr`       |  6,551 | **[lib.zip]** (2.6.0) — PKZIP `.zip` container: in-memory reader + writer, methods 0 (store) / 8 (DEFLATE), CRC-verified, zip-slip guards, per-member ratio cap, 2.6.4 i64-overflow-safe Zip64 bounds. The DEFLATE closure + crc32 + `zip.cyr`; excludes `tar.cyr`. agnosai's `.agpkg` profile |
| `dist/sankoch-zipall.cyr`    | 13,313 | **[lib.zipall]** (2.6.1) — ZIP with EVERY method sankoch owns: 0 / 8 / 12 (bzip2) / 93 (zstd) / 95 (xz), read + write. Adds `zip_methods.cyr` + the xz/bzip2/zstd codecs to the `[lib.zip]` closure. Use `[lib.zip]` when only store + DEFLATE are needed — it is less than half the size |
| `dist/sankoch-tar.cyr`       | 13,137 | **[lib.tar]** (2.5.1) — sovereign tar cursor + every envelope `tar_open_auto` dispatches to (gzip / xz / bzip2 / zstd); the "extract any tarball" profile (takumi source tarballs, agnova rootfs) |
| `dist/sankoch-brotli.cyr`    |  1,896 | **[lib.brotli]** (2.8.0) — Brotli decode only: types + the generated dictionary + `brotli.cyr` + runtime + `reset_brotli.cyr`. The only codec profile besides `woff` that carries the 122,784-byte dictionary |
| `dist/sankoch-woff.cyr`      |  7,257 | **[lib.woff]** (2.8.0) — web fonts: the `[lib.zlib]` closure + Brotli, so WOFF 1.0 and WOFF2 come from ONE bundle (one sankoch bundle per program). rekha's profile |

All zero deps. **12 bundles**, one per profile in `cyrius.cyml`; CI and release loop over `scripts/profile-link-gate.sh --list-profiles`, gate drift and tracking on every bundle, and run the link gate (link + run + `alloc_reset` survival + AGNOS reachability) against each.

## In-flight slots

**Open issue queue: 0.** The profile-link filing (rekha, 2026-09-15) shipped fixed in 2.8.0 and is
archived. The Brotli proposal shipped and is archived under `proposals/archived/`.

**2.8.0 shipped: a link failure that was hiding a memory-safety gap.** The filing reported that
profile bundles would not link. Making them link showed that 2.7.10's reset had never been complete:
- xz BT4 and zstd tables survived `alloc_reset()` and wrote into caller memory;
- unlocked builders had no guard;
- a canary could strand outside the region `alloc_reset()` zeroes;
- on AGNOS the reset was dead code.

**The lesson worth carrying: a gate that checks bytes proves currency, not function.** The dist gate
was green on unlinkable bundles for six releases. 2.8.0's own first link gate was then shown, by
mutation, to miss the AGNOS regression in 9 of 11 profiles. Every new gate in 2.8.0 now ships with a
mutant that fails it.

**▶ 2.8.x scheduled** ([`roadmap.md` § Scheduled](roadmap.md#-scheduled--28x)):
1. **2.8.1 = Brotli encoder (RFC 7932).** In flight next. It must decode byte-exact via `brotli -d` and
   `brotli_decompress`, has quality levels measured against `brotli -q N`, starts with no dictionary,
   and wires `compress(FORMAT_BROTLI)`. Encode stays out of `[lib.brotli]` / `[lib.woff]` unless a
   consumer asks.
2. **2.8.2 = SIMD CRC-32 via `PCLMULQDQ`.**
3. **2.8.3 = GPU texture compression**, whose first sub-step is the sankoch vs mabda home decision.
4. **The 2.8.x-closeout P(-1) pass.** Scope: the 2.7.x encoder surface, the Brotli decoder + encoder,
   the runtime reset seam, the PCLMULQDQ fold and the texture encoder. It carries the `_huff_build`
   Kraft-completeness finding and the coverage-as-a-matrix review.

**Backlog (unscheduled)**: a wire-identical DEFLATE match-finder speedup, measured by sit as its worst
row.

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
| bote               | DEFLATE (raw)    | RFC 7692 `permessage-deflate` on its WebSocket MCP transport — **sankoch half shipped 2.7.9** (`deflate_enc_flush` + friends). ⚠ Still blocked upstream: cyrius's `lib/ws_server.cyr` exposes no `Sec-WebSocket-Extensions` handshake hook, so do not expect adoption on sankoch's schedule |
| rekha              | zlib, **Brotli** (decode) | WOFF 1.0 (zlib per table) + WOFF2 (one Brotli stream) — **shipped 2.8.0** via `[lib.woff]` (both from one bundle) or `[lib.brotli]` (WOFF2 only); `brotli_decompress_capped` at the table-directory size |
| Any crate          | All              | Replaces zlib FFI / shelling to gzip |

## CI / release gates

- **Cleanliness**: `cyrius build` 0 warnings on library path; `cyrius lint` 0 warnings per source file; `cyrfmt --check` clean across all `src/` + `programs/` + `tests/` + `fuzz/`; `cyrius vet src/lib.cyr` clean (29 deps, 0 untrusted, 0 missing at 2.8.0).
- **Tests**: all tcyr suites green (split codec×direction suites incl. `zstd_compress` + `zip` + `ratio_cap` + `git_object`, auto-discovered by the CI Test loop; `detect_error` carries the 2.5.9 OOM-latch retry sweep across deflate/xz/bzip2); all fuzz harnesses green under `timeout 60` (7 files — lz4 / deflate / xz / bzip2 / zstd / zip / brotli, auto-discovered via `fuzz/*.fcyr`). **Note (2.5.9)**: `cyrius test` does not propagate a child suite's SIGSEGV as a non-zero exit — a crashing suite reports no failure line; verify a suspect suite by building + running its binary directly. **Note (2.7.14)**: the same is true, and worse, for a *hung* suite — measured: `cyrius test tests/tcyr/deep_huffman.tcyr` against a decoder with the 2.7.13 streaming hang never returns at all (exit 124 only under an external `timeout`), so the CI job stalls until the workflow-level timeout rather than reporting a failure. There is no per-suite timeout. This is why `deflate_dec_write` carries a no-progress liveness assertion: reverting the fix's litlen pre-fill while keeping the guard turns that same run into **34 reported assertion failures** instead of a stall. Prefer a fail-closed assertion over relying on CI to notice a hang.
- **Wire-format gate** (a convention, *not* an automated check — ci.yml runs `cyrius bench` at the `Benchmarks` step but never diffs its SIZE lines against a stored baseline, so this is enforced by review): **47** SIZE lines in `cyrius bench` output must remain byte-for-byte identical across patch / minor releases unless explicitly broken with a CHANGELOG `Breaking` entry. (2.3.3 added the four `lz4f_bm{4,5,6,7}` block-max-sweep lines; 2.5.8 added `SIZE zstd6_rec_256K`, a record-structured parse-quality canary — the three `zstd6_text_*` lines use a periodic filler that is one long match at any level, so they did not move a byte across either the 2.5.7 or 2.5.8 parse rewrite; pre-existing lines unchanged.) The **xz and bzip2 encoders** (2.4.1 / 2.4.3) and the **zstd encoder** (`SIZE zstd6_*`, 2.5.6) are **deliberately excluded** from this gate — their output is not bit-reproducible across encoder versions, so they ship informational ratio lines in `bench` instead, as does the 2.4.5 ratio-cap section.
- **Bundle gate**: `cyrius distlib` + every profile (list from `cyrius.cyml` via `profile-link-gate.sh --list-profiles`) regenerate all 12 `dist/` bundles; CI fails on drift or an untracked bundle.
- **Profile link gate** (2.8.0, CI + release): `scripts/profile-link-gate.sh` — per profile: reset registration, reachable-call link probe, reference-CLI vectors before/after `alloc_reset()` with a victim buffer, and a lock-only `--agnos` DCE probe that must keep `_sankoch_arena_guard` / `_sankoch_reset_tables` alive.
- **Brotli dictionary regen** (2.8.0): `scripts/brotli_dict2cyr.py` regenerates `src/brotli_dict.cyr` and CI `cmp`s it.
- **NUL-literal gate** (2.8.0): `scripts/nul-literal-gate.py` — no string literal may decode to NUL (cycc 6.6.4 interning hazard), exempt only `src/brotli_dict.cyr`.
- **Kernel-safe tripwire**: `programs/core_smoke.cyr` links ONLY the `[lib.core]` modules and exercises LZ4 batch decompress on known fixtures. Any alloc / syscall / mutex leak into the core subset fails the build.
- **aarch64 cross-build**: hard gate in both ci.yml and release.yml; `cyrius build --aarch64 src/lib.cyr` must succeed and produce a valid ARM aarch64 ELF. Workflows expect `cycc_aarch64` in the Cyrius bundle (renamed from `cc5_aarch64` at Cyrius 6.0).
- **Tag filter**: release workflow triggers on bare semver tags only (`2.4.5`, not `v2.4.5`).
- **Version-verify**: release asserts `VERSION == git tag` before building.

## Recent releases

Most recent first. Full per-release notes in [`../../CHANGELOG.md`](../../CHANGELOG.md).

| Tag    | Date       | Headline                                              |
|--------|------------|-------------------------------------------------------|
| 2.8.0  | 2026-09-16 | **Brotli decoder + per-profile arena-reset fix** — every alloc-bearing profile bundle linked again (unlinkable since 2.7.10); the fix found reset gaps in the full bundle too (xz BT4 229,370 caller words, zstd, unlocked builders, stranded canary, AGNOS dead reset); new profile link gate. RFC 7932 decode (`brotli_decompress` / `_capped`, `FORMAT_BROTLI`) in `[lib]` + `[lib.brotli]` + `[lib.woff]` for rekha's WOFF2; 1008/1008 reference smoke. Toolchain 6.6.4 |
| 2.7.15 | 2026-09-12 | Toolchain `6.6.0` → `6.6.2`; no source change |
| 2.7.14 | 2026-09-07 | **Streaming decoder infinite-loop (DoS) fix** — `zlib_dec_write` / `gzip_dec_write` spun forever on ordinary valid input (~50 % of real source text at level 6), holding `_sankoch_mtx` and so blocking the whole process; present since the 2.3.0 arc, batch decode never affected. Three Huffman pre-fills used **9** (`HUFF_TABLE_BITS`, the fast-table *peek* width) against dynamic codes that reach 15, so `_ddec_fill` no-opped and `deflate_dec_write` consumed nothing while both envelope loops retried forever. Underneath, `_ddec_decode_huff` mislabelled a conclusive `ERR_INVALID_HUFFMAN` as NEED_MORE — so raising the fills alone still left **321/12,000** corrupt streams hanging. Fixed with all three fills → `HUFF_MAX_BITS + 1`, the conclusive-failure verdict, and a no-progress liveness assertion at the DEFLATE level. New `deep_huffman.tcyr` (598 assertions that **hang** against 2.7.13); `fuzz_tree_shape`/`fuzz_skewed_freq` now also decode streaming — either would have caught this in 2.3.0. CI dist gate widened from 8 to all 10 bundles (`-zip`/`-zipall` carry the decoder and were unchecked) |
| 2.7.13 | 2026-09-07 | **Caller-overridable output ceiling** — `zlib_decompress_capped` + `zlib_dec_init_output_capped` close the chitra/crab filing. `DECOMPRESS_MAX_OUTPUT`'s 16 MB is the right default for a caller that cannot bound its own output and was an absolute wall for one that can: chitra validates a PNG IHDR against its own caps and knows the exact byte count a correct stream must produce, yet could not decode an ordinary phone photograph (~5.6 MP RGB), and the streaming API enforced the same ceiling so it was no way around it. **The default is unchanged** — this adds a way to ask, not a new global. `max_output` is an absolute count clamped to `dst_cap`; `out_max` threads through the DEFLATE decoder on `ratio_max`'s 0-sentinel convention, so every existing caller passes 0 and the emit-path guard stays one compare. New `output_cap.tcyr` (27 assertions, 96 MB heap — it pins that the same 18 MB stream the default entries must still refuse decodes byte-exactly through the capped ones) + `fuzz_output_cap` (120). ⚠ Writing that harness surfaced a **pre-existing High-severity streaming hang** (dynamic Huffman codes > 9 bits), reproduced against pristine 2.7.12 and filed rather than bundled |
| 2.7.12 | 2026-09-07 | **Toolchain re-verification on cyrius 6.6.0 + ledger repair** — no source change; `src/` byte-identical to 2.7.11 and all ten bundles regenerate identical but for the version stamp. The pin already read 6.6.0 and upstream's latest release *is* 6.6.0, so nothing moved; what changed is the **6.6.0 binaries themselves**, rebuilt in place 2026-09-07 — the one case a version pin cannot detect — so every gate was re-run rather than carried forward (4,495,218 assertions / 0 failures, 6 fuzz harnesses, core_smoke, aarch64, lint/fmt/vet). Repaired a ledger two releases behind (state.md stuck at 2.7.10 and still claiming pin 6.5.35; roadmap and doc-health at 2.7.9), re-counted source 16,265 → **16,326** and the roadmap File Summary 15,745 → **16,326**, and corrected the assertion total, which was **25 high** from summing the runner's own file-count line. First full SIZE table since pre-2.4.0: 40 of 43 shared rows identical, 3 improved — exactly the rows 2.7.9's block chooser was expected to move |
| 2.7.11 | 2026-09-06 | **cyrius 6.6.0 (`Result` value form): pin bump + re-vendor** — 6.6.0 makes `Result`/`Option`/`Either` `: stack` types, so a payload variant is a register pair and `payload()`/`tagged_new()` are gone; a single-variable bind or `store64(&slot, f())` is now a compile error rather than a silent payload drop. sankoch needed **no source change**, and that was verified rather than assumed: the public surface returns plain `i64` codes from `enum Error`, and the repo vendors neither `result.cyr` nor `tagged.cyr`. The dangerous shape — a hand-rolled `load64(r)`/`load64(r + 8)` pair, which still compiles — was swept: eight `src/` variables read at both offsets, all eight inspected and cleared as sankoch's own documented heap structs. Pin 6.5.35 → 6.6.0; all ten bundles regenerated |
| 2.7.10 | 2026-08-24 | **Surviving a caller's `alloc_reset()`** — every lazy global here is a raw arena pointer memoized behind `if (ptr == 0)`, `_sankoch_mtx` included, and `alloc_reset()` rewinds the arena without telling anyone, leaving them all dangling-but-non-zero. Filed by chitra as a PNG decode error; the decode failure was the benign symptom and the defect was a **wild write** — one ordinary `crc32_init_table()` call after a reset overwrote **16,351 bytes** of the caller's own buffer. Detection is exact, not heuristic: `alloc_reset()` zeroes the span it rewinds, so an arena canary is guaranteed destroyed — one load and one compare, checked before `_sankoch_mtx` is touched and again inside `crc32_init_table()`, which consumers call without the lock. `crc32_init_table()` also became idempotent (it had rebuilt the 16 KB table on every call). New `arena_reset.tcyr`, 21 assertions, all failing against 2.7.9 |
| 2.7.9  | 2026-08-23 | **DEFLATE sync flush for RFC 7692 + pin → 6.5.35** — `deflate_enc_flush` (BFINAL=0 + `00 00 FF FF`, window retained), `deflate_enc_reset_context` (guarded against a mid-block call), `deflate_dec_produced` (the decode-side gap the bote filing flagged; `deflate_dec_finish` demanded a BFINAL=1 block *and* released the mutex). Measuring it exposed **+64 % vs reference zlib**, so the level ≥ 4 path now prices dynamic against fixed and emits the cheaper block — header cost measured exactly via a scratch bitwriter, not re-derived. RFC 7692 framing at 200-byte messages **4,764 → 2,908 B (−39.0 %), +64 % → +0.1 %** vs zlib; batch 3 of 43 SIZE rows improved, 40 unchanged, ~3 % throughput on 4 KB. Surfaced + fixed a latent **M-8-class OOM latch** in `_deflate_build_enc_fixed` (SIGSEGV in the retry sweep). New `deflate_sync_flush.tcyr` (24th file) + reference interop both ways vs Python `zlib` + 60 fuzz cases. ⚠ 6.5.35 made bare `cyrius fmt` rewrite in place → CI gate moved to `--check`, tree reformatted (24 files, indent only) |
| 2.7.8  | 2026-08-18 | **Toolchain catch-up to 6.5.26 + issue backlog cleared** — no source change; all ten `dist/` bundles regenerate byte-identical to 2.7.7 apart from the version stamp, which is the evidence the pin move is behaviour-neutral rather than merely untested. Both lingering issues were already fixed in place and simply never archived; open queue → 0 |
| 2.7.7  | 2026-08-09 | **ZIP: a sizing API, reclaimable readers, discriminated open failures** — `zip_bound` / `zip_bound_member` (the writer never grows `dst` and there was no way to ask how big it must be, so agnosai had reproduced the 30/46/22-byte header arithmetic in its own source), `zip_open_a` / `zip_writer_init_a`, `zip_last_error`. All three from the agnosai `.agpkg` consumer report |
| 2.7.6  | 2026-07-26 | **>1 MiB DEFLATE block-boundary corruption fix** — the batch chunker resumed each 1 MiB block at `block_end` while the encoders match against the full `src` and can overshoot by up to `LZ77_MAX_MATCH`, so the overshoot was emitted twice and the stream decoded **longer than the input**, with no error (no container checksum). Every consumer compressing >1 MiB was affected; no fixture in `tests/` or `fuzz/` had ever crossed 1 MiB on the one-shot path. Filed by stiva |
| 2.7.5  | 2026-07-21 | **zstd L9 optimal-parse hash-chain saturation cutoff** — the frame-global chain (2.7.4) made repetitive record data walk a 512-deep chain of strictly-worse same-length duplicates at every DP position (~2.6 s / 256 KiB L9). `_zo_getmatches` now bails after 128 consecutive non-improving candidates **once `best >= 32`** (the length gate separates saturated duplicates from useful depth — a gate-less/depth-warmup cutoff regresses text/object-code 4.5 %/10–30×). Record L9 **2.76 → 1.86 s (1.48×)**; worst real-corpus ratio Δ **+0.043 %** (object code), 0 % on text/prose/records/mixed; 43 gated SIZE lines untouched (L6 greedy). Cross-block L9 fuzz restored 3 → 10 calls; arch note 001 |
| 2.7.4  | 2026-07-21 | **zstd encoder cross-block match window** — both parses (greedy + DP-optimal) lifted to frame-global coordinates + a persistent 512 KiB window (`_ze_prev` 4 MiB), so a block's sequences reference matches in prior blocks. sankoch's zstd now **beats `zstd -19` on record data** (L9 227,721 → 125,886, −44.7 %) and on a 4.3 MB record fixture; source −10.5 %; single-block byte-identical; no frame/offset change (single-segment frames). +cross-block smoke (16 cases) + fuzz (40). **Completes the encoder ladder.** OOM-sweep crash caught + guarded |
| 2.7.3  | 2026-07-21 | **zstd encoder DP optimal parse (levels 7–9)** — shortest-path parse with per-node repcode state, gated behind `zstd_compress_level` 7–9; **per-block best-of** keeps it a strict improvement over the greedy default (real-source L9 −4.9 %, records best-of-neutral). Validated vs reference `zstd -d` (40 adversarial files + 800 round-trips); +500 fuzz round-trips + L9 smoke. Surfaced the zstd 128 KB window as the record-data limit (→ 2.7.4) |
| 2.7.2  | 2026-07-20 | **xz encoder dictionary/window growth** — xz-private match window 32 KB → 256 KB + matching 256 KB LZMA2 dict; real-source corpus **58704 → 54976 B (−6.4 %)**, gap to `xz -6` **+7.0 % → +0.2 %**; son[] → 8 MB (lazy, encode-only); DEFLATE window frozen; reference `xz -d` accepts every stream. **Completes the xz-encode arc** (2.7.0 repetitive speed, 2.7.1 real-source speed, 2.7.2 real-source ratio) |
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

The **2.8.0 pre-release review** ([`docs/audit/2026-09-16-2.8.0-brotli-and-reset.md`](../audit/2026-09-16-2.8.0-brotli-and-reset.md)) is remediated: 0 HIGH · 4 MEDIUM · 15 LOW · 4 INFO, all fixed except R-22, which concerns an upstream cyrius doc. Carried to the closeout: the canary-arm residual (a real 8-byte OOM that recovers within one call) and the libbrotlidec mutation differential that was not run.

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
