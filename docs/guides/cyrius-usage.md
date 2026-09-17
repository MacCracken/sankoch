# Cyrius Usage (sankoch)

Single source of truth for toolchain commands in this repo. Every command
below is invoked via the `cyrius` frontend — never shell out to `cycc`
(or its predecessor names) directly.

## Prerequisites

Toolchain pinned in `cyrius.cyml`:

```toml
[package]
cyrius = "X.Y.Z"   # the pin; see cyrius.cyml for the current value
```

CI reads the pin from the manifest; locally you can install that version
with `cyrius_new` (bootstrapper) or via a GitHub release tarball.

## Commands

### Build

```bash
cyrius deps                              # resolve stdlib → lib/
cyrius build src/lib.cyr build/sankoch   # compile-check the library
CYRIUS_DCE=1 cyrius build src/lib.cyr build/sankoch   # strip dead code
```

`sankoch` is a pure library — the produced `build/sankoch` binary has no
entry point and is essentially empty. The build step exists to catch
compile errors across the full include chain before running tests.

### Test

```bash
cyrius test                              # all tcyr suites (auto-discovered)
cyrius test tests/tcyr/xz_compress.tcyr  # a single split suite
cyrius test tests/tcyr/git_object.tcyr   # git-object regressions (grew with 2.0.2 / 2.0.3 cl-tree fixtures)
```

The suite is split by **codec × direction** (since 2.4.1): one `.tcyr`
file per codec and direction under `tests/tcyr/` (e.g.
`deflate_compress.tcyr`, `xz_decompress.tcyr`), plus the cross-cutting
`detect_error` / `ratio_cap` suites and `git_object.tcyr` (current
file / function / assertion counts live in state.md). Each suite
`include "tests/tcyr/_harness.tcyr"` —
the shared harness owns the `src/lib.cyr` (full chain) + `lib/assert.cyr`
includes, the 4 MB heap setup (`_test_init`), and the cross-cutting
helpers; it has no `main()`, so it is never run directly (the CI Test
loop skips `_`-prefixed files). Suites carry no manual stdlib imports.
Bare `cyrius test` auto-discovers and runs every suite.

Current test-function and assertion totals live in
[`../development/state.md`](../development/state.md) — refreshed every
release. The headline numbers below explain what the assertion count
*means*, not what it currently *is*.

#### What "assertions" means here (and why the number is so large)

**Assertions ≠ test cases.** The suites contain a small number of
distinct test functions — the kind of unit you'd usually count as
"tests." Those functions emit a much larger number of individual
`assert(...)` calls when run, and the second number is what
`cyrius test` reports as the "passed" count.

The headline number is dominated by **per-byte round-trip
verification**. A streaming round-trip test on a 200 KB input contains
a `while (i < 200000) { assert(load8(dst+i) == load8(src+i), …); i++ }`
loop — one test function, 200,000 assertions. The streaming suite
covers 64 K / 100 K / 150 K / 200 K inputs across DEFLATE / zlib /
gzip / LZ4F at multiple levels, plus the 2.0.2 / 2.0.3 cl-tree
regression fixtures in `git_object.tcyr` that walk every byte of
synthetic worst-case inputs (134 → 13,929 → 346,583 across the two
patches). The assertion count climbs proportionally with test input
size, not with "number of distinct test functions" — that's by
design.

Why this design (per `CLAUDE.md` "Key Principles"): wrong compression
silently corrupts data, and the only way to catch a single-byte
divergence in a 200 KB DEFLATE round-trip is to assert each byte
individually. A pass/fail at "buffers are equal" hides which byte
differed; per-byte assertions point straight at the corruption site.

Read the headline as **"millions of byte-level proofs of correctness
across a few hundred logically distinct scenarios"** — it's a
coverage-density number, not a coverage-breadth number (the live totals
are in state.md).

### Benchmark

```bash
cyrius bench tests/bcyr/sankoch.bcyr
```

Emits machine-readable `SIZE` lines (compressed size per input) and
timing totals. Throughput numbers archived in `docs/benchmarks/`.

### Bundle (distlib)

```bash
cyrius distlib                           # → dist/sankoch.cyr (full)
cyrius distlib core                      # → dist/sankoch-core.cyr (kernel-safe)
cyrius distlib brotli                    # → dist/sankoch-brotli.cyr (Brotli decode only)
cyrius distlib woff                      # → dist/sankoch-woff.cyr (zlib closure + Brotli, web fonts)
bash scripts/profile-link-gate.sh --list-profiles   # every profile cyrius.cyml defines
```

12 bundles as of 2.8.0: full, core, zlib, gzip, xz, bzip2, zstd, tar, zip, zipall, brotli, woff.
The list lives only in `cyrius.cyml`. CI and release loop over `--list-profiles`, and a new
`[lib.<name>]` needs a `probe_body_<name>` in the link gate.

**One sankoch bundle per program.** Profiles are closures, not layers. Two in one program collide on
`runtime.cyr`'s globals (see `docs/architecture/003-per-profile-reset-dispatch.md`), so pick the
smallest single profile that carries every codec you need.

`cyrius distlib` reads `[lib].modules` from `cyrius.cyml`, strips
`include` lines, and concatenates the listed files into a single
`dist/sankoch.cyr`. Downstream consumers (and the Cyrius stdlib under
`lib/sankoch.cyr`) use this bundle.

`cyrius distlib core` reads `[lib.core].modules` and produces
`dist/sankoch-core.cyr` — the kernel-safe LZ4 decompress profile
(types + xxhash32 + lz4_decode; no alloc, no syscalls, no mutex)
consumed by the AGNOS initrd loader as `lib/sankoch-core.cyr`.

CI regenerates every bundle and asserts each matches the committed, tracked file.
Bundles are tracked artifacts, not generated ephemerals. A new bundle needs its
`!dist/` re-include in `.gitignore`.

**Link gate** (2.8.0): `bash scripts/profile-link-gate.sh` proves each committed bundle links and runs.
It checks reset registration, builds a reachable-call probe, decodes reference-CLI vectors before
and after `alloc_reset()`, and requires the reset to stay reachable from `_sankoch_lock` under
`--agnos`. Use `--bundle-dir DIR` to test other bundles (the directory must be inside the repo).

### Quality gates

```bash
cyrius lint src/*.cyr programs/*.cyr tests/tcyr/*.tcyr tests/bcyr/*.bcyr fuzz/*.fcyr
for f in src/*.cyr programs/*.cyr tests/tcyr/*.tcyr tests/bcyr/*.bcyr fuzz/*.fcyr; do
  cyrius fmt --check "$f" > /dev/null 2>&1 || echo "needs fmt: $f"   # ONE file per call
done
cyrius vet  src/lib.cyr         # audit include dependencies
python3 scripts/nul-literal-gate.py   # no NUL in string literals (docs/architecture/004)
python3 scripts/brotli_dict2cyr.py docs/sources/brotli/dictionary.bin build/brotli_dict.regen.cyr \
  && cmp build/brotli_dict.regen.cyr src/brotli_dict.cyr   # generated module is current
bash scripts/brotli-smoke.sh          # local only: differential vs brotli -d 1.2.0 (needs the CLI)
```

Sankoch is stdlib-only, so there is no `cyrius.lock` and no
`cyrius deps --verify` gate — the stdlib snapshot is implicitly pinned
by the toolchain version (the `cyrius = "X.Y.Z"` pin in `cyrius.cyml`). Add
`cyrius.lock` / `cyrius deps --verify` only if a git-sourced dep is
ever added under `[deps.*]`.

All of these except `brotli-smoke.sh` run in CI. `cyrius fmt --check <file>` reports drift **only through
its exit code** (Cyrius 6.5.35+), and it exits 0 on drift when given more than one file, so check one
file per call and read `$?`. Bare `cyrius fmt <file>` rewrites the file in place.

### Fuzz

```bash
cyrius fuzz                          # auto-discovers fuzz/*.fcyr
# or run one harness at a time:
cyrius build fuzz/fuzz_lz4.fcyr     build/fuzz_lz4     && ./build/fuzz_lz4
cyrius build fuzz/fuzz_deflate.fcyr build/fuzz_deflate && ./build/fuzz_deflate
cyrius build fuzz/fuzz_xz.fcyr      build/fuzz_xz      && ./build/fuzz_xz
cyrius build fuzz/fuzz_bzip2.fcyr   build/fuzz_bzip2   && ./build/fuzz_bzip2
cyrius build fuzz/fuzz_zstd.fcyr    build/fuzz_zstd    && ./build/fuzz_zstd
```

Round-trip fuzzing at varying sizes + malformed-input survival. Five
auto-discovered harnesses — `fuzz_lz4`, `fuzz_deflate`, `fuzz_xz`,
`fuzz_bzip2`, `fuzz_zstd` — cover round-trip and malformed/corruption input
across every codec plus the streaming and ratio-cap paths. All run in CI per
`.github/workflows/ci.yml` — a non-zero exit (assert fires or crash) fails the
build. Current per-harness iteration counts live in
[`../development/state.md`](../development/state.md#fuzz-totals).

## Release flow

```bash
./scripts/version-bump.sh X.Y.Z          # updates VERSION
# edit CHANGELOG.md — add [X.Y.Z] section with release date
cyrius distlib                           # regenerate dist/sankoch.cyr with new version header
cyrius distlib core                      # regenerate dist/sankoch-core.cyr too
git commit -am "release X.Y.Z"
git tag X.Y.Z                            # bare semver, no v prefix
git push --tags                          # triggers .github/workflows/release.yml
```

Update [`docs/development/state.md`](../development/state.md) in the
same commit — it's the live snapshot CI/consumers read.

The release workflow: runs CI → verifies `VERSION == tag` → builds
with `CYRIUS_DCE=1` → verifies ELF → tests → fuzz → regenerates
bundle → archives src tarball + `dist/sankoch.cyr` + SHA256SUMS →
creates a GitHub Release. No `cyrius.lock` is shipped — sankoch is
stdlib-only (zero git deps), so the `cyrius = "X.Y.Z"` pin in
`cyrius.cyml` is the lockfile. The release also regenerates and publishes every profile bundle
(the list comes from `cyrius.cyml` via `profile-link-gate.sh --list-profiles`) after the link gate.

## Gotchas

- **`var buf[N]` is N bytes, not N×8.** Use `&buf` when passing to
  `load*` / `store*`.
- **No closures over locals.** All state through globals or struct-like
  heap blobs (see `src/bitreader.cyr` layout comment).
- **`break` in `var`-heavy loops unreliable.** Prefer a sentinel check
  in the loop condition.
- **`sys_write` / `sys_open` are banned** in `src/` — compression is a
  pure in-memory operation. CI security scan fails on any occurrence.
