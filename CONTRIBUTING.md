# Contributing to Sankoch

See [AGNOS First-Party Standards](https://github.com/MacCracken/agnosticos/blob/main/docs/development/applications/first-party-standards.md) for full development conventions.

## Quick Start

```sh
cyrius build src/lib.cyr build/sankoch
cyrius test
```

## Key Rules

- Every algorithm must cite its specification (see `docs/sources/compression.md`)
- Round-trip tests are mandatory — compress then decompress, verify identical
- DEFLATE output must be decompressible by standard zlib (cross-compatibility)
- Benchmarks must report MB/s throughput and compression ratio
- Zero external dependencies

## License

By contributing, you agree that your contributions will be licensed under GPL-3.0-only.
