# Architecture Notes — sankoch

> Invariants, constraints, and quirks that a reader **cannot derive from the code alone**. These are *how the world is*, not *what we chose* (which lives in [`../adr/`](../adr/)).
>
> Conventions mirrored from [first-party-documentation § Architecture Notes](https://github.com/MacCracken/agnosticos/blob/main/docs/development/first-party/first-party-documentation.md#architecture-notes). Reference implementation: [sit's architecture notes](https://github.com/MacCracken/sit/tree/main/docs/architecture).

## Conventions

- **Filename**: `NNN-kebab-case-title.md`, zero-padded to three digits. **Never renumber.**
- Numbered chronologically in order of discovery.
- Not a decision (that's an ADR), not a how-to (that's a guide). An architecture note documents reality.

## What belongs here

- Stdlib quirks the project relies on.
- Cross-module invariants enforced by convention, not by the compiler.
- Ordering requirements, lifetime assumptions, memory-layout assumptions.
- "Don't touch X without reading Y first" warnings.

## What does NOT belong here

- Bug reports — use [`../development/issues/`](../development/issues/).
- TODOs — use code comments or the [roadmap](../development/roadmap.md).
- Narrative prose — sankoch doesn't carry articles.
- Decisions — those live in [`../adr/`](../adr/).

## Index

No architecture notes filed yet. Sankoch's current invariants are documented inline in `CLAUDE.md § Key Constraints` and in code comments at the relevant sites:

- **Include order matters** — `src/lib.cyr` is the only file that imports stdlib; domain modules carry zero transitive includes. This makes `cyrius distlib` (strip-include concatenation) produce a compile-clean bundle.
- **`[lib.core]` profile is alloc/syscall/mutex-free** — verified by the CI tripwire (`programs/core_smoke.cyr`). Any new code added to a `[core]` module must hold to this contract.
- **All public-API mutable state behind one mutex** — `_sankoch_mtx`. Streaming encoders/decoders hold the mutex for their `init → finish` lifetime. Concurrent streaming sessions on the same thread are forbidden by the single-threaded contract.
- **Stack array sizing**: `var buf[N]` declares N **bytes**, not N entries. Use `&buf` for `load*`/`store*` addresses. This trips up new contributors every time.
- **Bit accumulator overpull** — the streaming DEFLATE decoder's `_ddec_fill` pulls full bytes from input even when only a few bits are needed. zlib / gzip wrappers must rewind `cp` by `(ctx.bits >> 3)` when the inner transitions to DONE; the encoder's `bw_align` byte-pads at finish to make this safe.

Any of these would be a good first architecture note when a future contributor stumbles into it. Convention: when an invariant burns more than ~30 minutes of debugging, promote it from inline comment / CLAUDE.md to a numbered architecture note.

---

*See also: [`../adr/`](../adr/) for the *why*; [`../guides/`](../guides/) for the *how*; [`../sources/compression.md`](../sources/compression.md) for algorithm citations.*
