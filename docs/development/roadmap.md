# Sankoch Development Roadmap

> **Status**: Stable (v2.0.0) | **Last Updated**: 2026-04-19

---

## v2.0.0 — shipped 2026-04-19

Four-item v2.0.0 track landed as incremental minor bumps, then cut to
2.0.0 after a P(-1) pass. Declares the LZ4 + DEFLATE + zlib + gzip
surface stable. No API changes in 2.0.0 itself — just a closeout pass
(two LOW audit findings fixed, dead accessors removed, docs swept).
See `docs/audit/2026-04-19-pre-2.0.0.md`.

### ✅ v1.5.0 — Adaptive DEFLATE block splitting (shipped 2026-04-19)

Dynamic-Huffman path now emits multiple adaptive sub-blocks per caller
chunk, flushing when the shared symbol buffer fills. Each sub-block
ships its own optimal tree tuned to its own frequencies. Replaces the
1.4.0- fallback-to-fixed downgrade.

**Impact shipped:** 64K random −4.8%; 256K random went from
`-ERR_BUFFER_TOO_SMALL` to valid output. No regression on the 26
high-locality text bench sizes.

### ✅ v1.6.0 — LZ4 multi-block frames (shipped 2026-04-19)

`lz4f_compress` now chunks inputs into ≤64KB blocks per the BD byte
instead of emitting a single oversized block. Each chunk compresses
independently (B.Indep=1) and falls back to an uncompressed block
per-chunk when needed. `lz4f_decompress` needed no change — its
block-size loop already handled multi-block frames.

**Impact shipped:** 128K text = 647B (2 blocks), 256K text = 1279B
(4 blocks), 128K random = 131095B (2 uncompressed blocks — validates
the per-chunk fallback path). Reference `lz4` CLI now accepts our
output.

### ✅ v1.6.1 — xxHash32 spec compliance + P(-1) hardening (shipped 2026-04-19)

P(-1) audit before v1.7.0 uncovered that our `xxhash32` was the
short-length variant only and used PRIME2 instead of PRIME4 in the
4-byte tail. Compressor and decompressor were self-consistent but
reference `lz4` CLI rejected our output. Fixed the hash, added 9
known-vector tests (from `xxh32sum`), validated end-to-end against
`lz4 -dc`. Breaking wire-format change; no shipping downstream
consumers yet. See `docs/audit/2026-04-19.md`.

**Tracked for v1.7.0:** direct-entry APIs (`lz4f_compress`,
`zlib_*_dict`, `deflate_*_dict`, `stream_*`) bypass the public mutex
— fix lands alongside the streaming refactor that release needs
anyway.

### ✅ v1.7.0 — True incremental streaming + MED-01 (shipped 2026-04-19)

Today's `stream_compress_finish` buffers the whole input then
compresses in one shot. True incremental streaming means the
compressor emits output bytes as each `stream_write` chunk arrives.
Scope for 1.7.0 is **all four formats**: DEFLATE (foundation),
zlib/gzip (thin wrappers over DEFLATE with incremental Adler-32 /
CRC-32 trailers), and LZ4F (multi-block frame with per-block emit,
leveraging B.Indep=1).

**Design decisions locked (2026-04-19):**
- Per-format incremental API: `<fmt>_enc_init(level, dst, dst_cap)` →
  `<fmt>_enc_write(ctx, chunk, len)` → `<fmt>_enc_finish(ctx)` →
  `total_bytes_written`. `deflate_enc_*` is the foundation; zlib/gzip
  wrap it; `lz4f_enc_*` wraps `lz4_compress` per 64KB block.
- Encoder owns a 64 KB sliding window; slides every 32 KB of new
  input; rebases `_lz77_head`/`_lz77_prev` on each slide (accept
  ~16 B/input-byte rebase cost for first cut; ring-buffer rewrite of
  match-finder deferred to 1.7.x if benchmarks justify).
- Lazy matching disabled in streaming fixed path (levels ≤3 — greedy
  only). Level ≥4 dynamic path is already greedy; no change there.
- BFINAL choreography: `enc_write` always emits BFINAL=0; `enc_finish`
  always emits one final sub-block with BFINAL=1 (even if the symbol
  buffer is empty — trivial BFINAL=1 stored block with LEN=0).
- Dynamic-path block emit refactored into three primitives
  (`_dyn_reset`, `_dyn_collect_at`, `_dyn_flush_subblock`) so the
  batch path and streaming path share the sub-block code.
- Incremental xxhash32 API added (`xxhash32_init` / `_update` /
  `_final`) for LZ4F content-checksum streaming; batch `xxhash32`
  stays for callers who have the full input.
- **Bundles MED-01 fix**: public direct-entry APIs (`lz4f_*`,
  `zlib_*`, `gzip_*`, `deflate_*`, `stream_*`) get the two-tier
  public/internal split so they can safely take `_sankoch_mtx`
  without recursing through batch `compress()`. Single mutex held
  from `enc_init` to `enc_finish`; concurrent encoders serialize.
  Single-threaded contract: a live encoder precludes other
  `compress`/`decompress` calls on the same thread until `finish`.

**Impact**: required for compressing data larger than available
memory; also unblocks network-streaming consumers and closes the
MED-01 thread-safety gap from the 2026-04-19 audit.

### ⏸ Deferred — SIMD CRC-32 via `PCLMULQDQ`

4–10× CRC-32 speedup on x86_64 via the `PCLMULQDQ` carry-less multiply
instruction. Gated on Cyrius exposing an inline-asm / intrinsic
mechanism — 5.4.7 does not. Current table-driven CRC-32 runs at ~278
MB/s on 4KB, which is fine for the consumers we have today. Revisit
when Cyrius ships asm support.

---

## v2.x candidates (post-2.0.0, no commitment yet)

Follow-ups that don't change the public API and don't require a
major-version bump. Each lands in its own 2.x point release when
there's a reason to prioritize it:

- **True incremental decompression** — mirror the streaming encoder
  work on the decompression side. The current buffered model
  (`stream_decompress_*` accumulates compressed input then batch-
  decompresses) is fine for most consumers but doesn't help when
  decompressed output is larger than memory.
- **Ring-buffer LZ77 match-finder** — replace the window-slide +
  `lz77_rebase` scheme (currently ~16 B/input-byte of rebase
  overhead) with a proper circular buffer that wraps the window.
  Zero slide cost; requires `_lz77_find_match` to handle wrap-around.
- **Preset dictionary in streaming encoders** — `<fmt>_enc_init_dict`
  variants carrying a caller-provided dict (matches existing
  `deflate_decompress_dict` / `zlib_decompress_dict` semantics).
- **Configurable LZ4F block-max size** — today the BD byte is fixed
  to 64 KB; allow 256 KB / 1 MB / 4 MB per the spec.
- **Adler-32 16-byte unroll in `adler32_update`** — mirror the batch
  inner-loop shape for streaming throughput parity (INFO-02 in the
  2026-04-19-pre-2.0.0 audit).
- **Defensive `alloc()` failure handling** in `*_enc_init` — wrap
  alloc + unlock-on-failure helper (INFO-01 in that audit).

---

## Scaffold follow-ups (independent of codec work)

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
