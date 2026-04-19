# Sankoch Development Roadmap

> **Status**: Stable (v1.5.0) | **Last Updated**: 2026-04-19

---

## v2.0.0 track — Performance and Streaming

Shipping the four major items as minor bumps rather than one big 2.0.0
drop — smaller bites, easier bisection if regressions surface, each
feature goes live as soon as it's ready. 2.0.0 gets cut when the stack
is complete.

### ✅ v1.5.0 — Adaptive DEFLATE block splitting (shipped 2026-04-19)

Dynamic-Huffman path now emits multiple adaptive sub-blocks per caller
chunk, flushing when the shared symbol buffer fills. Each sub-block
ships its own optimal tree tuned to its own frequencies. Replaces the
1.4.0- fallback-to-fixed downgrade.

**Impact shipped:** 64K random −4.8%; 256K random went from
`-ERR_BUFFER_TOO_SMALL` to valid output. No regression on the 26
high-locality text bench sizes.

### 🚧 v1.6.0 — LZ4 multi-block frames

Current `lz4f_compress` emits a single block per frame regardless of
input size. The reference `lz4` CLI chunks inputs over 64KB into
multiple 64KB blocks within the same frame. Wrapper-level change in
`lz4.cyr` (`lz4f_compress` / `lz4f_decompress` already handle the
frame envelope, just not multi-block bodies).

**Impact**: byte-identical output to `lz4` CLI on inputs >64KB;
unlocks streaming-like LZ4F consumption patterns.

### 🚧 v1.7.0 — True incremental DEFLATE streaming

Today's `stream_compress_finish` buffers the whole input then
compresses in one shot. True incremental streaming means the
compressor emits DEFLATE bytes as each `stream_compress_write` chunk
arrives. Requires `deflate.cyr` to expose a "consume up to N bytes,
emit what's ready" API and `stream.cyr` to be re-architected around
that state machine.

**Impact**: required for compressing data larger than available
memory; also unblocks network-streaming consumers.

### ⏸ Deferred — SIMD CRC-32 via `PCLMULQDQ`

4–10× CRC-32 speedup on x86_64 via the `PCLMULQDQ` carry-less multiply
instruction. Gated on Cyrius exposing an inline-asm / intrinsic
mechanism — 5.4.7 does not. Current table-driven CRC-32 runs at ~278
MB/s on 4KB, which is fine for the consumers we have today. Revisit
when Cyrius ships asm support.

---

## Scaffold follow-ups (parallel to v2.0.0 track)

### `cyrius fmt` in-place mode

Fmt gate prints formatted source to stdout; applying fixes requires a
shell one-liner. `cyrius fmt --write` in 5.4.7 is a no-op (prints to
stdout like `--check`). Adopt once the flag actually writes.

### Multi-profile distlib (kernel-safe subset)

Yukti 1.3.0 ships a `dist/yukti-core.cyr` profile for bare-metal AGNOS
kernel use. Sankoch's analog: an LZ4-only (no alloc, no stdlib) subset
for initrd decompression in the kernel itself. Would require
refactoring the LZ4 match-finder hash table off the heap onto a
caller-provided workspace, and stripping the mutex. Not obviously
needed yet — the AGNOS initrd loader hasn't asked — track as the next
"hardening" step once a consumer wants it.

### Cross-arch aarch64 builds

Yukti 2.1.1 added `cyrius build --aarch64` to CI. Sankoch is
pure-compute (no syscalls in `src/`), so the x86 build is already
trivially portable — but shipping prebuilt aarch64 binaries + an
`aarch64` ELF check in CI would match the first-party pattern.

---

## Future (separate crate or major version)

- **Zstandard** — tANS + LZ77. Shravan's Opus range encoder (`opus.cyr:175-284`) is the entropy coding primitive tANS generalizes from. ~30K lines in reference impl. Research Duda's ANS paper (arXiv:1311.2540) first.
- **LZMA** — LZ77 + range coding + LPC prediction. Shravan's FLAC LPC decoder (`flac.cyr:517-580`) is the prediction stage. The range coder from Opus covers the entropy stage.
- **Brotli** — if web serving needs arise.
- **GPU texture compression** (BC1-BC7, ASTC) — mabda has generic compute dispatch (`compute.cyr`). Texture format enums are defined but codecs not yet implemented.

---

## Extraction Sources

Primitives that already exist in the AGNOS ecosystem, mapped to where they live:

| Primitive | Home | File | Lines | Status |
|-----------|------|------|-------|--------|
| Bit-reader (generic) | shravan | main.cyr | 1244-1283 | **Extracted** → bitreader.cyr (LSB-first) |
| Bit-writer (with grow) | shravan/FLAC | flac.cyr | 1007-1147 | **Extracted** → bitwriter.cyr (LSB-first, FLAC-specific stripped) |
| Canonical Huffman decode | shravan/AAC | aac.cyr | 843-873 | **Extracted** → huffman.cyr (DEFLATE codebooks) |
| Rice/Golomb coding | shravan/FLAC | flac.cyr | 367-437 | Reference (future codecs) |
| Range encoder | shravan/Opus | opus.cyr | 175-284 | Reference (future Zstandard/LZMA) |
| LPC prediction | shravan/FLAC | flac.cyr | 517-580 | Reference (future LZMA) |
| GPU compute dispatch | mabda | compute.cyr | 142 lines | Future GPU texture compression |

---

## File Summary

| File | Lines | Role |
|------|-------|------|
| types.cyr | 36 | Enums: formats, errors, limits |
| checksum.cyr | 189 | Adler-32, CRC-32, xxHash32 |
| bitreader.cyr | 99 | LSB-first bit-stream reader |
| bitwriter.cyr | 142 | LSB-first bit-stream writer |
| huffman.cyr | 491 | Huffman build/decode, fixed trees, optimal tree construction |
| lz4.cyr | 457 | LZ4 block + frame compress/decompress |
| lz77.cyr | 124 | Sliding window match-finder |
| deflate.cyr | 1257 | DEFLATE decompress + compress, multi-block, dictionary support |
| zlib.cyr | 102 | RFC 1950 wrapper + FDICT dictionary support |
| gzip.cyr | 159 | RFC 1952 wrapper + concatenated member support |
| lib.cyr | 115 | Public API, thread safety |
| stream.cyr | 124 | Streaming compress/decompress |
| **Total** | **3295** | |

Tests: 48 functions in sankoch.tcyr (856 lines) + git_object.tcyr (119 lines)
Assertions: 5897 + 134 = 6031 total

## Dependencies

**Zero.** Checksums (Adler-32, CRC-32) are inline. No sigil dependency. No stdlib beyond what `[deps.stdlib]` in `cyrius.cyml` provides.

## Key References

- RFC 1951 — DEFLATE Compressed Data Format Specification
- RFC 1950 — ZLIB Compressed Data Format Specification
- RFC 1952 — GZIP File Format Specification
- LZ4 Block Format — github.com/lz4/lz4/blob/dev/doc/lz4_Block_format.md
- Feldspar, "An Explanation of the Deflate Algorithm" — clearest DEFLATE walkthrough
- Duda, "Asymmetric Numeral Systems" (arXiv:1311.2540) — for future Zstandard work

---

*Last Updated: 2026-04-19*
