# Cyrius Usage (sankoch)

Single source of truth for toolchain commands in this repo. Every command
below is invoked via the `cyrius` frontend — never shell out to `cc5`
directly.

## Prerequisites

Toolchain pinned in `cyrius.cyml`:

```toml
[package]
cyrius = "6.0.1"
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
cyrius test tests/tcyr/sankoch.tcyr      # 1,029,265 assertions
cyrius test tests/tcyr/git_object.tcyr   #   346,583 assertions (git integration; grew with 2.0.2 / 2.0.3 cl-tree regression fixtures)
```

Both tcyr files include `src/lib.cyr` (full chain) + `lib/assert.cyr`.
No manual stdlib imports — `src/lib.cyr` owns that.

#### What "assertions" means here (and why the number is so large)

**Assertions ≠ test cases.** At v2.2.0 the two suites contain
**103 distinct test functions** (93 in `sankoch.tcyr`, 10 in
`git_object.tcyr`) — the kind of unit you'd usually count as "tests."
Those 103 functions emit **1,375,848 individual `assert(...)` calls**
when run, and the second number is what `cyrius test` reports as the
"passed" count.

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

Read the headline as **"~1.4 M byte-level proofs of correctness across
~100 logically distinct scenarios"** — it's a coverage-density
number, not a coverage-breadth number.

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
```

`cyrius distlib` reads `[lib].modules` from `cyrius.cyml`, strips
`include` lines, and concatenates the listed files into a single
`dist/sankoch.cyr`. Downstream consumers (and the Cyrius stdlib under
`lib/sankoch.cyr`) use this bundle.

`cyrius distlib core` reads `[lib.core].modules` and produces
`dist/sankoch-core.cyr` — the kernel-safe LZ4 decompress profile
(types + xxhash32 + lz4_decode; no alloc, no syscalls, no mutex)
consumed by the AGNOS initrd loader as `lib/sankoch-core.cyr`.

CI regenerates both bundles and asserts they match the committed
files — `dist/sankoch.cyr` and `dist/sankoch-core.cyr` are tracked
artifacts, not generated ephemerals.

### Quality gates

```bash
cyrius lint src/*.cyr programs/*.cyr tests/tcyr/*.tcyr tests/bcyr/*.bcyr fuzz/*.fcyr
cyrius fmt  src/*.cyr --check   # prints formatted output; compare to file
cyrius vet  src/lib.cyr         # audit include dependencies
```

Sankoch is stdlib-only, so there is no `cyrius.lock` and no
`cyrius deps --verify` gate — the stdlib snapshot is implicitly pinned
by the toolchain version (`cyrius = "6.0.1"` in `cyrius.cyml`). Add
`cyrius.lock` / `cyrius deps --verify` only if a git-sourced dep is
ever added under `[deps.*]`.

All four run in CI. `fmt --check` emits the formatted source; CI diffs
against the committed file and fails on drift. To apply the fix
in-place (Cyrius 5.5.22+, also available on 6.0.1):

```bash
cyrfmt --write src/checksum.cyr    # or -w
```

Idempotent — re-running on a clean file is a no-op (mtime unchanged).

### Fuzz

```bash
cyrius fuzz                          # auto-discovers fuzz/*.fcyr
# or run one harness at a time:
cyrius build fuzz/fuzz_lz4.fcyr     build/fuzz_lz4 && ./build/fuzz_lz4
cyrius build fuzz/fuzz_deflate.fcyr build/fuzz_deflate && ./build/fuzz_deflate
```

Round-trip fuzzing at varying sizes + malformed-input survival.
`fuzz_lz4` runs 500 round-trip + 200 malformed iterations; `fuzz_deflate`
runs 240 + 100 for DEFLATE itself, 160 each for zlib/gzip wrappers,
plus 204 streaming iterations across all four streaming encoders
(DEFLATE / zlib / gzip / LZ4F). Both harnesses run in CI per
`.github/workflows/ci.yml` — a non-zero exit (assert fires or crash)
fails the build.

## Release flow

```bash
./scripts/version-bump.sh 2.1.1          # updates VERSION
# edit CHANGELOG.md — add [2.1.1] section with release date
cyrius distlib                           # regenerate bundle with new version header
git commit -am "release 2.1.1"
git tag 2.1.1                            # bare semver, no v prefix
git push --tags                          # triggers .github/workflows/release.yml
```

The release workflow: runs CI → verifies `VERSION == tag` → builds
with `CYRIUS_DCE=1` → verifies ELF → tests → fuzz → regenerates
bundle → archives src tarball + `dist/sankoch.cyr` + SHA256SUMS →
creates a GitHub Release. No `cyrius.lock` is shipped — sankoch is
stdlib-only (zero git deps), so the stdlib pin via `cyrius = "6.0.1"`
in `cyrius.cyml` is the lockfile.

## Gotchas

- **`var buf[N]` is N bytes, not N×8.** Use `&buf` when passing to
  `load*` / `store*`.
- **No closures over locals.** All state through globals or struct-like
  heap blobs (see `src/bitreader.cyr` layout comment).
- **`break` in `var`-heavy loops unreliable.** Prefer a sentinel check
  in the loop condition.
- **`sys_write` / `sys_open` are banned** in `src/` — compression is a
  pure in-memory operation. CI security scan fails on any occurrence.
