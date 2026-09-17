# 003 — `_sankoch_reset_tables` is per bundle, and a module reset must be registered in every bundle that carries the module

This is a constraint that no compiler enforces. `src/runtime.cyr` is in every bundle except `core`,
and its arena guard calls `_sankoch_reset_tables()`. That function is **not** defined in
`runtime.cyr`. Each bundle defines its own copy, over exactly the modules the bundle contains.
2.7.10–2.7.15 defined it only in `lib.cyr`, so no consumer could link a program that called into any
codec profile.

## The shape (2.8.0)

| Bundle | Defines `_sankoch_reset_tables` in | Calls |
|---|---|---|
| `[lib]` (`dist/sankoch.cyr`) | `src/lib.cyr` | every module reset |
| `[lib.<name>]` | `src/reset_<name>.cyr`, listed last, after `runtime.cyr` | only the resets of modules in that profile |
| `[lib.core]` | — (no `runtime.cyr`, no alloc) | — |

A module that memoizes an arena pointer, or a flag that gates one, defines
`_<module>_reset_tables` at the end of its own file. That function zeroes exactly that module's
globals. The modules that do this today are checksum, huffman, lz77, lz4, deflate, xz, bzip2, zstd
and brotli.

## The rule

Adding a lazy global means changing **four** places:

1. Zero it in the module's own `_<module>_reset_tables`.
2. If the module is new, call its reset from `lib.cyr`'s `_sankoch_reset_tables`...
3. ...and from `src/reset_<name>.cyr` of **every** profile that lists the module.
4. Add it to the inventory cell in `tests/tcyr/arena_reset.tcyr`
   (`test_reset_tables_zeroes_every_memoized_pointer`).

A public entry that memoizes state and is reachable **without** `_sankoch_lock` calls
`_sankoch_arena_guard()` itself (`crc32_init_table`, `crc64_init_table`, `crc32_bzip2_init_table`,
`lz77_init`, `huff_build_*`).

## What enforces what

- **`scripts/profile-link-gate.sh`** (CI and release) runs on every profile parsed from `cyrius.cyml`:
  - *registration*: the resets a bundle defines equal the resets its dispatcher calls;
  - *link*: a probe calls real entries, and any undefined function fails;
  - *run*: known vectors decode, then decode again after `alloc_reset()` with the whole old arena
    handed to a victim buffer, which must stay intact;
  - *AGNOS*: a lock-only probe built with `--agnos` under DCE must keep `_sankoch_arena_guard` and
    `_sankoch_reset_tables` alive.
- **The gate cannot prove a module reset is complete.** A probe only notices a surviving pointer
  that its own calls write through: of 171 single-global omissions, 41 fail the gate. The
  per-global net is step 4.
- **The stranded-canary predicate is pinned in both directions** by `arena_reset.tcyr`:
  - a reset is detected when the canary lies outside the first chunk;
  - no reset is reported in steady state when the bump pointer is outside the first chunk too.

## One sankoch bundle per program

Profile bundles are closures, not layers. Two of them in one program, say `sankoch-zlib.cyr` +
`sankoch-zstd.cyr`, each carry `runtime.cyr` and their own dispatcher:

- cycc accepts duplicate `fn`s with a warning only;
- a duplicate `var` is a **separate** global;
- a call binds to whichever definition comes first.

So one bundle's guard runs the other bundle's dispatcher. Measured under 6.6.4: zlib+zstd segfaults
after a reset, in either include order. A program that needs two codecs uses the smallest profile
that carries both. `[lib.woff]` exists for exactly that (zlib + Brotli, rekha), and
`[lib.tar]`, `[lib.zipall]` or the full bundle serve larger mixes.

## Why not `#ifdef` markers

`#define SANKOCH_HAS_<MODULE>` plus guarded calls in one shared dispatcher does work, in both the
include chain and a distlib concatenation. But cycc has **one 16-entry flag table per compile**,
shared with the consumer, never deduplicated, and with no `#undef`. Three entries are compiler
predefines, and `lib/sigil.cyr` alone takes 7. Eight sankoch markers would break every consumer
that also pulls sigil. Upstream: `cyrius/docs/development/issues/2026-09-16-sankoch-preprocessor-flag-table-16-entries-no-dedup.md`.

## See also

- [002](002-lazy-globals-and-alloc-reset.md): why every lazy global is a memory-safety liability under `alloc_reset()`.
- `src/runtime.cyr`: the guard, the canary, and the rule at the point of use.
- [Archived issue](../development/issues/archived/2026-09-15-profile-bundles-call-sankoch-reset-tables-outside-their-closure.md) and CHANGELOG 2.8.0.
