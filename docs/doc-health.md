---
name: Sankoch Documentation Health
description: Living state of doc currency in the sankoch repo — fresh / stale / archived / open-question. Refreshed in place when docs are touched.
type: state
---

# Documentation Health — sankoch

> **Last refresh**: 2026-07-18 (structural-figure re-count pass, following the same-day 2.5.2 cut — state.md Source + Dist bundles and roadmap.md File Summary re-counted for the 19-module / 8-bundle tree; SECURITY.md next-audit pointer genericized) | **Refresh cadence**: opportunistic — update the affected row whenever a doc is touched.
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
| `README.md` | 2026-06-25 | ✅ Fresh | Current through 2.4.6: ratio-cap API subsection (batch `*_with_ratio_cap` + streaming `*_dec_init_capped`); Architecture table rows note ratio-cap on deflate/zlib/gzip + the agnos lock no-op on lib. Defers all volatile line / test / assertion / distlib counts to state.md (no inlined figures). |
| `CHANGELOG.md` | 2026-07-18 | ✅ Fresh | **Source of truth per CLAUDE.md.** Through `[2.5.2] — 2026-07-18` (toolchain pin refresh → 6.4.66; no source/API change); `[2.5.1]` per-codec distlib profiles; `[2.5.0]` sovereign zstd + tar cursor + pin → 6.4.43. Empty `[Unreleased]` header at top per Keep-a-Changelog convention. |
| `CLAUDE.md` | 2026-05-23 | ✅ Fresh | **Restructured 2026-05-23**: volatile state extracted to `docs/development/state.md`; durable rules retained. Broken standards link fixed (`applications/` → `first-party/`). Stale `cc5` refs updated. Now matches example_claude.md shape. |
| `CONTRIBUTING.md` | 2026-05-23 | ✅ Fresh | Standards link fixed (same path correction). |
| `SECURITY.md` | 2026-07-18 | ✅ Fresh | Supported Versions table at 2.5.x. "Next periodic audit" pointer genericized to the pre-next-minor P(-1) closeout (was a stale/dangling "2.4.x decode-only xz/bzip2 arc" ref — xz/bzip2 encode had since shipped @2.4.1/2.4.3 and roadmap no longer listed that item). |
| `CODE_OF_CONDUCT.md` | 2026-05-01 | 🔵 Evergreen | Standard text; touch only when the project's CoC policy changes. |
| `LICENSE` | 2026-05-01 | 🔵 Evergreen | GPL-3.0-only. |
| `VERSION` | 2026-07-18 | ✅ Fresh | `2.5.2`. Single source of truth per the standards. |
| `cyrius.cyml` | 2026-07-18 | ✅ Fresh | Toolchain pin `cyrius = "6.4.66"` (bumped from 6.4.43 in 2.5.2; `cyrius deps` re-resolved, all gates clean on the new toolchain). |
| `.gitignore` | 2026-05-23 | ✅ Fresh | Updated 2026-05-23 to match the first-party standard: `/dist/`, `*.tar.gz`, `cyrius-*.tar.gz`, `SHA256SUMS`, `!lib/k*.cyr` exception, `.env*` / `*.pem` / `*.key`. |

---

## Tier 2 — Operational / Development (`docs/development/`)

| File | Last touched | Status | Notes |
|---|---|---|---|
| `roadmap.md` | 2026-07-18 | ✅ Fresh | Status header (→ Stable v2.5.2) + Dependencies pin at 6.4.66. **File Summary re-counted** for the 19-module tree — added `runtime.cyr` (73) / `zstd.cyr` (729) / `tar.cyr` (513) rows, corrected `lib.cyr` 282→239 + `types.cyr` 41→42 + core-total 316→317, total 10,078→11,351; Distlib paragraph refreshed to the current eight bundles (full 11,394 / core 331 + six lean profiles). Anchor `#file-summary-at-230` kept stable. |
| `state.md` | 2026-07-18 | ✅ Fresh | Version/pin/date fields at 2.5.2 (pin 6.4.66). **Source + Dist bundles rows re-counted** — Source 10,078/16-module → 11,351/19-module; Dist table refreshed (full 11,394 / core 331 / zlib 4,924) + five per-codec profile rows added (gzip 5,077 / xz 2,697 / bzip2 2,014 / zstd 782 / tar 9,308), regeneration note corrected to all eight profiles. Clears the pre-2.4.7 stale-figure debt flagged since 2.5.0. Test/fuzz totals unchanged (234 fns / 4,483,834 asserts; 3,929 fuzz). |
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
