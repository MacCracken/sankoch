---
name: Sankoch Documentation Health
description: Living state of doc currency in the sankoch repo — fresh / stale / archived / open-question. Refreshed in place when docs are touched.
type: state
---

# Documentation Health — sankoch

> **Last refresh**: 2026-07-20 (**2.7.0 cut — xz encoder repetitive-data speedup**; rep-only `nice_len` greedy shortcut + interior DP cut in `xz.cyr` (1,836 → 1,939); text/zeros encode ~290–473× faster and smaller, corpus neutral, reference `xz -d` round-trip preserved; research + adversarial design ran as a workflow; new `docs/benchmarks/2026-07-20-2.7.0-baseline.md` (before + after); toolchain pin 6.4.67 → 6.4.68; VERSION/CHANGELOG/state/roadmap → 2.7.0; roadmap ladder re-cut (2.7.1 = HC4 match finder for the real-source 7.3× gap, 2.7.2 = zstd optimal parse); source 14,899; test totals 293 fns / 4,484,493 (unchanged — encoder speed, no new tests); fuzz 6,999 across 6 files; full bundle 14,946. Previously — **2.6.4 cut — P(-1) hardening: first security audit of the ZIP surface**; new `docs/audit/2026-07-20-zip-container.md` [0 HIGH · 3 MEDIUM · 1 LOW confirmed, all fixed — i64 Zip64-bounds overflow ×4 → subtraction-form, streaming-abandon lock leak → `_zip_abandon`, mid-stream-add overlap + name-length truncation → rejected; HIGH symlink claim rebased LOW: ZIP is memory-only]; new `fuzz/fuzz_zip.fcyr` (6 strategies, raises fuzz harness count 5 → 6); `zip.tcyr` 175 → 206 assertions; `zip-smoke.sh` 13 checks unchanged; VERSION/CHANGELOG/state/roadmap → 2.6.4; source 14,796 [zip.cyr 1,206]; test totals 293 fns / 4,484,493; fuzz 6,999 across 6 files; full bundle 14,843. Previously — **2.6.3 cut — ZIP streaming write + per-entry metadata**; completes the 2.6.x ZIP arc; `zip.tcyr` 20 tests / 175 assertions; `zip-smoke.sh` 13 checks incl. metadata, data descriptors and a streaming-write check; VERSION/CHANGELOG/state/roadmap → 2.6.3; source 14,601; test totals 287 fns / 4,484,462; roadmap notes the un-audited ~1,900 ZIP lines for the next P(-1). Previously — **2.6.2 cut — ZIP Zip64**; EOCD record + locator + extended-information extra field, read + write; entry cap 65,535 → 16,777,216; latent 2.6.0 name-aliasing fix; `zip.tcyr` 16 tests / 123 assertions; `zip-smoke.sh` 10 checks incl. two Zip64 read fixtures + a Zip64 write check; VERSION/CHANGELOG/state/roadmap → 2.6.2; source 14,313; test totals 283 fns / 4,484,410. Previously — **2.6.1 cut — ZIP: every method**; new `src/zip_methods.cyr` (174) + `[lib.zipall]` profile (10 bundles); `zip.tcyr` 15 tests / 98 assertions; `zip-smoke.sh` 7 shapes incl. a bsdtar-written xz archive; VERSION/CHANGELOG/state/roadmap → 2.6.1; CLAUDE.md gained the zip_methods.cyr row + bsdtar in the reference-CLI rule; source 14,135 across 21 modules; test totals 282 fns / 4,484,385. Previously — **2.6.0 cut — ZIP archive container**; new `src/zip.cyr` (487) + `tests/tcyr/zip.tcyr` (22nd suite) + `scripts/zip-smoke.sh` + `[lib.zip]` profile (9 bundles); VERSION/CHANGELOG/state/roadmap → 2.6.0; CLAUDE.md architecture block gained the zip.cyr row + the ZIP reference-CLI rule; source 13,926 across 20 modules; test totals 278 fns / 4,484,346. Previously — **2.5.10 cut — P(-1) audit remainder**; closes the deferred half of the audit [zstd arena leaks → 0, tar ladder DoS, multi-frame zstd, multi-member gzip, L-2/L-3/L-4/R-1, L-5/I-1 testability]; **every confirmed audit finding resolved — 2.6.0 cleared**; VERSION/CHANGELOG/state/roadmap → 2.5.10; source 13,437 [zstd.cyr 2,384]; full bundle 13,480; test totals 267 fns / 4,484,286; fuzz 5,379 across 28 fns; INFO-D narrowed to the arena design item, INFO-I1 CLOSED. Previously — **2.5.9 cut — P(-1) security hardening**; first audit of the never-audited 2.4.x/2.5.x surface [xz/bzip2/tar/zstd-encoder] → new `docs/audit/2026-07-19-pre-2.6.0.md` [1 HIGH + 13 MEDIUM + 5 LOW] + `docs/benchmarks/2026-07-19-2.5.9-p1-baseline.md`; VERSION/CHANGELOG/state/roadmap → 2.5.9; source re-counted [tar.cyr 513→701, total 13,099; full bundle 13,142]; test totals 267 fns / 4,484,226; INFO-E resolved [negative], INFO-D amplified, INFO-I1 new; remainder → 2.5.10. Previously — **2.5.8 cut — zstd encoder priced parse**; VERSION / CHANGELOG / state / roadmap bumped to 2.5.8, source re-counted [zstd.cyr 1,992→2,058; total 12,845; full bundle 12,827], test totals 267 fns / 4,484,022 — **and corrected a long-standing under-count**: every historical assertion figure was 21 low, because the tally pattern dropped the one suite whose summary line omits the `(N total)` suffix, new benchmark doc `2026-07-19-2.5.8-priced-parse.md`, roadmap 2.5.8 shipped + the optimal/2-pass DP moved to a Deferred arc with the measured comparison that justified deferring it; roadmap File Summary re-counted against `wc -l` — it had drifted to a 12,248 total and stale Tests/Fuzz/Distlib paragraphs) | **Refresh cadence**: opportunistic — update the affected row whenever a doc is touched.
>
> **Scope**: this repo only (`sankoch`) — the entire `docs/` tree plus root-level files (README, CHANGELOG, CLAUDE.md, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, LICENSE, VERSION, cyrius.cyml, .gitignore). Per-stdlib-dep docs live in their own repos.
>
> **Convention** (adopted from agnosticos / cyrius 2026-05-23): pattern from `cyrius/docs/doc-health.md`, scoped to sankoch's smaller doc tree (~21 markdown files vs cyrius's ~105). Tier structure is lighter here; principle is the same.

This is a **ledger**, not a one-time audit. Rewrite-in-place as docs change.

---

## At a glance — 2026-05-23 inventory (post-2.3.0 + standards sweep)

**21 markdown files** across the repo. Bucket counts:

| Bucket | Count | What it means |
|---|---|---|
| ✅ **Fresh / touched in current cycle** | 16 | Every root file refreshed at 2.3.0 cut; new state.md / doc-health.md / adr/ / architecture/ / guides/getting-started.md scaffolded this sweep; roadmap.md trimmed to forward-only; CHANGELOG cut for 2.3.0; existing audit + bench files all dated artifacts touched at release. |
| 🟡 **Stale — refresh in place** | 0 | None flagged. |
| 🟠 **Read-through outstanding** | 0 | None. |
| 🔵 **Probably evergreen** | 3 | LICENSE, CODE_OF_CONDUCT.md, docs/sources/compression.md (RFC + spec citations — change only when a referenced spec moves). |
| 📦 **Archive — frozen by design** | 2 | `docs/development/issues/archived/` (2 — both 2.0.2/2.0.3 zlib cl-tree regression fixtures, resolved). |
| ❓ **Open strategic question** | 0 | None. |

Numbers exact at this snapshot.

**Why now**: doc-health convention adopted from cyrius/agnosticos at the 2.3.0 cut, alongside a first-party-standards conformance sweep. Sankoch's doc tree was active but lacked the meta-surface — the audit history, the benchmark series, the roadmap have all been maintained, but the *aggregate* currency had no surface. This file is that surface.

**2026-05-23 sweep notes**: full standards conformance sweep. Findings:

1. **CLAUDE.md inlined volatile state** — version, source line counts, test/assertion counts, distribution history all in `CLAUDE.md`'s "Current State" block. Per the first-party-documentation.md mandate (CLAUDE.md = durable, state.md = volatile), this rots within a minor. Fixed: extracted to `docs/development/state.md`; CLAUDE.md now carries a pointer block.
2. **Broken standards link** — `applications/first-party-standards.md` (since renamed to `first-party/`) referenced in CLAUDE.md and CONTRIBUTING.md. Fixed.
3. **Stale `cc5` references** — Cyrius's bootstrap binary was renamed `cc5 → cycc` at v5.0.0 and `cycc → cyc` at v6.0.0. CLAUDE.md still said "compiled by cc5" + "NEVER use raw `cat file | cc5`". Updated to reference toolchain via `cyrius.cyml` pin + `cycc` shorthand.
4. **Missing doc-tree scaffolds** — `docs/adr/` (decisions), `docs/architecture/` (invariants), `docs/guides/` (how-tos) were absent per the standard's minimum layout. Scaffolded with READMEs + a template under adr/ and getting-started.md under guides/. `docs/development/cyrius-usage.md` moved to `docs/guides/cyrius-usage.md` (it's a how-to, not a development artifact).
5. **Stale architecture table in README** — line counts at 4,675 total (current: 6,299); missing `xxhash32.cyr` and `lz4_decode.cyr` rows entirely (added in 2.1.2); assertion total at 1,375,921 (current: 1,708,518); distlib at 4,824 (current: 6,326); plus the "landing in next Cyrius lang release" line was outdated (sankoch has shipped through 2.3.0 in stdlib via 6.0.x). Refreshed.
6. **Stale SECURITY.md** — Supported Versions table only listed 2.0.x. Updated to 2.3.x; audit list extended through the 2026-05-23 redux.
7. **.gitignore drift from standard** — missing `/dist/`, `*.tar.gz`, `cyrius-*.tar.gz`, `SHA256SUMS`, `!lib/k*.cyr` exception, secrets glob. Updated to the standard's posture.

Also created: this file (`docs/doc-health.md`).

---

## Tier 1 — Root files

| File | Last touched | Status | Notes |
|---|---|---|---|
| `README.md` | 2026-07-18 | ✅ Fresh | Formats table + codec paragraphs updated at 2.5.5 to add **zstd** (de+compress, `FORMAT_ZSTD`) — was stale (missing zstd/tar since 2.5.0). Current through 2.4.6 otherwise: ratio-cap API subsection (batch `*_with_ratio_cap` + streaming `*_dec_init_capped`); Architecture table rows note ratio-cap on deflate/zlib/gzip + the agnos lock no-op on lib. Defers all volatile line / test / assertion / distlib counts to state.md (no inlined figures). |
| `CHANGELOG.md` | 2026-07-20 | ✅ Fresh | **Source of truth per CLAUDE.md.** Through `[2.7.0] — 2026-07-20` (xz encoder repetitive-data speedup — rep-only `nice_len` greedy shortcut + interior DP cut, ~290–473× faster on text/zeros and smaller, corpus neutral; pin → 6.4.68); `[2.6.4] — 2026-07-20` (P(-1) hardening — first security audit of the ZIP surface: i64 Zip64-bounds overflow, streaming-abandon lock leak, mid-stream-add overlap, name-length truncation — all fixed; `fuzz_zip.fcyr`); `[2.6.3] — 2026-07-19` (ZIP streaming write + per-entry metadata — completes the ZIP arc); `[2.6.2]` ZIP Zip64 read + write + the latent name-aliasing fix); `[2.6.1]` ZIP: every method sankoch owns — 12/93/95 both ways, `[lib.zipall]`); `[2.6.0]` ZIP archive container — `zip.cyr` in-memory reader + writer, agnosai `.agpkg` core); `[2.5.10]` P(-1) audit remainder — zstd arena leaks → 0, tar ladder DoS, multi-frame zstd, multi-member gzip, testability; clears 2.6.0); `[2.5.9]` P(-1) security hardening (1 HIGH tar symlink-chain traversal + xz OOB/DoS/sha256 + OOM-latch class + zstd concurrency lock + stream allocs); `[2.5.8]` zstd encoder priced parse; `[2.5.7]` parse quality (repcode matching + adaptive FSE sequence tables); `[2.5.6]` competitiveness + decoder hardening; `[2.5.5]` sovereign zstd encoder; `[2.5.4]` xz/bzip2 throughput; `[2.5.3]` xz/bzip2 ratio cap; `[2.5.2]` pin → 6.4.66; `[2.5.1]` per-codec distlib profiles; `[2.5.0]` sovereign zstd + tar cursor. Empty `[Unreleased]` header at top per Keep-a-Changelog convention. **2.5.7 closeout restored the `[2.5.6]` header** (a bite's Edit had dropped it, orphaning 2.5.6 content under `[Unreleased]`). |
| `CLAUDE.md` | 2026-07-18 | ✅ Fresh | Restructured 2026-05-23 (volatile state → state.md; standards link + `cc5` refs fixed). **2026-07-18**: removed the stale "Do not implement Zstandard in this crate" hard rule (superseded — zstd decode shipped 2.5.0, encode scheduled 2.5.5) and added a positive **Modular by profile — every lossless codec lives here** principle capturing why (per-codec distlib profiles mean no consumer bloat). |
| `CONTRIBUTING.md` | 2026-05-23 | ✅ Fresh | Standards link fixed (same path correction). |
| `SECURITY.md` | 2026-07-18 | ✅ Fresh | Supported Versions table at 2.5.x. "Next periodic audit" pointer genericized to the pre-next-minor P(-1) closeout (was a stale/dangling "2.4.x decode-only xz/bzip2 arc" ref — xz/bzip2 encode had since shipped @2.4.1/2.4.3 and roadmap no longer listed that item). |
| `CODE_OF_CONDUCT.md` | 2026-05-01 | 🔵 Evergreen | Standard text; touch only when the project's CoC policy changes. |
| `LICENSE` | 2026-05-01 | 🔵 Evergreen | GPL-3.0-only. |
| `VERSION` | 2026-07-20 | ✅ Fresh | `2.7.0`. Single source of truth per the standards. |
| `cyrius.cyml` | 2026-07-20 | ✅ Fresh | Toolchain pin `cyrius = "6.4.68"` (refreshed 6.4.67 → 6.4.68 heading into the 2.7.0 arc; 2.6.4 shipped on 6.4.67. `cyrius deps` re-resolved, clean rebuild + all gates clean — no source/API/wire-format change). |
| `.gitignore` | 2026-05-23 | ✅ Fresh | Updated 2026-05-23 to match the first-party standard: `/dist/`, `*.tar.gz`, `cyrius-*.tar.gz`, `SHA256SUMS`, `!lib/k*.cyr` exception, `.env*` / `*.pem` / `*.key`. |

---

## Tier 2 — Operational / Development (`docs/development/`)

| File | Last touched | Status | Notes |
|---|---|---|---|
| `roadmap.md` | 2026-07-18 | ✅ Fresh | Status header (→ Stable v2.5.2) + Dependencies pin at 6.4.66. **File Summary re-counted** for the 19-module tree — added `runtime.cyr` (73) / `zstd.cyr` (729) / `tar.cyr` (513) rows, corrected `lib.cyr` 282→239 + `types.cyr` 41→42 + core-total 316→317, total 10,078→11,351; Distlib paragraph refreshed to the current eight bundles (full 11,394 / core 331 + six lean profiles). Anchor `#file-summary-at-230` kept stable. **Ladder scheduled 2026-07-18**: intro "no release committed" → committed ladder; Backlog section became `▶ Scheduled` with 2.5.3 (xz/bzip2 ratio cap) / 2.5.4 (encoder throughput) / **2.5.5 (zstd encode)** / 2.6.x (full-feature ZIP archive container arc, agnosai-first: 2.6.0 store+DEFLATE round-trip scoped from agnosai's `definitions/packaging.rs`, then 2.6.1 other methods [incl. zstd method 93, writable once 2.5.5 lands] / 2.6.2 zip64 / 2.6.3 streaming+metadata; encryption/multi-disk/Deflate64 non-goals). **Future reframed**: Zstandard removed (now scheduled), section retitled "additional codecs (in-scope, unscheduled)" per the modular-by-profile principle — Brotli + GPU-texture remain; Deferred untouched. **2.5.4 shipped 2026-07-18**: status → v2.5.4; 2.5.3 + 2.5.4 moved from the ladder to ✅-shipped notes (ladder now 2.5.5 → 2.6.x); File Summary re-counted (xz 1,819 / bzip2 1,316 / total 11,509). **2.5.6 shipped 2026-07-18**: status → v2.5.6; 2.5.5 + 2.5.6 moved to ✅-shipped; ladder now **2.5.7 (zstd repcode-aware matching)** → 2.6.x; intro updated (competitiveness landed). **2.5.7 shipped 2026-07-18**: status → v2.5.7; 2.5.7 → ✅-shipped (repcode + adaptive FSE tables); ladder now **2.5.8 (optional optimal parse)** → 2.6.x; intro notes the encoder beats `zstd -3`. **2.5.8 shipped 2026-07-19**: status → v2.5.8; 2.5.8 → ✅-shipped (priced parse); the optimal/2-pass parse became a **`⏸ Deferred`** section carrying the measured DP-vs-shipped comparison; ladder now 2.6.x only. **File Summary re-counted against `wc -l`** (it had drifted badly — total 12,248 → 12,845, zstd.cyr 1,462 → 2,058, lib.cyr 239 → 246) and the stale Tests / Fuzz / Distlib paragraphs beneath it refreshed (234 fns → 267; 4 fuzz files → 5; distlib full 11,394 → 12,827). |
| `state.md` | 2026-07-18 | ✅ Fresh | Version/pin/date fields at 2.5.2 (pin 6.4.66). **Source + Dist bundles rows re-counted** — Source 10,078/16-module → 11,351/19-module; Dist table refreshed (full 11,394 / core 331 / zlib 4,924) + five per-codec profile rows added (gzip 5,077 / xz 2,697 / bzip2 2,014 / zstd 782 / tar 9,308), regeneration note corrected to all eight profiles. Clears the pre-2.4.7 stale-figure debt flagged since 2.5.0. Test/fuzz totals unchanged (234 fns / 4,483,834 asserts; 3,929 fuzz). **Ladder pass 2026-07-18**: In-flight slots rewritten from "none committed" to the scheduled 2.5.3 / 2.5.4 / 2.6.x ladder; Consumers table gained a pending `agnosai` (ZIP read+write, 2.6.0) row. **2.5.4 cut 2026-07-18**: version → 2.5.4, source 11,509 (xz 1,819 / bzip2 1,316), dist full 11,552 / xz 2,778 / bzip2 2,091 / tar 9,466, In-flight slots → 2.5.4 shipped / 2.5.5 next (+ benchmark-doc link). **2.5.6 cut 2026-07-18**: version → 2.5.6, source 12,583 (zstd.cyr 1,798), test 264 fns / 4,483,985, fuzz 5 files / 5,279 iters (+`fuzz_zstd.fcyr`), dist full 12,565 / zstd 1,840 / tar 10,488, In-flight slots → 2.5.6 shipped / 2.5.7 next, SIZE-gate note adds zstd to the informational-exclusion list. **2.5.7 cut 2026-07-18**: version → 2.5.7, source 12,779 (zstd.cyr 1,992), test 265 fns / 4,483,989, dist full 12,761 / zstd 2,034 / tar 10,682, In-flight → 2.5.7 shipped / 2.5.8 optional; Recent-releases + Version-history rows gained 2.5.7. **2.5.8 cut 2026-07-19**: version → 2.5.8, source 12,845 (zstd.cyr 2,058), test 267 fns / 4,484,022 (+ a counting-correction note: historical totals were 21 low), dist full 12,827 / zstd 2,100 / tar 10,748, In-flight rewritten (2.5.8 shipped; the optimal-parse DP deferred with its measured justification), zstd_compress suite description gained the two 2.5.8 regression tests, SIZE-gate note explains the new `zstd6_rec_256K` canary and why the `zstd6_text_*` lines were blind to parse quality. |
| `issues/archived/2026-04-24-zlib-compress-2.0.2-partial-fix-2-remaining-inputs.md` | 2026-04-24 | 📦 Archive | Resolved by 2.0.3 cl-tree depth-cap fix. |
| `issues/archived/2026-04-24-zlib-compress-non-roundtrip-on-tree-shaped-input.md` | 2026-04-24 | 📦 Archive | Resolved by 2.0.2 + 2.0.3 cl-tree depth-cap fixes. |

---

## Tier 3 — Guides (`docs/guides/`)

| File | Last touched | Status | Notes |
|---|---|---|---|
| `getting-started.md` | 2026-05-23 | ✅ Fresh | **NEW 2026-05-23.** Five-minute clone-to-built path; companion to `cyrius-usage.md`. |
| `cyrius-usage.md` | 2026-06-25 | ✅ Fresh | Toolchain command reference. Destaled 2026-06-25: split-suite description genericized (was "15 files" / "two suites" / "~1.4 M assertions" — all rotted; now defers live counts to state.md). Moved here from `docs/development/` at the 2026-05-23 sweep. |

---

## Tier 4 — ADRs (`docs/adr/`)

| File | Last touched | Status | Notes |
|---|---|---|---|
| `README.md` | 2026-05-23 | ✅ Fresh | **NEW 2026-05-23.** Conventions + index + candidate-ADR list (inline-checksum decision, streaming-decoder bridge decision) for future writes. |
| `template.md` | 2026-05-23 | ✅ Fresh | **NEW 2026-05-23.** Standard 5-section ADR template. |

No filed ADRs yet. Sankoch's load-bearing decisions are currently codified in `CLAUDE.md` (zero deps, no FFI, no floats, all mutable state behind one mutex). First filed ADR will land when a new decision has competing alternatives worth recording. See [`adr/README.md`](adr/README.md) for the candidate list.

---

## Tier 5 — Architecture (`docs/architecture/`)

| File | Last touched | Status | Notes |
|---|---|---|---|
| `README.md` | 2026-05-23 | ✅ Fresh | **NEW 2026-05-23.** Conventions + a list of current invariants that would each make a good first numbered note (include-order, `[lib.core]` profile contract, mutex contract, `var buf[N]` byte sizing, bit-accumulator overpull). |

No filed notes yet. Convention: promote an invariant from inline comment / CLAUDE.md to a numbered architecture note when it burns more than ~30 minutes of debugging time for a contributor.

---

## Tier 6 — Audits (`docs/audit/`)

Periodic audit reports; per-audit timestamped (don't refresh in place — supersede with a new audit doc).

| File | Last touched | Status |
|---|---|---|
| `2026-04-15.md` | 2026-04-15 | 🔵 Dated artifact (initial audit — CRIT-01/02/03 fixed) |
| `2026-04-19.md` | 2026-04-19 | 🔵 Dated artifact (P(-1) before v1.7.0 — HIGH-01 xxHash32 fix shipped 1.6.1) |
| `2026-04-19-pre-2.0.0.md` | 2026-04-19 | 🔵 Dated artifact (P(-1) before v2.0.0 cut) |
| `2026-05-01-pre-2.2.0.md` | 2026-05-01 | 🔵 Dated artifact (P(-1) — HIGH-01 stored-block OOB + MED-01 HLIT cap + 2 LOWs fixed) |
| `2026-05-01-pre-2.3.0.md` | 2026-05-01 | 🔵 Dated artifact (P(-1) closeout for the 2.2.x line) |
| `2026-05-23-pre-2.3.0-redux.md` | 2026-05-23 | 🔵 Dated artifact (P(-1) closeout at 2.2.7 — pre-2.3.0 streaming-decomp arc) |
| `2026-06-16-pre-2.4.0.md` | 2026-06-16 | 🔵 Dated artifact (2.3.8 P(-1) closeout — zero findings; re-checked the 2.3.3–2.3.7 paths) |
| `2026-07-18-zstd-decoder-hardening.md` | 2026-07-18 | 🔵 Dated artifact (2.5.6 — 36 zstd-decoder OOB/DoS findings fixed; malformed corpus 25 SIGSEGV + 133 hang → 0/0) |
| `2026-07-19-pre-2.6.0.md` | 2026-07-19 | 🔵 Dated artifact (P(-1) — **first audit of the never-audited 2.4.x/2.5.x surface**; 1 HIGH + 13 MEDIUM + 5 LOW. **Fully remediated across 2.5.9 + 2.5.10**; INFO-E resolved negative, INFO-I1 closed. Carries a post-audit remediation-status section, updated at the 2.5.10 cut) |
| `2026-07-20-zip-container.md` | 2026-07-20 | 🔵 Dated artifact (2.6.4 P(-1) — **first audit of the never-audited 2.6.x ZIP surface**; 0 HIGH + 3 MEDIUM + 1 LOW confirmed, all fixed in 2.6.4 [i64 Zip64-bounds overflow ×4, streaming-abandon lock leak, mid-stream-add overlap, name-length truncation]. One HIGH symlink claim rebased LOW — ZIP is memory-only. `fuzz_zip.fcyr` delivered) |

Next periodic audit: **2.3.4 P(-1) closeout** for the 2.3.x line per [`development/roadmap.md`](development/roadmap.md).

---

## Tier 7 — Benchmarks (`docs/benchmarks/`)

| File | Last touched | Status |
|---|---|---|
| `2026-04-15-first-run.md` | 2026-04-15 | 🔵 Dated artifact (v1.0.0 baseline) |
| `2026-04-15-size-comparison.md` | 2026-04-15 | 🔵 Dated artifact (size baseline) |
| `2026-05-23-pre-2.3.0.md` | 2026-05-23 | 🔵 Dated artifact (pre-2.3.0 throughput baseline; SIZE-line gate reference) |
| `2026-06-16-2.3.4-crc-sliceby8.md` | 2026-06-16 | 🔵 Dated artifact (CRC-32 slice-by-8 before/after; ~2× throughput, wire-identical) |
| `2026-06-16-pre-2.4.0.md` | 2026-06-16 | 🔵 Dated artifact (2.3.8 P(-1) baseline; 43-line SIZE wire-format gate reference for 2.4.0+) |
| `2026-07-18-2.5.4-encoder-throughput.md` | 2026-07-18 | 🔵 Dated artifact (2.5.4 xz/bzip2 encoder before/after; xz ~5× on text, output-byte-identical) |
| `2026-07-18-2.5.5-zstd-encode.md` | 2026-07-18 | 🔵 Dated artifact (2.5.5 zstd encoder compression ratios vs reference `zstd -1/-3`; within +2.4% on ASCII, beats -1 on repetitive) |
| `2026-07-18-2.5.6-zstd-competitiveness.md` | 2026-07-18 | 🔵 Dated artifact (2.5.6 zstd ratios + level knob; now *beats* `zstd -1` on source/binary/repetitive, +7.5% on UTF-8 text) |
| `2026-07-18-2.5.7-parse-quality.md` | 2026-07-18 | 🔵 Dated artifact (2.5.7 repcode + adaptive FSE sequence tables; now *beats* `zstd -3` — the default — by 4–11% on real code/text/binary) |
| `2026-07-19-2.5.8-priced-parse.md` | 2026-07-19 | 🔵 Dated artifact (2.5.8 priced parse; corpus −9.9%, no regression on any of 11 fixtures, beats `zstd -3` on *every* fixture; includes the measured side-by-side that deferred the optimal-parse DP) |
| `2026-07-19-2.5.9-p1-baseline.md` | 2026-07-19 | 🔵 Dated artifact (2.5.9 P(-1) benchmark baseline; all gates green; documents the ~900× xz-encode-throughput gap vs reference `xz -6`) |
| `2026-07-20-2.7.0-baseline.md` | 2026-07-20 | 🔵 Dated artifact (2.7.0 xz-encode baseline + profiling attribution [repetitive = DP-bound, real-source = HC3-bound] + results: `nice_len` greedy shortcut → text/zeros ~290–473× faster and smaller, corpus neutral; the HC4 real-source gap left for 2.7.1) |

Pattern: every P(-1) closeout captures a new bench reference. The wire-format gate (43 SIZE lines) must remain byte-for-byte stable across patch / minor releases.

---

## Tier 8 — Sources (`docs/sources/`)

| File | Last touched | Status | Notes |
|---|---|---|---|
| `compression.md` | 2026-04-12 | 🔵 Evergreen | RFC + spec citations (RFC 1951 / 1950 / 1952 / LZ4 block/frame / xxHash32 spec). Touch only when a referenced spec moves or a new algorithm is added. |

---

## Refresh procedure

When docs are touched:

1. Find the affected row in the relevant tier table.
2. Update **Last touched** to the new date.
3. Update **Status** if the bucket changed.
4. Update **Notes** if the next step changed.
5. If a doc moved or was archived, update its row.
6. Re-anchor "Last refresh" date in the header.

When the bucket counts at the top drift by more than ~2 in any cell, refresh the at-a-glance table.

This file's refresh cadence is **opportunistic** (touched when other docs are touched), not periodic.

---

## What this file is NOT

- Not a substitute for [`development/state.md`](development/state.md) (which holds live version / size / test totals).
- Not a CHANGELOG (which records what shipped, not what's stale).
- Not a TODO list (open work for the project lives in [`development/roadmap.md`](development/roadmap.md)).
- Not a per-doc review log (this is the ledger of where each doc stands, not the per-doc reasoning).

---

*Initial scaffold: 2026-05-23 (v2.3.0 cut — first-party-standards conformance sweep). Refresh in place when docs are touched.*
