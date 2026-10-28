# gzip has no caller-raisable output ceiling, and no decoder inflates in bounded memory

**Status:** 🟡 OPEN — two asks. The first mirrors 2.7.13's zlib API for gzip. The second is the ring
window already planned for 2.9.5, seen from a second consumer.
**Placement:** `src/gzip.cyr` (`gzip_decompress`, `gzip_dec_init`), beside `zlib_decompress_capped` /
`zlib_dec_init_output_capped` in `src/zlib.cyr`; for the second ask, the streaming DEFLATE decoder in
`src/deflate.cyr`.
**Filed:** 2026-10-28, by **mela** (the AGNOS marketplace; its install path inflates `.agnos-agent`
bundles).
**Affects:** sankoch **2.8.9**, as vendored by cyrius **6.7.18**.
**Severity:** **Medium as a capability gap; not a bug.** The 16 MiB default is the right backstop
for a caller with no bound of its own. mela has one.

## The consumer

An `.agnos-agent` bundle is a gzipped ustar archive. mela verifies its Ed25519 signature and SHA-256
digest, then inflates and extracts it (mela ADR-0008, ADR-0014). Flutter apps ship their engine,
`libflutter_engine.so`, inside the bundle, and real engines are tens of MB.

mela already bounds the input itself:
- a bundle over **100 MiB** is refused before anything is read;
- the registry's storage quota is checked against the extracted size before any file is written;
- the tar walker validates the whole archive before writing.

What it cannot get past is the decoder's ceiling. Measured on cyrius 6.7.18 (sankoch 2.8.9),
`gzip_decompress` with a 17 MiB `dst`:

| payload | result |
|---:|---|
| 16,777,216 B | decodes |
| 16,777,217 B | `-ERR_OUTPUT_LIMIT` (-6) |
| 20,971,520 B | `-ERR_OUTPUT_LIMIT` (-6) |

So no bundle whose tar is over 16 MiB can be installed, by any mela consumer. As of mela 1.3.0 the
packer refuses to build one, so nothing gets published that cannot install.

## Ask 1 — a gzip output ceiling the caller can raise

The same shape as 2.7.13's zlib pair:

```
fn gzip_decompress_capped(src, src_len, dst, dst_cap, max_output): i64
fn gzip_dec_init_output_capped(dst, dst_cap, max_output): i64
```

with the same rules:
- `max_output` is clamped to `dst_cap`;
- the default `gzip_decompress` is unchanged;
- the ceiling persists across members, as the ratio cap does.

The inner DEFLATE context already carries `out_max` at +184 (2.7.13), so this is the gzip wrapper
setting it, as `zlib_dec_init_output_capped` does.

**On its own this is enough for mela 1.x to lift the ceiling**, at the cost of holding the whole tar
in memory, up to whatever ceiling mela picks.

## Ask 2 — inflate in bounded memory

What mela needs eventually is to extract a large bundle without the tar in memory: inflate a chunk,
hand it to the tar walker, write the file data, and reuse the buffer. Today every streaming decoder
writes into one contiguous `dst` and reads back-references from it, so output memory grows with the
stream.

The roadmap's **2.9.5** moves the streaming DEFLATE state into the context, and the decoder into a
ring window, for bote's RFC 7692. mela needs the same structure. The shape that would serve it is a
drain:
- the decoder emits into a ring of at least `DEFLATE_WINDOW_SIZE`;
- the caller consumes what is new since the last write (`*_dec_drain(ctx, out, cap)` or a sink
  callback);
- the decoder never needs more than the window behind the current position.

Please count mela as a second consumer when the 2.9.5 ADR decides memory per context. mela opens
one decoder per install, so that cost is not a concern for it.

## What mela does meanwhile

mela 1.3.0 (ADR-0014):
- raises its own ceiling from 8 MiB to sankoch's 16 MiB;
- inflates each bundle once per install;
- has its tar walker yield one entry at a time, validating the whole archive in a first pass and
  writing in a second.

When Ask 1 lands, mela can lift the ceiling. When Ask 2 lands, each pass becomes a streaming
inflate feeding the same walker. mela's roadmap tracks both.
