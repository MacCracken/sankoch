# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- **LZ4 block compression** — hash-table match-finder (4096 entries, Knuth multiplicative hash on 4-byte sequences), greedy matching. Compress + decompress functional with real compression.
- **DEFLATE decompression** (RFC 1951) — all three block types: uncompressed (00), fixed Huffman (01), dynamic Huffman (10). Length/distance decoding with extra bits.
- **DEFLATE compression** (RFC 1951) — fixed Huffman codes with LZ77 sliding window match-finder (32KB window, 3-byte hash, 64-deep chain search).
- **Huffman coding** — canonical Huffman code construction, 9-bit fast lookup table decode, fixed tree tables from RFC 1951 Section 3.2.6, dynamic tree header parsing (HLIT/HDIST/HCLEN, repeat codes 16/17/18).
- **Bit-stream I/O** — LSB-first bit reader and writer for DEFLATE. Lifted from shravan (audio codecs), adapted from MSB-first to LSB-first.
- **LZ77 match-finder** — 32KB sliding window, hash table with chaining, configurable chain depth.
- **zlib wrapper** (RFC 1950) — compress + decompress with CMF/FLG header validation and Adler-32 checksum verification.
- **gzip wrapper** (RFC 1952) — compress + decompress with full header parsing (FEXTRA, FNAME, FCOMMENT, FHCRC), CRC-32 + ISIZE verification.
- **Checksums** — Adler-32 (RFC 1950) and CRC-32 (RFC 1952), inline implementations.
- **Format auto-detection** — detect_format() identifies gzip (magic bytes) and zlib (CMF/FLG checksum).
- **Public API** — compress(), decompress(), detect_format() supporting LZ4, DEFLATE, zlib, gzip.
- **Test suite** — 24 tests covering checksums, LZ4, DEFLATE (known vectors from zlib), zlib, gzip, format detection, round-trips with compression ratio assertions.
- Project scaffold — CLAUDE.md, roadmap, source citations, directory structure
- Cyrius-native from day one (no Rust port)
