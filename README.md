# Sankoch — Lossless Compression for AGNOS

> Sanskrit: संकोच — contraction, compression

Sovereign lossless compression library written in Cyrius. Zero external
dependencies. Zero C FFI. Ships as `lib/sankoch.cyr` in the Cyrius
standard library (landing in the next Cyrius lang release).

## Formats

| Format          | Constant         | Batch | Streaming | Reference-CLI verified |
|-----------------|------------------|:-----:|:---------:|:----------------------:|
| LZ4 block       | `FORMAT_LZ4`     | ✓     | —         | (block format — no CLI) |
| LZ4 frame       | `FORMAT_LZ4F`    | ✓     | ✓         | `lz4 -dc`              |
| DEFLATE (raw)   | `FORMAT_DEFLATE` | ✓     | ✓         | (wrapped via zlib/gzip) |
| zlib            | `FORMAT_ZLIB`    | ✓     | ✓         | Python `zlib.decompress` |
| gzip            | `FORMAT_GZIP`    | ✓     | ✓         | `gunzip`               |

## API

### Batch

```cyr
compress(format, src, src_len, dst, dst_cap)           -> bytes or -err
compress_level(format, src, src_len, dst, dst_cap, lv) -> bytes or -err
decompress(format, src, src_len, dst, dst_cap)         -> bytes or -err
detect_format(src, src_len)                             -> Format or -err
```

### Streaming (v1.7.0+)

```cyr
var ctx = <fmt>_enc_init(level, dst, dst_cap)  # per format, or via stream.cyr
<fmt>_enc_write(ctx, chunk, len)               # feed input incrementally
var total = <fmt>_enc_finish(ctx)              # flush + close
```

Format-agnostic wrappers in `stream.cyr`:

```cyr
stream_compress_init(format, level, dst, dst_cap)   -> ctx
stream_write(ctx, chunk, len)
stream_compress_finish(ctx)                         -> bytes or -err
```

Incremental Adler-32, CRC-32, and xxHash32 checksum APIs
(`<name>_init` / `_update` / `_final`) are exposed for callers who
want to feed their own data streams.

## Build

```sh
cyrius deps                              # resolve stdlib into lib/
cyrius build src/lib.cyr build/sankoch   # compile-check
cyrius test tests/tcyr/sankoch.tcyr      # 1,028,625 assertions
cyrius test tests/tcyr/git_object.tcyr   # 346,583 assertions
cyrius fuzz                              # all 6 harnesses, 1,649 iters
cyrius bench tests/bcyr/sankoch.bcyr     # throughput + sizes
cyrius distlib                           # → dist/sankoch.cyr
```

Full command reference: [`docs/development/cyrius-usage.md`](docs/development/cyrius-usage.md).

## Architecture

| File          | Lines | Role |
|---------------|------:|------|
| types.cyr     |    37 | Enums: formats, errors, limits, magic bytes |
| checksum.cyr  |   508 | Adler-32, CRC-32, xxHash32 — batch + incremental |
| bitreader.cyr |    99 | LSB-first bit-stream reader |
| bitwriter.cyr |   143 | LSB-first bit-stream writer |
| huffman.cyr   |   661 | Huffman build/decode, fixed + optimal trees, encoder pre-reversed codes |
| lz77.cyr      |   161 | Sliding window match-finder, 8-byte word-compare match extend, rebase |
| lz4.cyr       |   647 | LZ4 block + frame de/compress + streaming enc |
| deflate.cyr   |  1600 | DEFLATE de/compress, adaptive blocks, streaming enc, dict |
| zlib.cyr      |   169 | RFC 1950 wrapper + FDICT + streaming enc |
| gzip.cyr      |   237 | RFC 1952 wrapper + concatenated members + streaming enc |
| stream.cyr    |   162 | Streaming dispatch |
| lib.cyr       |   150 | Include chain + public API + thread safety |

**4,574 lines** of Cyrius. **1,375,208 assertions** across 2 test
suites + **1,649 fuzz iterations** across 6 harnesses. Distlib:
`dist/sankoch.cyr` at 4,597 lines, zero deps.

## Toolchain

Cyrius 5.6.42 (pinned in `cyrius.cyml`).

## Why

AGNOS needs compression without linking zlib (C dependency) or
shelling to gzip. Sankoch provides the canonical compression interface
for the ecosystem — every crate that needs compression uses sankoch
instead of rolling its own.

The critical path: LZ4 for immediate AGNOS use (initrd, snapshots,
pack cache), DEFLATE/zlib for a sovereign git implementation
(`git clone` / `fetch` / `push`), gzip for archive interchange,
streaming for anything that doesn't fit in memory.

## License

GPL-3.0-only
