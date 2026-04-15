# Sankoch — Lossless Compression for AGNOS

> Sanskrit: संकोच — contraction, compression

Sovereign lossless compression library written in Cyrius. Zero external dependencies. Zero C FFI.

## Algorithms

| Algorithm | Phase | Status | Use Case |
|-----------|-------|--------|----------|
| LZ4 block | 1 | **Done** | Fast internal compression (initrd, snapshots, pack cache) |
| DEFLATE | 2-3 | **Done** | Git compatibility (clone, fetch, push) |
| zlib | 4 | **Done** | Git object format |
| gzip | 4 | **Done** | Archive interchange |

## API

```
compress(format, src, src_len, dst, dst_cap)   -> compressed_len or negative error
decompress(format, src, src_len, dst, dst_cap)  -> decompressed_len or negative error
detect_format(src, src_len)                      -> Format enum or negative error
```

Formats: `FORMAT_LZ4`, `FORMAT_DEFLATE`, `FORMAT_ZLIB`, `FORMAT_GZIP`

## Build

```sh
cyrius build src/lib.cyr build/sankoch
cyrius test
```

## Architecture

| File | Lines | Role |
|------|-------|------|
| types.cyr | 35 | Enums: formats, errors, limits |
| checksum.cyr | 56 | Adler-32, CRC-32 |
| lz4.cyr | 266 | LZ4 block compress + decompress |
| bitreader.cyr | 89 | LSB-first bit-stream reader |
| huffman.cyr | 309 | Huffman build/decode, fixed trees |
| deflate.cyr | 617 | DEFLATE decompress + compress |
| bitwriter.cyr | 141 | LSB-first bit-stream writer |
| lz77.cyr | 98 | Sliding window match-finder |
| zlib.cyr | 76 | RFC 1950 wrapper |
| gzip.cyr | 120 | RFC 1952 wrapper |
| lib.cyr | 74 | Public API |

1881 lines of Cyrius. 24 tests.

## Why

AGNOS needs compression without linking zlib (C dependency) or shelling to gzip. Sankoch provides the canonical compression interface for the ecosystem — every crate that needs compression uses sankoch instead of rolling its own.

The critical path: LZ4 for immediate AGNOS use, then DEFLATE/zlib for a sovereign git implementation.

## License

GPL-3.0-only
