---
name: Sankoch Documentation Health
description: Living state of doc currency in the sankoch repo — fresh / stale / archived / open-question. Refreshed in place when docs are touched.
type: state
---

# Documentation Health — sankoch

> **Last refresh**: 2026-09-16 (**2.8.0 cut — Brotli decoder + per-profile arena-reset fix.** Touched: CHANGELOG, VERSION, README, CLAUDE.md, SECURITY, state, roadmap (ladder re-cut: 2.8.1 Brotli encoder → 2.8.2 SIMD CRC-32 → 2.8.3 GPU texture → P(-1)), guides/cyrius-usage (stale 6.4.68 pin + old fmt semantics removed), sources/compression (+RFC 7932) + new `sources/brotli/`. New: ADR **0001** (the first ADR), architecture **003** (per-profile reset dispatch) + **004** (NUL-literal rule), 002 updated. Also new: audit `2026-09-16-2.8.0-brotli-and-reset.md` and benchmark `2026-09-16-2.8.0-brotli.md`. Archived: the profile-link issue (RESOLVED 2.8.0) and the Brotli proposal, in the new `proposals/archived/` (SHIPPED 2.8.0). Previous refresh narratives are in git history.)
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
| `README.md` | 2026-09-16 | ✅ Fresh | **2.8.0**: Brotli decode row + API section, the 12-profile list, one bundle per program, architecture rows for `brotli*.cyr` / `reset_<profile>.cyr`. |
| `CHANGELOG.md` | 2026-09-16 | ✅ Fresh | **Source of truth per CLAUDE.md.** Through `[2.8.0] — 2026-09-16`. |
| `CLAUDE.md` | 2026-09-16 | ✅ Fresh | **2.8.0**: Goal + Brotli decode; architecture tree + `brotli.cyr` / generated `brotli_dict.cyr` / `reset_<profile>.cyr` / new scripts; Quick Start + brotli/woff distlib, link gate, brotli smoke; Key Constraints + reset registration, one bundle per program, NUL-literal rule; CI + link / dictionary / NUL gates. |
| `CONTRIBUTING.md` | 2026-05-23 | ✅ Fresh | Standards link fixed (same path correction). |
| `SECURITY.md` | 2026-09-16 | ✅ Fresh | **2.8.0**: 2.8.x supported; 2026-09-16 review added to audit history. |
| `CODE_OF_CONDUCT.md` | 2026-05-01 | 🔵 Evergreen | Standard text; touch only when the project's CoC policy changes. |
| `LICENSE` | 2026-05-01 | 🔵 Evergreen | GPL-3.0-only. |
| `VERSION` | 2026-09-16 | ✅ Fresh | `2.8.0`. Single source of truth per the standards. |
| `cyrius.cyml` | 2026-09-16 | ✅ Fresh | Toolchain pin `6.6.4`; `[lib.brotli]` + `[lib.woff]`; every alloc-bearing profile ends `runtime.cyr, reset_<name>.cyr`. |
| `.gitignore` | 2026-09-16 | ✅ Fresh | `/dist/` contents ignored with all 12 committed bundles re-included (+ brotli, woff). |

---

## Tier 2 — Operational / Development (`docs/development/`)

| File | Last touched | Status | Notes |
|---|---|---|---|
| `roadmap.md` | 2026-09-16 | ✅ Fresh | **2.8.0 cut**: status v2.8.0; 📌 notes and the Brotli backlog item removed; ladder 2.8.1 Brotli encoder → 2.8.2 SIMD CRC-32 → 2.8.3 GPU texture → P(-1) closeout (scope + Brotli decoder + reset seam); File Summary / distlib re-counted. |
| `state.md` | 2026-09-16 | ✅ Fresh | **Current at v2.8.0** (source 18,503 / 33 files, 12 bundles, 27 suites / 4,500,520, fuzz 12,722 across 7 files; consumers + rekha). |
| `issues/archived/2026-08-23-bote-rfc7692-needs-public-sync-flush.md` | 2026-08-23 | 📦 Archive | Resolved by 2.7.9 (`deflate_enc_flush` + `deflate_enc_reset_context` + `deflate_dec_produced`). The resolution log records the ratio finding the fix surfaced — always-dynamic blocks made the newly-exposed flush +64 % over reference zlib until the chooser landed — and repeats the filer's own caveat that cyrius's `ws_server` handshake gap still blocks bote. |
| `issues/archived/2026-09-15-profile-bundles-call-sankoch-reset-tables-outside-their-closure.md` | 2026-09-16 | 📦 Archive | Resolved by 2.8.0 (per-profile reset dispatch + link gate); Resolution section records what the filing missed. |
| `proposals/archived/2026-09-15-brotli-decoder-for-woff2.md` | 2026-09-16 | 📦 Archive | Shipped in 2.8.0; What-shipped section maps needs 1–5 + deviations (`[lib.woff]`, full-bundle placement, trailing policy; encode → 2.8.1). |
| `issues/archived/2026-04-24-zlib-compress-2.0.2-partial-fix-2-remaining-inputs.md` | 2026-04-24 | 📦 Archive | Resolved by 2.0.3 cl-tree depth-cap fix. |
| `issues/archived/2026-04-24-zlib-compress-non-roundtrip-on-tree-shaped-input.md` | 2026-04-24 | 📦 Archive | Resolved by 2.0.2 + 2.0.3 cl-tree depth-cap fixes. |

---

## Tier 3 — Guides (`docs/guides/`)

| File | Last touched | Status | Notes |
|---|---|---|---|
| `getting-started.md` | 2026-05-23 | ✅ Fresh | **NEW 2026-05-23.** Five-minute clone-to-built path; companion to `cyrius-usage.md`. |
| `cyrius-usage.md` | 2026-09-16 | ✅ Fresh | **2.8.0**: brotli/woff profiles, `--list-profiles`, one bundle per program, link / NUL / dictionary gates; stale 6.4.68 pin and pre-6.5.35 fmt semantics replaced (per-file `--check`, exit code only). |

---

## Tier 4 — ADRs (`docs/adr/`)

| File | Last touched | Status | Notes |
|---|---|---|---|
| `README.md` | 2026-05-23 | ✅ Fresh | **NEW 2026-05-23.** Conventions + index + candidate-ADR list (inline-checksum decision, streaming-decoder bridge decision) for future writes. |
| `template.md` | 2026-05-23 | ✅ Fresh | **NEW 2026-05-23.** Standard 5-section ADR template. |
| `0001-brotli-decoder-placement.md` | 2026-09-16 | ✅ Fresh | **NEW 2.8.0 — the first ADR.** Brotli decode in `[lib]` + `[lib.brotli]` + `[lib.woff]`, dictionary as a generated literal, trailing bytes rejected, measured DCE cost. |

One filed ADR (`0001`, 2.8.0). Older load-bearing decisions stay codified in `CLAUDE.md` and the audit history.

---

## Tier 5 — Architecture (`docs/architecture/`)

| File | Last touched | Status | Notes |
|---|---|---|---|
| `README.md` | 2026-07-21 | ✅ Fresh | **NEW 2026-05-23.** Conventions + a list of candidate invariants for future notes (include-order, `[lib.core]` profile contract, mutex contract, `var buf[N]` byte sizing, bit-accumulator overpull). **2026-07-21**: now indexes the first filed note (001). |
| `001-zstd-optimal-chain-cutoff.md` | 2026-07-21 | 🔵 Dated artifact | **NEW 2026-07-21 (2.7.5) — the first filed architecture note.** Why the L9 DP optimal parser's hash-chain walk (`_zo_getmatches`) needs a saturation cutoff: bail after `_zo_chain_cut` (128) consecutive non-improving candidates, but only once `best >= _zo_chain_gate` (32) — the length gate separates saturated duplicates (records) from useful depth (text / object code, which a gate-less cutoff regresses 4.5 %/10–30×). |
| `002-lazy-globals-and-alloc-reset.md` | 2026-09-16 | ✅ Fresh | 2.7.10 note; **2.8.0** updated where the guard lives (every target, unlocked builders, stranded canary, failed arm) and points the registration rule at 003. |
| `003-per-profile-reset-dispatch.md` | 2026-09-16 | ✅ Fresh | **NEW 2.8.0.** Per-bundle `_sankoch_reset_tables`, the four-place registration rule, one bundle per program, why not `#ifdef`. |
| `004-string-literal-nul-rule.md` | 2026-09-16 | ✅ Fresh | **NEW 2.8.0.** No NUL in string literals (cycc interning hazard); `brotli_dict.cyr` exempt; `scripts/nul-literal-gate.py`. |

Four filed notes (`001`–`004`). Convention: promote an invariant from inline comment / CLAUDE.md to a numbered architecture note when it burns more than ~30 minutes of debugging time for a contributor.

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
| `2026-09-16-2.8.0-brotli-and-reset.md` | 2026-09-16 | 🔵 Dated artifact (2.8.0 pre-release review of the Brotli decoder + reset seam; 0 H · 4 M · 15 L · 4 I, all fixed but the upstream-doc R-22; libbrotlidec mutation differential not run) |

Next periodic audit: **the 2.8.x-closeout P(-1) pass** — scheduled at the **end of the 2.8.x
line** (before the next minor opens), per the 2026-07-21 roadmap decision. 2.8.x opens straight
into the feature (no P(-1) lead), so the **un-audited 2.7.x encoder surface** — BT4 `son[]`, the
4 MiB frame-global hash chain, the DP-optimal arrays, and the window / saturation-cutoff math —
plus the 2.8.x additions (the Brotli decoder + encoder, the runtime reset seam, the hand-assembled
`PCLMULQDQ` fold, the GPU block encoder) are audited together there. It ships as its own release, as 2.6.4 did. Last audit: **2.8.0 pre-release review** ([`2026-09-16-2.8.0-brotli-and-reset.md`](audit/2026-09-16-2.8.0-brotli-and-reset.md)); last full P(-1): **2.6.4** (ZIP
surface, [`2026-07-20-zip-container.md`](audit/2026-07-20-zip-container.md)).

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
| `2026-08-23-2.7.9-sync-flush.md` | 2026-08-23 | 🔵 Dated artifact (2.7.9 — RFC 7692 sync-flush framing vs reference zlib at three message sizes, before/after the fixed-vs-dynamic chooser: +64 % → +0.1 %; the 43-line batch SIZE control [3 improved, 40 unchanged] and the ~3 % small-block throughput cost accepted to buy it) |
| `2026-07-19-2.5.8-priced-parse.md` | 2026-07-19 | 🔵 Dated artifact (2.5.8 priced parse; corpus −9.9%, no regression on any of 11 fixtures, beats `zstd -3` on *every* fixture; includes the measured side-by-side that deferred the optimal-parse DP) |
| `2026-07-19-2.5.9-p1-baseline.md` | 2026-07-19 | 🔵 Dated artifact (2.5.9 P(-1) benchmark baseline; all gates green; documents the ~900× xz-encode-throughput gap vs reference `xz -6`) |
| `2026-07-20-2.7.0-baseline.md` | 2026-07-20 | 🔵 Dated artifact (2.7.0 xz-encode baseline + profiling attribution [repetitive = DP-bound, real-source = HC3-bound] + 2.7.0 results [`nice_len` greedy shortcut → text/zeros ~290–473× faster] + **2.7.1 results** [BT4 binary-tree finder → real-source corpus +21 % and better ratio, 7.1× → 5.8× vs `xz -6`, repetitive neutral; the HC4 detour recorded] + **2.7.2 results** [window 32 KB → 256 KB → corpus ratio gap to `xz -6` +7 % → +0.2 %; full window sweep 64K–1M vs ratio/memory]) |
| `2026-07-21-2.7.3-zstd-optimal.md` | 2026-07-21 | 🔵 Dated artifact (2.7.3 zstd DP optimal parse at levels 7–9; per-block best-of → real-source L9 −4.9 %, records best-of-neutral; correctness detail — 40 adversarial files + 800 round-trips vs reference `zstd -d`, +500 fuzz + L9 smoke) |
| `2026-07-21-2.7.4-zstd-window.md` | 2026-07-21 | 🔵 Dated artifact (2.7.4 zstd cross-block match window; the block/parse restructure explained + a `_ze_maxwin` sweep 256 KiB–4 MiB on records/bigrec/src → 512 KiB default (4 MiB `_ze_prev`); sankoch L9 beats `zstd -19` on record data (record −44.7 %) and on a 4.3 MB record fixture; single-block byte-identical) |
| `2026-09-16-2.8.0-brotli.md` | 2026-09-16 | 🔵 Dated artifact (2.8.0 Brotli decode throughput baseline; 47 SIZE rows unchanged) |

Pattern: every P(-1) closeout captures a new bench reference. The wire-format gate (43 SIZE lines) must remain byte-for-byte stable across patch / minor releases.

---

## Tier 8 — Sources (`docs/sources/`)

| File | Last touched | Status | Notes |
|---|---|---|---|
| `compression.md` | 2026-09-16 | 🔵 Evergreen | RFC + spec citations; **2.8.0** + RFC 7932, google/brotli v1.2.0, zlib `enough.c`. Brotli source data (dictionary, tables, extractor) lives in `sources/brotli/`. |

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
