# 0002 — The Brotli encoder is a separate module in the full bundle only, on the `brotli -q` quality scale

- **Status**: Accepted
- **Date**: 2026-10-13
- **Deciders**: sankoch maintainers

## Context

2.8.0 shipped Brotli *decode* ([0001](0001-brotli-decoder-placement.md)) for rekha's WOFF2, in the
full bundle and the two decode profiles `[lib.brotli]` and `[lib.woff]`. 0001 left encode out of
scope "as its own decision about profiles". 2.8.4 completes the codec, as 2.5.5 completed zstd.

Several things were already true:

- A distlib profile is a module list. The decoder lives in `src/brotli.cyr`, which both decode
  profiles list, so anything added to that file reaches rekha's bundles.
- rekha only reads fonts. No consumer has asked to *write* Brotli from a profile.
- Every other sankoch codec takes a 1..9 level with 6 as the default (`compress()`'s default).
  Brotli's own scale is quality 0..11, and the reference CLI defaults to 11.
- The encoder needs the decoder's context lookup table (RFC 7932 §7.1, 2,048 bytes) and its
  bit-reversal table. Duplicating them would let encoder and decoder disagree silently.

## Decision

**A separate module, `src/brotli_enc.cyr`, listed in `[lib]` only, after `src/brotli.cyr`; quality
0..11 on the `brotli -q` scale, default 6.**

- **In scope**:
  - **API**: `brotli_compress(src, src_len, dst, dst_cap)` (quality 6),
    `brotli_compress_level(…, quality)` (0..11; values outside are clamped), and
    `brotli_compress_bound(src_len)`, google/brotli's `BrotliEncoderMaxCompressedSize` formula.
    `compress(FORMAT_BROTLI)` / `compress_level(FORMAT_BROTLI, …, level)` encode; they returned
    `ERR_UNSUPPORTED_FORMAT` through 2.8.3. The level is passed through as the quality.
  - **Placement**: `[lib]` lists `brotli_enc.cyr`; `[lib.brotli]` and `[lib.woff]` do not, so the
    decode profiles are byte-for-byte what they were (bar the version stamp). The encoder registers
    `_brotli_enc_reset_tables` in `lib.cyr`'s dispatcher only.
  - **Shared tables**: the encoder calls the decoder's `_brd_init_tables` and reads `_brd_ctx` and
    `_brd_rev`. The literal context is therefore computed by the very table the decoder uses.
  - **No static dictionary on the first cut.** RFC 7932 does not require an encoder to emit
    dictionary references.
  - **Literal context modeling is decided by exact cost.** Candidate modes are clustered by an
    estimate, then compared against a single tree by writing the context map and every tree into a
    scratch stream and adding Σ count × code length. Context modeling therefore never costs more
    literal bits than one tree.
- **Out of scope**: an encode profile (one is cut when a consumer asks: `[lib.brotli_enc]` or
  similar would list types, `brotli_dict.cyr`, `brotli.cyr`, `brotli_enc.cyr`, runtime and a
  reset file); streaming encode; the static dictionary, block splitting and an optimal parse
  (roadmap ratio steps).

## Consequences

- **Positive**
  - rekha's `[lib.brotli]` / `[lib.woff]` bundles do not grow; the profile link gate proves they
    still link and survive `alloc_reset()` without the encoder.
  - A caller can pass the same number to `brotli_compress_level` as to `brotli -q`, and the bench
    and smoke compare sankoch with the reference at matching qualities directly.
  - Encoder and decoder cannot disagree about literal contexts or bit order.
- **Negative**
  - `brotli_enc.cyr` depends on `brotli.cyr` internals (`_brd_*`). A change to the decoder's table
    layout must be checked against the encoder too; `tests/tcyr/brotli_compress.tcyr` E1 pins the
    shared tables from both sides.
  - The quality scale differs from every other sankoch codec's 1..9. `compress_level(FORMAT_BROTLI,
    …, 9)` is quality 9, not "best": 10 and 11 exist, although at 2.8.4 they equal 9.
  - The default (6) is not the reference CLI's (11). A caller wanting the smallest output must ask.
- **Neutral**
  - Memory grows with quality: a 2.15 MiB workspace + 128 KiB of hash counters + a bucket table of
    128 KiB × 2^bb (bb 0..6), allocated on first use and grown (never shrunk) when a later call asks
    for more: about 2.4 MiB at quality 0, 6.3 MiB at 6, 10.3 MiB at 9.

## Alternatives considered

- **The encoder inside `src/brotli.cyr`** (as zstd keeps both halves in one file). Lost: it would
  put ~1,900 lines into rekha's decode-only bundles, or force a second decoder file to keep them
  out.
- **sankoch's 1..9 scale, mapped onto Brotli's 0..11.** Lost: any mapping makes "level N" mean a
  different quality from `brotli -q N`, which is the comparison the roadmap asked for and the one a
  caller porting from the reference library will make. Under a 1..9 mapping, quality 0 (the fastest
  setting) would be unreachable.
- **Default 11, as the reference CLI does.** Lost: 6 is the default of every sankoch codec through
  `compress()`, and at 2.8.4 quality 11 buys nothing over 9 while costing the largest bucket table.
- **Choosing the context mode by estimate alone.** Lost on measurement: Shannon-plus-description
  estimates overfit sparse histograms. On the 300 KB ELF fixture cut into 8 KiB chunks, context
  modeling chosen by estimate coded the literals 2.6 % *larger* than one tree; with exact-cost
  selection it can only match or beat one tree. google/brotli's `BrotliPopulationCost` was also
  ported and measured as the clustering estimate: no better overall (−0.1 % to +1.9 % per smoke
  fixture against the simpler estimate) at twice the clustering time.

## References

- RFC 7932 (§3 prefix codes, §5 insert-and-copy, §7 context modeling, §9 stream format).
- google/brotli v1.2.0 `c/enc/` (`brotli_bit_stream.c`, `entropy_encode.c`,
  `backward_references_inc.h`, `hash_longest_match_inc.h`, `encode.c` ShouldCompress) as the design
  model; no code copied (different language, integer-only).
- [0001 — Brotli decoder placement](0001-brotli-decoder-placement.md).
- `src/brotli_enc.cyr`, `tests/tcyr/brotli_compress.tcyr`, `fuzz/fuzz_brotli_enc.fcyr`,
  `scripts/brotli-encode-smoke.sh`.
