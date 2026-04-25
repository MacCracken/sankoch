# Sankoch — Claude Code Instructions

## Project Identity

**Sankoch** (Sanskrit: संकोच — contraction, compression) — Lossless
compression library for AGNOS.

- **Type**: Flat library (include-based) + distlib bundle
- **License**: GPL-3.0-only
- **Language**: Cyrius (sovereign systems language, compiled by cc5)
- **Version**: SemVer, version file at `VERSION`
- **Status**: 2.1.0 (stable) — shipping as `lib/sankoch.cyr` in Cyrius stdlib via the cyrius 5.6.x toolchain releases
- **Genesis repo**: [agnosticos](https://github.com/MacCracken/agnosticos)
- **Standards**: [First-Party Standards](https://github.com/MacCracken/agnosticos/blob/main/docs/development/applications/first-party-standards.md)

## Goal

Own lossless compression. One library provides LZ4, DEFLATE, zlib, and
gzip de/compression for everything downstream — ark packages, AGNOS
initrd, git object reads, shravan/tarang container formats. Zero
external dependencies, zero C FFI, zero shell-outs to `gzip`.

## Current State

- **Source**: 4574 lines across 12 domain modules (`src/*.cyr`)
- **Tests**: 1,028,625 (sankoch.tcyr) + 346,583 (git_object.tcyr) =
  1,375,208 assertions across 2 tcyr suites (most are per-byte round-trip
  checks across streaming tests + the 2.0.2 / 2.0.3 cl-tree regression
  fixtures); 1,649 fuzz iterations across 6 harnesses
  (lz4 / deflate batch + 4 streaming + 2 tree-shape/skewed-freq); 45+ benchmarks
- **Dist bundle**: `dist/sankoch.cyr` at ~4,597 lines, zero deps
- **Stable**: 2.1.0 — the v2.0.0 track feature set is complete:
  LZ4 block + multi-block frame with reference-`lz4`-CLI-compatible
  xxHash32; DEFLATE with adaptive dynamic-block splitting; zlib incl.
  FDICT; gzip incl. concatenated members; true incremental streaming
  across all four formats (DEFLATE, zlib, gzip, LZ4F) via
  `*_enc_init/write/finish` APIs; public-API thread safety via the
  two-tier mutex split
- **Toolchain**: Cyrius 5.6.42 (`cyrius.cyml: cyrius = "5.6.42"`)
- **Integration**: will be consumed by future git impl, ark, AGNOS
  kernel (initrd), shravan, tarang
- **Distribution**: 2.0.2 landed in Cyrius 5.6.34's stdlib; 2.0.3
  picked up in Cyrius 5.6.35; 2.1.0 ships as `lib/sankoch.cyr` in
  the next Cyrius 5.6.x release that picks up this tag. Consumers
  import it via `include "lib/sankoch.cyr"` — no separate dependency
  declaration needed in their `cyrius.cyml`.

## Consumers

| Consumer             | Uses             | Why                                     |
|----------------------|------------------|-----------------------------------------|
| Future git impl      | DEFLATE, zlib    | Git objects are zlib-compressed         |
| ark                  | LZ4 or DEFLATE   | Package compression                     |
| AGNOS kernel         | LZ4              | initrd, snapshots                       |
| shravan / tarang     | DEFLATE, gzip    | Embedded compressed streams             |
| Any crate            | All              | Replaces zlib FFI / shelling to gzip    |

## Dependencies

- **Cyrius stdlib** — `syscalls`, `string`, `alloc`, `fmt`, `vec`,
  `fnptr`, `thread`, `assert` (ships with Cyrius >= 5.6.42)

No external deps. No FFI. No libc. Checksums (Adler-32, CRC-32,
xxHash32) are inline — no sigil dependency for 30-line primitives that
live inside the compression format specs anyway.

## Quick Start

See [`docs/development/cyrius-usage.md`](docs/development/cyrius-usage.md)
for the full command reference.

At a glance:

```bash
cyrius deps                              # resolve stdlib into lib/
cyrius build src/lib.cyr build/sankoch   # compile-check (library — binary is trivial)
cyrius test tests/tcyr/sankoch.tcyr      # 1,028,625 assertions
cyrius test tests/tcyr/git_object.tcyr   # 346,583 assertions
cyrius bench tests/bcyr/sankoch.bcyr     # throughput + compressed-size table
cyrius distlib                           # → dist/sankoch.cyr
```

## Architecture

```
src/
  lib.cyr          — Include chain (stdlib + domain modules) + public API + _sankoch_mtx
  types.cyr        — Enums: formats (incl. FORMAT_LZ4F), errors, limits
  checksum.cyr     — Adler-32 / CRC-32 / xxHash32, batch + incremental (_init/_update/_final)
  bitreader.cyr    — LSB-first bit-stream reader (DEFLATE)
  bitwriter.cyr    — LSB-first bit-stream writer (DEFLATE)
  huffman.cyr      — Huffman build/decode, fixed trees, optimal trees
  lz77.cyr         — Sliding window match-finder + lz77_rebase (for streaming slide)
  lz4.cyr          — LZ4 block + frame de/compress + lz4f_enc_*
  deflate.cyr      — DEFLATE de/compress, adaptive blocks, dict, deflate_enc_* streaming
  zlib.cyr         — zlib wrapper + FDICT + zlib_enc_*
  gzip.cyr         — gzip wrapper + concatenated members + gzip_enc_*
  stream.cyr       — Streaming dispatch (stream_compress_init / write / finish → *_enc_*)
tests/tcyr/        — test suites (sankoch.tcyr, git_object.tcyr)
tests/bcyr/        — benchmarks (sankoch.bcyr)
fuzz/              — fuzz harnesses (lz4, deflate — both wired into CI)
dist/
  sankoch.cyr      — distlib bundle (`cyrius distlib`); ships as lib/sankoch.cyr in Cyrius stdlib
cyrius.cyml        — package manifest (toolchain pin, [deps], [lib] modules)
```

**Include order matters.** `src/lib.cyr` declares the full chain:
stdlib first, then domain modules in dependency order. Stdlib includes
live **only** in `lib.cyr` — never in individual domain modules.
Domain modules are flat: zero transitive includes, which is what makes
`cyrius distlib` (strip-include concatenation) produce a compile-clean
bundle.

## Key Constraints

- **Zero external deps.** Every bit is in this tree. Adler-32 /
  CRC-32 are inline — pulling sigil for 30-line functions used in the
  inner loop is wrong.
- **All mutable state behind one mutex.** The compression globals
  (bitreader, bitwriter, hash tables, Huffman tables, symbol buffers)
  serialize on `_sankoch_lock()` / `_sankoch_unlock()`. No per-call
  allocation on the hot path.
- **Integer math only, i64 or fixed-size strings.**
- **No floating point** — anywhere.
- **Stack arrays: `var buf[N]` is N bytes, not N×8.** Use `&buf` for
  `load*`/`store*` addresses. (See
  [memory/reference_stack_array_addr.md](../../.claude/projects/-home-macro-Repos-sankoch/memory/reference_stack_array_addr.md).)
- **Bundle gate.** CI regenerates `dist/sankoch.cyr` via
  `cyrius distlib` and fails if it drifts from the committed file.
  Don't hand-edit the bundle.

## Development Process

### P(-1): Scaffold Hardening (before any new features)

0. Read CHANGELOG + roadmap — know what was intended
1. Cleanliness: `cyrius build` (0 warnings for library path),
   `cyrius lint` (0 warnings), `cyrius fmt --check` diff-clean,
   `cyrius vet src/lib.cyr` clean
2. Test sweep: both tcyr suites green, fuzz harnesses green
3. Benchmark baseline: `cyrius bench tests/bcyr/sankoch.bcyr`
4. Internal deep review — gaps, optimizations, correctness
5. External research — RFC errata / zlib / lz4 reference changes
6. Security audit — `docs/audit/YYYY-MM-DD.md`
7. Additional tests / benchmarks from findings
8. Post-review benchmarks — prove the wins
9. Documentation audit — CLAUDE.md, roadmap, CHANGELOG
10. Repeat if heavy

### Work Loop (continuous)

1. Work phase — implement algorithm, add tests/benchmarks
2. Build: `cyrius build src/lib.cyr build/sankoch`
3. Test: `cyrius test tests/tcyr/sankoch.tcyr` — 0 failures
4. Benchmark: throughput (MB/s) and ratio for changes in the hot path
5. Audit: verify against spec (RFC 1951, LZ4 block format)
6. Documentation — CHANGELOG, roadmap
7. Version check — `VERSION` and CHANGELOG header in sync
8. Return to step 1

### Closeout Pass (before every minor/major bump)

1. Full test suite — 0 failures on both tcyr suites
2. Benchmark run — `cyrius bench`, save CSV
3. Dead code audit — review `dead:` list from `cyrius build`;
   unreferenced public functions should be removed or justified
4. Stale comment sweep — old version refs, outdated TODOs
5. Security re-scan — `grep sys_system`, unchecked writes, buffer
   size mismatches
6. Downstream check — Cyrius stdlib `lib/sankoch.cyr` still matches
   `dist/sankoch.cyr`
7. CHANGELOG / roadmap sync — docs reflect current state; `VERSION`,
   CHANGELOG header, intended git tag all consistent
8. `cyrius distlib` regenerates `dist/sankoch.cyr` clean
9. Clean rebuild — `rm -rf build lib && cyrius deps && cyrius build`

### Task Sizing

- **Low/Medium effort**: batch freely — multiple items per cycle
- **Large effort**: small bites only — break into sub-tasks, verify
  each before moving on
- **If unsure**: treat it as large

## Key Principles

- **Correctness is the optimum sovereignty** — wrong compression
  silently corrupts data. Every DEFLATE round-trip must match a
  known-good zlib output byte-for-byte
- **Numbers don't lie** — never claim a performance improvement
  without before/after benchmark numbers
- **Own the stack** — zero external dependencies; every byte in this
  tree
- **Test after EVERY change**, not after the feature is done
- **ONE change at a time** — never bundle unrelated changes
- **Study the RFCs** — RFC 1951 is the DEFLATE bible; read before
  writing code
- `cyrius build` / `cyrius test` handle everything — NEVER use raw
  `cat file | cc5`

## CI / Release

- **Toolchain pin**: `cyrius = "5.6.42"` in `cyrius.cyml`. CI and
  release both read from the manifest
- **Tag filter**: release workflow triggers on bare semver tags
  (`2.0.0`, not `v2.0.0`)
- **Version-verify gate**: release asserts `VERSION == git tag` before
  building
- **Lint gate**: CI runs `cyrius lint` per source; treat warnings as
  errors
- **Format gate**: CI runs `cyrius fmt --check`; drift fails the build
- **No lock gate**: sankoch is stdlib-only (zero git deps), so there is
  no `cyrius.lock` to verify against. The stdlib pin comes from the
  toolchain version itself (`cyrius = "5.6.42"` in `cyrius.cyml`)
- **Dist gate**: CI regenerates `dist/sankoch.cyr` via
  `cyrius distlib` and fails on drift
- **Concurrency**: CI uses `cancel-in-progress: true` keyed on
  workflow + ref

## Key References

- [`docs/development/cyrius-usage.md`](docs/development/cyrius-usage.md)
  — toolchain commands, distlib, lint/fmt gates
- [`docs/development/roadmap.md`](docs/development/roadmap.md)
  — milestones through v2.0
- [`docs/sources/compression.md`](docs/sources/compression.md)
  — RFC citations, algorithm references
- [`docs/benchmarks/`](docs/benchmarks) — throughput + size history
- `CHANGELOG.md` — source of truth for all changes

## DO NOT

- **Do not commit or push** — the user handles all git operations
- **NEVER use `gh` CLI** — use `curl` to the GitHub API if needed
- Do not add external dependencies — zero-dep is load-bearing
- Do not depend on sigil for Adler-32 / CRC-32 — they're inline
- Do not implement Zstandard in this crate — it deserves its own
- Do not skip spec verification — every DEFLATE test must round-trip
  against known-good zlib output
- Do not hand-edit `dist/sankoch.cyr` — regenerate with
  `cyrius distlib`
- Do not add Cyrius stdlib includes in individual `src/*.cyr` —
  `src/lib.cyr` owns the whole include chain
- Do not hardcode toolchain versions in CI YAML — read
  `cyrius.cyml`
- Do not add `v` prefix to version tags — use bare semver
- Do not re-vendor stdlib into `src/` — `cyrius deps` manages `lib/`
