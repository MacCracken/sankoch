# Sankoch — Lossless Compression for AGNOS

> Sanskrit: संकोच — contraction, compression

Sovereign lossless compression library written in Cyrius. Zero external
dependencies. Zero C FFI. Ships as `lib/sankoch.cyr` in the Cyrius
standard library (toolchain pin in [`cyrius.cyml`](cyrius.cyml); current
release in [`VERSION`](VERSION)).

## Formats

| Format          | Constant         | Batch | Streaming | Reference-CLI verified |
|-----------------|------------------|:-----:|:---------:|:----------------------:|
| LZ4 block       | `FORMAT_LZ4`     | ✓     | —         | (block format — no CLI) |
| LZ4 frame       | `FORMAT_LZ4F`    | ✓     | ✓         | `lz4 -dc`              |
| DEFLATE (raw)   | `FORMAT_DEFLATE` | ✓     | ✓         | (wrapped via zlib/gzip) |
| zlib            | `FORMAT_ZLIB`    | ✓     | ✓         | Python `zlib.decompress` |
| gzip            | `FORMAT_GZIP`    | ✓     | ✓         | `gunzip`               |
| xz / LZMA2      | `FORMAT_XZ`      | ✓     | —         | `xz -dc` / `xz -d`     |

xz is a **full codec** — decode (`xz_decompress` / `FORMAT_XZ`, v2.4.0+)
and encode (`xz_compress` / `compress(FORMAT_XZ, …)`, v2.4.1+). `.xz`
container + LZMA2 + LZMA range coder both ways, with CRC-32 / CRC-64
checks. The encoder uses an optimal (price-table) parse; `xz -d` decodes
its output. Within a few percent of `xz -6` on text/code (it does not
claim bit-identical parity).

## API

### Batch

```cyr
compress(format, src, src_len, dst, dst_cap)           -> bytes or -err
compress_level(format, src, src_len, dst, dst_cap, lv) -> bytes or -err
decompress(format, src, src_len, dst, dst_cap)         -> bytes or -err
detect_format(src, src_len)                             -> Format or -err
```

### Streaming encode (v1.7.0+, preset-dict v2.2.0+)

```cyr
var ctx = <fmt>_enc_init(level, dst, dst_cap)  # per format, or via stream.cyr
<fmt>_enc_write(ctx, chunk, len)               # feed input incrementally
var total = <fmt>_enc_finish(ctx)              # flush + close

# Preset dictionary (deflate / zlib / gzip) — preloads the LZ77 window
# so back-references can reach into dict territory. Decoder must apply
# the same dict via `<fmt>_decompress_dict`. zlib emits an FDICT-bearing
# header + DICTID; gzip's wire format has no FDICT, so dict-warmed
# gzip is a private contract between matching encoder/decoder pairs.
var ctx = <fmt>_enc_init_dict(level, dst, dst_cap, dict, dict_len)
```

### Streaming decode (v2.3.0+)

```cyr
var ctx = <fmt>_dec_init(dst, dst_cap)         # per format
<fmt>_dec_write(ctx, chunk, len)               # feed compressed input incrementally
var total = <fmt>_dec_finish(ctx)              # validate trailer, return total bytes
```

Output bytes flow into `dst` as compressed input arrives. Available for
DEFLATE, zlib, gzip, and LZ4F. FDICT zlib + concatenated-member gzip
streaming are deferred to a 2.3.x patch (see roadmap).

### Format-agnostic dispatch (in `stream.cyr`)

```cyr
stream_compress_init(format, level, dst, dst_cap)        -> ctx
stream_decompress_init_inc(format, dst, dst_cap)         -> ctx  # v2.3.0+
stream_write(ctx, chunk, len)
stream_compress_finish(ctx)                              -> bytes or -err
stream_decompress_finish_inc(ctx)                        -> bytes or -err
```

The legacy buffered `stream_decompress_init(format)` + `stream_decompress_finish(ctx, dst, dst_cap)` path is also still supported.

Incremental Adler-32, CRC-32, and xxHash32 checksum APIs
(`<name>_init` / `_update` / `_final`) are exposed for callers who
want to feed their own data streams.

## Build

```sh
cyrius deps                              # resolve stdlib into lib/
cyrius build src/lib.cyr build/sankoch   # compile-check
cyrius test                              # all tcyr suites (auto-discovered)
cyrius test tests/tcyr/xz_compress.tcyr  # one split suite (codec × direction)
cyrius fuzz                              # all fuzz harness functions
cyrius bench tests/bcyr/sankoch.bcyr     # throughput + sizes
cyrius distlib                           # → dist/sankoch.cyr (full)
cyrius distlib core                      # → dist/sankoch-core.cyr (kernel-safe)
```

Full command reference: [`docs/guides/cyrius-usage.md`](docs/guides/cyrius-usage.md).
Current test / assertion / line totals live in [`docs/development/state.md`](docs/development/state.md).

## Architecture

| File           | Role                                                                                  | Profile |
|----------------|---------------------------------------------------------------------------------------|---------|
| types.cyr      | Enums: formats, errors, limits, magic bytes                                            | core    |
| xxhash32.cyr   | xxHash32 batch (helpers + enum)                                                        | core    |
| lz4_decode.cyr | LZ4 block + frame decompress + LZ4F enum                                               | core    |
| checksum.cyr   | Adler-32, CRC-32 (slice-by-8), CRC-64/XZ, xxHash32 batch + incremental state APIs      | full    |
| bitreader.cyr  | LSB-first bit-stream reader                                                            | full    |
| bitwriter.cyr  | LSB-first bit-stream writer                                                            | full    |
| huffman.cyr    | Huffman build/decode, fixed + optimal trees, encoder pre-reversed codes                | full    |
| lz77.cyr       | Sliding window match-finder, 8-byte word-compare match extend, rebase                  | full    |
| lz4.cyr        | LZ4 block + frame compress + `lz4f_enc_*` + `lz4f_dec_*` streaming                     | full    |
| deflate.cyr    | DEFLATE de/compress, adaptive blocks, `deflate_enc_*` + `deflate_dec_*`, dict          | full    |
| zlib.cyr       | RFC 1950 wrapper + FDICT batch + `zlib_enc_*` + `zlib_dec_*` streaming                 | full    |
| gzip.cyr       | RFC 1952 wrapper + concatenated batch + `gzip_enc_*` + `gzip_dec_*` streaming          | full    |
| xz.cyr         | `.xz` de/compress — container + LZMA2 + LZMA range coder, optimal-parse encoder        | full    |
| stream.cyr     | Streaming dispatch (compress + buffered/incremental decompress)                        | full    |
| lib.cyr        | Include chain + public API + `_sankoch_mtx` two-tier lock dispatch                    | full    |

`core` modules form the `[lib.core]` profile → `dist/sankoch-core.cyr` (kernel-safe LZ4 batch decompress; no `alloc`, no syscalls, no mutex). Verified by `programs/core_smoke.cyr` (a CI tripwire that links only the core subset and asserts decompress still works).

Per-file line counts, test totals, and distlib sizes for the current release live in [`docs/development/state.md`](docs/development/state.md). Most of sankoch's headline assertion count is per-byte round-trip verification on multi-KB streaming inputs — see [`docs/guides/cyrius-usage.md`](docs/guides/cyrius-usage.md#what-assertions-means-here-and-why-the-number-is-so-large) for what the number actually measures.

## Toolchain

Cyrius — pinned in [`cyrius.cyml [package].cyrius`](cyrius.cyml). CI and release both read the pin from the manifest.

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
