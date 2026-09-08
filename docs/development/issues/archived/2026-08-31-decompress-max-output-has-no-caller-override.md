# `DECOMPRESS_MAX_OUTPUT` is an absolute 16 MiB with no caller override, so a vetted large stream cannot be inflated at all

**Status:** ✅ **RESOLVED in 2.7.13** (2026-09-07). Shipped `zlib_decompress_capped` and
`zlib_dec_init_output_capped` — the parameterised ceiling exactly as asked, including the streaming
peer, and *without* raising the default for anyone else: `zlib_decompress` is byte-for-byte
unchanged and 16 MB is still what an unbounded caller gets. `max_output` is clamped to `dst_cap`,
since the caller has already allocated that buffer and no decode may write past it. The alternative
shape this filing offered — publishing `DECOMPRESS_MAX_OUTPUT` as a documented constant contract —
was **not** taken: it would have left every consumer's supported image size a function of a sankoch
internal, which is the thing the filing itself objected to.
⚠ Chasing regression coverage for this fix surfaced an unrelated and more severe defect — a hang in
the streaming zlib decoder on any dynamic-Huffman code longer than 9 bits, present since the 2.3.0
streaming arc. Filed separately as
`2026-09-07-streaming-zlib-decoder-hangs-on-dynamic-huffman-codes.md`; it is **not** caused by this
change and does not affect the batch path this filing was about.
**Original status:** 🟡 OPEN — a request for a parameterised ceiling, not a request to raise the default.
**Placement:** `src/types.cyr` (`DECOMPRESS_MAX_OUTPUT`), the guards in `src/deflate.cyr`
(:155, :191, :396, :497, :1020), and a new capped entry point beside
`zlib_decompress_with_ratio_cap` in `src/zlib.cyr`.
**Filed:** 2026-08-31, by **chitra** (via **crab**, the consumer that hit it).
**Affects:** sankoch **2.7.10**, and every cyrius release that vendors it as a stdlib leaf.
**Severity:** **Medium as a capability gap, and it is not a bug.** The ceiling is a deliberate
anti-bomb backstop and the default is defensible. What is missing is a way for a caller that has
*already* bounded its input to ask for more.

## The consumer

chitra decodes PNG. PNG's IDAT is DEFLATE, so every decode routes through `zlib_decompress`, and the
inflated scanline data for an RGB image is `height × (1 + width × 3)`. That crosses 16 MiB at
about **5.6 megapixels** — bracketed exactly:

| image | inflated bytes | result |
|---|---:|---|
| 2200×2200 RGB | 14,522,200 | decodes |
| 2370×2370 RGB | 16,853,070 | `ERR_OUTPUT_LIMIT` |

⇒ **An ordinary phone photograph saved as PNG cannot be decoded**, by any consumer, on any platform.
`CHITRA_MAX_PIXELS` advertises 4096×4096; the reachable limit for RGB is roughly 2370×2370.

⚠ **The streaming API does not help**, which is the part worth stating plainly: `zlib_dec_write`
enforces the same ceiling (`src/deflate.cyr:1020`), so `zlib_dec_init` / `_write` / `_finish` cannot
be used to work around it either. There is no sankoch entry point that emits past 16 MiB.

## The ask

A ceiling the caller can raise, alongside the ratio cap that already exists:

```
fn zlib_decompress_capped(src, src_len, dst, dst_cap, max_output): i64
```

…and a `zlib_dec_init_output_capped` peer for the streaming decoder. `dst_cap` is already an explicit
caller bound; `max_output` would simply stop `DECOMPRESS_MAX_OUTPUT` from overriding it downward.

⚠ **Not a request to raise the default.** 16 MiB is a good default precisely because most callers
inflate untrusted wire data and have no independent bound. The asymmetry is that a caller like chitra
*does*: it has parsed an IHDR, validated the dimensions against its own caps, checked the
inflated/compressed ratio against `CHITRA_MAX_INFLATE_RATIO` (1100), and knows exactly how many bytes
a correct stream must produce — it passes that number as `dst_cap` already. For such a caller the
absolute ceiling is a second, lower bound it cannot reason about.

⛔ **The alternative shape, if a parameter is unwelcome**: expose the ceiling as a *documented public
constant contract* rather than an implementation detail, so consumers can pre-check against it. That
is what chitra 1.0.1 does today — it reads `DECOMPRESS_MAX_OUTPUT` and refuses before allocating —
and it works, but it makes every consumer's supported image size a function of a sankoch internal.

## What chitra did in the meantime (1.0.1)

Not a workaround for the limit — there is none — but a fix for what the limit *cost*:

⚠ chitra's own ceiling (`CHITRA_MAX_RAW_BYTES`) is 256 MB, **sixteen times** what sankoch emits. So a
valid 4096×2160 PNG passed every guard, chitra allocated the IDAT concatenation **and** a 26.5 MB
inflate buffer, and only then did `zlib_decompress` refuse. **Measured: 26,617,512 bytes spent to
return 0** — and cyrius's allocator is a bump allocator with no `free()`, so those bytes never came
back. chitra now compares against `DECOMPRESS_MAX_OUTPUT` before allocating anything and returns a
distinct `CHITRA_ERR_INFLATE_LIMIT` in under 64 KiB.

⇒ The failure is now cheap and correctly named. It is still a failure, and only sankoch can change
that.
