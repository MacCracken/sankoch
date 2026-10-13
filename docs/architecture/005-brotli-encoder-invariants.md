# 005 — The Brotli encoder's invariants: the bound, the mirrored ring, and the decoder's tables

`src/brotli_enc.cyr` (2.8.4) keeps four properties that no compiler checks and that a ratio change
(a static dictionary, block splitting, an optimal parse; all on the roadmap) can break silently,
because the stream it then writes may still decode on most inputs. Read this before changing the
encoder's meta-block loop, its parse, or the decoder's tables.

## 1. A meta-block is written compressed only when that is no larger than storing it

`_bre_encode` snapshots the writer (`_bre_bp`, `_bre_acc`, `_bre_nb`, `_bre_err`) and the
distance ring before each meta-block, writes it compressed, and compares the end bit position with
what an uncompressed meta-block would reach from the same start: header bits, zero padding to a
byte, `8 × MLEN`, plus the 2-bit empty `ISLAST` trailer and final padding when it is the last one.
If the compressed form is larger, or `_bre_compressed` declined (`ShouldCompress`, returning -1),
everything is restored and the bytes are stored.

That comparison is what makes `brotli_compress_bound(n) = n + 6 + 4·(n >> 14)` (google/brotli's
`BrotliEncoderMaxCompressedSize`) a guarantee rather than a hope: the stream is never longer than
the all-stored layout, which for meta-blocks of up to `BRE_MB_MAX` (256 KiB) costs at most 4 bytes
for the first header (behind up to 4 WBITS bits), 3 for each later one, and 1 for the trailer. Any
new meta-block shape must keep the compare-and-rewind, or the bound must be re-derived.
`tests/tcyr/brotli_compress.tcyr` E4/E5 encode into `dst` at exactly the bound, flush against a
PROT_NONE page.

Uncompressed meta-blocks cannot be `ISLAST` (RFC 7932 §9.2): a stored final meta-block is followed
by the 2-bit `ISLAST = 1, ISLASTEMPTY = 1` meta-block. An empty input is that trailer alone behind
WBITS 16: the single byte `0x06`.

## 2. The encoder's distance ring is the decoder's ring

The decoder pushes the last-distances ring **only** for an explicit distance code ≥ 1. Code 0, the
implicit distance of insert-and-copy symbols 0..127, and static-dictionary references leave it
alone (`brotli.cyr` `_brd_mb_body`; google/brotli `decode.c`). `_bre_parse` pushes on exactly the
same rule (`dc != 0`), and short codes 4..15 are chosen against the ring as it stands before the
command (`_bre_dcode`, google/brotli `ComputeDistanceCode`).

Two consequences:

- A meta-block that is parsed and then **stored** must restore the ring: an uncompressed meta-block
  carries no commands, so the decoder's ring did not move. `_bre_encode` restores `_bre_r0..3` with
  the writer. The bug is masked unless a later command reaches the stale entry, so the guarding
  test builds that case on purpose: `test_e6_ring_across_stored` stores a block whose parse pushed
  distance 500, then opens the next block with a copy from 500 back (mutation-verified: without
  the restore it decodes from the wrong place).
- A future static-dictionary reference must not push, and must leave the cache candidates
  (`_bre_cache_dist`) consistent with that.

## 3. Matches reach back across meta-blocks, never forward past MLEN, never beyond the window

The hash is reset once per call, not per meta-block, so a copy may refer to bytes of any earlier
meta-block, stored ones included (they are in the decoder's output). Every lookup bounds the
distance by `min(pos, (1 << WBITS) - 16)`: a larger distance is not an error to the decoder but a
**static-dictionary reference** (RFC 7932 §8), so it would decode to different bytes, or fail.
E7 builds an 18 MiB input whose only repeat lies 17 MiB back. Copy lengths are bounded by the
meta-block's end (`e - pos`), because a meta-block's commands must cover exactly MLEN bytes.
Positions are stored as u32, so the encoder accepts `src_len < 2^32`.

## 4. Literal contexts and code bit order come from the decoder

The encoder computes literal contexts with the decoder's own `_brd_ctx` table and reverses prefix
codes with the decoder's `_brd_rev` (both built by `_brd_init_tables`, which `_bre_init_tables`
calls). Changing the layout of either table in `brotli.cyr` changes the encoder too: E1 pins the
encoder's length-code tables against the decoder's command LUT and its distance codes against the
decoder's distance LUT; E2 and E3 read every written prefix code and context map back with the
decoder's own readers.

## Memory

All encoder memory is arena-allocated on first use and memoized: a 2.15 MiB workspace slab (command
arrays for one 256 KiB meta-block, histograms, Huffman scratch, a 16 KiB scratch stream for exact
costs), 128 KiB of bucket counters, and a bucket table of 128 KiB × 2^bb, where bb is 0..6 by
quality. The table grows (a new allocation; the old one is abandoned to the bump arena) when a call
needs more than any earlier one, and never shrinks. Peak live per process: about 10.3 MiB (quality
≥ 9); a caller that raises the quality one step at a time also strands each smaller table (0 → 7
strands about 7.9 MiB) until the next `alloc_reset()`. Every non-empty call zeroes the 128 KiB of
counters, which is most of a small input's encode time.
All four pointers (`_bre_ws`, `_bre_hnum`, `_bre_hbuck`, and the size `_bre_hbb`) are cleared by
`_brotli_enc_reset_tables`, registered in `lib.cyr` only, since only `[lib]` carries the encoder
([003](003-per-profile-reset-dispatch.md)).
