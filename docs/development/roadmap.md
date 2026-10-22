# Sankoch Development Roadmap

> **Status**: Stable (**v2.8.9**, cyrius **6.7.16**); open filings **0** (sit's `br_init` shipped fixed
> in 2.8.9). The 2.8.x line shipped the Brotli decoder (2.8.0) and encoder (2.8.4), the PCLMULQDQ CRC-32
> fold (2.8.5), the 2.8.x-closeout P(-1) pass (2.8.6: 2 HIGH · 10 MEDIUM · 19 LOW · 12 INFO;
> [dossier](../audit/2026-10-13-2.8.x-closeout.md)), a name fix for the stdlib fold (2.8.7), four
> toolchain releases (2.8.1–2.8.3, 2.8.8) and the repairs the 2.8.8 review found (2.8.9). Next: **2.9.0,
> public names as 6.7.x types**. **Every item of work has a release below**; of the INFOs `state.md`
> carried without one until 2.8.8, INFO-B and INFO-D's batch half closed in 2.8.9, INFO-C is 2.9.4 and
> INFO-D's per-context half 2.9.5. Before the next pin move, read
> [*Toolchain notes*](#toolchain-notes-for-the-next-pin-move). | **Last Updated**: 2026-10-22

This file is the **forward** ladder: **▶ Next**, then **▶ Scheduled**, each release pinned. **Shipped
history lives in [`CHANGELOG.md`](../../CHANGELOG.md); the live per-release snapshot lives in
[`state.md`](state.md).** This file does not re-list what shipped.

**Where the library stands.** Every lossless codec it carries de+compresses:
LZ4 / LZ4F / DEFLATE / zlib / gzip / xz / bzip2 / zstd / Brotli (decode 2.8.0, RFC 7932 including the
static dictionary; encode 2.8.4, without it). On top of that:
- ratio-capped decompression across the DEFLATE family + xz + bzip2;
- a shared tar cursor;
- a full PKZIP `.zip` container (reader + writer, every method sankoch owns, Zip64, streaming,
  tar-parity metadata).

The zstd encoder beats `zstd -3` on every benchmark fixture and `zstd -19` on record data; xz encode is
within ~0.2 % of `xz -6` on inputs that fit its window. Since 2.8.6 the LZ4F and xz decoders accept and
reject exactly what `lz4 -d` and `xz -d` do. Security reviews so far:
- the pre-2.6.0 P(-1) pass over the 2.4.x/2.5.x codec surface;
- the 2.6.4 P(-1) pass over the ZIP surface
  ([`docs/audit/2026-07-20-zip-container.md`](../audit/2026-07-20-zip-container.md));
- the 2.8.0 pre-release review of the Brotli decoder and the reset seam
  ([`docs/audit/2026-09-16-2.8.0-brotli-and-reset.md`](../audit/2026-09-16-2.8.0-brotli-and-reset.md));
- the 2.8.6 closeout over the 2.7.x encoders, the 2.8.x additions, the runtime seam and the DEFLATE
  2.7.9 surface ([`docs/audit/2026-10-13-2.8.x-closeout.md`](../audit/2026-10-13-2.8.x-closeout.md)).

**How the ladder is kept.** Each release below is committed in **order**; the numbers are not. A
toolchain or ecosystem release that has to land first takes the next patch number and shifts the
rest (as 2.8.1–2.8.3 did). New work does not go into a backlog: it takes a slot here, either at the
end (before the closeout) or, when it outranks something, ahead of it with the reason written down.
Large items ship as small bites (CLAUDE.md, *Task Sizing*). The `C-NN` ids are the 2.8.6 audit's.

---

## ▶ Next — 2.9.0, public names as 6.7.x types (minor)

A minor because it changes the public surface; the 2.8.6 closeout was its P(-1) pass, so it opens the
2.9.x line directly.

- **Public integer constants → `const`**: `TAR_*` (12, `src/tar.cyr`), `ZIP_*` (21, `src/zip.cyr`) and
  `SANKOCH_ARENA_MAGIC` are never-written `var`s today. A `const` beside a same-name `var` is a hard
  error in cyrius, so survey cyrius's `lib/` and every fold for each name first. **Checked at 2.8.8
  against cyrius 6.7.16's `lib/`:** no other leaf declares any of the bundle's 1,036 top-level names or
  its 223 enum members, as a `var`, `fn`, `const`, `enum` or `struct`, so nothing blocks the conversion
  today. Re-run the census at the 2.9.0 pin: cyrius's own `var`-to-`const` arc is open (its
  `docs/development/issues/2026-10-08-lib-public-constants-const-migration.md`).
- **A `SANKOCH_ERR_*` namespace** for the error codes: `enum Error`'s bare `OK` / `ERR_*` names and
  the `TAR_ERR_*` values share the stdlib's one global namespace with every consumer (cyrius's lint has
  noted the 12 `ERR_*` members since 6.7.10, and still does at 6.7.16).
- **`: bool`** on the public predicates, and on the five private path / checksum safety predicates
  (`_star_path_safe`, `_star_symlink_safe`, `_star_ledger_prefix_unsafe`, `_star_checksum_ok`,
  `_zip_path_safe`).
- **The Huffman / LZ77 primitives go private** (C-08's follow-through): `huff_build_*`, `huff_decode_*`,
  `huff_compute_lengths`, `huff_build_enc_codes`, `lz77_init`, `lz77_rebase`. They share the library's
  tables, so a consumer cannot use them safely beside other sankoch calls; no other repo calls them
  (checked across ~/Repos on 2026-10-13). 2.8.6 made them lock; 2.9.0 removes them from the surface.
- **`zstd_set_level` goes** (C-36): public, unlocked, and overwritten by every compress entry.
- **The checksum read entries after `alloc_reset()`** (C-28): `crc32`, `crc32_update`, `crc64`,
  `crc32_bzip2` read a table that a reset invalidates and do not re-check. Decide in the API pass:
  make them self-initialising under the guard (one compare on the hot path), or keep "call
  `*_init_table()` first, and again after a reset" and say so on every entry.

---

## ▶ Scheduled — the 2.9.x ladder

### 2.9.1 — DEFLATE match-finder throughput

**The trigger has fired.** sit measured it as its single worst benchmark row (sit v1.4.8–1.5.x,
`docs/benchmarks/2026-08-19-v1.4.8.md`):

| measurement | value |
|---|---:|
| `add-1MB`, sit vs git | **6.37×** (104.27 ms vs 16.38 ms) |
| of which `zlib_compress` | **~100 ms — the dominant term** |
| `blob-hash-1048576B` (sigil SHA-256, same 1 MB) | 4.73 ms |
| `zlib-compress-65536B` | 1.067 ms |
| `zlib-compress-1024B` | 123.7 µs |

Hashing the same megabyte costs 4.7 ms against compression's ~100 ms; sit has driven every other row it
controls to parity or better, so this is the largest gap that is not sit's own code.

**The constraint is the hard part.** zlib byte-for-byte parity is load-bearing for sankoch's consumers,
so `good_match` and friends are off the table (they change output). A win has to find the *same*
matches faster: tighter chain-walk scheduling, a better hash, or a provably output-preserving
lazy-match restructure. **Every candidate is gated on byte-identical output across a real corpus
before a benchmark number is quoted.** The CRC-32 fold does not touch this (sit's cost is match finding
in `lz77.cyr`; zlib checks with Adler-32). Open-ended: bites, each with its own before/after.

### 2.9.2 — Bounded work per input byte

The closeout's CPU findings, all under the lock, so each stalls every other sankoch call:
- **xz encoder interior-cut check** (C-29): O(4·W²) per 4 KiB window on near-uniform input (20–27 s/MiB
  on zeros with sparse changes, against 1.5–4.8 s/MiB normally and `xz -9e`'s 0.12 s). Within a window
  `pos + avail` is constant, so the check depends only on the rep distance: cache the last mismatch per
  distance once per window and each check is O(1). Must be output-identical (a digest over a corpus,
  before and after), as the 2.7.x encoder work was.
- **Brotli IMTF** (C-30): about 7× libbrotlidec's work per input byte on chained 256-type meta-blocks
  (a wider move, or google's `mtf_upper_bound`), or the bound written into the threat model.
- **Encoders stop on a full `dst`** (C-37): the zstd and xz encoders keep encoding after `dst`
  overflows, so a 1-byte cap costs a full level 9 / xz encode.
- The measure: the reviews' adversarial inputs (`build/review/xz/p6..p8`, the IMTF chain) as relative
  work budgets in the suites, the way `test_long_codes_decode_in_bounded_work` bounds DEFLATE.

### 2.9.3 — LZ4F frame completeness and decoder placement coverage

- **Concatenated and skippable frames** (C-43): `lz4 -dc` decodes a stream of frames and skips
  skippable ones; sankoch decodes one frame per call and leaves the rest unread (batch) or unconsumed
  (streaming). Batch and streaming both, and the kernel-safe `[lib.core]` decoder must stay alloc-free.
- **One output cap**: a streaming raw block is capped frame-wide at 16 MB while compressed blocks are
  capped per block (C-43); make it one rule.
- **Guard-page placement in CI for the DEFLATE-family decoders** (the coverage matrix's open cell): the
  fuzzers place only Brotli against `PROT_NONE` pages today.

### 2.9.4 — CRC-32 dispatch: aarch64, AGNOS ring 0, provenance

- **A faster CRC-32 on aarch64.** 2.8.5 left aarch64 on slice-by-8 (ADR 0003): PMULL and the CRC32
  instructions are optional in ARMv8.0, and the supported feature check (AT_HWCAP) reads
  `/proc/self/auxv`, which `src/` may not open. Options: Linux's userland emulation of
  `mrs ID_AA64ISAR0_EL1` (not on macOS / AGNOS), or a caller-supplied capability flag.
  `qemu-aarch64` is available locally to verify either.
- **A no-SIMD build for AGNOS ring 0** (C-40): every profile with `checksum.cyr` carries xmm
  instructions, which the AGNOS kernel forbids, and the kernel's roadmap plans in-kernel sankoch. Today
  the only opt-out is `_crc32_hw = 0` at run time.
- **Provenance to the binary** (C-41): `scripts/crc32-clmul-asm.sh --check` should also find the
  assembled `.text` in a built binary, and cover the hand-written CPUID and `param_load` lines.
- **The stranded-canary predicate under `CYRIUS_POISON` on macOS / Windows** (C-42, suspected): verify
  on a host, and switch to the exact form (record `_heap_ptr` at arm time) if it misfires.
- **INFO-C, while the aarch64 work is open** (carried in `state.md` with no release until 2.8.8): the
  one unaligned `load64` in the LZ77 / FDICT path. Measure it under `qemu-aarch64` beside the CRC
  work; keep it if the cost is noise, otherwise align the read.

### 2.9.5 — RFC 7692 both directions (per-context DEFLATE streaming state)

C-11: the 2.7.9 `permessage-deflate` support holds the lock from init to finish, so a connection's
encoder and decoder cannot both be open on one thread, a process serves one compressed connection at a
time (and on AGNOS, where the lock is a no-op, two open contexts would share the global tables), and
the decoder's output only grows. The fix is structural: the streaming DEFLATE state (bit I/O, Huffman
tables, the LZ77 window and hash chains) moves from globals into the context, so the lock is held per
call rather than per context, and the decoder writes into a ring window. **An ADR first** (memory per
context, what stays global, how the batch paths share code). bote is the consumer that asked.

**Memory per context is a repair, not only a design question** (the 2.8.8 review). Every streaming
init takes its context from the bump arena and nothing returns it, finish included. Measured at 2.8.8:
**one `zlib_enc_init` → write → finish keeps 65,728 B**, 65,536 of it the encoder's window
(`DENC_WINDOW_CAP`). A server that opens a context per connection grows by that much per
connection. The others that do the same:
- `deflate_dec_init` (192 B, plus `dict_len` with a dictionary);
- the zlib / gzip decoder contexts;
- `lz4f_dec_init` and `lz4f_enc_init_ex` (a context plus a 64 KiB to 4 MiB block buffer);
- `stream_*_init` (48 B, plus `STREAM_INIT_CAP` for buffered decompress);
- `tar_open` (128 B) and `tar_open_auto` (the whole decompressed archive).

The ADR decides one rule for all of them. The precedent is the zip reader and writer (2.7.7): `_via`
forms that take a caller arena, which `reset_via` really frees, where a `*_close` on a bump allocator
could only be a no-op that reads like a reclaim (`src/runtime.cyr`, `_sankoch_alloc_via`). This is
INFO-D's remaining half; 2.8.9 closed its batch half (`heap_growth.tcyr`).

### 2.9.6 — Brotli encoder: priced / optimal parse (qualities 10–11)

Measured against `brotli -q N -w 24` 1.2.0
([`docs/benchmarks/2026-10-13-2.8.4-brotli-encoder.md`](../benchmarks/2026-10-13-2.8.4-brotli-encoder.md)):
sankoch is smaller at q1–q6 on source, binary and font data and within 1 % at q9; the reference leads by
10–13 % at q11, and from q5 on record-structured data. Qualities 10–11 equal 9 today. Model it on the
zstd DP parse (2.7.3): per-node distance-cache state, costs from a first pass's statistics. It is also
the fix for record data, where google/brotli's static score prefers a longer, farther match over a
cheap repeat distance. Keep architecture 005's four invariants.

### 2.9.7 — Brotli encoder: block splitting

NBLTYPES > 1 for literals, commands and distances, with block-switch codes. The reference uses it from
q4; it matters most on heterogeneous input. Architecture 005's invariants hold.

### 2.9.8 — Brotli encoder: static-dictionary references and transforms

The reference's lead on small text. The decoder's dictionary and transform tables are already in the
tree. A dictionary reference must not push the distance ring (architecture 005).

### 2.9.9 — Encoder polish

- **zstd** (C-38): ~0.37 ms fixed cost per call (resetting, snapshotting and restoring the 64K-bucket
  head table moves ~1.5 MB per call), and the level-ladder inversion on token data (L1 119 KB,
  L2–L6 134–137 KB; `test_zc_level_knob` asserts only L9 ≤ L1).
- **xz** (C-39): emit LZMA2 uncompressed chunks for incompressible data (random input grows 1.38 % today)
  and count pending carry bytes against the chunk's compressed soft cap.
- **Brotli encode speed**: q6 runs at 7.3 MB/s on alice29 (clustering and per-literal bit writes
  dominate). No consumer has asked yet; this is where it goes when one does.

### 2.9.10 — Primitives for mabda's texture work (opens on mabda's request)

ADR 0004; mabda's filing `docs/development/issues/2026-10-13-gpu-texture-compression-encoder.md`.
Already available, no sankoch work: KTX2 supercompression scheme 2 (Zstandard) via `zstd_decompress` /
`zstd_compress_level` and scheme 3 (ZLIB) via `zlib_decompress_capped` / `zlib_compress`. **This slot**
is a public cost estimate ("bits this block costs after LZ + entropy coding, given the bytes before
it") for a rate-distortion-optimized BCn encoder, built from the existing match finders, Huffman / FSE
coders and the Q16 log2. Its entry condition is mabda filing the shape it needs; if that has not
happened when the slot's turn comes, the closeout goes first and this keeps the next number.

### 2.9.11 — the 2.9.x-closeout P(-1) pass

The P(-1) before the next minor ([`CLAUDE.md` § P(-1)](../../CLAUDE.md)), over everything 2.9.x added:
the API pass, the match-finder rewrite (byte-identity is its whole contract), the per-context DEFLATE
state and its lock lifetime, the Brotli encoder's parse / splitting / dictionary, the CRC dispatch and
any new asm. Review coverage as a matrix again (input × path × buffer placement × oracle), and keep the
reference differentials of 2.8.6 (`lz4 -dc`, `xz -dc`, libbrotlidec, zlib) as standing tools.

Primitive sources for future codec items (Rice/Golomb, range encoder, LPC) are tabulated under
[§ Primitive sources](#primitive-sources-for-future-codecs) below.

---

## ZIP container — deliberately not there

**Non-goals** (like the codec non-goals): **encryption** — ZipCrypto is
cryptographically broken, and AES-in-ZIP needs a real AES primitive sankoch
deliberately doesn't carry (zero-crypto-dep, cf. xz's unverified SHA-256);
**multi-disk / spanned** archives (obsolete); **Deflate64** (method 9 — a
separate codec, not RFC 1951).

---

## Known limitations / non-goals

- **Brotli encode** (2.8.4) writes no static-dictionary references and one block type per category,
  so qualities 10 and 11 equal 9; there is no streaming encoder, and the encoder is in the full bundle
  only. Its output is not SIZE-gated until the ratio steps (2.9.6–2.9.8) settle.

- **LZ4F decode** reads one frame per call; concatenated and skippable frames are 2.9.3.

- **xz**: `--check=sha256` streams are **rejected** (`ERR_UNSUPPORTED_FORMAT`)
  since 2.5.9 — sankoch carries no SHA-256 primitive, so it fails closed rather
  than accept an unverified payload (CRC-32 / CRC-64 checks are verified). The
  legacy `.lzma` alone-format is not handled. xz encode is within ~1–5 % of
  `xz -6` (optimal parse, not bit-identical to `xz`). Since 2.7.0 the *repetitive*
  regime is within ~1.5× of `xz -6` (the `nice_len` greedy shortcut); since 2.7.1
  the *real-source* regime is ~5.8× slower (0.73 vs 4.2 MB/s, BT4 match finder); since
  2.7.2 its **ratio is within ~0.2 % of `xz -6`** on inputs that fit the 256 KB window
  (was +7 %). A speed gap to xz's optimized C persists, and inputs larger than 256 KB
  keep a small ratio residue (a one-line window bump closes it, at more memory). bzip2
  encode is byte-identical to `bzip2 -9`. Neither encoder is in the wire-format SIZE gate
  — both ship informational ratio lines in `bench`.

---

## New-codec context (for future codec items)

Because the per-codec distlib profiles let a consumer pull only the closure it
needs (see *Modular by profile* in [`CLAUDE.md`](../../CLAUDE.md)), sankoch is the
home for **every** lossless-compression codec — new formats never bloat consumers
that don't use them, so nothing is "a separate crate." Brotli decode shipped in 2.8.0
and encode in 2.8.4. **Lossy** GPU texture compression (BC1–BC7 / ASTC) is not a sankoch codec: it
lives in mabda ([ADR 0004](../adr/0004-gpu-texture-compression-in-mabda.md)), leaning on sankoch's
lossless primitives (2.9.10);
Zstandard is done (decode 2.5.0, sovereign encoder 2.5.5, beats `zstd -3`, optimal
parse 2.7.3 — its remaining record-data ratio residue is the 2.7.4 window item, not
a new codec).

### Primitive sources for future codecs

| Primitive | Home | File | Lines |
|-----------|------|------|-------|
| Rice/Golomb coding | shravan/FLAC | flac.cyr | 367-437 |
| Range encoder | shravan/Opus | opus.cyr | 175-284 |
| LPC prediction | shravan/FLAC | flac.cyr | 517-580 |

---

## File Summary (at 2.3.0)

> Heading anchor kept stable (`#file-summary-at-230`) for the CLAUDE.md and state.md cross-links.
> The figures are refreshed every release. Current as of **2.8.9**, re-counted with `wc -l`.
> 2.8.9 grew `bitreader.cyr` 100 → 108, `bitwriter.cyr` 145 → 152 (the in-place initialisers),
> `deflate.cyr` 3,000 → 3,004 and `zlib.cyr` 542 → 545 (the INFO-B comments). No line changed at
> 2.8.7 (a rename) or 2.8.8 (a toolchain release).
> 2.8.6 (the closeout's fixes) grew `lz4_decode.cyr` 181 → 211, `lz4.cyr` 949 → 1,002, `xz.cyr`
> 2,136 → 2,199, `huffman.cyr` 709 → 808, `deflate.cyr` 2,976 → 3,000, `checksum.cyr` 732 → 748;
> `runtime.cyr` 275 → 271, `zip.cyr` 1,386 → 1,367 (dead code removed).
> 2.8.5 grew `checksum.cyr` 567 → 732 (the PCLMULQDQ fold).
> 2.8.4 added `brotli_enc.cyr` (1,865) and grew `lib.cyr` 252 → 258.
> 2.8.3 moved the dictionary literal out of `brotli_dict.cyr` into `cyrius.cyml [embed]` and made
> `zstd.cyr`'s backtrack a `loop` (82 → 83 and 3,114 → 3,113 lines; the total is unchanged).
> 2.8.0 added `brotli.cyr` + the generated `brotli_dict.cyr` (one 122,784-byte literal, so few lines)
> and ten `reset_<profile>.cyr` dispatchers. It also moved each module's reset into the module,
> which is why `lib.cyr` shrank.
> The tree is **24 domain modules + 10 reset dispatchers**.

| File | Lines | Role | Profile |
|------|-------|------|---------|
| types.cyr        |   44 | Enums: formats (incl. FORMAT_XZ, FORMAT_BZIP2, FORMAT_ZSTD, FORMAT_BROTLI), errors (incl. ERR_OOM, ERR_RATIO_LIMIT, ERR_OUTPUT_LIMIT), limits | core |
| xxhash32.cyr     |   94 | xxHash32 batch + helpers + XXH32 enum (kernel-safe) | core |
| checksum.cyr     |  748 | Adler-32 / CRC-32 (slice-by-8, + the x86_64 PCLMULQDQ fold 2.8.5) / CRC-64-XZ / CRC-32-BZIP2 + incremental state APIs; unlocked table builders carry the arena guard (2.8.0) | full |
| bitreader.cyr    |  108 | LSB-first bit-stream reader; batch inflate keeps its reader on the stack (`_br_init_at`, 2.8.9) | full |
| bitwriter.cyr    |  152 | LSB-first bit-stream writer; batch deflate keeps its writer on the stack (`_bw_init_at`, 2.8.9) | full |
| huffman.cyr      |  808 | Huffman build/decode (Kraft-validated, canonical count/offset slow path, 2.8.6), fixed + optimal trees, encoder pre-reversed codes; public builders lock around `_inner` bodies (2.8.6) | full |
| lz77.cyr         |  208 | Sliding window match-finder, 8-byte word-compare match extend, `lz77_rebase`, ring-buffer slide | full |
| lz4_decode.cyr   |  211 | LZ4 block + frame decompress (checked as `lz4 -d`, linked blocks, 2.8.6) + LZ4F enum (kernel-safe) | core |
| lz4.cyr          | 1002 | LZ4 block + frame compress + `lz4f_enc_*` + `lz4f_dec_*` streaming | full |
| deflate.cyr      | 3004 | DEFLATE de/compress, adaptive blocks, `deflate_enc_*` + `deflate_dec_*` streaming, dict, ratio cap, RFC 7692 sync flush + fixed-vs-dynamic block chooser | full |
| zlib.cyr         |  545 | RFC 1950 wrapper + FDICT + streaming + ratio cap + caller output ceiling (`zlib_decompress_capped`) | full |
| gzip.cyr         |  656 | RFC 1952 wrapper + concatenated batch/streaming + FHCRC + ratio cap | full |
| xz.cyr           | 2199 | `.xz` de/compress: LZMA2 + range coder (decode checked as liblzma, 2.8.6), optimal parse, BT4 finder, 256 KB window, ratio cap | full |
| bzip2.cyr        | 1347 | `.bz2` de/compress: BWT + MTF/RLE2 + Huffman + RLE1, ratio cap | full |
| zstd.cyr         | 3123 | `.zst` de+compress (RFC 8878): hardened decoder + encoder (FSE/Huffman, DP optimal parse L7–9, cross-block window, chain cutoff) | full |
| brotli.cyr       | 1460 | **Brotli decode (RFC 7932, 2.8.0)**: bit reader, prefix codes, context maps + IMTF, block switching, command loop, dictionary transforms; `brotli_decompress` / `_capped` | full, brotli, woff |
| brotli_enc.cyr   | 1865 | **Brotli encode (RFC 7932, 2.8.4)**: bucketed-hash LZ77 + distance cache + lazy step, literal context modeling chosen by exact cost, length-limited prefix codes + context maps, stored fallback; `brotli_compress` / `_level` / `_bound` | full |
| brotli_dict.cyr  |   83 | RFC 7932 dictionary geometry (NDBITS / DOFFSET) + FNV-1a verify; the 122,784 bytes are `cyrius.cyml [embed] _brotli_dict_bin` (2.8.3; a generated literal before) | full, brotli, woff |
| zip.cyr          | 1367 | PKZIP `.zip` container: reader + writer, methods 0/8, Zip64, streaming write, Unix metadata, sizing + reclaimable readers | full |
| zip_methods.cyr  |  150 | ZIP methods 12 / 93 / 95 (bzip2 / zstd / xz), kept out of `[lib.zip]` | full |
| tar.cyr          |  710 | POSIX ustar + v7 tar pull-cursor (`tar_open_auto` sniffs gzip/xz/bzip2/zstd), traversal guards | full |
| stream.cyr       |  262 | Streaming dispatch (`stream_compress_*`, buffered + incremental decompress) | full |
| runtime.cyr      |  271 | Lock (a BSS cell, guard under it, 2.8.6) + alloc seam + arena guard: canary, stranded-canary predicate, failed-arm handling (2.8.0); the reset registration rule | full |
| lib.cyr          |  258 | Include chain + public API + format dispatch + the full bundle's `_sankoch_reset_tables` | full |
| reset_<profile>.cyr ×10 | 179 | Per-profile `_sankoch_reset_tables` dispatchers (brotli 15, bzip2 16, gzip 18, tar 21, woff 20, xz 17, zip 18, zipall 21, zlib 18, zstd 15) | one each |
| **Total**        | **20854** | | |

`core` modules (types + xxhash32 + lz4_decode = 349 source lines)
form `[lib.core]` → `dist/sankoch-core.cyr`. They contain no
`alloc()`, no syscalls, no mutex usage — verified by the CI
"Kernel-safe tripwire" gate (`programs/core_smoke.cyr`).

Tests: 32 runnable suites in `tests/tcyr/` producing **4,501,380 assertions** (0 failed), including
`brotli_decompress.tcyr` (4,555), `heap_growth.tcyr` (394, 2.8.9: zero heap growth over every batch
entry), `xz_decompress.tcyr` (7,052), `deflate_decompress.tcyr` (2,545),
`zip.tcyr` (311), `zstd_compress.tcyr` (193), `stream.tcyr` (179), `arena_reset.tcyr` (124) and the
2.8.6 `oom_matrix.tcyr` (5 verdicts over every allocation of 24 operations). Most of the total comes from per-byte
round-trip loops on the streaming suites. A single 200 KB round-trip contributes 200,000 assertions
through one `while (i < N) assert(byte_eq)` loop, so the headline number measures coverage *density*,
not coverage *breadth*. See
[`../guides/cyrius-usage.md`](../guides/cyrius-usage.md#what-assertions-means-here-and-why-the-number-is-so-large)
for the full explanation.

Fuzz: 9 files (`fuzz_lz4`, `fuzz_deflate`, `fuzz_xz`, `fuzz_bzip2`, `fuzz_zstd`, `fuzz_zip`,
`fuzz_brotli`, `fuzz_brotli_enc`, `fuzz_crc32`). 2.8.0 added `fuzz_brotli`: 13 seeds + 5,000 mutated / random /
truncated / spliced inputs, with src and dst placed against PROT_NONE guard pages. 2.8.4 added
`fuzz_brotli_enc`: 2,000 encodes at random qualities, guard-paged, each decoded exactly. 2.8.5 added
`fuzz_crc32`: 6,000 PCLMULQDQ-fold-vs-table cases (buffers, offsets, registers, chunkings, bit flips). Per-file breakdown in
[`state.md` § Fuzz totals](state.md#fuzz-totals).

Distlib: **12 bundles**, one per profile in `cyrius.cyml`:

| Bundle | Lines |
|---|---:|
| `sankoch.cyr` (full) | 20,745 |
| `sankoch-core.cyr` (kernel-safe) | 363 |
| `sankoch-zlib.cyr` | 6,043 |
| `sankoch-gzip.cyr` | 6,154 |
| `sankoch-xz.cyr` | 3,612 |
| `sankoch-bzip2.cyr` | 2,548 |
| `sankoch-zstd.cyr` | 3,474 |
| `sankoch-tar.cyr` | 13,549 |
| `sankoch-zip.cyr` (methods 0/8) | 6,866 |
| `sankoch-zipall.cyr` (every method) | 13,700 |
| `sankoch-brotli.cyr` (Brotli decode) | 1,905 |
| `sankoch-woff.cyr` (zlib closure + Brotli) | 7,602 |

Per-bundle roles are in [`state.md` § Dist bundles](state.md#dist-bundles).

## Dependencies

**Zero external.** Checksums (Adler-32, CRC-32, xxHash32 — batch and
incremental) are inline. No sigil dependency. Stdlib-only: `syscalls`,
`string`, `alloc`, `fmt`, `vec`, `fnptr`, `thread`, `assert` (all
ship with Cyrius ≥ 6.0.1; the pin is in `cyrius.cyml`, 6.7.16 at 2.8.8).

## Key References

- RFC 1951 — DEFLATE Compressed Data Format Specification
- RFC 1950 — ZLIB Compressed Data Format Specification
- RFC 1952 — GZIP File Format Specification
- RFC 7932 — Brotli Compressed Data Format (errata 6977); google/brotli v1.2.0 `c/dec/decode.c` as cross-check
- LZ4 Block Format — github.com/lz4/lz4/blob/dev/doc/lz4_Block_format.md
- LZ4 Frame Format — github.com/lz4/lz4/blob/dev/doc/lz4_Frame_format.md
- The .xz File Format v1.1.0 — tukaani.org/xz/xz-file-format.txt
- LZMA SDK `LzmaDec.c` / xz-embedded `xz_dec_lzma2.c` — LZMA decoder reference shape
- Feldspar, "An Explanation of the Deflate Algorithm" — clearest DEFLATE walkthrough
- Intel, "Fast CRC Computation for Generic Polynomials Using PCLMULQDQ Instruction" (whitepaper, Dec 2009)
- Duda, "Asymmetric Numeral Systems" (arXiv:1311.2540) — for future Zstandard work

---

*Last Updated: 2026-10-22 (the 2.8.9 cut: status v2.8.9; the shipped 2.8.9 repairs section removed; ▶ Next = 2.9.0; 2.9.5 notes INFO-D's batch half closed; File Summary / tests / distlib re-counted; *Toolchain notes*: the `--agnos` refusals handled by the link gate). Previous: 2026-10-22 (the 2.8.8 review: status v2.8.8 on cyrius 6.7.16; ▶ Next = **2.8.9, repairs**, ahead of 2.9.0 with the reason written down: sit's `br_init` filing (was 2.9.11) widened to `bw_init`, measured, plus INFO-B, the `core_smoke` NUL, a stale zstd comment and the lint deferral list; INFO-C pinned to 2.9.4, per-context memory (INFO-D's other half) to 2.9.5; the closeout back to 2.9.11; the 2.9.0 `const` collision census run against 6.7.16; the bzip2 bundle's line count corrected, 2,535 → 2,548). Previous: 2026-10-20 (sit filed `br_init`'s per-inflate 32 B as 2.9.11; the closeout moved to 2.9.12). Previous: 2026-10-13 (the 2.8.6 cut: status v2.8.6; ▶ Next = 2.9.0 (with the closeout's API items); the Backlog retired: every item and every deferred finding pinned to 2.9.1–2.9.11; File Summary / tests / distlib re-counted. Previous: 2026-10-13, GPU texture compression moved to mabda.)*

---

## Toolchain notes for the next pin move

**The 2.8.3 blocker is resolved.** cyrius refuses an `[embed] NAME` that a leaf of the pinned stdlib
declares, and sankoch's own fold (`lib/sankoch.cyr`) is such a leaf; from 2.8.3 on it declares
`_brotli_dict_bin`. cyrius **6.7.6** stopped counting the project's own fold as an owner (its
changelog: "an `[embed]` NAME is no longer refused by the project's OWN fold"), and 2.8.4 moved the
pin to **6.7.10**, whose stdlib carries the 2.8.3 fold. So **6.7.6 is this repo's toolchain floor**;
a pin below it cannot build against a stdlib that folds 2.8.3 or later.

**Every compile in this project carries the dictionary.** cyrius prepends the `[embed]` module to each
build here, `--no-deps` included. A build that also includes a bundle carrying the embed (the
link-gate probes for `full` / `brotli` / `woff`, `sankoch_raw_include.tcyr`) defines the accessor
twice: cycc warns `duplicate fn '_brotli_dict_bin'` (or `_brotli_dict_bin_len`) and links the bundle's
(the later) definition. That warning is expected. A bundle that calls the accessor without listing it
under `embed` is refused by `cyrius distlib`, which CI's dist gate runs for every profile.

**cyrius's lint notes `types.cyr`'s bare `ERR_*` enum members** (a *note*, which CI does not gate on;
only `warn` lines fail), from 6.7.10 through 6.7.16. The 2.9.0 `SANKOCH_ERR_*` item is the fix.

**The 6.7.16 move (2.8.8) needed no source change.**
- `cyrius deps` re-vendored 12 of the 28 `lib/` leaves (alloc, alloc_cx, mmap, the seven syscall
  peers, thread, thread_local). The changes are comments, the cx heap, and epoll / poll / errno work in
  the peers. `alloc.cyr`'s `_heap_*` globals, which `src/runtime.cyr` reads, did not change. No added
  name collides with one of sankoch's.
- The 6.7.11–6.7.16 behaviour changes that could have reached this tree do not. sankoch already does
  what each one requires, or uses nothing it touches:
  - cyrlint's constant-offset and write-length checks (TL-3, TL-21): 0 warnings;
  - the duplicate-global warning (FX-6, the one that caught `_bre_err`): none here;
  - the one-owner distlib rule (TL-4): sidecars unchanged;
  - enum members need `;` or `,` (FE-16): every member already ends in `;`;
  - `param_load` needs the whole register name (TL-8): `rdi` / `rsi` / `rdx` / `rcx` / `r8` already;
  - `cyrius tests` was removed (TL-7): CI runs `cyrius test <file>`.
- No reserved word was added. The `--agnos` refusals are handled since 2.8.9: on a host whose CLI
  cannot build AGNOS images, `scripts/profile-link-gate.sh` reports that step NOT RUN and exits 77.
- The baseline-first run is recorded in
  [`docs/benchmarks/2026-10-22-2.8.8-toolchain-6.7.16.md`](../benchmarks/2026-10-22-2.8.8-toolchain-6.7.16.md):
  every gate identical, the 47 SIZE rows identical, speed neutral, the DCE binary 4,096 B smaller.
- 6.7.16's stdlib vendors **2.8.7** (`lib/sankoch.cyr` is byte-identical to the tag's `dist/sankoch.cyr`;
  refolded at 6.7.11, cyrius `docs/ecosystem.md`).

**Worth watching at the next move:** cyrius's open issue
`2026-10-21-value-builtin-statement-load8-compiles-load16-unexpected.md`. If it is decided by
refusing a bare `load8(p);` statement, that is a new error. This tree has none today.

**How the pin moves** (2.8.4's recipe, used again at 2.8.8):
- Run the local CI replica on the **old** pin first, as the baseline.
- Then bump `cyrius.cyml` and run `cyrius deps`.
- Then run the whole CI sequence again, **before** any source change, so a toolchain regression cannot
  hide inside a feature diff. That is lint, fmt, vet, every bundle regenerated and diffed, the link
  gate, every suite, the raw-include `--no-deps` builds, the aarch64 cross-build, every fuzz harness,
  and the bench's SIZE rows and timings against the baseline.
- cyrius re-execs into the pinned toolchain, so both runs use the right compiler.
- ⚠ Switching the pin back and building re-locks `lib/` to the old stdlib. Run `cyrius deps` again
  after any such comparison.
- Read cyrius's `docs/development/ecosystem-migration.md` for each version passed.
