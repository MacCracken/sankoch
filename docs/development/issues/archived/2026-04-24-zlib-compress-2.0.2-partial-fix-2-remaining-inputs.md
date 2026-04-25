# sankoch 2.0.2 partial fix — 2 sit-tree inputs at ~1.5 KB / ~2 KB still produce non-decompressible output

**Status:** ✅ **Resolved in sankoch 2.0.3** (2026-04-24). Root cause was
in `_huff_redistribute` (added in 2.0.2): the loop terminated on
`overflow == 0` (count of leaves originally clipped above max_bits),
but each iteration's Kraft-sum decrease is `2^(15-max_bits)` regardless
of where the overflow leaves came from. zlib's `overflow -= 2`
shortcut from `gen_bitlen` is correct only when every overflow leaf
sat at depth max_bits+1. Inputs with cl-tree natural depth at
max_bits+2 or deeper under-iterated and left the cl tree silently
over-subscribed (Kraft = 33024, target = 32768, off by exactly
`2^(15-7) = 256` for the 1504-byte case — one missing iteration). 2.0.3
switched the loop's exit condition to Kraft-sum-based: it iterates
until `kraft == 2^15`, which is unconditionally correct because each
step removes a known fixed amount and starting from a complete natural
Huffman tree the post-clip Kraft is always a multiple of that amount.
Permanent regressions in `tests/tcyr/git_object.tcyr`
(`test_tree_1504_byte_regression`, `test_tree_2021_byte_regression`)
read the archived repros at runtime and verify roundtrip. See
CHANGELOG `[2.0.3]` for the full write-up.

**Filed:** 2026-04-24, after 2.0.2 ship.
**Severity:** High — same severity as the parent issue (silent
data loss for affected inputs); only the affected-input set
shrunk.
**Affects:** sankoch 2.0.2 (verified against `dist/sankoch.cyr`
at this tag).
**Predecessor:** archived
[`2026-04-24-zlib-compress-non-roundtrip-on-tree-shaped-input.md`](2026-04-24-zlib-compress-non-roundtrip-on-tree-shaped-input.md).

## Status update on the parent issue

The 2.0.2 fix resolves the parent bug for the original 751-byte
minimal repro and for **51 of the 53** sit-tree-shaped inputs
that originally failed roundtrip. **2 inputs still fail** and
this follow-up tracks them.

### Verified passing on 2.0.2

```sh
$ cat docs/development/issues/archived/repros/2026-04-24-zlib-compress-2.0.2-partial-fix-driver.cyr \
    | build/cc5 > /tmp/repro && chmod +x /tmp/repro
$ /tmp/repro < docs/development/issues/archived/repros/2026-04-24-zlib-compress-non-roundtrip.bin
input_len=751
clen=660
dlen=751
PASS
```

The original 751-byte minimal repro now round-trips cleanly. ✅

### Still failing on 2.0.2

| Input file | Size (bytes) | clen | dlen | Result |
|---|---:|---:|---:|---|
| `archived/repros/2026-04-24-zlib-2.0.2-partial-fix-input-1504.bin` | 1504 | 1242 | -8 | FAIL |
| `archived/repros/2026-04-24-zlib-2.0.2-partial-fix-input-2021.bin` | 2021 | 1632 | -8 | FAIL |

Both inputs are sit tree objects (`tree N\0<entries>` where each
entry is `100644 file_<i>.txt\0<32 binary hash bytes>`),
matching the parent bug's shape — just larger sizes.

```sh
$ /tmp/repro < docs/development/issues/archived/repros/2026-04-24-zlib-2.0.2-partial-fix-input-1504.bin
input_len=1504
clen=1242
dlen=-8
FAIL: dlen != input_len

$ /tmp/repro < docs/development/issues/archived/repros/2026-04-24-zlib-2.0.2-partial-fix-input-2021.bin
input_len=2021
clen=1632
dlen=-8
FAIL: dlen != input_len
```

Deterministic — same input bytes always produce the same broken
compressed output across processes. End-to-end through real sit
(cyrius v5.6.35 + sankoch 2.0.2 cross-built sit binary running
the 100-commit / 100-file fixture) reports `checked 298
objects, 2 bad` with these same two hashes.

## New-shape signal: zero-run mid-stream

The corrupt compressed output has a striking pattern not
present in the original failure mode. The first 32 bytes of
each output:

**1504-byte input → 1242-byte broken output** (first 32 bytes):

```
00000000: 7801 45d3 7938 d479 1cc7 7100 0000 0000  x.E.y8.y..q.....
00000010: 0000 0000 0000 0000 0000 0000 0000 0000  ................
```

**2021-byte input → 1632-byte broken output** (first 32 bytes):

```
00000000: 7801 45d3 793c d37d 1cc0 7100 0000 0000  x.E.y<.}..q.....
00000010: 0080 0000 0000 0000 0001 0006 0000 3000  ..............0.
```

Both start with a valid zlib header (`78 01`) and ~10 bytes of
plausible deflate-stream prefix, then **a long run of zeros**
where deflate symbols should be, then more plausible-looking
data later in the stream. The tail bytes (last ~32 of each
output) look like normal compressed data, not zeros.

This is **not** the same shape as the parent bug's failure
mode. The parent bug produced compressed bytes whose Huffman
table or block header encoded a bad symbol distribution; the
2.0.2 partial fix corrected that. The new-shape failures
suggest something else — possibly a bit-stream emission gap
where some interval of literals/lengths got skipped (zero-
filled by a memset-then-overwrite pattern that the overwrite
missed), or a block-header field that's encoded as zeros where
it should be nonzero.

## Reproduction (committed artifacts)

All four artifacts live alongside this file under `archived/repros/`:

| File | Purpose |
|---|---|
| `2026-04-24-zlib-2.0.2-partial-fix-driver.cyr` | ~50-line standalone cyrius program: `read stdin → zlib_compress → zlib_decompress → memcmp`. Same driver as the parent issue. |
| `2026-04-24-zlib-2.0.2-partial-fix-input-1504.bin` | 1504-byte raw input (smallest still-failing case). |
| `2026-04-24-zlib-2.0.2-partial-fix-input-2021.bin` | 2021-byte raw input (second still-failing case). |
| `2026-04-24-zlib-2.0.2-partial-fix-output-1504.cz` | The 1242-byte broken output for the 1504-byte input. Useful for offline DEFLATE-stream analysis (e.g. `infgen` or hand-stepping the bit reader). |
| `2026-04-24-zlib-2.0.2-partial-fix-output-2021.cz` | The 1632-byte broken output for the 2021-byte input. |

Build + run:

```sh
cat docs/development/issues/archived/repros/2026-04-24-zlib-2.0.2-partial-fix-driver.cyr \
  | build/cc5 \
  > /tmp/repro && chmod +x /tmp/repro
/tmp/repro < docs/development/issues/archived/repros/2026-04-24-zlib-2.0.2-partial-fix-input-1504.bin
# Expected: PASS once 2.0.3 ships.
# Actual:   FAIL: dlen != input_len  (dlen=-8 from zlib_decompress)
```

## Investigation suggestions

The same suggestions from the parent issue apply, narrowed by
the new-shape signal:

1. **Bisect by input size on the 1504B input.** Truncate to
   1500, 1400, 1300, … 1000, 800 and find the smallest input
   that fails. Combined with the parent bug's old failure
   threshold (was 751B; that case now passes on 2.0.2), this
   should bracket the size band where the new-shape bug lives
   — likely a specific window size or block boundary that 2.0.2
   handles correctly for ≤ ~1400B but not ≥ 1504B.
2. **Diff the corrupt `.cz` output against a known-good
   reference.** Run the 1504B input through `gzip -1 | tail -c+11
   | head -c<N>` (or equivalent zlib reference encoder) and
   diff byte-by-byte against the saved
   `repros/2026-04-24-zlib-2.0.2-partial-fix-output-1504.cz`.
   The first divergence pinpoints where the encoder went wrong.
3. **Force fixed-Huffman block** on this input via
   `_deflate_compress_fixed_block` directly, skip
   `_deflate_compress_dynamic_block`. If fixed-Huffman
   roundtrips correctly → bug is dynamic-block-specific
   (Huffman code construction, HCLEN/HLIT/HDIST emission, or
   the dynamic-block header bit-stream). If fixed-Huffman ALSO
   fails → bug is in LZ77 token stream itself or bit-writer.
4. **Step through the bit-writer for the first ~10 bytes of
   the corrupt output**, where the zero-run begins. Determine
   whether the writer emitted a sequence that the decoder would
   correctly decode but interpret as "skip/zero" symbols — vs
   whether the bit-writer truly output zeros where deflate
   symbols should be (the latter would be a bw_write skip).

## Resolution

When fixed in 2.0.3 (or whatever the next sankoch tag is):

- Add `repros/2026-04-24-zlib-2.0.2-partial-fix-input-{1504,2021}.bin`
  to `tests/tcyr/zlib_compress.tcyr` as permanent regression
  cases. (Keep them committed under repros/ as well — they're
  small enough that the binary commit is fine.)
- Update the parent issue's "When fixed" section to point at
  this follow-up issue's resolution.
- Move this file to `docs/development/issues/archived/` once
  cyrius v5.6.35 picks up the fix and the sit fsck gate goes
  green.

## Downstream

- **cyrius v5.6.35** stays in-flight pending this fix. cyrius's
  `cyrius.cyml` `[release]` table currently has sankoch pinned
  at 2.0.1 (NOT bumped to 2.0.2 — partial fix of an upstream
  bug doesn't qualify as "fix bundled in this slot"). When
  2.0.3 ships and resolves both inputs, cyrius bumps to 2.0.3,
  flips `tests/regression-sit-status.sh`'s `CYRIUS_V5635_SHIPPED`
  guard, and tags v5.6.35.
- **sit** (consumer): same mitigation as before — fl_alloc swap
  + post-commit `read_object` verify in `cmd_commit`. Still
  refuses commits that produce unreadable objects (loud failure
  rather than silent corruption).
