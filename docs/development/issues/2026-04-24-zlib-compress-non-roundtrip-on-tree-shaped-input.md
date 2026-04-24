# sankoch 2.0.1 `zlib_compress` produces output that fails `zlib_decompress` for sit-tree-shaped inputs

**Discovered:** 2026-04-24 during cyrius v5.6.35 triage of sit's
"symptom 2 of 2" memory anomaly at scale (sit S-33).
**Severity:** High — silent data loss for any consumer compressing
mixed-text+binary blocks at certain length boundaries.
**Affects:** sankoch 2.0.1 (verified). Earlier 2.0.x not tested.

## Summary

For specific input byte patterns matching sit's git-tree object shape
(`tree N\0<entries>` where each entry is `100644 file_<i>.txt\0<32
binary hash bytes>`), `zlib_compress` returns a positive `clen` and
writes `clen` bytes — but `zlib_decompress` on those same bytes
returns `-8` (zlib internal error code).

The encoder is **deterministic**: re-running `zlib_compress` on the
same input in a fresh process produces byte-identical output, and
that output also fails to decompress. So this isn't transient state
corruption — it's the encoder producing a structurally-malformed
DEFLATE stream for these specific inputs.

## Reproduction

A 751-byte minimal repro is committed at:

- `docs/development/issues/repros/2026-04-24-zlib-compress-non-roundtrip.bin` —
  the exact 751-byte input
- `docs/development/issues/repros/2026-04-24-zlib-compress-non-roundtrip.cyr` —
  ~50-line standalone cyrius program

Build + run:

```sh
# from any cyrius checkout:
cat docs/development/issues/repros/2026-04-24-zlib-compress-non-roundtrip.cyr \
  | build/cc5 \
  > /tmp/repro && chmod +x /tmp/repro
/tmp/repro < docs/development/issues/repros/2026-04-24-zlib-compress-non-roundtrip.bin
```

Expected output:

```
input_len=751
clen=...
dlen=751
PASS
```

Actual output (sankoch 2.0.1):

```
input_len=751
clen=660
dlen=-8
FAIL: dlen != input_len
```

The 751-byte input begins with `tree 742\0100644 f0.txt\0` followed
by a 32-byte binary hash, then 16 more `100644 f<i>.txt\0<32 bytes>`
entries (16 × 47 = 752 bytes; the input is one byte short of clean-
boundary because file names f0..f15 average ~14 chars each plus the
header).

## Scope

Cyrius v5.6.35 triage produced sidecar dumps of all 300 tree/blob/
commit object bodies that sit's 100-commit fixture writes through
sankoch. Replaying every one through standalone sankoch in a fresh
process:

- 250/300 round-trip cleanly (compress → decompress → byte-identical).
- **50/300 fail standalone roundtrip** with the same `-8` error.
- All 50 failing inputs are tree objects (sizes 751–4700 bytes).
- The 250 passing inputs include all blobs (~17 B each) and all
  commits (~150-300 B each) plus the smallest trees (≤ ~700 B).

The failure correlates with **size + content shape**, not with row
order or process state.

## Triage exclusions (cyrius-side)

Triage at cyrius v5.6.35 ruled out:

- **patra 1.6.0**: 1600+ standalone roundtrips clean across single-
  process and cross-process patterns; 300 cross-process inserts of
  sankoch-compressed blobs all read back identical.
- **cyrius bump allocator**: the `compressed` buffer is not mutated
  during `patra_insert_row` (pre/post checksums match for all 300
  inserts).
- **cyrius alloc grow-undersize bug (v5.6.34)**: separate fix
  shipped in cyrius v5.6.34; this issue reproduces with the v5.6.34
  fix in place.
- **sit-side buffer aliasing**: in-process `zlib_decompress` of
  the just-produced `compressed` bytes (added to sit's
  `write_typed_object` as instrumentation) failed identically —
  bytes can't roundtrip even microseconds after `zlib_compress`
  returns, in the same lock window, on the same buffer.

The failure is reachable with a 30-line standalone cyrius program
that does nothing but `read stdin → zlib_compress → zlib_decompress
→ memcmp`. No patra, no sit, no allocator state pressure required.

## Suspected layer

`_deflate_compress_level_inner` at level 6 dispatches to
`_deflate_compress_dynamic_block`. The 751-byte input falls within
ONE dynamic block (`DEFLATE_BLOCK_SIZE` is much larger). The bug is
likely in either:

- The dynamic Huffman code construction for this specific
  literal/length frequency distribution (lots of repeated `100644 `
  + `.txt\0` ASCII intermixed with high-entropy 32-byte binary
  hashes), OR
- The bit-stream emission of length/distance codes when matches
  span the ASCII-→-binary boundary, OR
- The block header encoding (HLIT/HDIST/HCLEN) for this specific
  symbol-set shape.

The encoder isn't crashing or producing a truncated stream — it's
producing a stream that decodes to the wrong number of bytes (or
fails at a Huffman/length boundary). `dlen = -8` is sankoch's
`ERR_*` code corresponding to a structural decoder mismatch.
Decoding our own output should always succeed; that it doesn't here
points at the encoder producing a stream that doesn't match the
decoder's expectation.

## Investigation suggestions

1. **Bisect by input size**: truncate the 751-byte input to 700,
   650, 600, … bytes and find the smallest input that fails. The
   first-byte at which corruption appears in `decompressed` (when
   length is correct but bytes diverge — a different mode of fail
   than `-8`) often points at the symbol where the encoder mis-
   wrote a length/distance code.
2. **Force fixed-Huffman block**: invoke
   `_deflate_compress_fixed_block` directly on this input and see
   if THAT roundtrips. If yes → bug is in the dynamic-block
   encoding path (Huffman table or HCLEN/HLIT/HDIST). If no →
   bug is in the LZ77 match-finder or token stream itself.
3. **Compare against zlib reference output**: run `gzip -1` (or
   `pigz` etc) on the same input bytes and diff the deflate stream.
   The first divergence byte pinpoints the encoding decision that
   differs.

## Resolution

When fixed:

- Tag a sankoch patch release (2.0.2 or 2.1.0).
- Add this 751-byte input to `tests/tcyr/zlib_compress.tcyr` (or
  whichever tcyr file covers zlib roundtrips) as a permanent
  regression case.
- Add `docs/development/issues/repros/2026-04-24-zlib-compress-non-roundtrip.{bin,cyr}`
  to the repository so the repro is preserved.
- Move this file to `docs/development/issues/archived/` once the
  fix is verified.

## Downstream

- **cyrius v5.6.35** (in-flight): waiting on this fix to ship.
  Slot bundles this fix as the resolution to sit's "symptom 2 of 2"
  (`sit/docs/development/issues/2026-04-24-cyrius-stdlib-memory-
  anomalies-at-scale.md`). cyrius will pin the fixed sankoch tag
  in `cyrius.cyml` and add a `tests/regression-sit-status.sh` gate
  that spins up the 100-commit fixture and asserts `sit fsck`
  reports 0 bad.
- **sit** (consumer): currently routes big allocs through
  `fl_alloc` (mitigation for cyrius v5.6.34 grow-undersize, which
  is already shipped) and adds post-commit `read_object` verify
  (mitigation for THIS bug — turns silent corruption into refused
  commits). sit's mitigation can be reverted when sankoch's fix
  ships and cyrius v5.6.35 picks it up.
