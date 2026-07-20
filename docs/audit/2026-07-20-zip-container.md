# Sankoch — 2.6.3 P(-1) Audit: the ZIP Container (Pre-2.6.4)

**Date:** 2026-07-20
**Auditor:** P(-1) scaffold-hardening sweep — adversarial multi-lens fan-out over the ZIP surface, every non-INFO finding independently reproduced and then put through a refute-first verifier (severity below is the **verifier's** judgment, not the reporting lens's).
**Scope:** First-ever security audit of the PKZIP container, built across the 2.6.0–2.6.3 arc and **never previously audited**: `src/zip.cyr` (1013 lines — EOCD/Zip64 locator + EOCD parse, central-directory walk, `_zip_z64_extra`, `_zip_prepare`, STORE/DEFLATE extract, the batch writer, and the `zip_enc_*` streaming writer) and `src/zip_methods.cyr` (148 lines — the method-12/93/95 extract + add fan-out that keeps xz/bzip2/zstd out of the lean `[lib.zip]` closure). Public API audited: `zip_open`, `zip_count`, `zip_entry_{name,method,crc,csize,size,mode,mtime,is_dir,is_symlink}`, `zip_find`, `zip_extract`, `zip_extract_capped`, `zip_extract_any`, `zip_extract_any_capped`, `zip_method_supported`, `zip_writer_init`, `zip_add`, `zip_add_meta`, `zip_add_any`, `zip_add_any_meta`, `zip_writer_finish`, `zip_enc_begin`, `zip_enc_write`, `zip_enc_end`. The reader is a parser for **fully attacker-controlled** archives (in-memory: caller buffer + length) — exactly the shape where the previous pass found a HIGH in the tar cursor.
**Toolchain at audit:** Cyrius 6.4.67 (manifest-pin; `~/.cyrius/current` = 6.4.67).
**Reference CLIs:** unzip 6.00 (Info-ZIP), bsdtar 3.8.8 / libarchive 3.8.8, python3 3.14.6 (`zipfile` supports methods 0/8/12/93 and Zip64 — **not** 95), xz 5.8.3, bzip2 1.0.8, zstd 1.5.7. (**valgrind is not installed** — every memory error below was proven by execution: guard-page probes (`mmap` two pages, `mprotect` the second `PROT_NONE`, archive placed flush against the boundary), crafted crashing inputs (SIGSEGV / exit 139), and bounds-assertion probe copies.)
**Diff base:** `2026-07-19-pre-2.6.0.md` (the last full P(-1) pass, which closed the 2.5.x line and predates the ZIP surface entirely — it audited xz/bzip2/tar/zstd but no ZIP code existed then). Audit HEAD: `0d0ff07` (tag 2.6.3).

---

## TL;DR

The ZIP container is the newest and least-exercised surface in the tree, and this is its first security audit — the pre-2.6.0 pass could not have covered it because none of this code existed yet. The 175-assertion `zip.tcyr` suite has **no adversarial coverage of the 64-bit Zip64 fields**, so all standard gates are green.

**Confirmed, post-verification: 0 HIGH · 3 MEDIUM · 1 LOW.** One HIGH claim (zip-slip by analogy to the previous audit's tar HIGH) was **rebased to LOW** on verification. Every confirmed finding was reproduced by execution and carries a verified patch.

The findings collapse into **two root causes**:

1. **A single i64 additive-overflow pattern (`field + const > len`) repeated at four bounds checks in the reader** (Z-1). Cyrius i64 arithmetic is two's-complement wraparound with no trap. Any Zip64 field read by `_zip_le64` whose value is a large positive below 2⁶³ passes its `< 0` guard, but `field + const` overflows to a negative i64 so `> len` is false — the check is defeated and the code then dereferences `buf + field` at a fully attacker-chosen ~2⁶³ displacement. All four sites are reachable from the primary public entry points (`zip_open`, `zip_extract`) on a fully attacker-controlled in-memory archive, and each was proven to SIGSEGV (exit 139) by a tiny crafted archive (42 / 81 / 98 / 117 bytes). Verified **MEDIUM ×4 sites** (OOB read / crash-DoS; one site also allows a conditional ~64 KB heap over-read into the caller's `dst`, which one lens over-called HIGH — the verifier settled MEDIUM because writes stay `dst_cap`-bounded).

2. **Missing state-machine guards in the writer** (Z-2, Z-3, Z-4) — a streamed DEFLATE member abandoned before `deflate_enc_finish` leaks the shared `_sankoch_mtx` and deadlocks the whole library process-wide (host builds only); a batch `zip_add` issued while a streamed member is open silently produces an overlapped, corrupt archive returned with success codes; a member name > 65535 bytes truncates in the u16 name-length field into an unreadable archive.

**The tar-style cross-entry symlink hole does *not* exist in the ZIP surface.** ZIP is purely in-memory and performs **zero filesystem operations** — no `symlink`/`open`/`write`/`mkdir` anywhere in `zip.cyr` or `zip_methods.cyr`. `zip_extract` copies decoded bytes into a caller buffer bounded by `dst_cap`; it never resolves or materializes a symlink and never joins a path against a root. The previous audit's HIGH (H-1, silent file write above the extraction root) has no analogue here because there is no write-to-disk path to escape. See the refuted table (R-1) and the coverage statement.

**Also delivered:** `fuzz/fuzz_zip.fcyr` — the previously-missing ZIP fuzz harness (six strategies incl. Zip64 injection). It passes on the writer/reader/streaming round-trips and reliably SIGSEGVs today in the Zip64-injection strategy, pinpointing Z-1; it goes green once the Z-1 guards are fixed.

**Verdict: NOT clean at `0d0ff07` for the reader.** The Z-1 class is an attacker-reachable crash/DoS (+OOB read) from `zip_open`/`zip_extract` on untrusted input. Every fix is a one-line subtraction-form rewrite (or a small guard), all verified against `zip.tcyr` + `cyrius fuzz` + reference-CLI parity; none require redesign. This is a remediation-then-clear, not a rewrite.

---

## Confirmed findings

Severity = verifier's judgment. Every location is against `0d0ff07`.

### MEDIUM

#### Z-1 — i64 additive-overflow defeats four Zip64 bounds checks → OOB read / SIGSEGV from `zip_open` and `zip_extract`

- **Severity:** MEDIUM (one class, four independently-reproduced crash sites). Reachable from public `zip_open` / `zip_extract` / `zip_extract_capped` / `zip_extract_any(_capped)` on a fully attacker-controlled in-memory archive.
- **Mechanism (shared):** `_zip_le64` assembles a full 64-bit little-endian value (top byte `<< 56`), so a field whose high byte is `0x7F` is a large positive i64 that survives every `< 0` guard. `_zip_z64_extra` resolves a member's local-header offset / compressed size / uncompressed size from the attacker-controlled Zip64 extended-information extra field via `_zip_le64` with **no upper bound** against `len`. Each bounds check is then written in the overflow-unsafe additive form `field + const > len`; for `field` near 2⁶³ the sum wraps two's-complement to a negative i64, so `> len` is false and the guard falls through to a dereference at `buf + field`.

| Site | Location | Field (source) | Trigger (proven) | Crash |
|---|---|---|---|---|
| **Z-1a** | `src/zip.cyr:304` guard, `:305`/`:308-310` deref | Zip64 EOCD **locator** offset `z64` (`_zip_le64(buf+loc+8)`) | 42-byte archive: `[Zip64 locator sig 0x07064b50, offset=0x7FFFFFFFFFFFFFE2][bare EOCD, comment_len=0]` | `zip_open` SIGSEGV (exit 139) at `_zip_le32(buf+z64)` |
| **Z-1b** | `src/zip.cyr:314` guard, `:331`/`:332` loop deref | `cd_off + cd_size` from the Zip64 EOCD record (`:309-310`) | 98-byte archive: Zip64 EOCD `{count=1, cd_size=0x100, cd_off=0x7FFFFFFFFFFFFFF6}` + locator + EOCD | `zip_open` SIGSEGV at `_zip_le32(buf+p)`, `p = cd_off` |
| **Z-1c** | `src/zip.cyr:359` (zip_open) + `:502` guard, `:503` deref (`_zip_prepare`) | member local-header offset `lho` (base = `0xFFFFFFFF` sentinel, resolved from Zip64 extra id 0x0001) | 81-byte archive: one STORE member, CD `lho` sentinel + Zip64 extra `{offset=0x7FFFFFFFFFFFFFF0}` | `zip_open` **accepts** it; `zip_extract` SIGSEGV at `_zip_le32(buf+lho)` |
| **Z-1d** | `src/zip.cyr:507` guard | `data + csize`; `csize` resolved from Zip64 extra to `0x7FFFFFFFFFFFFFFF` | 117-byte archive: method-8 member, one STORED sub-block claiming `LEN=0xFFFF`, CD `csize` sentinel + Zip64 extra `{csize=2⁶³-1}`, `usize=65535` | `zip_extract`: huge `csize` handed to the DEFLATE bitreader; stored-block copy walks ~64 KB past the buffer → SIGSEGV on a guard page (heap read into `dst` on a normal heap, then `ERR_CHECKSUM_MISMATCH`) |

- **Proof:** All four PROVED-BY-EXECUTION. Z-1a/Z-1b crash inside `zip_open` itself (the primary entry point any consumer calls first on an untrusted archive); Z-1c/Z-1d crash inside `zip_extract`. Boundary sweep on Z-1a is exact: `z64 = 0x7FFFFFFFFFFFFFC7` is cleanly rejected, `0x7FFFFFFFFFFFFFC8` (= the first value where `+56` reaches `INT64_MIN`) crashes. Z-1d was demonstrated two ways — an instrumented probe copy reported a 65 513-byte OOB input read, and an un-instrumented guard-page probe SIGSEGV'd; the byte-identical archive with a plain non-Zip64 `csize=0xFFFFFFF0` is correctly rejected with `ERR_CORRUPT_DATA` (or bottoms out in DEFLATE), isolating the Zip64 overflow as the specific bypass.
- **Severity note:** All four are OOB **reads** → SIGSEGV / crash-DoS. On Z-1a/Z-1b/Z-1c the loaded word only feeds a signature comparison or a branch and never returns to the caller, so there is no info-leak; on Z-1d the DEFLATE copy can move up to ~64 KB of adjacent heap into the caller's `dst` before the CRC check fails (a *conditional* disclosure to a caller that reads `dst` on a negative return), but the write side stays `dst_cap`-bounded (`deflate.cyr:392`) — no OOB write. Per the rubric (OOB read / crash-DoS = MEDIUM; HIGH requires OOB write / corruption / path escape) this is **MEDIUM**, and the initial HIGH framing of Z-1d was rebased down. Note on Z-1b: one lens initially judged `:314` benign (the negative `cd_end` is caught by the in-loop `p + 46 > cd_end` secondary guard when `count==0`), but other lenses **proved a direct crash** with `count=1` — so `:314` is a live MEDIUM, not merely defense-in-depth.
- **Verified fix (all four sites):** Never add an attacker value before comparing to `len`; bound the operand first, then subtract on the known-non-negative side. Each rewrite is algebraically identical to the original for every non-overflowing value, so **no legitimate archive is newly rejected** (verified: `zip-smoke.sh` 13/13, including sankoch's own Zip64 self-reopen).
  - `:304` → `if (z64 < 0 || len < 56 || z64 > len - 56) { return 0; }`
  - `:314` → `if (cd_off > len || cd_size > len - cd_off) { return 0; }` (`cd_off`,`cd_size` ≥ 0 already established at `:313`)
  - `:359` and `:502` → `if (lho < 0 || len - lho < 30) { ... }` (mirror at both sites; `:502` returns `0 - ERR_CORRUPT_DATA`)
  - `:507` → `if (data < 0 || data > len || csize > len - data) { return 0 - ERR_CORRUPT_DATA; }` (ordering `data > len` first guarantees `len - data ≥ 0`)
  - `_zip_prepare` is the single choke point for every extract path (STORE/DEFLATE **and** the method-12/93/95 decoders in `zip_methods.cyr`, which are handed `(buf+data, csize)`), so the `:502`/`:507` fixes close all codecs at once.
  - After each fix the crafted trigger is rejected with no crash; `cyrius test` all suites 0 failed, `cyrius fuzz` 5/5, and `src/zip.cyr` still references only deflate + crc32 + runtime (lean `[lib.zip]` intact). Regenerate `dist/sankoch.cyr` + `dist/sankoch-zip.cyr` (+`-zipall`) for the dist gate.

#### Z-2 — Streamed DEFLATE member abandoned before `deflate_enc_finish` leaks `_sankoch_mtx` → library-wide deadlock

- **Location:** `src/zip.cyr:778-820` (`zip_enc_begin` → `deflate_enc_init` takes `_sankoch_lock()`; the **only** unlock site is `deflate_enc_finish`); leak paths at `:857` (`zip_enc_end` short-circuits on the sticky error and never finishes the encoder), `:897` (`zip_writer_finish` refuses an open member without finishing it), and `:834-843` (`zip_enc_write` returning `ERR_BUFFER_TOO_SMALL` sets the sticky error).
- **Severity:** MEDIUM. Reachable from the public streaming-writer API; STORE streaming is immune (never takes the encoder lock).
- **Trigger (two paths, both PROVED-BY-EXECUTION, exit 124 under `timeout`):** (a) `zip_enc_begin(w,name,ZIP_DEFLATE,…)`; `zip_enc_write(…)`; then `zip_writer_finish(w)` while the member is still open — the encoder is never finished, the lock leaks, and the next `deflate_compress` anywhere in the process hangs forever. (b) Stream **incompressible** input into a bounded output buffer until `zip_enc_write` returns `ERR_BUFFER_TOO_SMALL` (a mid-write sub-block flush overflows the bitwriter); `zip_enc_end` short-circuits on the resulting sticky error and never calls `deflate_enc_finish` → same permanent leak. A STORE control with the identical sequence survives (exit 0), isolating the cause to the DEFLATE encoder lock.
- **Severity note:** Host-side only — on `CYRIUS_TARGET_AGNOS` both `_sankoch_lock` and `mutex_lock` are no-ops, so the flagship AGNOS consumer is immune; the hazard is tests, tooling, and non-AGNOS embedders. Path (b) requires incompressible input large enough to force the flush (compressible input lets `deflate_enc_finish`, called inside `zip_enc_end`, release the lock on its own error path). Still a realistic remote DoS via a documented, normal error condition. Not HIGH: no memory corruption, no OOB, writer-side.
- **Verified fix:** Add `_zip_abort_stream(w)` that funnels every abandon path through `deflate_enc_finish(w+104)` (the sole unlock site) to release the lock, then clears `w+104`/`w+56`. It is a **no-op for STORE** (`load64(w+80) != ZIP_DEFLATE`) and only fires when a member is actually open (`_zip_streaming(w) != 0`), so it cannot double-unlock the stale-but-finished ctx left after a clean `zip_enc_end`. Wire it into the sticky-error guards of `zip_enc_end` / `zip_writer_finish` and the open-member rejection in `zip_writer_finish`. Verified: both triggers now exit 0; a double-unlock edge probe (clean member #1 finished, member #2 abandoned) exits 0; `cyrius test` 22/22 suites, `cyrius fuzz` 5/5.

#### Z-3 — `zip_add` / `zip_add_any` while a streamed member is open silently produces an overlapped, corrupt archive

- **Location:** `src/zip.cyr:709` (`zip_add_meta` has no `_zip_streaming` guard); `src/zip_methods.cyr:89` (`zip_add_any_meta` likewise).
- **Severity:** MEDIUM. Reachable from the public writer API by an out-of-order call sequence; returns success.
- **Trigger (PROVED-BY-EXECUTION):** `zip_enc_begin` reads `hdr = load64(w+16)` but does not advance the write cursor `w+16` until `zip_enc_end`. A `zip_add`/`zip_add_meta` issued between `zip_enc_begin` and `zip_enc_end` reads the same stale `w+16`, writes its own local header over the streamed member's header/data, and records a CD entry whose `hdr` equals the streamed member's — two CD records pointing into overlapping data. All calls return success (`begin=0, write=0, add=0, write2=0, end=0, finish>0`), yet the archive is corrupt: sankoch's own reader extracts member0 but returns `-5` (`ERR_CHECKSUM_MISMATCH`) on member1; `unzip -t` reports "invalid zip file with overlapped components (possible zip bomb)"; Python `zipfile` warns "Overlapped entries" and `testzip()` fails.
- **Severity note:** Writer-side, caller-sequence bug (not attacker-controlled parser input), so below the HIGH bar — but a genuine reachable silent-data-corruption outcome accepted with all-success codes, so above LOW. `zip_enc_begin` already guards double-begin and `zip_writer_finish` guards a half-written member; the two batch-add doors were simply never given the same check.
- **Verified fix:** Add `if (_zip_streaming(w) == 1) { return 0 - ERR_INVALID_INPUT; }` at the top of `zip_add_meta` (covers `zip_add`) and `zip_add_any_meta` (covers the 12/93/95 path; the STORE/DEFLATE delegation is already covered by the `zip.cyr` guard). `_zip_streaming` lives in `zip.cyr` and is in every profile that includes it — no new cross-module or codec dependency. Verified: the mid-stream add now returns `-1`, the streamed member is untouched, `unzip -t` and `zipfile.testzip()` clean; `cyrius test` 175/175 + aggregate 0 failed, fuzz 5/5, smoke 13/13.

### LOW

#### Z-4 — Member name longer than 65535 bytes silently truncates the u16 name-length field → unreadable archive

- **Location:** `src/zip.cyr:719` (`zip_add_meta`, `nlen = strlen(name)`) → `_zip_emit_local` `:607` writes `_zip_put16(hdr+26, nlen)`; `zip_writer_finish` `:897`/`:913` writes the CD `_zip_put16(+28, nlen)`; also `zip_enc_begin` `:788` and `zip_add_any_meta` `zip_methods.cyr:103`.
- **Severity:** LOW. Write path; the offending name is supplied by the library's **consumer**, not decoded from an attacker-controlled archive (the reader can never produce `nlen > 65535` — it reads a u16). No memory-safety impact: bounds are computed against the full `nlen` versus `cap`, so there is **no OOB write** — only silent structural corruption returned as success.
- **Trigger (PROVED-BY-EXECUTION):** `zip_add(w, name, …)` with `strlen(name) > 65535` (a 70000-byte name passes `_zip_path_safe`). `_zip_put16` masks the length to `nlen & 0xFFFF` (70000 → 4464) while the full name bytes are still copied and offsets advance by the full `nlen`, so the local header and CD record declare a length disagreeing with the bytes present and the central directory self-desyncs. `zip_add`/`zip_writer_finish` return success; the emitted archive is rejected by sankoch's own reader (`-5`), `unzip -t` ("didn't find end-of-central-dir signature"), bsdtar, and Python `zipfile` ("Bad magic number for central directory").
- **Verified fix:** ZIP has no Zip64 extension for name length — the 16-bit field is the hard format limit. Add `if (nlen > ZIP_Z64_U16) { return 0 - ERR_INVALID_INPUT; }` at all three writer entry points (`zip_add_meta`, `zip_enc_begin`, `zip_add_any_meta`). `ZIP_Z64_U16 = 0xFFFF` and `ERR_INVALID_INPUT` are already in the `[lib.zip]` closure. Verified: a 65535-byte name is still accepted and round-trips cleanly through Python `zipfile`; 65536/70000 are rejected; full `cyrius test` green, fuzz 5/5, `cyrfmt --check` + `cyrius lint` clean, both `distlib zip`/`zipall` bundles compile standalone with no codec references introduced.

---

## Refuted / severity-rebased (do not re-report)

| # | Report (claimed sev) | Verdict | Why |
|---|---|---|---|
| R-1 | No symlink-target validation and no cross-entry ledger → zip-slip via a planted symlink, despite the docstring claiming parity with `tar.cyr` (**HIGH**) | **LOW** | The factual observations reproduce, but HIGH requires a path escape reachable from a public API. **No such escape is reachable through any ZIP API.** A grep of `src/zip.cyr` + `src/zip_methods.cyr` shows **zero filesystem operations** (no `syscall`/`symlink`/`open`/`write`/`mkdir`): ZIP is purely in-memory — `zip_extract` copies bytes into a caller buffer bounded by `dst_cap`, never creates or resolves a symlink, and never joins a path against a root. The only in-repo code that calls `sys_symlink` is `programs/tar_smoke.cyr` (tar, not zip). Materializing a symlink entry (and thus any traversal risk) is the consumer's responsibility — the same residual noted for the tar H-1 fix. Recorded here as a docstring/defense-in-depth note, not a defect. |

### Does the tar-style cross-entry symlink hole exist in ZIP?

**No.** The previous audit's HIGH (H-1) was an *on-disk* symlink-chain traversal in the tar cursor — a relative symlink planted by one entry redirected a later entry's write above the extraction root. That defect is intrinsically about writing files to disk and resolving link chains during extraction. The ZIP surface does neither: it is an in-memory codec that hands decoded bytes back to the caller. `zip_entry_is_symlink` merely reports the Unix mode bits from the central directory; nothing in `zip.cyr`/`zip_methods.cyr` follows, resolves, or creates a link. A ZIP consumer that materializes entries to disk must apply its own per-component `O_NOFOLLOW` / `openat2(RESOLVE_BENEATH)` guard — exactly the residual the tar fix left standing — but the cursor-level traversal bug has no reachable analogue in this code. The module docstring's parity claim with `tar.cyr` should nonetheless be corrected to state plainly that ZIP is memory-only and performs no traversal enforcement (there are no filesystem writes to enforce against).

---

## Sound behaviour confirmed (negative results worth keeping)

Everything below was checked and found genuinely sound — by execution where noted:

- **`_zip_find_eocd` backward scan** — bounds correct (`len < 22` incl. 0/negative returns −1 up front; the scan covers `[len − min(65557,len), len − 22]`, every `_zip_le32`/`_zip_le16` in `[0,len)`) and **not quadratic**: a 264 KB buffer that is *entirely* `PK\x05\x06` lookalikes parses in ~0.001 s (scan capped at ~65557 O(1) iterations).
- **Non-Zip64 EOCD path is overflow-immune** — `count` is u16, `cd_size`/`cd_off` are u32, so `cd_off + cd_size` cannot overflow i64 and the additive guard catches every out-of-range combination (verified by targeted field-mutation fuzz at 0/1/0x7FFF/0xFFFF/0x7FFFFFFF/0xFFFFFFFF). The Z-1 class is **strictly a Zip64 problem** — only `_zip_le64` fields can reach near-2⁶³.
- **`_zip_z64_extra` internal bounds are sound** — it iterates within `elen`, every `_zip_le64` is guarded by `q+8 > end` and each record by `p+4+dsz > elen`, and the caller pre-checks the whole extra region lies within `cd_end ≤ len`. A duplicate id-0x0001 record is ignored (first wins); a sentinel with no matching extra is rejected.
- **Entry-table allocation is safe** — bounded by `count ≤ cd_size/46` (each CD header ≥ 46 bytes) so `count * ZIP_ENT_SIZE` stays ~1.4× the file size; `alloc()` rejects `size ≤ 0` / `> ALLOC_MAX` and `zip_open` null-checks it. A huge Zip64 count (`0xFFFFFFFFFFFF`) with `cd_size=0` is rejected.
- **Struct offsets verified by hand** — reader/writer entry record `ZIP_ENT_SIZE = 64` uses slots `+0..+56` (last `store64` writes 56..63); writer ctx `ZIP_W_CTX = 128` uses init slots `+0..+56` and streaming slots `+56..+120` (last `store64` writes 120..127). No overlap, no overrun — the **2.6.0 overlapping-slot class is genuinely fixed**.
- **Stack arrays correctly sized** (`var buf[N]` is N bytes) — `dt[16]`, `dtc[16]` (2×u64), `ymd[24]`, `ov[24]`, `v[24]` (3×u64) all fit their `store64` offsets. The 2.4.7/2.4.8 undersized-array class does not recur.
- **Name-aliasing 2.6.2 class absent** — `_zip_record` copies the name via `_zip_cstr` and the streaming path copies into `+56`; no caller buffer is retained past its producing call.
- **`_zip_path_safe`** (byte-identical to tar's `_star_path_safe`) rejects empty, absolute (leading `/`), any `..` component, empty interior (`a//b`), NUL, control bytes < 32, and backslash; it runs on every extraction via `_zip_prepare`.
- **DOS↔Unix time helpers** — `_zip_days_from_civil` / `_zip_civil_from_days` are exact inverses across 1.7M days with no div-by-zero, overflow, or hang on extreme inputs.
- **CRC on every extract path** — `_zip_verify` enforces `got == usize` then the CRC-32 compare; STORE, DEFLATE (zip.cyr) and bzip2/xz/zstd (zip_methods.cyr) all check the decoder return `< 0` before verifying. No path returns member bytes without a CRC check. STORE additionally requires `csize == usize` and `usize ≤ dst_cap`. The ratio cap handles `csize==0` without divide-by-zero and uses integer division only.

---

## The new fuzz harness — `fuzz/fuzz_zip.fcyr`

The ZIP harness was **missing** from the tree (the pre-2.6.0 pass shipped lz4/deflate/xz/bzip2/zstd only). This audit wrote `fuzz/fuzz_zip.fcyr` in the exact house style of `fuzz_xz.fcyr` (LCG `_fuzz_seed`/`_fuzz_next`, strategy functions, a `main` that runs each N times printing one line per strategy; base archives built in-process with the writer). It compiles clean (`cyrius build fuzz/fuzz_zip.fcyr`) and is auto-discovered by `cyrius fuzz`.

Six strategies:
1. Random bytes + random-with-planted-EOCD-signature at `zip_open`.
2. Full truncation prefix sweep over writer-built archives.
3. 1..4-byte corruption, then open + extract-all.
4. Header-field fuzzing of `count`/`cd_size`/`cd_off`/`nlen`/`elen`/`lho`/`csize`/`usize`/`method`/`flags`/`made-by` to absurd values, **plus (4b) Zip64 injection** — plants a Zip64 extended-info extra with absurd 64-bit sizes/offsets, the surface a 32-bit field fuzzer cannot reach.
5. Writer round-trip asserting byte-identical read-back.
6. Streaming round-trip via `zip_enc_*` with random chunk splits.

**Ran hard:** strategies 1 (600), 2 (40 base × every prefix), 3 (400), 4 (400), 5 (300, byte-identical), 6 (300, byte-identical) **all pass** — no crash, no hang, no mis-parse, no 2.6.2-style aliasing regression, no struct-slot overlap. The harness then reliably SIGSEGVs (exit 139) in strategy **4b**, pinpointing exactly the Z-1 class; first crashing case: `seed=1, target=2` (local-header offset), `val=0x7FFFFFFFFFFFFFFF`. The harness goes green once the Z-1 subtraction-form guards land, so it doubles as the Z-1 regression gate. **Recommend merging it** (raises the fuzz harness count 5 → 6; wire into CI alongside the existing five).

---

## Coverage statement

**Examined this cycle** (first audit for all): the entire ZIP **reader** — `_zip_find_eocd`, `zip_open`, the central-directory walk, `_zip_le16/32/64`, `_zip_z64_extra`, `_zip_prepare`, `_zip_local_z64`/`_zip_local_size`, `_zip_path_safe`, `_zip_cstr`, `_zip_verify`, and all four `zip_extract*` variants — under ~120k fuzz cases across three generators (general mutation/truncation/corruption of Python-`zipfile` archives, a 264 KB all-signature scan-cost buffer, and a targeted in-range Zip64 fuzz), plus guard-page probes and hand-built hostile archives; the **writer** — `_zip_put16/32/64`, `_zip_z64_extra` emit, `_zip_emit_local`, `_zip_record`, `zip_writer_finish`, the Zip64 EOCD/locator emit — with every store64/load64 offset tabulated against its allocation; the **streaming state machine** (`zip_enc_begin`/`write`/`end`, `zip_writer_finish`) under timeout-guarded deadlock probes and multi-chunk STORE/DEFLATE round-trips; the DOS↔Unix time helpers as exact inverses; path safety against every traversal trick; and reference-CLI parity in both directions (unzip 6.00 / bsdtar / Python `zipfile`, methods 0/8/12/93/95, Zip64, metadata, data descriptors).

**NOT examined / gaps for the next pass:**
- **Method 95 (xz) via `zip_extract_any` was not cross-checked against Python `zipfile`** — its `zipfile` does not support method 95; parity for 95 rests on bsdtar + sankoch self-round-trip only.
- The **method-12/93/95 decoders themselves** (bzip2/xz/zstd) were audited only for the shared `_zip_prepare` bound they inherit — their internals were covered by the prior codec passes, not re-audited here. The Z-1d `:507` fix protects their `csize` argument.
- **Encryption / multi-disk / Deflate64 / method-14 (LZMA-alone)** are deliberate non-goals (rejected on purpose) and were confirmed rejected, not fuzzed for depth.
- `scripts/zip-smoke.sh` uses **fixed shared `/tmp` paths** (`/tmp/sankoch-zip-in.zip`, `/tmp/sankoch-zip-out.zip`); concurrent audit agents in sibling worktrees clobber them, producing spurious run-to-run failures. Isolated-path copies pass 13/13 deterministically. **Worth hardening the smoke driver to per-run `mktemp` paths** (independent of any finding here).
- `dist/` bundle regeneration was intentionally **not** committed by the audit lenses (minimal diffs); the CI dist-drift gate will require `cyrius distlib` for the full, `zip`, and `zipall` bundles once the fixes land.

---

## Prioritised remediation

**BLOCKING — must land before the ZIP surface is promoted to consumers / before 2.6.4** (public-API-reachable, attacker-controlled input, verified patches ready):

1. **Z-1** — rewrite all four additive guards in subtraction form: `src/zip.cyr:304`, `:314`, `:359` + `:502`, `:507`. One line each, algebraically identical for legitimate input; `:502`/`:507` in `_zip_prepare` close STORE/DEFLATE **and** the 12/93/95 decoders at once.
2. **Z-2** — `_zip_abort_stream(w)` on every streaming-writer abandon path (no-op for STORE, guarded against double-unlock).
3. **Z-3** — `_zip_streaming` guard at the top of `zip_add_meta` and `zip_add_any_meta`.

**CARRYABLE — fix opportunistically:**
4. **Z-4** — reject `nlen > ZIP_Z64_U16` at the three writer entry points.
5. **Merge `fuzz/fuzz_zip.fcyr`** and wire it into `cyrius fuzz`/CI; add the four Z-1 crafted archives (42/81/98/117-byte) to `tests/tcyr/zip.tcyr` so the additive-overflow class can never silently regress.
6. Harden `scripts/zip-smoke.sh` to per-run `mktemp` paths (removes the concurrent-worktree flakiness).

**After all source fixes:** regenerate `dist/sankoch.cyr`, `dist/sankoch-zip.cyr`, `dist/sankoch-zipall.cyr` and confirm the drift gate; re-verify `[lib.zip]` stays lean (no `xz_`/`bzip2_`/`zstd_` references in `src/zip.cyr` — confirmed clean at audit).

---

## Gates (at HEAD `0d0ff07`, tag 2.6.3)

| Gate | Status | Note |
|---|---|---|
| `cyrius build src/lib.cyr` | GREEN | 0 warnings on library path |
| `cyrius lint` (per source) | GREEN | 0 warnings/file |
| `cyrfmt --check` | GREEN | diff-clean across src/programs/tests/fuzz |
| `cyrius test tests/tcyr/zip.tcyr` | GREEN | 175 passed / 0 failed |
| `cyrius test` (full) | GREEN | 98 suites + 80112 assertions + 22, 0 failed |
| `cyrius fuzz` (5 harnesses) | GREEN | 5/5 — **no ZIP harness present** (`fuzz_zip.fcyr` is the deliverable) |
| `scripts/zip-smoke.sh` | GREEN* | 13/13 reference-parity on isolated paths (flaky on shared `/tmp` under concurrency) |
| dist drift (`zip`/`zipall`/full) | GREEN | matches committed; `[lib.zip]` compiles standalone |

**All standard gates are green — and that is precisely the problem.** `zip.tcyr`'s 175 assertions exercise the writer and the happy-path reader but have **zero adversarial coverage of the 64-bit Zip64 fields** the Z-1 class abuses, there was no ZIP fuzz harness at all, and there is no concurrency/deadlock test for the streaming writer. Green gates were necessary to ship 2.6.3 but are not sufficient to certify the never-audited 2.6.0–2.6.3 ZIP code.

---

## Verdict

**NOT clean at `0d0ff07` for the ZIP reader.** No HIGH survived verification — and, importantly, the previous audit's HIGH class (on-disk symlink-chain traversal) has **no analogue** in the ZIP surface, which is memory-only and performs no filesystem writes. But the reader carries one root-cause class, Z-1, that is a crash/DoS + OOB read reachable from the primary public entry points (`zip_open`, `zip_extract`) on a fully attacker-controlled in-memory archive, proven at four distinct sites by 42–117-byte crafted inputs; plus two writer-side MEDIUMs (Z-2 deadlock, Z-3 overlap corruption) and one LOW (Z-4). Every finding carries a verified patch; every fix is a one-line subtraction-form rewrite or a small guard, and none require redesign.

- Land the BLOCKING list (Z-1 + Z-2 + Z-3), then Z-4, merge `fuzz/fuzz_zip.fcyr` with the four Z-1 regression archives, regenerate the three ZIP-touching dist bundles, and re-run all gates.
- Correct the `src/zip.cyr` docstring's tar-parity claim: ZIP is in-memory and enforces no traversal (there is nothing on disk to enforce against); consumers must guard materialization themselves.
- Once the BLOCKING list is landed and green, the ZIP container is cleared for consumer promotion and the 2.6.4 cut. Update `docs/development/state.md` (ZIP surface: audited; Open INFOs) at that cut.

This audit contrasts sharply with the 2.3.x closeout (zero findings) precisely because the ZIP arc added a large, attacker-facing parser that the ZIP-free pre-2.6.0 pass never saw — a short but real confirmed list (0 HIGH · 3 MEDIUM · 1 LOW), all closable without redesign.