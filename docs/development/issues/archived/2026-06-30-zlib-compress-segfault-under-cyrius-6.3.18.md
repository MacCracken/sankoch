# zlib_compress.tcyr segfaults (exit 139) under cyrius 6.3.18

**Status**: ✅ **RESOLVED (2026-06-30).** Root cause was **in the test harness, not the
library**: `test_zlib_enc_roundtrip` declared `var chunks[4]` — a **bare 4-BYTE** array local
(one 8-byte slot) — then wrote **32 bytes** into it via `store64(&chunks + i*8)` for `i = 0..3`.
The daimon footgun (author meant four i64 **slots**, declared four **bytes**). Benign while array
locals lived in shared `.bss`; frame-corrupting since cyrius 6.3.13 moved function-local arrays to
the stack — the 24-byte overrun clobbered the frame and crashed the 80 K streamed round-trip.
**Fix**: `var chunks[4]` → `var chunks: i64[4]` (the element-typed slot spelling, 32 bytes).
A full compress-path array audit (zlib / deflate / huffman / bitwriter / lz77 / stream / checksum,
adversarially verified) found **every `var X[N]` correctly sized** — the library needs no change.
The whole suite now passes 0-failed on cycc 6.3.18; the `cyrius.cyml` pin moved 6.2.44 → 6.3.18.

**Priority**: **High** — a hard crash in the zlib compress path on the current toolchain.

## Context

> Historical pre-fix diagnostics. The pin has since moved 6.2.44 → 6.3.18 → **6.4.68**;
> the root cause was a test-harness `var chunks[4]` undersize, fixed 2026-06-30 (see
> **Status** above). Present-tense claims below reflect the state at time of the crash.

- sankoch's `cyrius.cyml` still pins **6.2.44**; the crash shows under **6.3.18** (toolchain
  drift warning printed). The other 19 test suites — including `bzip2_compress` (151060),
  `deflate_compress` (355460), `zlib_decompress` (1337), `gzip_compress` (80130) — all pass
  0-failed under 6.3.18. Only `zlib_compress.tcyr` crashes.
- The likely cause is the **same class** as the just-fixed bzip2 bug: an undersized `var X[N]`
  array local (or slot-idiom footgun) in the **zlib/deflate compress** path, latent-benign while
  function-local arrays lived in shared `.bss` but **frame-corrupting since cyrius 6.3.13** moved
  them to the stack (`THREAD_STACK_SIZE` 64 KB→2 MB + `PROT_NONE` guard page). cyrius's own
  `sankoch deflate` fsck test does not hit the crashing path, so it slipped through there too.

## Repro

```sh
cd sankoch && cyrius test tests/tcyr/zlib_compress.tcyr   # exit 139
```

## Ask

1. Bisect the segfault under cycc 6.3.18 (start: run `zlib_compress.tcyr` under a debugger / with
   `CYRIUS_STACK_ARRAYS=0` to confirm it's the stack-locals class).
2. If it's an undersized array local, size it to the bytes actually written (the daimon footgun —
   author meant i64 SLOTS, declared BYTES; cf. the 2.4.7 bzip2 `pos[6]`→`[48]` / `present[16]`→`[128]`).
   Audit the whole zlib/deflate compress path (`grep 'var [a-z_]+\[[0-9]+\]'` + check each against its
   `store*`/`load*`/loop-bound usage).
3. Move sankoch's `cyrius.cyml` pin off 6.2.44 to the current toolchain so this can't drift again.
4. Add the crashing input as a regression fixture.
