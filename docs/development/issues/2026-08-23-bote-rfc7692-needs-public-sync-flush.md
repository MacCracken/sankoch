# 2026-08-23 — bote needs a public DEFLATE **sync-flush** for RFC 7692 (WebSocket `permessage-deflate`)

**Status**: **OPEN — confirmed absent in sankoch 2.7.8** (verified 2026-08-23 against `dist/sankoch.cyr` at that tag).
**Reporter**: bote 3.3.7 blocker re-derivation. bote audited its "Blocked on cyrius / external" table item by item and found six of seven premises had expired; this one flipped from *"blocked on stdlib"* to *"sankoch already has 95% of it"*.
**Side**: bote is a prospective **consumer** — it does not declare sankoch today.
**Severity**: enhancement. Nothing is broken; a feature is unreachable.
**Depends on**: nothing. Purely additive.

---

## The ask, in one line

Expose a **sync flush**: end the current DEFLATE block sequence at a byte boundary with **BFINAL=0**, keeping the stream open and the LZ77 window intact, so the next message can continue the same compression context.

---

## Why bote wants it

RFC 7692 `permessage-deflate` is the standard WebSocket compression extension. bote ships a WebSocket MCP transport (`src/transport_ws.cyr`, `build/bote-ws`) where payloads are JSON-RPC — highly compressible and highly repetitive across messages, which is exactly the case context-takeover is designed for.

bote's roadmap carried this for months as *"LZ77 + Huffman in stdlib; likely via a future `lib/dynlib.cyr` zlib binding."* **That premise is dead** — sankoch already implements native DEFLATE, so no binding is needed. Re-deriving the row is what produced this filing.

## What sankoch 2.7.8 already provides (verified, `dist/sankoch.cyr`)

| Need | Have | Where |
|---|---|---|
| Raw DEFLATE, no zlib wrapper | `FORMAT_DEFLATE` | `:14` |
| Streaming encode | `deflate_enc_init` / `_init_dict` / `_write` / `_finish` | `:5254` / `:5273` / `:5353` / `:5484` |
| Streaming decode | `deflate_dec_init` / `_init_dict` / `_init_capped` / `_reset` / `_write` / `_finish` | `:3768` / `:3815` / `:3849` / `:3875` / `:3911` / `:4266` |
| Preset dictionary (context seeding) | `deflate_enc_init_dict`, `deflate_dec_init_dict` | `:5273`, `:3815` |
| Decompression-bomb guard | `deflate_dec_init_capped(dst, dst_cap, expected_src_len, max_ratio)` | `:3849` |

That is a genuinely strong base — `_init_capped` in particular matters, because `permessage-deflate` is a well-known amplification vector and a consumer that had to hand-roll the ratio cap would get it wrong.

## The one missing piece

RFC 7692 §7.2.1 frames each message as: compress the payload, **sync-flush**, then strip the trailing 4 bytes `00 00 FF FF`. The receiver appends those 4 bytes back and decompresses. Crucially the stream is **not** ended between messages — that is what "context takeover" means, and it is where the compression ratio comes from.

sankoch's only public way to close out a message is `deflate_enc_finish`, which **ends the stream**:

```
# dist/sankoch.cyr:5502-5506
    if (is_dyn == 1) {
        # Dynamic: last sub-block is BFINAL=1. ...
        rc = _dyn_flush_subblock(bw, 1);
```

`BFINAL=1` means "no more blocks in this stream". After it, the encoder cannot continue and the window cannot carry into the next message. So today a consumer must choose between:

- calling `deflate_enc_finish` per message → a fresh stream each time, i.e. **`no_context_takeover` only**, and even then the trailer bytes are wrong for RFC 7692; or
- not implementing the extension.

⭐ **The machinery already exists — it is only the exposure that is missing.** `_dyn_flush_subblock(bw, bfinal)` (`:5091`) already takes `bfinal` as a parameter, and `deflate_enc_finish` is simply the `bfinal = 1` caller. What is not reachable from outside is the `bfinal = 0` path plus the empty-stored-block terminator that makes the output byte-aligned.

⚠ Not a workaround: `_dyn_flush_subblock` and `_denc_*` are underscore-private. Cyrius has one flat namespace so a consumer *can* call them, but reaching into another crate's privates is how bote got burned by libro's `struct error` (bote CHANGELOG 3.3.4) — it will not do that again.

## Proposed shape

```
# Close the current block sequence at a byte boundary with BFINAL=0 and
# emit the RFC 1951 §"sync flush" empty stored block (00 00 FF FF).
# The stream stays open and the LZ77 window is retained, so a subsequent
# deflate_enc_write continues the same compression context.
# Returns bytes written to dst, or negative on error.
fn deflate_enc_flush(ctx): i64
```

A `deflate_enc_reset_context(ctx)` (drop the window, keep the stream) would additionally let a consumer honour the negotiated `client_no_context_takeover` / `server_no_context_takeover` parameters without tearing down and rebuilding the encoder. Nice-to-have, not required.

Decoder side appears already sufficient: `deflate_dec_write` can be fed the payload plus the re-appended `00 00 FF FF`, and `deflate_dec_reset` (`:3875`) covers the no-context-takeover direction. ⚠ Worth confirming that `deflate_dec_write` does not *require* a BFINAL=1 block before yielding output — if it buffers until end-of-stream, the decoder needs an incremental-flush answer too, and that would be a second gap.

## Caveats worth stating

- ⚠ **This does not unblock bote on its own.** RFC 7692 is negotiated via the `Sec-WebSocket-Extensions` handshake header, and cyrius's `lib/ws_server.cyr` exposes no handshake hook and no way to add a response header — its whole exported surface is 13 functions with no seam. That is a separate upstream ask against cyrius. **Do not schedule this expecting bote to adopt it immediately**; it is the half sankoch owns.
- Sync flush costs ratio on small messages (each flush forces a block boundary). That is inherent to RFC 7692, not to sankoch, and is the consumer's trade-off.
- bote does not declare sankoch today (absent from its `[deps] stdlib`), though `lib/sankoch.cyr` is present via the toolchain fold.

## Proposed sankoch roadmap entry

> **`deflate_enc_flush` — public sync flush (BFINAL=0 + `00 00 FF FF`).**
> Ends a message's block sequence at a byte boundary without ending the
> stream, retaining the LZ77 window. Required by RFC 7692
> `permessage-deflate` with context takeover; blocks bote's WebSocket
> transport from adopting compression. `_dyn_flush_subblock(bw, bfinal)`
> already takes the flag — this is exposure plus the stored-block
> terminator, not new compression work.

## Log

- **2026-08-23** — Filed. Verified against `dist/sankoch.cyr` @ 2.7.8: public encoder surface is `deflate_enc_init` / `_init_dict` / `_write` / `_finish` only; no flush/sync entry point (`grep -nE '^fn .*(flush|sync)'` returns only private helpers `_dyn_flush_subblock`, `_xze_flush`, `_bze_flush_bits`, `_zew_flush`, `_zo_sync_insert`). `deflate_enc_finish` confirmed to emit BFINAL=1 at `:5502-5506`.
