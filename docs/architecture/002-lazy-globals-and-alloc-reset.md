# 002 — Every lazy global is an arena pointer, and `alloc_reset()` invalidates all of them

Non-obvious constraint a reader cannot derive from either API: sankoch memoizes
its tables as raw pointers into the stdlib bump arena, and the stdlib's
`alloc_reset()` rewinds that arena without any notification. This note records
why that combination is a memory-safety problem rather than a caching one, and
what 2.7.10 does about it.

## The shape

Nearly every table in this library is built once and remembered:

```
var crc32_table = 0;
fn crc32_init_table(): i64 {
    if (crc32_table == 0) { crc32_table = _sankoch_alloc(16384); }
    ...
}
```

`_sankoch_reset_tables()` lists them: the CRC-32 slice table, the Huffman
literal/distance/code-length tables, the fixed-tree caches, the LZ77 and LZ4
hash tables, the zstd encoder's context pools — around twenty pointers. And
`_sankoch_mtx`, the library-wide mutex, is allocated the same way by
`mutex_new()`.

All of them live in the bump arena. `alloc_reset()` rewinds that arena to its
first chunk. **It does not, and cannot, tell sankoch.** So after a reset every
one of those pointers is dangling *while still being non-zero* — which is
exactly the condition the `if (ptr == 0)` guards test. The guards conclude
"already built" and the library proceeds to read and write through memory a
different owner now holds.

## What it cost, measured

Against 2.7.9, at this library's own boundary:

- A caller that allocated 32 KB after `alloc_reset()` and then made **one
  ordinary `crc32_init_table()` call** had **16,351 of its own bytes
  overwritten** with CRC table data. `crc32_init_table` rebuilt the table on
  every call, so the stale pointer was not merely read — it was the destination
  of a 16 KB write.
- A `zlib_compress` / `zlib_decompress` round-trip after a reset returned
  `clen = -2`, `dlen = -1`, and kept failing on every subsequent call.

The mutex is the worst of the three: `mutex_lock()` on re-owned memory.

chitra found this downstream and filed it as "calling `alloc_reset()` between
decodes breaks the next PNG decode". The decode error was the benign symptom.

## Why detection is exact rather than heuristic

`alloc_reset()` **zeroes the span it rewinds** before handing those addresses
out again — an information-leak mitigation it performs for its own reasons
(memory-reuse disclosure). That is what makes a canary sound here:

- Allocate an 8-byte canary from the arena and stamp it with a magic.
- After a reset, the scrub is *guaranteed* to have zeroed it.
- So `load64(canary) != MAGIC` means the arena was reset, definitively — not
  probably.

Two alternatives were considered and rejected:

- **An `alloc_used()` watermark.** Unsound: a caller can reset and then
  allocate back past the recorded mark before calling sankoch again, and the
  counter also under-counts on the macOS and Windows backends via their
  large-object path.
- **An explicit `sankoch_reset()` for callers to call after `alloc_reset()`.**
  This is what `_sankoch_reset_tables()` already was, minus the documentation —
  and it has the same failure mode it is meant to fix, because a caller who
  forgets gets the wild write. A library should not require a ritual to be
  memory-safe.

**Residual, stated rather than left implicit:** a caller could reset, take the
canary's address for its own use, and happen to write exactly
`SANKOCH_ARENA_MAGIC` at exactly that offset. That is a 1-in-2⁶⁴ coincidence,
and it is the same bargain every guard value in systems software makes.

## Where the check lives

2.7.10 put it in two places. 2.8.0 widened both and added a third kind of site:

- **`_sankoch_lock()`, before `_sankoch_mtx` is touched, on every target.** Every
  public API entry goes through the lock, and the mutex pointer can itself be
  dangling, so the guard cannot run after it. Before 2.8.0 it sat after the
  AGNOS early return, which made the reset dead code on AGNOS.
- **Every memoizing public entry reachable without the lock.** That is
  `crc32_init_table()` (chitra re-inits per PNG decode) and, since 2.8.0,
  `crc64_init_table` / `crc64_init`, `crc32_bzip2_init_table`, `lz77_init` and
  the `huff_build_*` family. Before 2.8.0 those overwrote up to 524,288 caller
  bytes after a reset.
- **The stranded-canary predicate (2.8.0).** `alloc_reset()` zeroes only the
  first chunk. A canary placed in a later chunk (because the caller filled the
  first one before sankoch's first call) is treated as reset once the bump
  pointer is back in the first chunk. `arena_reset.tcyr` pins both directions.

When the guard fires it drops every memoized pointer and re-arms the canary, so
the ordinary lazy-init guards rebuild from scratch on the next use. The drop goes
through `_sankoch_reset_tables()`, which since 2.8.0 is the **bundle's**
dispatcher; see [003](003-per-profile-reset-dispatch.md). A canary whose 8-byte
alloc fails no longer disarms detection: the next guard treats the unarmed epoch
as a reset.

## Consequence for anyone adding a lazy global

Follow the registration rule in [003](003-per-profile-reset-dispatch.md): zero it
in its module's `_<module>_reset_tables`, make sure that reset is called from
`lib.cyr` and from every `src/reset_<profile>.cyr` whose profile lists the module,
and add it to the `arena_reset.tcyr` inventory cell. That reset is the recovery
path, not test scaffolding, and a pointer missing from it survives a reset it
should not have survived. 2.7.10's single list missed xz BT4 and zstd tables
(229,370 caller words overwritten, measured on 2.7.15 sources). The pattern to be
suspicious of is any `if (ptr == 0)` guard over an arena allocation: correct
before 2.7.10 only by accident, correct after it only because something zeroes
the pointer first.

## See also

- `tests/tcyr/arena_reset.tcyr` — the regression cells, all of which fail
  against 2.7.9.
- `src/runtime.cyr` — `_sankoch_arena_guard`, the canary, and the reasoning at
  the point of use.
- [003](003-per-profile-reset-dispatch.md) — the per-bundle dispatcher and the registration rule.
- CHANGELOG 2.7.10, 2.8.0.
