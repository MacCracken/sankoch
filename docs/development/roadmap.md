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
instruction. Cyrius 5.5.22 exposes raw `asm { byte; byte; … }` blocks
(see `lib/thread.cyr` `_thread_spawn`), so the toolchain gate is
cleared. Not prioritized yet because current table-driven CRC-32 runs
at ~278 MB/s on 4KB, which is fine for the consumers we have today —
revisit if a consumer actually pushes CRC-32 onto the hot path.

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
- ~~**Adler-32 16-byte unroll in `adler32_update`**~~ — **landed in
  the Unreleased / next 2.x point release**. INFO-02 from the
  2026-04-19-pre-2.0.0 audit is closed; streaming zlib now sits
  ~6 % closer to streaming DEFLATE on 128 KB inputs.
- **Defensive `alloc()` failure handling** in `*_enc_init` — wrap
  alloc + unlock-on-failure helper (INFO-01 in that audit).

---

## Scaffold follow-ups (independent of codec work)

### ✅ `cyrfmt` in-place mode — shipped in Cyrius 5.5.22

`cyrfmt --write <file.cyr>` (or `-w`, gofmt convention) reformats in
place. Idempotent — a clean file short-circuits before the write
syscall so mtime doesn't churn. Truncate-and-overwrite (not atomic
temp+rename; Cyrius doesn't expose `sys_rename` yet). Replaces the
prior `cyrfmt x.cyr > x.new && mv x.new x` shell one-liner. The
`cyrius fmt` frontend banner still shows only `[--check]` in 5.5.22
but passes `--write` / `-w` through to the underlying `cyrfmt`
binary — use the direct `cyrfmt` invocation or pass the flag
through `cyrius fmt` either way.

### Multi-profile distlib (kernel-safe subset)

Yukti 1.3.0 ships a `dist/yukti-core.cyr` profile for bare-metal AGNOS
kernel use. Sankoch's analog: an LZ4-only (no alloc, no stdlib) subset
for initrd decompression in the kernel itself. Would require
refactoring the LZ4 match-finder hash table off the heap onto a
caller-provided workspace, and stripping the mutex. Not obviously
needed yet — the AGNOS initrd loader hasn't asked — track as the next
"hardening" step once a consumer wants it.

### 📌 Cross-arch aarch64 builds (pinned — known issue)

**Status**: deferred. First-party parity with Yukti says we should
carry aarch64 cross-builds in CI and release, but there's a current
issue that has to be sorted before wiring it up. Not blocking v2.0.0.

**What Yukti does** (for reference when we revisit):
- CI step: `cyrius build --aarch64 src/main.cyr build/yukti-aarch64`
  (plus the same for programs/ and fuzz/), with a graceful skip if
  `cc5_aarch64` isn't in the toolchain bundle:

  ```yaml
  - name: Cross-build aarch64
    run: |
      if [ ! -x "$HOME/.cyrius/bin/cc5_aarch64" ]; then
        echo "::warning::cc5_aarch64 not shipped with Cyrius $CYRIUS_VERSION"
        exit 0
      fi
      CYRIUS_DCE=1 cyrius build --aarch64 src/main.cyr build/yukti-aarch64
      for bin in build/*-aarch64; do
        file "$bin" | grep -q "aarch64" || { echo "not aarch64 ELF"; exit 1; }
      done
  ```
- Release step: mirrors above with `ship prebuilt aarch64 binary if
  produced` best-effort copy in the archive step.

**Why sankoch hasn't adopted yet**: `cross build is still an issue
right now` (2026-04-19). When the underlying blocker clears, the
work is a straight port of the Yukti pattern above — no sankoch
source changes needed, since `src/` is pure-compute (no direct
syscalls). Revisit this item once the toolchain / cross-compile
path is unblocked.

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

## File Summary (at v2.0.0)

| File | Lines | Role |
|------|-------|------|
| types.cyr     |   37 | Enums: formats (incl. FORMAT_LZ4F), errors, limits |
| checksum.cyr  |  469 | Adler-32 / CRC-32 / xxHash32 — batch + incremental state APIs |
| bitreader.cyr |   99 | LSB-first bit-stream reader |
| bitwriter.cyr |  143 | LSB-first bit-stream writer |
| huffman.cyr   |  499 | Huffman build/decode, fixed trees, optimal tree construction |
| lz77.cyr      |  150 | Sliding window match-finder + `lz77_rebase` for streaming slides |
| lz4.cyr       |  647 | LZ4 block + frame de/compress + `lz4f_enc_*` streaming |
| deflate.cyr   | 1607 | DEFLATE de/compress, adaptive blocks, `deflate_enc_*` streaming, dict |
| zlib.cyr      |  169 | RFC 1950 wrapper + FDICT + `zlib_enc_*` streaming |
| gzip.cyr      |  237 | RFC 1952 wrapper + concatenated members + `gzip_enc_*` streaming |
| lib.cyr       |  150 | Public API, `_sankoch_mtx`, two-tier lock dispatch |
| stream.cyr    |  162 | Streaming dispatch (`stream_compress_init/write/finish` → per-format `_enc_*`) |
| **Total**     | **4369** | |

Assertions: 1028625 (sankoch.tcyr) + 134 (git_object.tcyr) = 1028759 total
Fuzz: 1564 iterations across both harnesses (incl. 204 streaming
round-trips covering all four `_enc_*` encoders)

## Dependencies

**Zero external.** Checksums (Adler-32, CRC-32, xxHash32 — batch and
incremental) are inline. No sigil dependency. Stdlib-only: `syscalls`,
`string`, `alloc`, `fmt`, `vec`, `fnptr`, `thread`, `assert` (all
ship with Cyrius ≥ 5.5.22).

## Key References

- RFC 1951 — DEFLATE Compressed Data Format Specification
- RFC 1950 — ZLIB Compressed Data Format Specification
- RFC 1952 — GZIP File Format Specification
- LZ4 Block Format — github.com/lz4/lz4/blob/dev/doc/lz4_Block_format.md
- Feldspar, "An Explanation of the Deflate Algorithm" — clearest DEFLATE walkthrough
- Duda, "Asymmetric Numeral Systems" (arXiv:1311.2540) — for future Zstandard work

---

*Last Updated: 2026-04-19*
