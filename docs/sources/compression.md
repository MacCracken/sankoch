# Compression — Source Citations

Every algorithm in sankoch traces to a published specification or paper.

## Core Specifications

| Spec | Title | Used By | URL |
|------|-------|---------|-----|
| RFC 1951 | DEFLATE Compressed Data Format Specification v1.3 | deflate.cyr, huffman.cyr | https://www.rfc-editor.org/rfc/rfc1951 |
| RFC 1950 | ZLIB Compressed Data Format Specification v3.3 | zlib.cyr | https://www.rfc-editor.org/rfc/rfc1950 |
| RFC 1952 | GZIP File Format Specification v4.3 | gzip.cyr | https://www.rfc-editor.org/rfc/rfc1952 |
| LZ4 Block Format | LZ4 Block Compression Format Description | lz4.cyr | https://github.com/lz4/lz4/blob/dev/doc/lz4_Block_format.md |
| LZ4 Frame Format | LZ4 Frame Format Description (with content checksum + multi-block) | lz4.cyr | https://github.com/lz4/lz4/blob/dev/doc/lz4_Frame_format.md |
| xxHash32 Spec | xxHash32 reference specification (stripe accumulators, primes) | checksum.cyr | https://github.com/Cyan4973/xxHash/blob/dev/doc/xxhash_spec.md |

## Foundational Papers

| Paper | Authors | Year | Relevance |
|-------|---------|------|-----------|
| A Universal Algorithm for Sequential Data Compression | Ziv, Lempel | 1977 | LZ77 — foundation of DEFLATE and LZ4 |
| Compression of Individual Sequences via Variable-Rate Coding | Ziv, Lempel | 1978 | LZ78 — background context |
| A Method for the Construction of Minimum-Redundancy Codes | Huffman | 1952 | Huffman coding — used in DEFLATE |
| Asymmetric Numeral Systems | Duda | 2009 | tANS — future Zstandard work (arXiv:1311.2540) |

## Reference Implementations

| Implementation | Language | Notes |
|----------------|----------|-------|
| zlib (inflate.c, deflate.c) | C | Gailly & Adler — the canonical DEFLATE impl |
| lz4 (lz4.c) | C | Yann Collet — reference LZ4 impl |
| miniz | C | Rich Geldreich — minimal single-file DEFLATE |

## Explanatory Resources

| Resource | Author | Notes |
|----------|--------|-------|
| "An Explanation of the Deflate Algorithm" | Antaeus Feldspar | Clearest walkthrough of DEFLATE internals |
| "Understanding zlib" | Mark Adler (Stack Overflow answers) | Authoritative clarifications from zlib's co-author |

## Checksum Algorithms

| Algorithm | Spec | Used By | Notes |
|-----------|------|---------|-------|
| Adler-32 | RFC 1950, Section 2.2 | zlib.cyr | Two running sums mod 65521; deferred-modulo inner loop with 16-byte unroll (batch) |
| CRC-32   | RFC 1952, Section 8  | gzip.cyr | Polynomial 0xEDB88320 (reflected); 8-byte unrolled table lookup |
| xxHash32 | xxHash spec (Cyan4973) | lz4.cyr (frame format), tests | 4-parallel-stripe accumulator for len ≥ 16; short path for len < 16. PRIME4 in the 4-byte tail — omitting it is a spec-divergent bug we shipped pre-v1.6.1 and have regression-tested against `xxh32sum` since |

All three are also exposed as incremental APIs (`<name>_init` /
`_update` / `_final`) for streaming consumers.
