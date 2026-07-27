# One-shot DEFLATE compress re-encodes bytes at every 1 MiB block boundary (silent corruption)

**Status**: ✅ **RESOLVED in v2.7.6** — see CHANGELOG [2.7.6].

> Fixed by giving the batch path the contract the streaming encoder always had: each per-block
> encoder publishes the offset it ACTUALLY consumed (`_deflate_block_reached`) and
> `_deflate_compress_level_inner` resumes there instead of at `block_end`. The overshoot is real and
> intentional — both block encoders match against the full `src` so back-refs can span blocks, which
> is what keeps the ratio — so the fix is to stop discarding it, not to stop producing it.
>
> Two cases beyond the core fix, either of which would have left it partial:
> 1. the fixed path's trailing lazy-match flush consumes to `sp - 1 + prev_match` (the match *starts*
>    at `sp - 1`), not `sp`;
> 2. `BFINAL` is decided from `block_end` before encoding, so the overshoot can now carry a
>    non-final block through to `src_len` — leaving every byte encoded but no `BFINAL` set. Closed
>    with an empty final fixed block (legal; DEFLATE permits mixing block types).
>
> Verified: 2 MB round-trip byte-exact at levels 1/6/9; **GNU `gunzip` accepts a 2 MB stream and its
> output is byte-exact** (previously rejected at char 1048797). Gate
> `tests/tcyr/deflate_block_boundary.tcyr` (21 assertions) is mutation-proven — restoring
> `sp = block_end` gives 2000153 decoded, first divergence at 1048729.
>
> The suite missed this because every pre-existing deflate/gzip test used an input smaller than
> `DEFLATE_BLOCK_SIZE` (largest 80000 B), so the outer chunker never took a second iteration.
>
> Original report follows.

**Was**: 🔴 OPEN — reproduced against `main` @ `68052c1` (v2.7.5), all levels 1–9.

**Priority**: **Critical** — silent data corruption in the one-shot compress path of the
library's most-used codec. `deflate_compress` has no container checksum, so the wrong output is
returned with **no error**; `zlib_compress` / `gzip_compress` produce streams that every
conforming decoder (including sankoch's own, and zlib) rejects with a checksum failure.

## Summary

`_deflate_compress_level_inner` (`src/deflate.cyr:1869`) chunks input into 1 MiB blocks
(`DEFLATE_BLOCK_SIZE = 1048576`, `:1847`). The per-block encoders find matches against the
**full** `src`, not against the block, so the last match in a block can advance past `sp_end` by
up to `LZ77_MAX_MATCH - 1` = **257 bytes**. Neither block encoder reports where it actually
stopped — both return `0` — and the outer loop then resumes at `sp = block_end` (`:1891`):

```cyrius
        rc = _deflate_compress_dynamic_block(bw, src, src_len, sp, block_end, bfinal);
        ...
        if (rc < 0) { return rc; }
        sp = block_end;              # <-- discards the overshoot
```

So every byte between `block_end` and the overshot position is emitted **twice**: once inside the
match that crossed the boundary, then again as the head of the next block. The stream decodes
**longer than the input**, by roughly 257 bytes per boundary.

Both paths are affected — `_deflate_compress_dynamic_block` (`:2155`, levels ≥ 4), whose
collector returns `sp + mlen` unclamped (`_dyn_collect_at`, `:2050`, `return sp + mlen` at
`:2084`), and `_deflate_compress_fixed_block` (`:1900`, levels < 4), whose `sp = sp - 1 +
prev_match` overshoots the same way.

**The streaming encoder is correct** — `deflate_enc_*` / `gzip_enc_*` round-trip 2 MiB cleanly.
Only the one-shot path is affected.

## Evidence

Extra bytes scale exactly with the number of block **boundaries** (`blocks - 1`), which is the
signature of the mechanism above. 2 MiB of zeros, level 6:

| input | blocks | `gzip_decompress` | DEFLATE payload decodes to | extra |
|---|---|---|---|---|
| 1 048 576 | 1 | 1 048 576 ✅ | 1 048 576 | **0** |
| 1 048 577 | 2 | `-5` | 1 048 578 | **1** |
| 2 097 152 | 2 | `-5` | 2 097 347 | **195** |
| 3 145 728 | 3 | `-5` | 3 146 118 | **390** |

Exactly `DEFLATE_BLOCK_SIZE` is the largest clean input. `-5` is `ERR_CHECKSUM_MISMATCH`; the
gzip trailer's CRC-32 and ISIZE are both **correct** (they are computed over the caller's input),
so the fault is the DEFLATE payload, not the wrapper.

Confirmed against an independent decoder — Python `zlib` expands the same blob to 1 049 195 from
a 1 049 000-byte input and `gzip.decompress` raises `BadGzipFile: CRC check failed`. sankoch's
decoder and zlib agree byte-for-byte, so the **encoder** is the wrong side.

Blast radius at 2 MiB of zeros:

| API | result |
|---|---|
| `deflate_compress` → `deflate_decompress` | returns **2 097 347**, **no error** — silent |
| `zlib_compress` → `zlib_decompress` | `-5` (adler32 catches it) |
| `gzip_compress_level`, **levels 1–9** | `-5`; payload decodes to 2 097 347 at every level |
| `gzip_enc_init` / `_write` / `_finish` (streaming) | **2 097 152 ✅ correct** |

Incompressible input of any size tested round-trips fine — no long match spans the boundary, so
there is nothing to overshoot. The bug needs a match crossing a 1 MiB boundary, which is the
common case for real data.

## Repro

Drop this in the repo root and run `cyrius test .repro.tcyr`:

```cyrius
include "tests/tcyr/_harness.tcyr"

fn main() {
    _test_init();
    var raw = 2097152;
    var src = alloc(raw);
    var i = 0;
    while (i < raw) { store8(src + i, 0); i = i + 1; }
    var cap = raw + 262144;
    var enc = alloc(cap);
    var out = alloc(cap);

    # Silent: raw DEFLATE has no checksum to catch it.
    var dl = deflate_compress(src, raw, enc, cap);
    println_int(deflate_decompress(enc, dl, out, cap));   # 2097347, expected 2097152

    # Detected, but only by the container checksum.
    var gl = gzip_compress(src, raw, enc, cap);
    println_int(gzip_decompress(enc, gl, out, cap));      # -5 ERR_CHECKSUM_MISMATCH
    return 0;
}

var r = main();
syscall(60, r);
```

## Why the suite did not catch it

Nothing in `tests/tcyr/` or `fuzz/` crosses `DEFLATE_BLOCK_SIZE`. The largest one-shot fixtures
are ~200–424 KB (the shared harness heap is 4 MiB total, `_harness.tcyr:28`), so every one-shot
compress test to date has run as a **single block** — the boundary that carries the bug is never
reached. `fuzz_deflate.fcyr` does exercise larger sizes, but through `deflate_enc_*`, the
streaming path, which is correct.

## Ask

1. **Fix.** Two shapes, minimal first:

   - **Clamp the match at the block boundary.** Pass `sp_end` into `_dyn_collect_at` and the
     fixed-block loop and truncate `mlen` so `sp + mlen <= sp_end`. The outer loop, `bfinal`, and
     the block accounting are all left untouched. Ratio cost is bounded by one truncated match
     per 1 MiB — noise.
   - **Or resume where the block actually stopped**: have the block encoders return the real end
     position and set `sp` to it. Slightly better ratio, but note the hazard — `bfinal` is
     decided *before* the block runs (`:1880-1882`). If an overshoot consumes the remaining
     input, the loop exits with no final block emitted at all, and the stream is then truncated
     rather than long. `bfinal` has to be decided after the fact, or an empty final block emitted.

2. **Regression test** at sizes straddling `DEFLATE_BLOCK_SIZE` — 1 048 576 / 1 048 577 /
   2 097 152 / 3 145 728 of compressible input, asserting the round-trip length equals the input
   for `deflate` / `zlib` / `gzip` at levels 1, 3, 6 and 9. The one-shot path needs at least one
   multi-block fixture; a single-block corpus cannot see this class of bug at all.

3. **Consider a release ahead of the 2.8.x ladder.** This is silent corruption in the default
   compress path, and consumers cannot detect it themselves on `deflate_compress`.

## Downstream impact (why this was found)

stiva calls `gzip_compress` in two live paths — `image_store_import` (`src/imagelayout.cyr:566`)
and `_il_docker_add_layer` (`:825`) — so `stiva import` and docker-archive `load` write corrupt
OCI layer blobs for any compressible layer tar over 1 MiB, which is nearly every real layer. The
blob is content-addressed and stored without a decode check, so the failure surfaces much later,
at unpack. Found while sizing a decompression-bomb test fixture for stiva's `unpack_layer`.

Workaround available to consumers today: the streaming `gzip_enc_*` / `deflate_enc_*` API.
