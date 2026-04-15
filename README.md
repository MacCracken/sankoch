# Sankoch — Lossless Compression for AGNOS

> Sanskrit: संकोच — contraction, compression

Sovereign lossless compression library written in Cyrius. Zero external dependencies. Zero C FFI.

## Algorithms

| Algorithm | Phase | Status | Use Case |
|-----------|-------|--------|----------|
| LZ4 block | 1 | Planned | Fast internal compression (initrd, snapshots, pack cache) |
| DEFLATE | 2-3 | Planned | Git compatibility (clone, fetch, push) |
| zlib | 4 | Planned | Git object format |
| gzip | 4 | Planned | Archive interchange |

## Build

```sh
cyrius build src/lib.cyr build/sankoch
cyrius test
```

## Why

AGNOS needs compression without linking zlib (C dependency) or shelling to gzip. Sankoch provides the canonical compression interface for the ecosystem — every crate that needs compression uses sankoch instead of rolling its own.

The critical path: LZ4 for immediate AGNOS use, then DEFLATE for a sovereign git implementation.

## License

GPL-3.0-only
