# Sankoch Development Roadmap

> **Status**: Stable (**v2.8.3**); open issue queue **0**. 2.8.0 shipped the Brotli decoder
> (rekha's WOFF2) and the per-profile arena-reset fix that made every codec profile link again.
> 2.8.1–2.8.3 were toolchain releases: the cyrius 6.6.18 pin (2.8.1), the `loop` rename (2.8.2), and
> the cyrius 6.7.5 pin with the dictionary as an `[embed]`, the zstd backtrack as a `loop` and the
> private knobs as `const` (2.8.3, the cyrius W2 stdlib wave).
> Next: **2.8.x**: Brotli encoder (2.8.4), then SIMD CRC-32, then GPU texture, then the P(-1) closeout.
> ⚠ The **DEFLATE match-finder** backlog item is no longer speculative: sit has
> measured it as its single worst benchmark row; see Backlog. ⚠ Before the next pin move, read
> [*Toolchain notes*](#toolchain-notes-for-the-next-pin-move). | **Last Updated**: 2026-10-08

This file is the **forward** ladder — the committed next releases
(**▶ Scheduled**) and an unscheduled **Backlog** to be re-organised when the
next arc opens. **Shipped history lives in [`CHANGELOG.md`](../../CHANGELOG.md);
the live per-release snapshot lives in [`state.md`](state.md).** This file does
not re-list what shipped.

**Where the library stands.** Every lossless codec it carries de+compresses:
LZ4 / LZ4F / DEFLATE / zlib / gzip / xz / bzip2 / zstd. Brotli **decodes** (2.8.0, RFC 7932
including the static dictionary). On top of that:
- ratio-capped decompression across the DEFLATE family + xz + bzip2;
- a shared tar cursor;
- a full PKZIP `.zip` container (reader + writer, every method sankoch owns, Zip64, streaming,
  tar-parity metadata).

The zstd encoder beats `zstd -3` on every benchmark fixture, and the zstd decoder is hardened
against hostile input. Security reviews so far:
- the pre-2.6.0 P(-1) pass over the 2.4.x/2.5.x codec surface;
- the 2.6.4 P(-1) pass over the ZIP surface
  ([`docs/audit/2026-07-20-zip-container.md`](../audit/2026-07-20-zip-container.md));
- the 2.8.0 pre-release review of the Brotli decoder and the reset seam (0 HIGH · 4 MEDIUM · 15 LOW ·
  4 INFO, all fixed; [`docs/audit/2026-09-16-2.8.0-brotli-and-reset.md`](../audit/2026-09-16-2.8.0-brotli-and-reset.md)).

The 2.4.x–2.7.x encoder work closed the largest measured gaps in the tree: the
xz-encode arc (2.7.0 repetitive speed, 2.7.1 BT4 match finder, 2.7.2 256 KB window),
then the zstd encoder (2.7.3 DP optimal parse, 2.7.4 cross-block match window —
which now **beats `zstd -19` on record data** — 2.7.5 repetitive-record chain-cutoff
refinement).

The **2.8.x line** (see **▶ Scheduled** below):
- **2.8.0** shipped the Brotli decoder;
- **2.8.1–2.8.3** shipped toolchain moves (no feature; see CHANGELOG);
- **2.8.4** = Brotli encoder;
- **2.8.5** = SIMD CRC-32 (`PCLMULQDQ`);
- **2.8.6** = GPU texture compression;
- then a **P(-1) hardening pass** closes out the line.

The feature releases were renumbered at 2.8.3 (they were 2.8.1–2.8.3): the toolchain releases took
those numbers first. A toolchain or ecosystem release that lands ahead of one again takes the next
patch number and shifts the ladder; the order is what is committed, not the numbers.

No P(-1) pass *leads* the line (deliberate). The closeout audits the un-audited 2.7.x encoder
surface together with the 2.8.x additions before the next minor opens. The remaining Backlog item
(DEFLATE match-finder) stays parked.

---

## ▶ Next — 2.8.4

Nothing preempts 2.8.4. Two findings are carried into the **2.8.x-closeout P(-1) pass** (below):

⚠ **Kraft completeness in `_huff_build`.** It is a latent correctness gap, not a fixed bug:
`_huff_build` never verifies **Kraft completeness**, so an incomplete Huffman table is buildable and
simply fails to match at decode time. That is what made the 2.7.14 mislabelled-`NEED_MORE` path
reachable. It is handled safely today, because the conclusive-failure verdict turns it into
`ERR_INVALID_HUFFMAN`. Rejecting an over-subscribed or incomplete table at *build* time is still the
spec-correct behaviour (RFC 1951 §3.2.2) and would fail earlier and more clearly. The 2.8.0 Brotli
decoder already checks completeness at build time and can serve as the model.

⚠ **The coverage lesson.** The 2.7.14 hang survived from 2.3.0 because the test and fuzz corpora had
a two-axis gap:
- every **rich-alphabet** harness decoded **batch**;
- every harness reaching `*_dec_write` used a **degenerate alphabet**.

Neither set looked deficient on its own. 2.8.0's review found the same shape again: harnesses that
decoded into roomy buffers could not see an over-write. When the P(-1) pass reviews coverage, review it
as a *matrix* (input distribution × code path × buffer placement), not as a checklist of which
functions have tests.

⚠ 2.7.9 shipped an **unaudited** addition to the DEFLATE encoder: the fixed-vs-dynamic block chooser
in `_dyn_flush_subblock`, its scratch-bitwriter header pricer, and the three new public entry points.
It joins the queue for the closeout pass. Two things to look at there:
- `_dyn_header_bits` writes a header into a fixed 512-byte buffer on the argument that a header cannot
  exceed 281 bytes. That is an argument, not a runtime bound, though `bw_write` does fail closed on
  overflow.
- The chooser made `_deflate_build_enc_fixed` reachable from the level >= 4 path, which is how its
  latent M-8 OOM latch surfaced. Assume siblings of that latch exist on paths the sweeps do not yet
  reach.

---

## ▶ Scheduled — 2.8.x

The committed forward ladder, then a **P(-1) hardening pass closes out the 2.8.x line**. The line
opened **straight into the feature**: no P(-1) pass *leads* it (deliberate). Instead, the un-audited
2.7.x encoder surface is audited together with the 2.8.x additions in the **2.8.x-closeout P(-1)
pass** (below), before the next minor opens. That surface is BT4 `son[]`, the 4 MiB frame-global chain,
the DP-optimal arrays, and the window/cutoff math.

### 2.8.4 — Brotli encoder (RFC 7932)

The encode half of the codec 2.8.0 started. It completes Brotli the way 2.5.5 completed zstd.

- **Interop is the bar.** Output must decode byte-exact via reference `brotli -d` **and** via sankoch's
  own `brotli_decompress`. The decoder's corpus, `scripts/brotli-smoke.sh` and the reference Python
  decoder are already in the tree to check against.
- **Quality levels**, with ratio compared to `brotli -q N` at matching levels and recorded as
  informational bench lines. Ratio is not SIZE-gated until the encoder settles.
- **No dictionary on the first cut.** Plain LZ77 + prefix codes + context modeling is a valid RFC 7932
  stream. Static-dictionary references and transforms are a later ratio step, not a correctness need.
- **Wiring.** `compress(FORMAT_BROTLI)` and `compress_level(FORMAT_BROTLI, …)`, which return
  `ERR_UNSUPPORTED_FORMAT` today.
- **Profiles.** Encode stays **out of** the decode profiles `[lib.brotli]` / `[lib.woff]` (rekha only
  reads), unless a consumer asks. If one does, it gets a separate profile.
- **Tests.** Fuzz round-trips (encode → both decoders) and a reference-CLI smoke. The encoder's surface
  joins the closeout P(-1) scope.

### 2.8.5 — SIMD CRC-32 via `PCLMULQDQ`

A carryless-multiply (fold-based) CRC-32 on x86_64, beyond the portable
**slice-by-8** table fold 2.3.4 already banked (~2×, wire-identical, x86_64 +
aarch64). PCLMULQDQ was off the critical path *because* slice-by-8 covered the
goal, so this is a further optimisation, not a correctness need — its bar is that
it must not regress and must be provably bit-exact.

Approach (mirrors the prior arcs' "verify each bite" cadence):
1. **x86_64 fold** — the 4-way PCLMULQDQ fold from the Intel whitepaper (folding
   constants per the CRC-32 polynomial), behind a runtime/compile-time gate; keep
   slice-by-8 as the unconditional fallback so no target loses a working path.
2. **aarch64** — either a PMULL (crypto-extension) parallel fold or an explicit
   **fall back to slice-by-8** (no regression on the aarch64 gate — never a scalar
   byte loop).
3. **Wire-identical proof** — every gated CRC-32 output must equal the slice-by-8
   table result **byte-for-byte** across the test corpus, plus a differential fuzz
   (`fold(x) == table(x)` on random buffers). Hand-assembled CRC-folding carries a
   silent-corruption risk; this gate is the whole point. `PCLMULQDQ`-off restores
   the table path.
- Ref: Intel, "Fast CRC Computation … Using PCLMULQDQ" (whitepaper, 2009).

### 2.8.6 — GPU texture compression (BC1–BC7 / ASTC)

The one genuinely different codec: **lossy** and GPU-format-specific, so it does
not fit sankoch's "lossless" identity the way every prior codec did.

- **First sub-step is a home decision, not code.** sankoch is the home for *every
  lossless* codec (modular-by-profile), but a lossy texture codec may instead belong
  with **mabda** — which already has generic compute dispatch (`compute.cyr`) and the
  texture-format enums, but no codecs yet. Resolve this before writing a block encoder;
  it decides the repo, the API shape, and whether the "lossless" framing in `CLAUDE.md`
  needs qualifying.
- **Then a first format** — a CPU reference block encoder (BC1/BC7 for desktop or ASTC
  for mobile, driven by whichever consumer surfaces), block-based, validated against a
  reference decoder.
- Needs a consumer to pin *which* formats matter; scheduled as the direction, with the
  home decision as its gating bite.

### 2.8.x closeout — P(-1) hardening pass

The P(-1) scaffold-hardening pass, run at the **end of the 2.8.x line** (before the next
minor opens), per [`CLAUDE.md` § P(-1)](../../CLAUDE.md). It ships as its own release, as
the 2.6.4 ZIP-surface and 2.5.9/2.5.10 audits did. Deferring it to the closeout (rather than
leading 2.8.0) is the one deviation from "P(-1) before each minor" — recorded deliberately.

Scope — the surface accrued since the last audit (2.6.4, ZIP), audited together:
- **The un-audited 2.7.x encoder surface** — the BT4 binary-tree finder's `son[]` indexing,
  the 4 MiB frame-global hash chain (`_ze_prev` + snapshot/restore/fill), the DP-optimal
  arrays (`_zo_*`, the 4200-entry bounds), and the window / saturation-cutoff math. ~1,000
  lines of new indexing / OOM / integer-range surface never security-reviewed.
- **The 2.8.x additions**:
  - **the Brotli decoder (2.8.0)**: attacker-controlled indices into its tables, the IMTF and
    dictionary paths, and the dictionary literal (an `[embed]` since 2.8.3). Run the libbrotlidec
    mutation differential that 2.8.0 did not;
  - **the runtime reset seam (2.8.0)**: per-module resets vs the memoized-global inventory,
    `src/reset_<profile>.cyr` registration, the stranded-canary predicate, and the canary-arm residual
    (a real 8-byte OOM that recovers within one call);
  - **the Brotli encoder (2.8.4)**;
  - **the hand-assembled `PCLMULQDQ` CRC fold (2.8.5)**: its silent-corruption risk is the whole reason
    it needs the wire-identical gate and an audit;
  - **the GPU texture codec's block encoder (2.8.6)**.
- **The carried findings** from ▶ Next: `_huff_build` Kraft completeness, the `_dyn_header_bits`
  bound, and the coverage review as a matrix.
- **Found at 2.8.3** (the cyrius W2 pin release; recorded, not fixed there — W2 carried only its
  planned scope):
  - ⚠ **Five of the seven fuzz harnesses do not fail on an assertion.** `fuzz_lz4`, `fuzz_deflate`,
    `fuzz_xz`, `fuzz_bzip2` and `fuzz_zstd` end `main` with `return 0;`, not
    `return assert_summary();` as `fuzz_zip` and `fuzz_brotli` do, so CI's fuzz step fails only on a
    crash or its 60 s timeout: a round-trip mismatch prints `FAIL:` and exits 0. Measured: a zstd
    optimal-parse backtrack that stops at its first node makes `fuzz_zstd` print 10 `FAIL` lines and
    exit 0. Fix: `return assert_summary();` in all five (each ran clean, 0 `FAIL` lines, at 2.8.3). This is the
    coverage-matrix review's first entry: a harness that cannot fail is not coverage.
  - **The optimal-parse backtrack had almost no coverage.** Only 2 of fuzz_zstd's 500 level 7-9
    round-trips build a multi-node DP chain (the 2.8.3 mutation run); `tests/tcyr/zstd_compress.tcyr`
    `test_zc_optimal_backtrack` now pins those two inputs. Look for the same shape in xz's optimal
    parse.
  - **A `while (1)` → `loop { … }` sweep**: 18 sites in `src/` (bzip2 7, deflate 4, xz 3, and one each
    in gzip, huffman, lz4, zlib) plus 1 in the tests; emulated breaks become `break`. Prove it the way
    2.8.3 proved the backtrack walk: compressed output hashed across levels, identical before and
    after.
  - **Stray merge lines in the raw-include suites' headers.** `tests/tcyr/sankoch_raw_include.tcyr` and
    `sankoch_zlib_raw_include.tcyr` each carry a second, truncated copy of the header after the first,
    including a live line `include "dist/<bundle>.cyr"` followed by the leftover words
    `` ` alone compiles.``. Harmless today (the file compiles, and the second include of the same
    bundle is a no-op), but it is a stale line a reader takes for the real include.
- Plus the standard closeout gates (cleanliness / dead-code / stale-comment sweeps, a fresh
  benchmark baseline, the security-audit dossier under [`docs/audit/`](../audit/), and a
  doc-health pass).

Primitive sources for the codec items (Rice/Golomb, range encoder, LPC, GPU
dispatch) are tabulated under [§ Primitive sources](#primitive-sources-for-future-codecs) below.

---

## Next minor (2.9.0) — public names as 6.7.x types

Public-surface changes, so a minor (2.8.3 kept 6.7.x adoption to private names):

- **Public integer constants → `const`**: `TAR_*` (12, `src/tar.cyr`), `ZIP_*` (21, `src/zip.cyr`) and
  `SANKOCH_ARENA_MAGIC` are never-written `var`s today. A `const` beside a same-name `var` is a hard
  error in cyrius, so survey cyrius's `lib/` and every fold for each name first.
- **A `SANKOCH_ERR_*` namespace** for the error codes: `enum Error`'s bare `OK` / `ERR_*` names and
  the `TAR_ERR_*` values share the stdlib's one global namespace with every consumer.
- **`: bool`** on the public predicates, and on the five private path / checksum safety predicates
  (`_star_path_safe`, `_star_symlink_safe`, `_star_ledger_prefix_unsafe`, `_star_checksum_ok`,
  `_zip_path_safe` — they return only 0 / 1 today; offered as optional at 2.8.3 and left for here).

---

## Backlog — unscheduled (to be re-organised)

Parked items with no committed release. Each has a *sound reason to wait* — the
payoff needs a real consumer profile to justify the cost/risk. **To be triaged
into a fresh ladder** when a consumer surfaces.

- **DEFLATE match-finder throughput.** ⚠ **The trigger has fired — this is no
  longer speculative.** The entry used to end "pick up if sit's
  `zlib_compress(1 MB)` target resurfaces as a priority". It has, repeatedly, and
  sit has measured it.

  **Evidence (sit v1.4.8–1.5.x, `docs/benchmarks/2026-08-19-v1.4.8.md`):**

  | measurement | value |
  |---|---:|
  | `add-1MB`, sit vs git | **6.37×** (104.27 ms vs 16.38 ms) |
  | of which `zlib_compress` | **~100 ms — the dominant term** |
  | `blob-hash-1048576B` (sigil SHA-256, same 1 MB) | 4.73 ms |
  | `zlib-compress-65536B` | 1.067 ms |
  | `zlib-compress-1024B` | 123.7 µs |

  **`add-1MB` is sit's single worst benchmark row**, and compression is
  essentially all of it — hashing the same megabyte costs 4.7 ms against
  compression's ~100 ms, a 21× gap. sit has driven every other row it controls
  to parity or better (`init` 0.64×, `commit` 0.59×, `fetch` 0.24×, `status`
  1.38×), so this is the largest remaining gap that is *not* sit's own code.

  **The constraint stands and is the hard part.** zlib byte-for-byte parity is
  load-bearing for sankoch's consumers, so `good_match` and friends are off the
  table — they are speed/ratio trade-offs that change output. A genuine win has
  to find the *same* matches faster: tighter chain-walk scheduling, a better
  hash, or a provably output-preserving lazy-match restructure. **Any candidate
  must be gated on a byte-identical-output test across a real corpus before a
  benchmark number is quoted.**

  Open-ended and large. Pairs naturally with the 2.8.5 SIMD work already
  scheduled, but note that CRC-32 via `PCLMULQDQ` does **not** touch this — the
  cost here is match finding in `lz77.cyr`, not checksumming.

---

## ZIP container — deliberately not there

**Non-goals** (like the codec non-goals): **encryption** — ZipCrypto is
cryptographically broken, and AES-in-ZIP needs a real AES primitive sankoch
deliberately doesn't carry (zero-crypto-dep, cf. xz's unverified SHA-256);
**multi-disk / spanned** archives (obsolete); **Deflate64** (method 9 — a
separate codec, not RFC 1951).

---

## Known limitations / non-goals

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

## New-codec context (for the Backlog codec items)

Because the per-codec distlib profiles let a consumer pull only the closure it
needs (see *Modular by profile* in [`CLAUDE.md`](../../CLAUDE.md)), sankoch is the
home for **every** lossless-compression codec — new formats never bloat consumers
that don't use them, so nothing is "a separate crate." Brotli decode shipped in 2.8.0
(encode is 2.8.4), and **GPU texture compression** (2.8.6) is the one not-yet-implemented codec;
Zstandard is done (decode 2.5.0, sovereign encoder 2.5.5, beats `zstd -3`, optimal
parse 2.7.3 — its remaining record-data ratio residue is the 2.7.4 window item, not
a new codec).

### Primitive sources for future codecs

| Primitive | Home | File | Lines |
|-----------|------|------|-------|
| Rice/Golomb coding | shravan/FLAC | flac.cyr | 367-437 |
| Range encoder | shravan/Opus | opus.cyr | 175-284 |
| LPC prediction | shravan/FLAC | flac.cyr | 517-580 |
| GPU compute dispatch | mabda | compute.cyr | 142 lines |

---

## File Summary (at 2.3.0)

> Heading anchor kept stable (`#file-summary-at-230`) for the CLAUDE.md and state.md cross-links.
> The figures are refreshed every release. Current as of **2.8.3**, re-counted with `wc -l`.
> 2.8.3 moved the dictionary literal out of `brotli_dict.cyr` into `cyrius.cyml [embed]` and made
> `zstd.cyr`'s backtrack a `loop` (82 → 83 and 3,114 → 3,113 lines; the total is unchanged).
> 2.8.0 added `brotli.cyr` + the generated `brotli_dict.cyr` (one 122,784-byte literal, so few lines)
> and ten `reset_<profile>.cyr` dispatchers. It also moved each module's reset into the module,
> which is why `lib.cyr` shrank.
> The tree is **23 domain modules + 10 reset dispatchers**.

| File | Lines | Role | Profile |
|------|-------|------|---------|
| types.cyr        |   44 | Enums: formats (incl. FORMAT_XZ, FORMAT_BZIP2, FORMAT_ZSTD, FORMAT_BROTLI), errors (incl. ERR_OOM, ERR_RATIO_LIMIT, ERR_OUTPUT_LIMIT), limits | core |
| xxhash32.cyr     |   94 | xxHash32 batch + helpers + XXH32 enum (kernel-safe) | core |
| checksum.cyr     |  567 | Adler-32 / CRC-32 (slice-by-8) / CRC-64-XZ / CRC-32-BZIP2 + incremental state APIs; unlocked table builders carry the arena guard (2.8.0) | full |
| bitreader.cyr    |  100 | LSB-first bit-stream reader | full |
| bitwriter.cyr    |  145 | LSB-first bit-stream writer | full |
| huffman.cyr      |  709 | Huffman build/decode, fixed + optimal trees, encoder pre-reversed codes; `huff_build_*` guard the arena (2.8.0) | full |
| lz77.cyr         |  199 | Sliding window match-finder, 8-byte word-compare match extend, `lz77_rebase`, ring-buffer slide | full |
| lz4_decode.cyr   |  181 | LZ4 block + frame decompress (incl. per-block checksum) + LZ4F enum (kernel-safe) | core |
| lz4.cyr          |  949 | LZ4 block + frame compress + `lz4f_enc_*` + `lz4f_dec_*` streaming | full |
| deflate.cyr      | 2976 | DEFLATE de/compress, adaptive blocks, `deflate_enc_*` + `deflate_dec_*` streaming, dict, ratio cap, RFC 7692 sync flush + fixed-vs-dynamic block chooser | full |
| zlib.cyr         |  542 | RFC 1950 wrapper + FDICT + streaming + ratio cap + caller output ceiling (`zlib_decompress_capped`) | full |
| gzip.cyr         |  650 | RFC 1952 wrapper + concatenated batch/streaming + FHCRC + ratio cap | full |
| xz.cyr           | 2136 | `.xz` de/compress: LZMA2 + range coder, optimal parse, BT4 finder, 256 KB window, ratio cap | full |
| bzip2.cyr        | 1347 | `.bz2` de/compress: BWT + MTF/RLE2 + Huffman + RLE1, ratio cap | full |
| zstd.cyr         | 3113 | `.zst` de+compress (RFC 8878): hardened decoder + encoder (FSE/Huffman, DP optimal parse L7–9, cross-block window, chain cutoff) | full |
| brotli.cyr       | 1460 | **Brotli decode (RFC 7932, 2.8.0)**: bit reader, prefix codes, context maps + IMTF, block switching, command loop, dictionary transforms; `brotli_decompress` / `_capped` | full, brotli, woff |
| brotli_dict.cyr  |   83 | RFC 7932 dictionary geometry (NDBITS / DOFFSET) + FNV-1a verify; the 122,784 bytes are `cyrius.cyml [embed] _brotli_dict_bin` (2.8.3; a generated literal before) | full, brotli, woff |
| zip.cyr          | 1386 | PKZIP `.zip` container: reader + writer, methods 0/8, Zip64, streaming write, Unix metadata, sizing + reclaimable readers | full |
| zip_methods.cyr  |  150 | ZIP methods 12 / 93 / 95 (bzip2 / zstd / xz), kept out of `[lib.zip]` | full |
| tar.cyr          |  710 | POSIX ustar + v7 tar pull-cursor (`tar_open_auto` sniffs gzip/xz/bzip2/zstd), traversal guards | full |
| stream.cyr       |  256 | Streaming dispatch (`stream_compress_*`, buffered + incremental decompress) | full |
| runtime.cyr      |  275 | Lock + alloc seam + arena guard: canary, stranded-canary predicate, failed-arm handling (2.8.0); the reset registration rule | full |
| lib.cyr          |  252 | Include chain + public API + format dispatch + the full bundle's `_sankoch_reset_tables` | full |
| reset_<profile>.cyr ×10 | 179 | Per-profile `_sankoch_reset_tables` dispatchers (brotli 15, bzip2 16, gzip 18, tar 21, woff 20, xz 17, zip 18, zipall 21, zlib 18, zstd 15) | one each |
| **Total**        | **18503** | | |

`core` modules (types + xxhash32 + lz4_decode = 319 source lines)
form `[lib.core]` → `dist/sankoch-core.cyr`. They contain no
`alloc()`, no syscalls, no mutex usage — verified by the CI
"Kernel-safe tripwire" gate (`programs/core_smoke.cyr`).

Tests: 29 runnable suites in `tests/tcyr/` producing **4,500,567 assertions** (0 failed), including
`brotli_decompress.tcyr` (4,555), `zstd_compress.tcyr` (173) and `arena_reset.tcyr` (107). Most of the total comes from per-byte
round-trip loops on the streaming suites. A single 200 KB round-trip contributes 200,000 assertions
through one `while (i < N) assert(byte_eq)` loop, so the headline number measures coverage *density*,
not coverage *breadth*. See
[`../guides/cyrius-usage.md`](../guides/cyrius-usage.md#what-assertions-means-here-and-why-the-number-is-so-large)
for the full explanation.

Fuzz: 7 files (`fuzz_lz4`, `fuzz_deflate`, `fuzz_xz`, `fuzz_bzip2`, `fuzz_zstd`, `fuzz_zip`,
`fuzz_brotli`). 2.8.0 added `fuzz_brotli`: 13 seeds + 5,000 mutated / random / truncated / spliced
inputs, with src and dst placed against PROT_NONE guard pages. Per-file breakdown in
[`state.md` § Fuzz totals](state.md#fuzz-totals).

Distlib: **12 bundles**, one per profile in `cyrius.cyml`:

| Bundle | Lines |
|---|---:|
| `sankoch.cyr` (full) | 18,392 |
| `sankoch-core.cyr` (kernel-safe) | 333 |
| `sankoch-zlib.cyr` | 5,711 |
| `sankoch-gzip.cyr` | 5,819 |
| `sankoch-xz.cyr` | 3,362 |
| `sankoch-bzip2.cyr` | 2,370 |
| `sankoch-zstd.cyr` | 3,468 |
| `sankoch-tar.cyr` | 13,141 |
| `sankoch-zip.cyr` (methods 0/8) | 6,556 |
| `sankoch-zipall.cyr` (every method) | 13,317 |
| `sankoch-brotli.cyr` (Brotli decode) | 1,909 |
| `sankoch-woff.cyr` (zlib closure + Brotli) | 7,270 |

Per-bundle roles are in [`state.md` § Dist bundles](state.md#dist-bundles).

## Dependencies

**Zero external.** Checksums (Adler-32, CRC-32, xxHash32 — batch and
incremental) are inline. No sigil dependency. Stdlib-only: `syscalls`,
`string`, `alloc`, `fmt`, `vec`, `fnptr`, `thread`, `assert` (all
ship with Cyrius ≥ 6.0.1; the pin is in `cyrius.cyml`, 6.7.5 at 2.8.3).

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

*Last Updated: 2026-10-08 (**2.8.3 cut**: the cyrius W2 pin release — 6.7.5, `[embed]` dictionary, `loop`, `const` knobs; ladder renumbered to 2.8.4 Brotli encoder → 2.8.5 SIMD CRC-32 → 2.8.6 GPU texture → P(-1) closeout, with 2.8.3's findings added to the closeout scope and a 2.9.0 section for the public-name changes; File Summary, test and distlib figures re-counted. Previous: 2026-09-16, the 2.8.0 cut.)*

---

## Toolchain notes for the next pin move

⛔ **Do not move the pin past 6.7.5 until cyrius stops counting sankoch's own fold as an `[embed]`
owner.** cyrius refuses an `[embed] NAME` that any leaf of the pinned stdlib snapshot declares, and
sankoch's own bundle IS a leaf of that snapshot (`lib/sankoch.cyr`). Measured at 2.8.3: with the 2.8.3
`dist/sankoch.cyr` in place of the stdlib's `lib/sankoch.cyr` (what the cyrius release that refolds
2.8.3 installs), `cyrius build src/lib.cyr` stops with `[embed] _brotli_dict_bin: _brotli_dict_bin is
already declared by the stdlib leaf sankoch`. At 6.7.5 it builds because that fold is 2.8.2, whose
literal had the old name — which is why 2.8.3 renamed the accessor from `_brotli_dict_data`. The fix is
cyrius's (skip the leaf the project itself folds); renaming the embed every release is not one. Filed
with the 2.8.3 W2 report.

**Every compile in this project carries the dictionary.** cyrius prepends the `[embed]` module to each
build here, `--no-deps` included. A build that also includes a bundle carrying the embed (the
link-gate probes for `full` / `brotli` / `woff`, `sankoch_raw_include.tcyr`) defines the accessor
twice: cycc warns `duplicate fn '_brotli_dict_bin'` and links the bundle's (the later) definition. That
warning is expected. A bundle that calls the accessor without listing it under `embed` is refused by
`cyrius distlib`, which CI's dist gate runs for every profile.

The 6.6.6 pin notes and the cyrius 6.6.19 notes that stood here are done: 2.8.1 moved the pin to
6.6.18, 2.8.3 adopted `[embed]` and retired both Python gates, and the getting-started platform line
now says what CI actually covers (CHANGELOG [2.8.1], [2.8.3]).
