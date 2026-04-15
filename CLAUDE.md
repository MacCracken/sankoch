# Sankoch — Claude Code Instructions

## Project Identity

**Sankoch** (Sanskrit: संकोच — contraction, compression) — Lossless compression library for AGNOS

- **Type**: Shared library crate (Cyrius-native, no Rust port)
- **License**: GPL-3.0-only
- **Version**: SemVer `0.D.M` pre-1.0
- **Version file**: `VERSION` at repo root (single source of truth)
- **Genesis repo**: [agnosticos](https://github.com/MacCracken/agnosticos)
- **Standards**: [First-Party Standards](https://github.com/MacCracken/agnosticos/blob/main/docs/development/applications/first-party-standards.md)
- **Recipes**: [zugot](https://github.com/MacCracken/zugot) — takumi build recipes

## What This Crate Does

Sankoch provides lossless compression and decompression for the AGNOS ecosystem. Zero external dependencies. Zero C FFI. All algorithms implemented in Cyrius from the specs.

**Algorithms (phased):**

| Algorithm | Format | Spec | Phase | Use Case |
|-----------|--------|------|-------|----------|
| LZ4 | Block | LZ4 block format spec | 1 | Fast internal compression (initrd, pack cache, snapshots) |
| DEFLATE | Bit-stream | RFC 1951 | 2-3 | Git compatibility (clone, fetch, push) |
| zlib | DEFLATE + Adler-32 | RFC 1950 | 4 | Git object format wrapper |
| gzip | DEFLATE + CRC-32 | RFC 1952 | 4 | Archive interchange |

**Not in scope (future crate or future phase):**
- Zstandard (tANS + LZ77 — 30K+ lines reference impl, deserves its own effort)
- Lossy compression (audio/video codecs live in shravan/tarang)
- Encryption (sigil owns all crypto)

## Consumers

| Consumer | Uses | Why |
|----------|------|-----|
| Future git implementation | DEFLATE, zlib | Git objects are zlib-compressed |
| ark | LZ4 or DEFLATE | Package compression |
| AGNOS kernel | LZ4 | initrd, kernel snapshots |
| shravan | DEFLATE/gzip | Container formats embedding compressed streams |
| tarang | DEFLATE/gzip | Same |
| Any crate needing compression | All | Replaces zlib FFI / shelling to gzip |

## Architecture

```
src/
  lib.cyr          — Public API: compress(), decompress(), format detection
  lz4.cyr          — LZ4 block compress/decompress (Phase 1)
  deflate.cyr      — DEFLATE decompress (Phase 2), compress (Phase 3)
  huffman.cyr      — Huffman tree build, canonical Huffman, fixed trees
  bitreader.cyr    — Bit-stream reader (DEFLATE is not byte-aligned)
  bitwriter.cyr    — Bit-stream writer (for DEFLATE compression)
  lz77.cyr         — LZ77 match-finder (sliding window, hash table)
  zlib.cyr         — zlib wrapper: DEFLATE + Adler-32 (Phase 4)
  gzip.cyr         — gzip wrapper: DEFLATE + CRC-32 (Phase 4)
  checksum.cyr     — Adler-32 and CRC-32 (inline, not from sigil)
  types.cyr        — Shared types, error codes, format constants
```

### Key Design Decisions

- **This is an extraction, not greenfield.** Most primitives already exist in shravan (audio codecs). The work is factoring them out, generalizing, and adding the LZ77 sliding window + zlib wrapper that shravan doesn't need.
- **Checksums are inline, not from sigil.** Adler-32 and CRC-32 are tiny (~30 lines each), part of the compression format specs, and used in the inner loop. Pulling sigil as a dependency for two 30-line functions adds coupling for no benefit.
- **LZ4 first.** Byte-aligned, simple format, proves the compress/decompress infrastructure. ~500 lines. No extraction needed — LZ4 is new.
- **Bit-reader is the critical abstraction.** DEFLATE codes straddle byte boundaries. Shravan already has a generic bitreader (`main.cyr:1244-1283`) and FLAC bitwriter (`flac.cyr:1007-1147`). Lift and generalize.
- **Fixed Huffman trees before dynamic.** DEFLATE has two modes — fixed trees are hardcoded in the spec, dynamic trees are transmitted in the stream header. Implement fixed first, test it, then add dynamic.

### Extraction Map (from shravan)

| Primitive | Source | File:Lines | Generalize? |
|-----------|--------|-----------|-------------|
| Bit-reader (generic) | shravan | main.cyr:1244-1283 | Lift as-is, add DEFLATE LSB-first mode |
| Bit-writer | shravan/FLAC | flac.cyr:1007-1147 | Lift, strip FLAC-specific (unary, UTF-8) |
| Canonical Huffman decode | shravan/AAC | aac.cyr:843-873 | Lift structure, replace AAC codebooks with DEFLATE tables |
| Rice/Golomb coding | shravan/FLAC | flac.cyr:367-437 | Reference only — not needed for DEFLATE/LZ4, useful for future codecs |
| Range encoder | shravan/Opus | opus.cyr:175-284 | Reference only — needed for future Zstandard (tANS) |
| FFT/MDCT | shravan | fft.cyr:29-356 | Not needed for lossless compression, but relevant for transform codecs |

**What's genuinely new (not in shravan):**
- LZ4 block format (byte-aligned, no bit I/O)
- LZ77 sliding window match-finder (hash table on 3-byte sequences)
- DEFLATE block framing (3 block types, length/distance code tables)
- zlib/gzip wrappers (headers + checksums)

### GPU Compute (future)

mabda has generic GPU compute dispatch (`compute.cyr`, 142 lines) — pipeline creation, bind groups, dispatch. Currently no texture compression codecs (BC1-BC7, ASTC are backlogged). When GPU-accelerated compression lands, it uses mabda's dispatch infrastructure.

## Development Process

### Work Loop (continuous)

1. Work phase — implement algorithm, add tests, add benchmarks
2. Build: `cyrius build src/lib.cyr build/sankoch`
3. Test: `cyrius test`
4. Benchmark: throughput (MB/s) and ratio for each algorithm
5. Audit: verify against spec (RFC 1951, LZ4 block format)
6. Documentation — update CHANGELOG, roadmap, docs
7. Version check — VERSION and docs all in sync
8. Return to step 1

### Task Sizing

- **Low/Medium effort**: Batch freely — multiple items per work loop cycle
- **Large effort**: Small bites only — break into sub-tasks, verify each before moving to the next
- **If unsure**: Treat it as large

## DO NOT

- **Do not commit or push** — the user handles all git operations
- **NEVER use `gh` CLI** — use `curl` to GitHub API only
- Do not add unnecessary dependencies (target: ZERO deps for v0.1)
- Do not implement Zstandard in this crate — it deserves its own
- Do not depend on sigil for checksums — Adler-32/CRC-32 are inline
- Do not skip spec verification — every DEFLATE test must round-trip against known-good zlib output
- **Study the RFCs** before writing code — RFC 1951 is the DEFLATE bible

## Key Implementation Notes

### LZ4 (Phase 1)
- Byte-aligned format — no bit-reader needed
- Block format only (not frame format)
- Hash table match-finder keyed on 4-byte sequences
- Minimum match length: 4 bytes
- Decompress is ~200 lines, compress is ~300 lines

### DEFLATE (Phase 2-3)
- **Bit-stream, not byte-stream.** Huffman codes straddle byte boundaries.
- Bit-reader reads LSB-first (least significant bit first)
- Three block types: uncompressed (00), fixed Huffman (01), dynamic Huffman (10)
- Fixed Huffman trees are defined in RFC 1951 Section 3.2.6
- Dynamic trees: HLIT, HDIST, HCLEN header → code length alphabet → literal/length and distance trees
- Sliding window: 32KB (32768 bytes)
- Match-finder: hash table on 3-byte sequences, chain for collision resolution
- Length codes: 257-285 map to lengths 3-258 (with extra bits)
- Distance codes: 0-29 map to distances 1-32768 (with extra bits)

### Checksums (Phase 4)
- **Adler-32**: Two running sums (s1, s2) mod 65521. ~15 lines.
- **CRC-32**: Table-driven, 256-entry lookup table. ~30 lines + table.

## Testing Strategy

- **Round-trip tests**: compress then decompress, verify identical
- **Known-vector tests**: decompress known-good compressed data (from zlib/gzip tools on the host)
- **Fuzz**: random data of varying sizes, verify round-trip
- **Spec compliance**: DEFLATE output must be decompressible by standard zlib
- **Edge cases**: empty input, single byte, all-same bytes, incompressible random data, maximum match lengths
- **Benchmarks**: MB/s throughput at various data sizes (1KB, 64KB, 1MB, 16MB), compression ratio vs input type (text, binary, random)

## Documentation Structure

```
Root files (required):
  README.md, CHANGELOG.md, CLAUDE.md, CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md, LICENSE

docs/ (required):
  development/roadmap.md — phased milestones through v1.0
  sources/compression.md — RFC citations, algorithm references, key papers

docs/ (when earned):
  adr/ — architectural decision records
  audit/ — security audit reports
  guides/ — integration patterns
  benchmarks-rust-v-cyrius.md — N/A (Cyrius-native, no Rust port)
```

## CHANGELOG Format

Follow [Keep a Changelog](https://keepachangelog.com/). Performance claims MUST include benchmark numbers (MB/s throughput, compression ratio). Breaking changes get a **Breaking** section with migration guide.
