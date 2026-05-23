# Getting Started with Sankoch

> Five minutes to *built and tested* on a fresh clone. Companion to the toolchain reference at [`cyrius-usage.md`](cyrius-usage.md).

## Prerequisites

- Cyrius toolchain at the version pinned in [`cyrius.cyml [package].cyrius`](../../cyrius.cyml). Install via `cyrius_new` (bootstrapper) or a GitHub release tarball.
- Linux on x86_64 or aarch64. macOS / Windows are not supported.

## Build, test, bench

```bash
git clone https://github.com/MacCracken/sankoch.git
cd sankoch

cyrius deps                              # resolve stdlib into lib/
cyrius build src/lib.cyr build/sankoch   # compile-check the library
cyrius test tests/tcyr/sankoch.tcyr      # main test suite (~few seconds)
cyrius test tests/tcyr/git_object.tcyr   # git-object regression suite
cyrius fuzz                              # all 12 harness functions
cyrius bench tests/bcyr/sankoch.bcyr     # throughput + SIZE lines
cyrius distlib                           # → dist/sankoch.cyr
cyrius distlib core                      # → dist/sankoch-core.cyr (kernel-safe)
```

`build/sankoch` is essentially empty (sankoch is a pure library); the build step exists to compile-check the include chain. The same is true for the binary that `cyrius distlib` regenerates — what matters is the bundled `dist/sankoch.cyr` file, not the binary output.

For the full command reference (CI gates, dead-code elimination, individual file builds, the kernel-safe tripwire), see [`cyrius-usage.md`](cyrius-usage.md).

## Consume sankoch from another Cyrius project

Sankoch ships as part of the Cyrius standard library. Consumers include it directly — no entry in their `[deps]` table.

```cyr
include "lib/sankoch.cyr"

# Now everything in sankoch's public API is available.
var c = alloc(1024);
var clen = zlib_compress(src, src_len, c, 1024);
```

For kernel-side consumers that need only LZ4 batch decompress with no alloc / no syscalls / no mutex:

```cyr
include "lib/sankoch-core.cyr"

# lz4_decompress + lz4f_decompress + xxhash32 only. Decompress-only.
```

The kernel-safe profile is verified by the `programs/core_smoke.cyr` tripwire that links ONLY the `[lib.core]` modules and exercises the LZ4 decompress paths on known fixtures. If a future change leaks `alloc` / syscalls / mutex usage into the core subset, the tripwire fails the build.

## What's where

| Question | Look at |
|----------|---------|
| What does each format / API look like? | [`README.md`](../../README.md) |
| What changed in version N? | [`CHANGELOG.md`](../../CHANGELOG.md) |
| What's the forward ladder? | [`../development/roadmap.md`](../development/roadmap.md) |
| What's the current state right now? | [`../development/state.md`](../development/state.md) |
| Toolchain command reference (deep) | [`cyrius-usage.md`](cyrius-usage.md) |
| Where does each algorithm come from? | [`../sources/compression.md`](../sources/compression.md) |
| Security audit history | [`../audit/`](../audit/) |
| Benchmark history | [`../benchmarks/`](../benchmarks/) |
| Why was X chosen over Y? | [`../adr/`](../adr/) |
| What invariants does the code rely on? | [`../architecture/`](../architecture/) + `CLAUDE.md § Key Constraints` |

## Reporting bugs

See [`../../SECURITY.md`](../../SECURITY.md) for security reports.

For non-security bugs, the GitHub issue tracker is the front door. If the bug needs durable in-repo design context (rejected fixes, invariants to preserve), it also gets a file under [`../development/issues/`](../development/issues/).
