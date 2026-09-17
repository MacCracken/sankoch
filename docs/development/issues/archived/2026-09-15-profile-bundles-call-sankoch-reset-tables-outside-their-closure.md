# Every codec profile bundle calls `_sankoch_reset_tables`, which only the full bundle defines — a consumer that calls the profile is refused at link

**Status:** ✅ **RESOLVED in 2.8.0** (2026-09-16) — per-module resets + per-profile dispatchers + a
link gate in CI and release. The filing understated the defect; see *Resolution*.
**Original status:** 🟡 OPEN — MEASURED against the committed `dist/` of sankoch **2.7.15**.
**Filed:** 2026-09-15, by **rekha** (adopting `[lib.zlib]` for WOFF 1.0).
**Affects:** `dist/sankoch-{zlib,gzip,xz,bzip2,zstd,tar,zip,zipall}.cyr` — every profile except
`core` — since **2.7.10** (commit `89771bb`, "repairs to alloc_reset").
**Severity:** **High for profile consumers.** The per-codec profiles are the documented way to pull one
codec without the rest (sit's and thoth's zlib path, the `max 1024 initialised globals` budget). Today a
program that actually CALLS into any of them cannot be built.

## What happens

2.7.10's arena guard in `src/runtime.cyr` calls `_sankoch_reset_tables()` when it detects an
`alloc_reset()` under a memoized pointer:

```cyr
fn _sankoch_arena_guard(): i64 {
    ...
    _sankoch_mtx = 0;
    _sankoch_reset_tables();          # src/runtime.cyr:63
```

`runtime.cyr` is in every codec profile's `modules` list; `_sankoch_reset_tables` is defined in
`src/lib.cyr` (:75), which is in none of them. So each profile bundle carries the call and not the
function:

| bundle | calls `_sankoch_reset_tables()` | defines it |
|---|---:|---:|
| sankoch-zlib / gzip / xz / bzip2 / zstd / tar / zip / zipall | 1 each | 0 |
| sankoch-core | 0 | 0 |
| sankoch (full) | — | 1 |

## MEASURED (cyrius 6.6.4, committed 2.7.15 bundles copied into a scratch `lib/`)

A probe including `string fmt alloc vec assert sync` and one profile bundle:

- `main` that calls nothing from the bundle — every one of the 8 profiles builds `OK`, but prints
  `warning: undefined function '_sankoch_reset_tables'`.
- `main` that calls `zlib_decompress_capped(...)` through `dist/sankoch-zlib.cyr`:

  ```
  warning: undefined function '_sankoch_reset_tables'
  warning: undefined function '_sankoch_reset_tables' (call site may be unreachable)
  error: refusing to emit binary with 1 reachable undefined function(s) (pass --allow-undef to downgrade)
  ```

- The full `dist/sankoch.cyr` and `dist/sankoch-core.cyr` build clean.

⚠ CI's profile gate is `cyrius distlib <profile>` + a byte diff against the committed copy — it proves
the bundles are CURRENT, not that they LINK, which is how this shipped in every release since 2.7.10.
(And the "undefined function in dead code → warning + binary" mode means a consumer whose only use is
behind a branch its build never reaches gets a green build that faults when the branch runs.)

## Why the obvious move is not enough

Moving `_sankoch_reset_tables` into `runtime.cyr` would not link either: its body zeroes the lazy
globals of EVERY codec (`_lz4_htab`, the `_huff_*` / `_deflate_*` / `_dyn_*` tables, …), and most
profiles do not contain most of those globals.

## Suggested fix (sankoch's call)

- Give each codec module its own reset (`_deflate_reset_tables`, `_lz4_reset_tables`, …) next to the
  globals it owns, and have the profile's reset call exactly the ones in its closure — e.g. a small
  per-profile `src/reset_<profile>.cyr`, or `#ifdef`-guarded calls keyed on module markers — with the
  full bundle's `_sankoch_reset_tables` calling all of them (the 2.3.7 fault-injection suite keeps
  its entry point).
- Add a LINK gate beside the byte gate: for each profile, build a probe that calls one public entry of
  the profile through a reachable path, and fail on `undefined function` / `refusing to emit`.

## What rekha does meanwhile

rekha 0.4.x's WOFF 1.0 reader builds its tests against the full `lib/sankoch.cyr` the toolchain pin
ships (2.7.15, which has `zlib_decompress_capped`), and keeps WOFF in its own `[lib.woff]` profile so
rekha's base bundle never requires sankoch. When the zlib profile links again, rekha documents it as
the lean way for a WOFF consumer to satisfy the dependency.

## Resolution (2.8.0)

**What shipped.**

- Every memoizing module defines `_<module>_reset_tables` next to the globals it owns (checksum,
  huffman, lz77, lz4, deflate, xz, bzip2, zstd, brotli).
- `src/lib.cyr`'s `_sankoch_reset_tables` calls all of them. Each alloc-bearing profile lists a
  `src/reset_<profile>.cyr` that calls exactly the resets in its closure.
- `scripts/profile-link-gate.sh` runs in CI and release, for every profile it parses from `cyrius.cyml`:
  - registration: module resets defined vs called;
  - a reachable-call link probe;
  - a run of reference-CLI vectors, repeated after `alloc_reset()` with the old arena handed to a
    victim buffer;
  - `--agnos` DCE reachability of the reset from `_sankoch_lock` alone.
- Rule and rationale: [`docs/architecture/003-per-profile-reset-dispatch.md`](../../../architecture/003-per-profile-reset-dispatch.md).

**What the filing missed.** It saw only the link error. The reset itself was incomplete even in the full
bundle, and it was measured once the link worked:

- **Memoized globals the 2.7.10 reset never zeroed.** Caller memory was overwritten after `alloc_reset()`
  on 2.7.15 sources: xz BT4 **229,370 words**, zstd L9 **712**, zstd L6 **14**.
- **Public builders that consumers call without the lock** had no guard: `crc64_init_table`,
  `crc32_bzip2_init_table`, `lz77_init`, the `huff_build_*` family. They now call
  `_sankoch_arena_guard`, and the lz77 and huff builders overwrote 524,288 and 8,701 caller bytes.
- **A stranded canary.** A caller that filled the first arena chunk before sankoch's first call got a
  canary that `alloc_reset()` never zeroes (475,882 caller bytes overwritten). Fixed by
  `_sankoch_canary_stranded`.
- **AGNOS.** The guard sat after `_sankoch_lock`'s AGNOS early return, so on AGNOS the reset was dead
  code. It now runs first on every target.
- The 2.8.0 review found two more gaps, both fixed before the cut:
  - the gate's first AGNOS check was defeated by those new direct guard calls;
  - a failed 8-byte canary alloc silently disarmed detection.

**Why not `#ifdef` module markers.** They work in both the include chain and a distlib concatenation
(probed under 6.6.4). But cycc has one 16-entry `#define` table per compile, shared with the consumer,
and 3 entries are compiler predefines. `lib/sigil.cyr` alone spends 7, so eight sankoch markers would
break every consumer that also pulls sigil. Upstream issue
`cyrius/docs/development/issues/2026-09-16-sankoch-preprocessor-flag-table-16-entries-no-dedup.md`.
