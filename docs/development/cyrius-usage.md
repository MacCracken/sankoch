# Cyrius Usage (sankoch)

Single source of truth for toolchain commands in this repo. Every command
below is invoked via the `cyrius` frontend — never shell out to `cc5`
directly.

## Prerequisites

Toolchain pinned in `cyrius.cyml`:

```toml
[package]
cyrius = "5.6.42"
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
cyrius test tests/tcyr/sankoch.tcyr      # 1,028,625 assertions
cyrius test tests/tcyr/git_object.tcyr   # 346,583 assertions (git integration; grew with 2.0.2 / 2.0.3 cl-tree regression fixtures)
```

Both tcyr files include `src/lib.cyr` (full chain) + `lib/assert.cyr`.
No manual stdlib imports — `src/lib.cyr` owns that.

The bulk of `sankoch.tcyr` assertions come from per-byte round-trip
checks in the streaming tests: every byte of each 65536 / 100000 /
150000 / 200000-byte test input is asserted equal after round-trip.
The assertion count climbs proportionally with test input size, not
with "number of distinct test functions" — that's by design.

### Benchmark

```bash
cyrius bench tests/bcyr/sankoch.bcyr
```

Emits machine-readable `SIZE` lines (compressed size per input) and
timing totals. Throughput numbers archived in `docs/benchmarks/`.

### Bundle (distlib)

```bash
cyrius distlib                           # → dist/sankoch.cyr
```

`cyrius distlib` reads `[lib.modules]` from `cyrius.cyml`, strips
`include` lines, and concatenates the listed files into a single
`dist/sankoch.cyr`. Downstream consumers (and the Cyrius stdlib under
`lib/sankoch.cyr`) use this bundle.

CI regenerates the bundle and asserts it matches the committed file —
`dist/sankoch.cyr` is a tracked artifact, not a generated ephemeral.

### Quality gates

```bash
cyrius lint src/*.cyr tests/tcyr/*.tcyr tests/bcyr/*.bcyr fuzz/*.fcyr
cyrius fmt  src/*.cyr --check   # prints formatted output; compare to file
cyrius vet  src/lib.cyr         # audit include dependencies
```

Sankoch is stdlib-only, so there is no `cyrius.lock` and no
`cyrius deps --verify` gate — the stdlib snapshot is implicitly pinned
by the toolchain version (`cyrius = "5.6.42"` in `cyrius.cyml`). Add
`cyrius.lock` / `cyrius deps --verify` only if a git-sourced dep is
ever added under `[deps.*]`.

All four run in CI. `fmt --check` emits the formatted source; CI diffs
against the committed file and fails on drift. To apply the fix
in-place (Cyrius 5.5.22+, also available on 5.6.42):

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
./scripts/version-bump.sh 2.1.0          # updates VERSION
# edit CHANGELOG.md — add [2.1.0] section with release date
cyrius distlib                           # regenerate bundle with new version header
git commit -am "release 2.1.0"
git tag 2.1.0                            # bare semver, no v prefix
git push --tags                          # triggers .github/workflows/release.yml
```

The release workflow: runs CI → verifies `VERSION == tag` → builds
with `CYRIUS_DCE=1` → verifies ELF → tests → fuzz → regenerates
bundle → archives src tarball + `dist/sankoch.cyr` + SHA256SUMS →
creates a GitHub Release. No `cyrius.lock` is shipped — sankoch is
stdlib-only (zero git deps), so the stdlib pin via `cyrius = "5.6.42"`
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
