# A Brotli decoder (RFC 7932), decode-only, as a `[lib.brotli]` profile — for rekha's WOFF2

**Status:** 🟡 **OPEN — a capability request.** The roadmap Backlog already names the trigger this
filing meets: *"Brotli (new codec) … land it when a web-serving / **font consumer** needs it."*
**Filed:** 2026-09-15, by **rekha** (the outline-font library; its v0.4.0 roadmap lists WOFF/WOFF2).
**Placement:** a new `src/brotli.cyr` (+ the RFC 7932 Appendix A dictionary as a data module), a
`FORMAT_BROTLI` arm in `decompress()`, and a `[lib.brotli]` distlib profile beside `[lib.zlib]`.
**Priority for rekha:** WOFF2 is the only web-font container that needs it. WOFF 1.0 is zlib per
table and is served by what sankoch already ships (`zlib_decompress_capped`, 2.7.13, via
`[lib.zlib]`), so rekha lands WOFF1 first and WOFF2 the moment this exists.

## The consumer

rekha parses TrueType (SFNT) bytes into glyph outlines for sadish to fill; dhancha, crab and agnos
draw text through it. Faces reach a target as files, and the web-font containers are how most faces
are distributed: **WOFF2's payload is ONE Brotli stream** holding every table (after WOFF2's own
glyf/loca transform), so without a Brotli decoder rekha cannot open a `.woff2` at all.

MEASURED on the face rekha already embeds (`fonts/LiberationSans-Regular.ttf`, 410,820 B), with the
reference CLI `brotli 1.2.0` and Python's zlib — the raw codec difference only, before WOFF2's glyf
transform, which shrinks the Brotli input further:

| encoding | bytes | of raw |
|---|---:|---:|
| raw SFNT | 410,820 | 100 % |
| WOFF1-style: zlib-9 per table + headers | 209,707 | 51.0 % |
| `brotli -q 11 -w 22` over the whole file | 169,278 | 41.2 % |

`brotli -d` round-trips it byte-exact, so the same file is a ready decoder test vector.

## What rekha needs

1. **Batch decode into a caller buffer**, the shape every sankoch decoder already has:
   `brotli_decompress(src, src_len, dst, dst_cap)` → bytes written, or `0 - ERR_*`. WOFF2 states the
   decompressed size up front (the sum of each table's `transformLength` / `origLength`), so rekha
   always knows the exact expected output and will pass `dst_cap` = that size.
2. **An output ceiling that fails closed**, like `zlib_decompress_capped`: a stream that would write
   past `dst_cap` (or a caller `max_output`) returns an error — never a truncated success. Font files
   are untrusted input; a Brotli bomb must not become an allocation rekha did not size.
3. **Hostile-input hardening to sankoch's zstd standard (2.5.6, fuzzed):** truncated streams,
   invalid/over-subscribed prefix codes, out-of-range distances and dictionary references, bad
   `WBITS`, and metadata blocks all return an error, with **bounded work** — the 2.7.14 streaming
   hang is the lesson here: every loop over input must make progress or fail. Complete-prefix-code
   checking at build time (the Kraft note already queued for the 2.8.x P(-1) pass) applies directly.
4. **The full format RFC 7932 defines** — context modeling, block-type/count switching, the
   **122,784-byte static dictionary and its 121 transforms**, window sizes 10..24 bits. Real WOFF2
   files are produced by the reference encoder at quality 11 and reference the dictionary; a decoder
   without it would reject them.
5. **A `[lib.brotli]` distlib profile** (types + bit reader + the Brotli module + dictionary data)
   so rekha — and through it dhancha/crab — pulls Brotli without the other codecs, the way
   `[lib.zlib]` serves sit and thoth. The ~123 KB dictionary must stay out of every other profile.

## Not asked for

- **Encode.** rekha only reads fonts. (A Brotli encoder is a separate, later sankoch question.)
- **Streaming.** WOFF2 hands over one complete stream with a known output size.
- **Large-window Brotli** (the non-RFC 30-bit extension). WOFF2 uses standard RFC 7932 streams.

## Validation rekha can offer

- The measured vector above (`brotli -q 11 -w 22` of LiberationSans; reference `brotli -d` output is
  the original file, sha256 `baccc64b…3bee`).
- Once `[lib.brotli]` exists, rekha's WOFF2 reader becomes a second consumer-side oracle: decode →
  WOFF2 reconstruct → compare every table against the source `.ttf`, plus a hostile-container suite
  (truncated/corrupted `.woff2`) in the style of rekha 0.3.11's `hostile_test`.
- Suggested sankoch-side corpus: the reference implementation's `tests/testdata` (`*.compressed`
  with originals), quality 0..11 and window 10..24 sweeps, and the dictionary-heavy text vectors.

## What rekha does meanwhile

rekha's v0.4.0 line proceeds without waiting: cmap formats 12/6/0, WOFF 1.0 over
`[lib.zlib]`, CFF (`OTTO`) outlines, and the WOFF2 **container + glyf/loca transform** reader written
and tested against transformed-but-uncompressed tables — so the only missing piece when this lands is
the one call to `brotli_decompress`.
