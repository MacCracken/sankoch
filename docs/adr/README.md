# Architecture Decision Records — sankoch

> Capture *why not the other thing*. If a future reader will reasonably ask "why did we do it this way?", the answer belongs here, not a commit message.
>
> Conventions are mirrored from [first-party-documentation § Architecture Decision Records (ADRs)](https://github.com/MacCracken/agnosticos/blob/main/docs/development/first-party/first-party-documentation.md#architecture-decision-records-adrs). Gold-standard reference: [sit 0001 — No FFI, first-party only](https://github.com/MacCracken/sit/blob/main/docs/adr/0001-no-ffi-first-party-only.md).

## Conventions

- **Filename**: `NNNN-kebab-case-title.md`, zero-padded to four digits. **Never renumber.**
- **One decision per ADR.** Supersessions add a new ADR and mark the old one `Superseded by NNNN`.
- **Status lifecycle**: `Proposed` → `Accepted` → (optionally) `Superseded` or `Deprecated`.
- Use [`template.md`](template.md) as the starting point.
- Pre-decision designs go in `docs/proposals/`. Promote into an ADR (this directory, next number) when the design is accepted; delete the proposal at that point.

## When to write an ADR

- Choosing between competing approaches with real trade-offs.
- Adopting or rejecting a dependency (especially relevant: zero-dep is load-bearing).
- Changing a public API.
- Accepting a performance, portability, or correctness trade-off.

If the decision could credibly have gone the other way, write the ADR. A reader six months from now should be able to reconstruct the reasoning without grepping git history.

## Index

No ADRs filed yet. Sankoch's load-bearing decisions are currently codified in `CLAUDE.md` (zero deps, no FFI, no floating point, all mutable state behind one mutex, etc.) and in the audit history. The first ADR will land when a new decision is made that has competing alternatives worth recording.

Some candidates that could earn an ADR retroactively if any of them surfaces a future reader asking *why* again:

- *Why is checksum code (Adler-32 / CRC-32 / xxHash32) inlined in sankoch instead of pulled from sigil?* — Reason: 30-line primitives that live inside the compression-format specs anyway; sigil dependency would invert the layering.
- *Why does the streaming decoder use a hold/bits bit accumulator with a bridge to `_huff_decode` instead of a per-symbol rewind?* — Reason: documented in CHANGELOG 2.3.0 bite-2; the bridge approach avoids per-call alloc and the speculative-rewind alternative would have required a carry-over tail buffer anyway.

Either of these would be a fine first ADR if a future decision rebuilds the alternative path.

---

*See also: [docs/architecture/](../architecture/) for invariants that are how-the-world-is (not decisions); [`../development/roadmap.md`](../development/roadmap.md) for the forward ladder; [`../../CHANGELOG.md`](../../CHANGELOG.md) for what shipped.*
