# ZIP consumer report from agnosai — no writer sizing API, no reader teardown, one-value open failure

**Status:** 🔴 OPEN — filed by a consumer, not fixed here.
**Filed:** 2026-08-09, against sankoch 2.7.6 as vendored in cyrius 6.5.16.
**Consumer:** `agnosai/src/definitions/packaging.cyr` — `.agpkg` bundle export/import,
a port of `rust-old/src/definitions/packaging.rs` off the Rust `zip` crate onto
`zip_*`. The port is complete and green; everything below is a workaround it is
carrying, not a blocker.

Three findings, ranked by how much they cost a consumer. Each names the workaround
agnosai shipped, so the bar in `issues/README.md` — *someone is working around this in
production code right now* — is met by all three.

---

## 1. The writer has no sizing API, so every consumer re-derives the record layout

`zip_writer_init(dst, dst_cap)` (`src/zip.cyr`, bundle line 14742) never allocates:
`dst` is the caller's, every write site bounds-checks against `dst_cap`, and the answer
to "too small" is `0 - ERR_BUFFER_TOO_SMALL` at nine separate sites (14794, 14806,
14876, 14938, 14971, 15018, 15068, 15088, 15220/15235). There is no growth path.

There is also no way to ask how big the buffer needs to be:

- no `zip_bound` / `zip_size_hint` / `zip_writer_cap`;
- `_zip_local_size(nlen, ulen)` (14663) is `_`-prefixed **and** covers only one local
  header — not the `46 + nlen + elen` central-directory record (15057) nor the EOCD;
- `zip_writer_finish` returns the true length (15104), but it is terminal, and on
  `ERR_BUFFER_TOO_SMALL` it tells you nothing about how short you were.

So a caller has exactly two options: guess and retry, or derive the layout. Retrying is
worse than it sounds — there is no resize, a partially written `dst` is not reusable,
and a retry means a fresh `zip_writer_init` plus re-adding **and re-compressing** every
member.

**What agnosai shipped** (`src/definitions/packaging.cyr`, `_agnosai_pkg_bound`):

```
bound = 98 + Σ_i (124 + 2*nlen_i + len_i)
```

`124 = 30 local + 20 zip64 extra + 46 CD record + 28 CD zip64 extra`, the name counted
twice because it appears in both headers, and `98 = 56 + 20 + 22` for a zip64 EOCD plus
locator plus EOCD. Plus a 256-byte slack constant, purely because sankoch is a vendored
bundle that can change under a toolchain bump.

This is **only** computable because `zip_add_meta` degrades DEFLATE to STORE whenever
compression does not shrink the member (14795-14810, `cl > 0 && cl < len`), which makes
`len` a hard upper bound on the stored payload. That is a load-bearing property of your
implementation that a consumer has to know to size a buffer at all, and it is not
stated anywhere near the writer's public surface.

**Ask:** `fn zip_bound(count, total_name_bytes, total_payload_bytes): i64`, or a
`zip_writer_bound(w)` that reports the worst case for what has been added so far.
Either removes the derivation. A doc line on `zip_writer_init` stating the
STORE-worst-case guarantee would help even without the function.

---

## 2. Nothing frees anything a reader or writer allocates

There is no destructor in the public surface. All 26 entry points:

```
zip_add zip_add_any zip_add_any_meta zip_add_meta zip_count zip_enc_begin zip_enc_end
zip_enc_write zip_entry_crc zip_entry_csize zip_entry_is_dir zip_entry_is_symlink
zip_entry_method zip_entry_mode zip_entry_mtime zip_entry_name zip_entry_size
zip_extract zip_extract_any zip_extract_any_capped zip_extract_capped zip_find
zip_method_supported zip_open zip_writer_finish zip_writer_init
```

No `zip_close`, no `zip_free`, no `zip_writer_free`. `_sankoch_alloc` (15576) is a thin
`alloc()` wrapper with a fault-injection counter and no counterpart.

**Per `zip_open`, for an archive of `n` entries** (14345-14356, 14401, 14419, 14113):

| allocation | size |
|---|---|
| reader ctx | 40 B |
| entry table | `n * ZIP_ENT_SIZE` = `n * 64` B |
| one NUL-terminated name copy per entry | `Σ (nlen_i + 1)` B |
| symlink ledger | `24 + cap*8`, `cap` = pow2 ≥ `4n`, min 64 → ≥ 536 B |

For the 100-entry ceiling agnosai's format imposes that is roughly **12 KB per
`zip_open`**, none of it reclaimable on a bump allocator. Every mid-loop `return 0`
after 14349 leaks whatever was allocated up to that point, so a **malformed** archive
leaks too — which is the case an attacker controls the rate of.

`zip_writer_init` is the same shape: ctx 128 B (`ZIP_W_CTX`), record table
`ZIP_REC_INIT * ZIP_ENT_SIZE` = 4096 B doubling on demand (14718), one `_zip_cstr` name
copy per member (14727), and if the record-table alloc fails at 14747 the already
allocated ctx is dropped on the floor.

**Why this is a real cost and not a style note:** the natural consumer shape for this
API is a server accepting an uploaded bundle. Every request that calls `zip_open` burns
its allocation permanently, valid or not. agnosai has not mounted such a route yet,
which is the only reason this is a report and not an incident.

**Ask:** `zip_close(z)` and `zip_writer_free(w)`, even as no-ops under a bump allocator,
so consumers can write the call now and get the reclaim when the allocator supports it.
Failing that, a header note stating the lifetime contract explicitly — the current
absence reads as "handles are cheap" rather than "handles are permanent".

---

## 3. `zip_open` collapses every failure into `0`

Around twenty distinct `return 0` sites (14308-14420) share one value: too short,
multi-disk, bad zip64 locator, CD out of bounds, bad CD signature, **an encrypted
member** (14364), unresolvable zip64 sentinel, and OOM. A caller cannot distinguish
"these bytes are not a zip" from "we ran out of memory" from "this archive is fine but
one member is encrypted".

That last one matters for parity work specifically. The Rust `zip` crate opens an
archive containing an encrypted member and fails only when that member is read, so a
consumer can skip it and read the rest; sankoch refuses the whole archive at open.
agnosai had to record that as a deliberate divergence
(`agnosai/docs/adr/018-sankoch-path-check-on-import.md`, point 6) rather than reproduce
the upstream behaviour, because there is nothing to branch on.

`zip_writer_init` has a milder version of the same problem: `0` covers `dst_cap < 22`
and two allocation failures (14743-14747).

**Ask:** a negative `0 - ERR_*` return, or a `zip_last_error()` in the style of
`bayan_json_last_error()`. `ERR_UNSUPPORTED_FORMAT` for the encrypted case alone would
be enough to let a consumer choose.

---

## Smaller things, no workaround needed

- **`zip_find` recomputes `strlen(name)` three times per entry** (14516 twice, 14517
  once) inside an O(n) scan. A consumer looking up N names in an N-entry archive — which
  is exactly the `by_name` shape the Rust crate encourages — pays `O(N² · |name|)`.
  Hoisting the `strlen` out of the loop is a two-line fix.
- **`zip_find` answers with the FIRST match**, and the Rust crate's name-keyed
  `IndexMap` answers with the **last** (a duplicate name replaces the value in place).
  agnosai ships its own `_agnosai_pkg_find_last` for parity. Worth a doc line either
  way, since "first" and "last" are both defensible and the choice is invisible.
- **`zip_count(z)` has no null guard** and faults on `zip_count(0)` (14439), which is
  the natural thing to write right after an unchecked `zip_open`.
- **`zip_entry_method`/`_crc`/`_csize`/`_size` return `0 - 1` for a bad index**, which
  is numerically `0 - ERR_INVALID_INPUT`; `zip_entry_mode`/`_mtime` return `0` for both
  "bad index" and "legitimately absent". Neither is distinguishable from a real value.
  Documented as "validate the index first" would be enough.

## What is good, so it does not get changed by accident

Three things agnosai depends on and would notice immediately:

- **`_zip_path_safe` on the READ path** (14541, via `_zip_prepare`), not just the write
  path. It is what makes zip-slip unreachable for a consumer that writes members by
  name, and it is stronger than the Rust crate, which leaves the check to the caller.
- **CRC is always verified and the declared size is always enforced** (`_zip_verify`,
  14587): `got != usize` → `ERR_CORRUPT_DATA`, then the CRC. The Rust crate enforces
  neither against the decompressed stream, so a bomb declaring
  `uncompressed_size = 10` inflates unbounded there and is bounded here. This turned
  agnosai's 1 MiB per-file cap from advisory into real.
- **DEFLATE degrading to STORE rather than growing a member.** Finding 1 depends on it.
