# Brotli test corpus

Streams read at runtime by `tests/tcyr/brotli_decompress.tcyr` and `scripts/brotli-smoke.sh`.
`MANIFEST.tsv` holds one row per stream (expected verdict, output length and CRC-32, stream sha256,
the decoder stage it needs) plus single-bit-flip digests (`#flip`), for every row that needs the
command loop the reference decoder's state after the first compressed meta-block header (`#header`),
and the rows that witness the block-switching rules and the distance-ring rule of dictionary
references (`#kills`: the reference-decoder mutants that decode the row differently). Regenerate it
with `python3 scripts/brotli-manifest.py` (needs `brotli` 1.2.0); `--check` verifies the committed
copy. Every row is agreed by two oracles: the `brotli -d` CLI and `scripts/brotli_ref_decoder.py`.

The hand-built streams (`crafted/`, `probe/`) and the synthetic-input CLI streams in `small/`
(`mixed_7k.*`, `bswitch_records_68k.*`, and `alice29_32k.q5w16`, re-encoded from the committed
`google/alice29.txt.compressed`) are rebuilt by `python3 scripts/brotli-craft.py`
(`--check` compares with the committed bytes); run `brotli-manifest.py` afterwards.

| dir | contents | origin / licence |
|---|---|---|
| `google/` | google/brotli v1.2.0 `tests/testdata/*.compressed*` (originals are not committed; the manifest stores length + CRC-32) | MIT (`LICENSE.brotli`) |
| `synth/` | upstream synthetic decoder-test streams (`js/decode_synth_test.ts`) | MIT (`LICENSE.brotli`) |
| `probe/` | hand-crafted edge-case streams (the research probe set, `scripts/brotli-craft.py`) | GPL-3.0-only |
| `crafted/` | hand-crafted streams from the bit writer / mini-encoder in `scripts/brotli-craft.py` | GPL-3.0-only |
| `small/` | `brotli` 1.2.0 CLI output of small synthetic / public-domain inputs | GPL-3.0-only |

Stages (`needs`): `frame` (header, empty / metadata / uncompressed meta-blocks), `codes` (prefix codes
and the compressed meta-block header), `cmds` (the command loop), `dict` (static dictionary). Every row runs; the column
classifies the stream (`cmds` and `dict` rows also carry a `#header` line for the T10 header check).
