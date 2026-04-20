# Contributing to Sankoch

See [AGNOS First-Party Standards](https://github.com/MacCracken/agnosticos/blob/main/docs/development/applications/first-party-standards.md) for full development conventions.

## Quick Start

```sh
cyrius deps                            # resolve stdlib into lib/
cyrius build src/lib.cyr build/sankoch # compile-check
cyrius test                            # auto-runs both tcyr suites
cyrius fuzz                            # both fuzz harnesses
cyrius bench tests/bcyr/sankoch.bcyr   # throughput + SIZE lines
```

Full command reference: [`docs/development/cyrius-usage.md`](docs/development/cyrius-usage.md).

## Key Rules

- Every algorithm must cite its specification (see
  [`docs/sources/compression.md`](docs/sources/compression.md))
- **Round-trip tests are mandatory** — compress then decompress,
  assert byte-identical output
- **Reference-CLI compatibility is load-bearing** — zlib output must
  decode via Python `zlib.decompress`; gzip via `gunzip`; LZ4F via
  `lz4 -dc`. The v1.6.1 xxHash32 bug is a cautionary tale: self-
  consistent round-trips hid a spec divergence for months
- Benchmarks must report MB/s throughput and compression ratio; SIZE
  lines in `bench` output are parsed by `scripts/compare-sizes.sh`
- Zero external dependencies — no git deps under `[deps.*]` in
  `cyrius.cyml`. Checksums live inline in `src/checksum.cyr`
- CI gates: `cyrius build` 0 warnings, `cyrius lint` 0 warnings,
  `cyrius fmt --check` diff-clean, `cyrius vet` 0 untrusted, both
  tcyr suites + both fuzz harnesses green, SIZE lines stable
- Version bumps require a matching `CHANGELOG.md` entry — the
  release workflow asserts `VERSION == tag` and greps the tag in
  CHANGELOG before publishing
- `dist/sankoch.cyr` is a tracked artifact — run `cyrius distlib`
  and commit the result whenever `src/` changes; CI fails on drift

## License

By contributing, you agree that your contributions will be licensed
under GPL-3.0-only.
