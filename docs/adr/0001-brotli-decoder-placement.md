# 0001 — Brotli decode ships in the full bundle and in `[lib.brotli]` / `[lib.woff]`, with its dictionary as a generated literal

- **Status**: Accepted
- **Date**: 2026-09-16
- **Deciders**: sankoch maintainers (filing: rekha)

## Context

rekha needs WOFF2, and WOFF2's payload is a single RFC 7932 Brotli stream
([proposal](../development/proposals/archived/2026-09-15-brotli-decoder-for-woff2.md)). rekha also reads
WOFF 1.0, which uses zlib per table, so one program needs both codecs. Several things were already
true:

- sankoch is the home for every lossless codec, with per-codec profiles.
- One sankoch bundle per program: two profile bundles collide on `runtime.cyr`'s globals
  ([architecture 003](../architecture/003-per-profile-reset-dispatch.md)).
- `src/` has no file access. The CI security scan rejects `sys_open` there.
- cycc 6.6.4 has a string-interning hazard for literals that contain NUL
  ([architecture 004](../architecture/004-string-literal-nul-rule.md)).
- cycc's DCE drops unreachable functions but keeps their literal and global data.

## Decision

**Decode only, one complete stream into a caller buffer, placed in three bundles.**

- **API.** It mirrors zlib:
  - `brotli_decompress(src, src_len, dst, dst_cap)`;
  - `brotli_decompress_capped(src, src_len, dst, dst_cap, max_output)`, with `max_output` clamped to
    `dst_cap` and allowed above 16 MiB;
  - `FORMAT_BROTLI = 9` through `decompress()`. `compress(FORMAT_BROTLI)` returns
    `ERR_UNSUPPORTED_FORMAT`.
- **Bound errors mirror `zlib_decompress_capped`.** The tighter of `dst_cap` and the ceiling reports
  first, as zlib's per-symbol checks do: `ERR_OUTPUT_LIMIT` when the ceiling is lower, and
  `ERR_BUFFER_TOO_SMALL` when `dst_cap` is lower or equal.
- **Placement.**
  - `src/brotli.cyr` and `src/brotli_dict.cyr` are in the full `[lib]`.
  - `[lib.brotli]` = types + dictionary + decoder + runtime + `reset_brotli.cyr`.
  - `[lib.woff]` = the `[lib.zlib]` module list plus Brotli, so rekha gets WOFF1 and WOFF2 from one
    bundle.
- **Dictionary.** It is `src/brotli_dict.cyr`, one 122,784-byte string literal generated from
  `docs/sources/brotli/dictionary.bin` by `scripts/brotli_dict2cyr.py`:
  - sha256 `20e42eb1…5c70`, CRC-32 `0x5136cb04` (the value RFC 7932 Appendix A states);
  - byte-identical to google/brotli v1.2.0 `c/common/dictionary.bin`;
  - CI regenerates it and `cmp`s. The decoder FNV-1a-checks it once per process at the first
    dictionary reference.
- **Trailing input is rejected.** Bytes after the final padding are `ERR_CORRUPT_DATA`, as with
  `brotli -d` and Python's `brotli`. Brotli has no checksum and no magic, so consuming the input
  exactly is a batch decoder's only end-of-stream integrity signal.
- **Out of scope**:
  - encode (scheduled for 2.8.1 as its own decision about profiles);
  - streaming;
  - Large Window Brotli, which is rejected with `ERR_UNSUPPORTED_FORMAT`;
  - shared dictionaries.

## Consequences

- **Positive.**
  - rekha links one bundle for both web-font containers.
  - The dictionary needs no alloc, no file access and no arena-reset registration: it is not
    arena memory.
  - `decompress()` gains a format with no change for existing callers.
- **Negative (measured).** Full-bundle consumers that never call Brotli pay for its data under
  cycc's current DCE. A `zlib_compress`-only consumer built with `CYRIUS_DCE=1` grows
  **74,352 → 213,072 B**:
  - 122,784 B dictionary literal;
  - 1,682 B other Brotli literals;
  - 10,160 B Brotli global arrays (emitted as file bytes);
  - about 2.9 KB of reachable reset code.

  A default build of the same consumer grows 455,280 → 626,768 B. Stopgap: the lean profiles
  (`[lib.zlib]` and the rest) do not carry Brotli, and upstream is filed
  (`cyrius/docs/development/issues/2026-09-16-sankoch-dce-keeps-string-literal-data-of-eliminated-fns.md`).
- **Neutral.**
  - One NUL-bearing literal exists in the tree. The NUL-literal gate exempts exactly that file.
  - `[lib.woff]`'s zlib half must be kept in step with `[lib.zlib]` by hand. The link gate probes
    both.

## Alternatives considered

- **Keep Brotli out of the full bundle** (`[lib.brotli]` only). This would avoid the DCE cost for
  full-bundle consumers. It lost because the full bundle is the "every codec" stdlib fold-in and
  `decompress()`'s dispatch lives in it; carving one codec out contradicts "modular by profile" in
  the other direction. Revisit if upstream DCE stays unfixed and a size-sensitive full-bundle
  consumer appears.
- **Dictionary as hex text decoded at first use.** It avoids the NUL literal, but 245 KB of source
  decodes into a 123 KB arena slab, which needs an alloc, an OOM path and a reset registration.
  Same DCE cost, twice the bytes.
- **Load the dictionary from a file.** `src/` has no file access, by rule.
- **Two profile bundles in one program** (`[lib.zlib]` + `[lib.brotli]`). Rejected by the
  one-bundle rule: duplicate `var`s become separate globals and the arena guard runs the wrong
  dispatcher (segfault, measured).
- **Accept trailing bytes**, as the C, JS and Java one-shot APIs do. It lost because with no
  checksum it would hide concatenation and truncation mistakes that `brotli -d` reports.

## References

- RFC 7932 (with errata 6977); google/brotli v1.2.0 `c/dec/decode.c`.
- [`docs/sources/brotli/`](../sources/brotli/README.md): dictionary, tables and extractor.
- [`docs/audit/2026-09-16-2.8.0-brotli-and-reset.md`](../audit/2026-09-16-2.8.0-brotli-and-reset.md).
- [`docs/sources/compression.md`](../sources/compression.md).
