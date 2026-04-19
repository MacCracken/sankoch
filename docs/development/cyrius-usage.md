# Cyrius Usage (sankoch)

Single source of truth for toolchain commands in this repo. Every command
below is invoked via the `cyrius` frontend — never shell out to `cc5`
directly.

## Prerequisites

Toolchain pinned in `cyrius.cyml`:

```toml
[package]
cyrius = "5.4.7"
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
cyrius test tests/tcyr/sankoch.tcyr      # 5897 assertions
cyrius test tests/tcyr/git_object.tcyr   # 134 assertions (git integration)
```

Both tcyr files include `src/lib.cyr` (full chain) + `lib/assert.cyr`.
No manual stdlib imports — `src/lib.cyr` owns that.

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
cyrius deps --verify            # check lib/*.cyr against cyrius.lock
```

All four run in CI. `fmt --check` emits the formatted source; CI diffs
against the committed file and fails on drift. To apply the fix:

```bash
cyrius fmt src/checksum.cyr --check > src/checksum.cyr.new
mv src/checksum.cyr.new src/checksum.cyr
```

(A direct in-place mode may land in a later Cyrius version.)

### Fuzz (currently out-of-CI)

```bash
cyrius build fuzz/fuzz_lz4.fcyr     build/fuzz_lz4
cyrius build fuzz/fuzz_deflate.fcyr build/fuzz_deflate
./build/fuzz_lz4 && ./build/fuzz_deflate
```

Round-trip fuzzing at varying sizes + malformed-input survival. The
harnesses compile clean under 5.4.7 but are not wired into CI pending a
dedicated runtime-stability pass — tracked on the roadmap.

## Release flow

```bash
./scripts/version-bump.sh 1.4.0          # updates VERSION
# edit CHANGELOG.md — add [1.4.0] section with release date
cyrius distlib                           # regenerate bundle with new version header
git commit -am "release 1.4.0"
git tag 1.4.0                            # bare semver, no v prefix
git push --tags                          # triggers .github/workflows/release.yml
```

The release workflow: runs CI → verifies `VERSION == tag` → builds +
tests + regenerates bundle → archives src tarball + `dist/sankoch.cyr`
+ `cyrius.lock` + SHA256SUMS → creates a GitHub Release.

## Gotchas

- **`var buf[N]` is N bytes, not N×8.** Use `&buf` when passing to
  `load*` / `store*`.
- **No closures over locals.** All state through globals or struct-like
  heap blobs (see `src/bitreader.cyr` layout comment).
- **`break` in `var`-heavy loops unreliable.** Prefer a sentinel check
  in the loop condition.
- **`sys_write` / `sys_open` are banned** in `src/` — compression is a
  pure in-memory operation. CI security scan fails on any occurrence.
