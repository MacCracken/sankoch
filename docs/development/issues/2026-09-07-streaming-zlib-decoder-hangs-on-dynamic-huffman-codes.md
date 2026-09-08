# `zlib_dec_write` hangs forever on any stream containing a dynamic Huffman code longer than 9 bits

**Status:** 🔴 **OPEN** — infinite loop (hang / DoS) on *valid, ordinary* input. Not a corruption
bug and not attacker-specific: the triggering stream is one this library's own encoder produces.
**Placement:** root cause in `src/deflate.cyr` (`DDEC_STATE_DECODE_SYM`, the `_ddec_fill(..., 9)`);
amplified to an infinite loop by `src/zlib.cyr` (`ZDEC_STATE_DEFLATE` in `zlib_dec_write`).
**Found:** 2026-09-07, while adding fuzz coverage for the 2.7.13 output cap. Not reported by a
consumer — it was found because the new harness was the first streaming fuzz to use non-uniform data.
**Affects:** 2.7.12 and every earlier release carrying the streaming decoder (the code dates to the
2.3.0 streaming arc). Reproduced against **pristine 2.7.12** with `src/` reverted, so it is not
introduced by 2.7.13.
**Severity:** **High.** A hang is worse than an error return for every consumer: it cannot be caught,
retried, or timed out from inside the API, and it burns a core. `sit` stream-inflates git objects and
`bote` uses the DEFLATE streaming path for `permessage-deflate`.

## Reproducer

848-byte zlib stream, produced by sankoch's own `zlib_compress`. The **batch** decoder returns all
1628 bytes byte-exactly; the **streaming** decoder never returns.

```
var _fs = 0;
fn fs(s) { _fs = s; return 0; }
fn fn_() { _fs = _fs * 6364136223846793005 + 1442695040888963407; return (_fs >> 33) & 255; }

fs(6158);
var n = 1628;
var src[2048];
var i = 0;
while (i < n) {
    if ((fn_() & 3) == 0) { store8(&src + i, fn_() & 255); }   # 25% random
    else { store8(&src + i, 65); }                             # 75% 'A'
    i = i + 1;
}
var compressed[8192];
var decompressed[8192];
var clen = zlib_compress(&src, n, &compressed, 8192);   # 848

zlib_decompress(&compressed, clen, &decompressed, 8192);   # -> 1628, byte-exact

var ctx = zlib_dec_init(&decompressed, 8192);
zlib_dec_write(ctx, &compressed, clen);                    # never returns
```

Nothing about the shape is special beyond "mixed enough to need long Huffman codes" — the bisect
found the first hanging length at **n = 1628** for this seed, with shorter prefixes fine.

## Root cause

`DDEC_STATE_DECODE_SYM` pre-fills the bit accumulator to **9** bits, on reasoning the comment states
outright:

```
# Pull enough bits to attempt a fast-table decode. Fixed
# litlen codes are 7-9 bits; the helper handles short bridges
# gracefully so we don't stall at the very end of a chunk.
cp = _ddec_fill(ctx, input, cp, end, 9);
```

The premise holds for **fixed** Huffman blocks. It does not hold for **dynamic** ones: RFC 1951
§3.2.7 allows litlen code lengths up to **15** bits. So when the next symbol's code is longer than 9
bits and the accumulator happens to hold exactly 9:

1. `_ddec_fill(ctx, input, cp, end, 9)` sees `bits (9) >= n (9)` and pulls **nothing** — `cp` is
   unchanged, even though input remains.
2. `_ddec_decode_huff` cannot resolve a >9-bit code from 9 bits and returns `DDEC_NEED_MORE`.
3. `deflate_dec_write` returns `cp` — **0 bytes consumed**, state unchanged.

At the DEFLATE level that is merely a wasted call. The loop is in the zlib wrapper:

```
} elif (state == ZDEC_STATE_DEFLATE) {
    ...
    var rc = deflate_dec_write(inner, input + cp, in_len - cp);
    if (rc < 0) { return _zdec_poison(ctx, rc); }
    ...
    cp = cp + rc;                       # rc == 0
    if (... == DDEC_STATE_DONE) { ... } elif (cp >= in_len) { return cp; }
}                                       # -> while (1) re-calls with identical arguments
```

`ZDEC_STATE_DEFLATE` has **no no-progress guard**: `rc == 0` with input still available and the
stream not finished sends `while (1)` around to make the exact same call forever.

Instrumented, at the moment it wedges: `cp = 151` of `in_len = 848`, `inner_state = 5`
(`DDEC_STATE_DECODE_SYM`), `inner_bits = 9`, `inner_dp = 147`.

## Why no existing test or fuzz harness caught it

Every streaming harness in `fuzz/fuzz_deflate.fcyr` — `fuzz_deflate_stream`,
`fuzz_stream_ratio_cap`, and the streaming halves of the ratio-cap suites — fills its source with a
**single repeated byte** (`var fillb = _fuzz_next() & 255;` then `while (i < capped) { store8(&src + i, fillb); ... }`).
A one-symbol alphabet yields Huffman codes far below 9 bits, so the 9-bit prefill was always
sufficient and the branch was never reached. The `tests/tcyr/stream.tcyr` fixtures are likewise text
or uniform. **The gap was in the input distribution, not the assertion coverage** — which is the
lesson worth carrying: uniform fill is the wrong default for any codec whose behaviour is
alphabet-dependent.

## Proposed fix

Two changes, and both are worth making rather than either alone:

1. **`src/deflate.cyr` — fill to the real maximum.** Three pre-fill sites pass `9`; two are wrong
   and one is fine, so this is not a blanket replace:

   | Site | State | Comment's premise | Verdict |
   |---|---|---|---|
   | ~1092 | `DDEC_STATE_DECODE_SYM` | "Fixed litlen codes are 7-9 bits" | ❌ **Bug** — dynamic litlen codes reach 15 bits. This is the reproducer's path. |
   | ~1145 | `DDEC_STATE_DECODE_DIST` | "Fixed distance table: all 30 codes are exactly 5 bits" | ❌ **Same bug, not yet observed** — dynamic *distance* codes also reach 15 bits. Fix both or the hang simply moves. |
   | ~1288 | code-length alphabet (`_huff_cl_*`) | — | ✅ **Fine.** RFC 1951 §3.2.7 gives the code-length alphabet 3-bit lengths, so its own codes are at most 7 bits; 9 already covers it. |

   Raise the two failing sites to `15` and correct their comments, which document the wrong premise
   rather than merely being terse. `_ddec_fill` already stops early on `cp >= end`, so a genuine
   end-of-stream short read still falls through to the helper's graceful path.
2. **`src/zlib.cyr` — make no-progress fail closed.** Even with (1), `ZDEC_STATE_DEFLATE` should
   never be able to spin: if `rc == 0` and the inner state is unchanged and `cp < in_len`, that is a
   decoder bug by definition, and it should poison with `ERR_CORRUPT_DATA` rather than loop. A hang
   is the one failure mode a caller cannot defend against.

Regression coverage must use **mixed-alphabet** data; the reproducer above is a ready fixture, and
`fuzz/fuzz_deflate.fcyr`'s `fuzz_output_cap` has its streaming half pinned to uniform fill with a
pointer to this file, to be restored once this lands.
