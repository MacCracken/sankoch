# 001 — zstd L9 optimal parser: the hash-chain saturation cutoff

> Don't retune `_zo_chain_gate` / `_zo_chain_cut` (`src/zstd.cyr`) without reading this.
> The two constants are a **speed/ratio trade-off**, and the *length gate* is the load-bearing
> half — not an obvious dial you can turn freely.

## The reality

The zstd encoder's optimal parser (levels 7–9, `_zo_lz_parse`) prices a shortest-path parse over
positions. To do that it calls the match finder `_zo_getmatches` **roughly once per input byte** —
not once per emitted match. On a 256 KiB input that is ~260 K calls, each walking the frame-global
hash chain (2.7.4) up to `chain_max` links deep (512 at L9).

On maximally-repetitive **record data** (a constant field recurring thousands of times — CSV rows,
log lines), the 4-byte hash of that constant field chains to thousands of prior positions. Past the
first few, every candidate yields the **same** match length at an **ever-larger** offset — i.e. a
strictly *worse* encoding (larger offset code, no extra length). Walking them is pure waste, and it
cost **~2.6 s per 256 KiB L9 compress** (~100× the L6 greedy parse). The 2.7.4 frame-global chain
made this worse than the 2.7.3 per-block chain, because the chain now spans all prior blocks.

## The cutoff (2.7.5)

The chain walk bails after `_zo_chain_cut` **consecutive** candidates fail to extend `best`, **but
only once `best >= _zo_chain_gate`**. Any improvement resets the fail counter.

```
_zo_chain_gate = 32    # only cut once we already hold a substantial match
_zo_chain_cut  = 128   # ... and this many consecutive non-improving candidates have passed
```

## Why the length gate is load-bearing (the non-obvious part)

The instinct is that "stop after N non-improving candidates" alone should work. It does **not** —
without the gate it regresses diverse data badly (English text measured **+4.5 %** at `cut=32`).
The reason: text/prose/object-code climb `best` in *small steps* (3→5→8→…) and a genuinely longer
match can sit **deep** in the chain, so a run of non-improving candidates is normal *productive*
search, not saturation. Cutting there drops real matches.

Records are different: `best` jumps to its saturated length (~48 for the constant field) almost
immediately and then never improves — hundreds of duplicates follow. Gating the cutoff on
`best >= 32` cleanly separates the two: below the gate we keep the full deep search (diverse data
safe); above it, the deeper same-length links are dead weight (records fast).

A **pure depth-warmup** variant (walk the first W candidates unconditionally, then cut — *no*
length gate) was measured and rejected: it was **10–30× worse** on object code (+1.9 % to +3.8 %)
than the length gate at equal records speedup. Chain *position* does not separate saturated
duplicates from useful depth; match *length* does.

## The measured frontier (256 KiB, L9)

| gate | cut | records speedup | worst real-corpus Δ (object code) |
|-----:|----:|----------------:|----------------------------------:|
|   32 | 128 |          1.48×  | **+0.043 %** (shipped default)     |
|   32 |  64 |          1.63×  | +0.13 %                            |
|   24 |  48 |          1.87×  | +0.25 %                            |
|   16 |  32 |          2.14×  | +0.4 %                             |

The shipped point is the ratio-conservative end (worst real corpus +0.043 %, everything else 0 %),
matching the project's "correctness is the optimum sovereignty" bias. It is one-constant-tunable
toward more speed if a consumer profile ever justifies it.

## What the cutoff does *not* fix

The 1.48× wall-clock ceiling (vs the 1.7× chain-iteration reduction) is the DP parser's
~1-call-per-byte match-finder invocation. Cutting *that* means raising the greedy tendency via
`_zo_suff` (the "sufficient match" threshold that ends the DP early), which trades ratio on **all**
data, not just the pathological case — so it is deliberately left alone. If the record cliff ever
needs to go lower, the right lever is a self-pruning match finder (a BT4 tree, as the reference
zstd optimal parser uses), not a smaller `_zo_suff`.
