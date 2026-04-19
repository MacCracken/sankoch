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
cyrius deps                              # resolve stdlib into lib/
cyrius build src/lib.cyr build/sankoch   # compile-check
cyrius test tests/tcyr/sankoch.tcyr      # 5897 assertions
cyrius bench tests/bcyr/sankoch.bcyr     # throughput + sizes
cyrius distlib                           # → dist/sankoch.cyr
```

Full command reference: [`docs/development/cyrius-usage.md`](docs/development/cyrius-usage.md).

## Architecture

| File | Lines | Role |
|------|-------|------|
| types.cyr | 36 | Enums: formats, errors, limits, magic bytes |
| checksum.cyr | 189 | Adler-32, CRC-32, xxHash32 (inline) |
| bitreader.cyr | 99 | LSB-first bit-stream reader |
| bitwriter.cyr | 142 | LSB-first bit-stream writer |
| huffman.cyr | 491 | Huffman build/decode, fixed + optimal trees |
| lz77.cyr | 124 | Sliding window match-finder |
| lz4.cyr | 457 | LZ4 block + frame compress/decompress |
| deflate.cyr | 1257 | DEFLATE de/compress, multi-block, dict |
| zlib.cyr | 102 | RFC 1950 wrapper + FDICT |
| gzip.cyr | 159 | RFC 1952 wrapper + concatenated members |
| stream.cyr | 124 | Streaming API |
| lib.cyr | 115 | Include chain + public API + thread safety |

~3300 lines of Cyrius. 6031 assertions across 2 test suites.

## Toolchain

Cyrius 5.4.7 (pinned in `cyrius.cyml`).

## Why

AGNOS needs compression without linking zlib (C dependency) or shelling to gzip. Sankoch provides the canonical compression interface for the ecosystem — every crate that needs compression uses sankoch instead of rolling its own.

The critical path: LZ4 for immediate AGNOS use, then DEFLATE/zlib for a sovereign git implementation.

## License

GPL-3.0-only
