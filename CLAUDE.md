# Sankoch — Claude Code Instructions

> **Core rule** (per [first-party-documentation § CLAUDE.md](https://github.com/MacCracken/agnosticos/blob/main/docs/development/first-party/first-party-documentation.md#claudemd)): this file is **preferences, process, and procedures** — durable rules that change rarely. Volatile state (current version, source line counts, test/assertion totals, in-flight slots, consumers, distribution targets) lives in [`docs/development/state.md`](docs/development/state.md), bumped every release. Do not inline state here — inlined state rots within a minor.

---

## Project Identity

**Sankoch** (Sanskrit: संकोच — contraction, compression) — Lossless compression library for AGNOS.

- **Type**: Shared library (include-based) + distlib bundle
- **License**: GPL-3.0-only
- **Language**: Cyrius (toolchain pinned in `cyrius.cyml [package].cyrius`)
- **Version**: `VERSION` at the project root is the source of truth — do not inline the number here
- **Genesis repo**: [agnosticos](https://github.com/MacCracken/agnosticos)
- **Standards**: [First-Party Standards](https://github.com/MacCracken/agnosticos/blob/main/docs/development/first-party/first-party-standards.md) · [First-Party Documentation](https://github.com/MacCracken/agnosticos/blob/main/docs/development/first-party/first-party-documentation.md)
- **Shared crates**: [shared-crates.md](https://github.com/MacCracken/agnosticos/blob/main/docs/development/planning/shared-crates.md)

## Goal

Own lossless compression. One library provides LZ4, DEFLATE, zlib, and gzip de/compression for everything downstream — ark packages, AGNOS initrd, git object reads, shravan/tarang container formats. Zero external dependencies, zero C FFI, zero shell-outs to `gzip`.

## Current State

> Volatile state lives in [`docs/development/state.md`](docs/development/state.md) —
> current version, source lines, test/assertion counts, distlib lines, in-flight
> slots, recent shipped releases, consumers, distribution targets. Refreshed every
> release.
> Historical release narrative lives in [`CHANGELOG.md`](CHANGELOG.md) (per-tag chronology).
> Forward ladder lives in [`docs/development/roadmap.md`](docs/development/roadmap.md).

This file (`CLAUDE.md`) is durable rules.

## Scaffolding

Project predates `cyrius init` / `cyrius port` — it was originally hand-scaffolded but has since been retrofitted onto the first-party layout. Going forward, new structural elements use the tools; **do not manually create new project structure** beyond what's already in place.

## Quick Start

```bash
cyrius deps                              # resolve stdlib into lib/
cyrius build src/lib.cyr build/sankoch   # compile-check (library — emitted binary is trivial)
cyrius test                              # all tcyr suites (auto-discovered)
cyrius test tests/tcyr/xz_compress.tcyr  # one split suite (codec × direction)
cyrius fuzz                              # all fuzz harness functions
cyrius bench tests/bcyr/sankoch.bcyr     # throughput + SIZE lines
cyrius distlib                           # → dist/sankoch.cyr (full)
cyrius distlib core                      # → dist/sankoch-core.cyr (kernel-safe LZ4 decompress)
```

Full command reference: [`docs/guides/cyrius-usage.md`](docs/guides/cyrius-usage.md).

## Architecture (at a glance)

```
src/
  lib.cyr          — Include chain (stdlib + domain modules) + public API + _sankoch_mtx
  types.cyr        — Enums: formats (incl. FORMAT_LZ4F), errors, limits        [core]
  xxhash32.cyr     — xxHash32 batch (helpers + enum) — kernel-safe              [core]
  checksum.cyr     — Adler-32 / CRC-32 / CRC-64-XZ / CRC-32-BZIP2 + incremental state APIs (alloc-using)
  bitreader.cyr    — LSB-first bit-stream reader (DEFLATE)
  bitwriter.cyr    — LSB-first bit-stream writer (DEFLATE)
  huffman.cyr      — Huffman build/decode, fixed trees, optimal trees
  lz77.cyr         — Sliding window match-finder + lz77_rebase (for streaming slide)
  lz4_decode.cyr   — LZ4 block + frame decompress + LZ4F enum — kernel-safe   [core]
  lz4.cyr          — LZ4 block + frame compress + lz4f_enc_* + lz4f_dec_*
  deflate.cyr      — DEFLATE de/compress, adaptive blocks, dict, deflate_enc_* + deflate_dec_*
  zlib.cyr         — zlib wrapper + FDICT batch + zlib_enc_* + zlib_dec_*
  gzip.cyr         — gzip wrapper + concatenated batch + gzip_enc_* + gzip_dec_*
  xz.cyr           — .xz de/compress: container + LZMA2 + LZMA range coder, optimal-parse encoder (xz_decompress / xz_compress)
  bzip2.cyr        — .bz2 de/compress: bit reader/writer + Huffman + MTF/RLE2 + inverse/forward BWT + RLE1 (bzip2_decompress / bzip2_compress)
  stream.cyr       — Streaming dispatch (compress + buffered/incremental decompress)
programs/
  core_smoke.cyr   — Kernel-safe tripwire: links ONLY [core] modules
tests/tcyr/        — test suites: 15 codec×direction files + _harness.tcyr (shared) + git_object.tcyr
tests/bcyr/        — benchmarks (sankoch.bcyr)
fuzz/              — fuzz harnesses (lz4, deflate — both wired into CI)
dist/
  sankoch.cyr      — full distlib bundle; ships as lib/sankoch.cyr in Cyrius stdlib
  sankoch-core.cyr — kernel-safe profile; ships as lib/sankoch-core.cyr alongside
cyrius.cyml        — package manifest (toolchain pin, [deps], [lib] + [lib.core] modules)
```

Modules tagged `[core]` are members of `[lib.core]` — the kernel-safe profile consumed by the AGNOS initrd loader. They contain no `alloc()`, no syscalls, and no mutex usage.

**Include order matters.** `src/lib.cyr` declares the full chain: stdlib first, then domain modules in dependency order. Stdlib includes live **only** in `lib.cyr` — never in individual domain modules. Domain modules are flat: zero transitive includes, which is what makes `cyrius distlib` (strip-include concatenation) produce a compile-clean bundle.

Per-file line counts and the current `[core]` total are in [`docs/development/state.md`](docs/development/state.md) and [`docs/development/roadmap.md` § File Summary](docs/development/roadmap.md#file-summary-at-230).

## Key Principles

- **Correctness is the optimum sovereignty** — wrong compression silently corrupts data. Every DEFLATE round-trip must match a known-good zlib output byte-for-byte.
- **Own the stack** — zero external dependencies; every byte in this tree.
- **Modular by profile — every lossless codec lives here.** The per-codec distlib profiles (`cyrius distlib <codec>`) let a consumer pull only the closure it needs, so adding a compression format never bloats consumers that don't use it. sankoch is therefore the home for *all* lossless-compression codecs (Zstandard included — decode shipped 2.5.0, encode on the ladder) — no "it deserves its own crate" carve-outs.
- **Numbers don't lie** — never claim a performance improvement without before/after benchmark numbers.
- **Test after EVERY change**, not after the feature is done.
- **ONE change at a time** — never bundle unrelated changes.
- **Study the RFCs** — RFC 1951 is the DEFLATE bible; read before writing code.
- **Reference-CLI compatibility is load-bearing** — zlib output must decode via Python `zlib.decompress`; gzip via `gunzip`; LZ4F via `lz4 -dc`. The 1.6.1 xxHash32 bug is the cautionary tale (self-consistent round-trips hid a spec divergence for months).

## Rules (Hard Constraints)

- **Read the genesis repo's CLAUDE.md first** — [agnosticos/CLAUDE.md](https://github.com/MacCracken/agnosticos/blob/main/CLAUDE.md)
- **Do not commit or push** — the user handles all git operations
- **NEVER use `gh` CLI** — use `curl` to the GitHub API if needed
- Do not add external dependencies — zero-dep is load-bearing
- Do not depend on sigil for Adler-32 / CRC-32 / xxHash32 — they're inline (30-line primitives that live inside the compression format specs anyway)
- Do not skip spec verification — every DEFLATE test must round-trip against known-good zlib output
- Do not hand-edit `dist/sankoch.cyr` or `dist/sankoch-core.cyr` — regenerate with `cyrius distlib` / `cyrius distlib core`
- Do not add Cyrius stdlib includes in individual `src/*.cyr` — `src/lib.cyr` owns the whole include chain
- Do not hardcode toolchain versions in CI YAML — read `cyrius.cyml` (`cyrius = "X.Y.Z"` pin is the only source of truth)
- Do not add `v` prefix to version tags — bare semver only
- Do not re-vendor stdlib into `src/` — `cyrius deps` manages `lib/`
- **Build with `cyrius build`, never raw `cat file | cycc`** — the manifest auto-resolves deps and prepends includes

## Key Constraints (load-bearing invariants)

- **All mutable state behind one mutex.** The compression globals (bitreader, bitwriter, hash tables, Huffman tables, symbol buffers) serialize on `_sankoch_lock()` / `_sankoch_unlock()`. No per-call allocation on the hot path.
- **Integer math only, i64 or fixed-size strings. No floating point — anywhere.**
- **Stack arrays: `var buf[N]` is N bytes, not N×8.** Use `&buf` for `load*`/`store*` addresses.
- **Bundle gate.** CI regenerates `dist/sankoch.cyr` via `cyrius distlib` and fails if it drifts from the committed file.

## Process

### P(-1): Scaffold Hardening (before each minor cut)

Run before opening any minor; closes any debt the previous minor accreted. See the latest [`docs/audit/`](docs/audit/) entry for the most recent run's findings.

0. Read CHANGELOG + roadmap — know what was intended.
1. **Cleanliness gates**: `cyrius build` 0 warnings on library path; `cyrius lint` per source file 0 warnings; `cyrfmt --check` diff-clean across `src/` + `programs/` + `tests/` + `fuzz/`; `cyrius vet src/lib.cyr` clean.
2. **Test sweep**: both tcyr suites green; all fuzz harnesses green.
3. **Benchmark baseline**: `cyrius bench tests/bcyr/sankoch.bcyr`, save CSV to `docs/benchmarks/YYYY-MM-DD-*.md`.
4. **Internal deep review** — gaps, optimizations, correctness.
5. **External research** — RFC errata / zlib / lz4 reference changes since the last audit.
6. **Security audit** — `docs/audit/YYYY-MM-DD-*.md`.
7. **Additional tests / benchmarks** from findings.
8. **Post-review benchmarks** — prove the wins.
9. **Documentation audit** — CLAUDE.md, roadmap, state.md, CHANGELOG, README, doc-health.
10. **Repeat if heavy** — keep drilling until clean.

### Work Loop (continuous)

1. Work phase — implement algorithm, add tests/benchmarks.
2. Build: `cyrius build src/lib.cyr build/sankoch`.
3. Test: `cyrius test` (all suites) — 0 failures.
4. Benchmark: throughput (MB/s) and ratio for changes in the hot path.
5. Audit: verify against spec (RFC 1951, LZ4 block format, etc.).
6. Documentation — CHANGELOG, roadmap, state.md.
7. Version check — `VERSION`, `cyrius.cyml` pin, CHANGELOG header in sync.
8. Return to step 1.

### Closeout Pass (before every minor/major bump)

1. Full test suite — 0 failures on both tcyr suites.
2. Benchmark run — `cyrius bench`, save CSV; compare against prior closeout.
3. Dead code audit — review `dead:` list from `cyrius build`; unreferenced public functions should be removed or justified.
4. Stale comment sweep — old version refs, outdated TODOs.
5. Security re-scan — `grep sys_system` (must be zero in `src/`), unchecked writes, buffer size mismatches.
6. Downstream check — Cyrius stdlib `lib/sankoch.cyr` matches `dist/sankoch.cyr`.
7. CHANGELOG / roadmap / state.md / doc-health sync — docs reflect current state; `VERSION`, `cyrius.cyml` pin, CHANGELOG header, intended git tag all consistent.
8. `cyrius distlib` + `cyrius distlib core` regenerate cleanly.
9. Clean rebuild — `rm -rf build lib && cyrius deps && cyrius build`.

### Task Sizing

- **Low/Medium effort**: batch freely — multiple items per cycle.
- **Large effort**: small bites only — break into sub-tasks, verify each before moving on. The 2.3.0 streaming-decompression arc shipped as 6 sequential bites; that pattern is the template.
- **If unsure**: treat it as large.

## CI / Release

- **Toolchain pin**: `cyrius = "X.Y.Z"` field in `cyrius.cyml [package]`. CI and release both read this; no hardcoded version strings in YAML.
- **Tag filter**: release workflow triggers on bare semver tags (`2.0.0`, not `v2.0.0`).
- **Version-verify gate**: release asserts `VERSION == git tag` before building.
- **Lint gate**: CI runs `cyrius lint` per source; treat warnings as errors.
- **Format gate**: CI runs `cyrfmt --check`; drift fails the build.
- **Dist gate**: CI regenerates `dist/sankoch.cyr` + `dist/sankoch-core.cyr` via `cyrius distlib` and fails on drift.
- **Kernel-safe tripwire**: CI builds + runs `programs/core_smoke.cyr` linked against the `[lib.core]` modules only.
- **aarch64 cross-build**: hard gate in both ci.yml and release.yml; expects `cycc_aarch64` in the Cyrius bundle (renamed from `cc5_aarch64` at Cyrius 6.0).
- **No lock gate**: sankoch is stdlib-only (zero git deps), so there is no `cyrius.lock` to verify against. The stdlib pin comes from the toolchain version itself.
- **Concurrency**: CI uses `cancel-in-progress: true` keyed on workflow + ref.

## Docs

- [`docs/adr/`](docs/adr/) — architecture decision records. *Why did we choose X over Y?*
- [`docs/architecture/`](docs/architecture/) — non-obvious constraints and quirks. *What can't I derive from the code alone?*
- [`docs/guides/`](docs/guides/) — task-oriented how-tos.
  - [`docs/guides/cyrius-usage.md`](docs/guides/cyrius-usage.md) — toolchain commands, distlib, lint/fmt gates.
- [`docs/development/roadmap.md`](docs/development/roadmap.md) — forward ladder (post-2.3.0); shipped history lives in CHANGELOG.
- [`docs/development/state.md`](docs/development/state.md) — **live state snapshot, refreshed every release**.
- [`docs/doc-health.md`](docs/doc-health.md) — fresh / stale / archive ledger across the whole doc tree.
- [`docs/sources/compression.md`](docs/sources/compression.md) — RFC citations, algorithm references.
- [`docs/audit/`](docs/audit/) — periodic security audits (timestamped, never refreshed in place).
- [`docs/benchmarks/`](docs/benchmarks/) — throughput + size history per release.
- [`CHANGELOG.md`](CHANGELOG.md) — source of truth for all release changes.

New quirks and constraints land in `docs/architecture/` as numbered items (`NNN-kebab-case.md`). New decisions land in `docs/adr/` using [`docs/adr/template.md`](docs/adr/template.md). **Never renumber either series.**

Full doc-tree convention: [first-party-documentation.md](https://github.com/MacCracken/agnosticos/blob/main/docs/development/first-party/first-party-documentation.md).
