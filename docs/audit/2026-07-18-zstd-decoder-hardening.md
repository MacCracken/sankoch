# Sankoch — zstd Decoder Hardening Audit (2.5.6)

**Date:** 2026-07-18
**Auditor:** Adversarial multi-agent decoder audit (per-section find → independent verify)
**Scope:** Memory-safety and DoS resistance of the RFC-8878 zstd **decoder**
(`zstd_decompress` and its closure in `src/zstd.cyr`, shipped decode-only at 2.5.0)
against hostile / malformed `.zst` input. Encoder side out of scope.
**Toolchain at audit:** Cyrius 6.4.67 (manifest-pin)
**Trigger:** A new `fuzz/fuzz_zstd.fcyr` decode-survival harness SIGSEGV'd on the
first random-input round — the zstd decoder had never been fuzzed (bzip2 / lz4 / xz
all had decode-survival harnesses; zstd did not).

---

## TL;DR

The decoder trusted attacker-controlled length and size fields throughout the decode
path. A crafted `.zst` could drive it to **read out of bounds, write past `dst_cap`,
or spin / allocate unboundedly**. An adversarial audit of every decoder section,
with each finding verified by an independent skeptic pass, surfaced **36 reachable
issues** (24 crash, 10 memory-corruption, 2 DoS) plus one sibling OOB in
`zstd_frame_content_size` (reachable from `tar.cyr`). All are fixed.

**Before → after (empirical):**

| corpus | before | after |
| --- | --- | --- |
| 1,148 malformed inputs (magic + hostile tails / headers) | 25 SIGSEGV, 133 hangs | **0 / 0** |
| 1,784 *valid* streams with byte-flips into Huffman/FSE/sequence decoders | (deep paths) | **0 / 0** |
| `fuzz_zstd.fcyr` (400 decode-survival + 600 round-trip + 150 corruption) | crash on case 1 | **PASS** |

**Happy path unchanged:** full tcyr suite green, reference `zstd -19` output (incl. a
1.2 MB binary) still decodes byte-identically, every round-trip byte-exact.

---

## Method

A workflow fanned out one auditor per decoder section (frame/block loop, literals,
Huffman tree, Huffman stream, FSE, sequences, bit readers). Each was given the buffer
invariants (`end`, `_z_outcap`, the 256 KiB `_z_lit`, the 2048-entry Huffman table,
per-call FSE dist sizes) and the one already-known crash as the pattern, then
enumerated every unchecked access or unbounded loop in its section as a structured
finding with a concrete triggering input and a proposed guard. Every finding was then
handed to an independent verifier prompted to **refute** it — confirm reachability
from `zstd_decompress(attacker_bytes, …)` with finite `dst_cap`, or reject it. 45
agents total; **2 findings rejected** as false positives (one an unreachable helper
path — later fixed anyway; one a write already bounded by an 18-bit size mask).

## Findings by section (36 confirmed)

| section | crash | mem-corruption | dos |
| --- | --- | --- | --- |
| frame header & block loop | 4 | 1 | — |
| literals section | 5 | 2 | — |
| Huffman tree description / build | 2 | 1 | — |
| Huffman stream decode | 1 | 1 | — |
| FSE readNCount / build | 2 | 1 | 1 |
| sequences decode & execute | 6 | 3 | 1 |
| bit readers | 2 | — | — |

## Root causes & fixes

1. **No frame `end` bound.** `end = src + src_len` (minus a trailing content checksum)
   is now established up front; the frame-header advance, the 3-byte block header, and
   every block's `bsize` are checked against it, so a truncated or oversized block
   cannot push any read past the input buffer. Each compressed block's `bend = p+bsize`
   is now `≤ end`, which makes the `end` handed to every sub-decoder a real bound.

2. **Output-capacity checked too late.** The only guard was `_z_outpos > _z_outcap`
   *after* a whole block was written. Now every write pre-checks `_z_outpos + n ≤
   _z_outcap`: Raw and RLE blocks, the no-sequence literal dump, per-sequence
   literal+match copies, and the trailing-literals copy.

3. **Scratch overflows.** Raw/RLE literal `regenerated_size` (up to 20 bits) is bounded
   to the 256 KiB `_z_lit`. Huffman `Max_Number_of_Bits` and each transmitted weight are
   capped at 11 (`HUF_TABLELOG_MAX`), so the 2048 = `1<<11` decode table can't overflow
   on build (`pos`) or lookup (`val`).

4. **Unbounded FSE (`readNCount`).** Now takes a read `limit` (bits requested past it
   read as 0, matching the spec's bitstream zero-padding — which also makes the
   zero-repeat loop terminate) and a per-table `Accuracy_Log` cap (weights ≤ 6, LL/ML ≤
   9, OF ≤ 8). It rejects a distribution that doesn't sum to exactly `1<<log`, a symbol
   overshoot past `maxSym`, or a read past the section. This eliminates the 24 MB-alloc
   / ~1 M-iteration DoS, the `_z_fse_build` infinite loop (needs a valid distribution to
   keep `highIdx ≥ 0`), and the downstream FSE-state index overrun (a validated table
   keeps every state `< 1<<log`). Both call sites (`_z_huff_tree`, `_z_seq_table`) now
   propagate its negative error.

5. **Sequence execution.** Offset codes (`≤ 31`), LL/ML/OF symbols (`< 36 / 53 / 32`),
   the match base (`mbase = _z_outpos − offset ≥ 0`, checked *after* the literals
   advance `_z_outpos`), and the literal cursor (`litptr + llen ≤ _z_litlen`) are all
   range-checked before use.

6. **`zstd_frame_content_size`** (the standalone helper `tar.cyr` calls to size an
   output buffer) had the same unbounded FCS/DID field reads; now every read is bounded
   by `src + src_len`.

## Verification

- **build** 0 warnings · **lint** 0 warnings/file · **cyrfmt --check** clean · **vet** clean.
- **Malformed corpus** (1,148 files): 0 SIGSEGV, 0 hang, 1,148 clean (was 25 + 133).
- **Deep corpus** (1,784 valid streams × byte-flips + truncations): 0 / 0 / clean.
- **Fuzz**: all 5 harnesses pass, including the new `fuzz_zstd.fcyr`.
- **Regression pin**: `test_zc_malformed_survive` decodes the exact 34-byte
  raw-block-overflow repro and asserts a clean error (a crash would abort the suite).
- **Happy path**: full tcyr suite green; reference `zstd -19` output for text, source,
  and a 1.2 MB binary decodes byte-identically; all round-trips byte-exact.

## Notes / residual

- The decoder remains **lenient** where leniency is memory-safe: past-limit bits read
  as 0 rather than erroring, matching the reference bitstream behavior. Rejections are
  reserved for structurally impossible tables/sizes.
- `src/zstd.cyr` is its own self-contained closure (`[lib.zstd]`); the hardening added
  no cross-module dependency — verified by a standalone compile of `types + zstd + stdlib`.
- No encoder changes. `dist/sankoch.cyr`, `dist/sankoch-zstd.cyr`, `dist/sankoch-tar.cyr`
  regenerated (decoder bytes changed); the other profiles are untouched.
