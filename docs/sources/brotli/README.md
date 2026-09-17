# Brotli (RFC 7932) source data

Authority files for sankoch's decode-only Brotli module (`src/brotli.cyr`, `src/brotli_dict.cyr`).

| file | what | provenance |
|---|---|---|
| `dictionary.bin` | the 122,784-byte static dictionary; sha256 `20e42eb1b511c21806d4d227d07e5dd06877d8ce7b3a817f378f313653f35c70`, CRC-32 `0x5136cb04` (the value RFC 7932 Appendix A states) | RFC 7932 Appendix A; byte-identical to google/brotli v1.2.0 `c/common/dictionary.bin` |
| `tables.txt` | every constant table a decoder needs, one line per table, each with the CRC-32 of its comma-joined decimal rendering | extracted from google/brotli v1.2.0 by `extract_tables.py`, cross-checked against RFC 7932 where the RFC states the table |
| `extract_tables.py` | the extractor | dev-time only; `python3 extract_tables.py [--src DIR]` — see *Re-running the extractor* |
| `probe/enough_results.tsv` | `n  entries`: the largest root-8 / max-15 prefix-code table over n symbols, which justifies the decoder's 396 / 632 / 646 / 896 / 1080 table caps | zlib `examples/enough.c` 1.5 (Mark Adler), `enough n 8 15`; for n >= 512 with its `syms < 1 << (root + 1)` guard removed (weaker evidence, flagged in the extractor) |
| `LICENSE.brotli` | MIT licence of google/brotli | applies to `dictionary.bin` and the tables derived from google/brotli |

## Re-running the extractor

`tables.txt` is committed, so nothing in the build needs the extractor. To re-derive it, fetch its two
external inputs into one directory (not committed; `build/` is a good place):

```sh
git clone --depth 1 --branch v1.2.0 https://github.com/google/brotli build/brotli-src
curl -sSo build/brotli-src/rfc7932.txt https://www.rfc-editor.org/rfc/rfc7932.txt
python3 docs/sources/brotli/extract_tables.py --src build/brotli-src   # 34 checks, 42 tables
```

sha256 of the inputs used for the committed `tables.txt` (2.8.0): `rfc7932.txt`
`394abd1879e016f4eac89512c2acaf92f7b2d67feb8ab58b6b118c213be07146`, `c/dec/decode.c`
`f7749b1296128c0add4eaa454b9d82ee1c7b0451c1c9ed47d96733e6de6f2d7b`, `c/common/dictionary.bin`
`20e42eb1b511c21806d4d227d07e5dd06877d8ce7b3a817f378f313653f35c70`. With those inputs the output is
byte-identical to the committed file. The `enough` probe is not re-run by the extractor; it reads
`probe/enough_results.tsv`.

## How they are used

- `scripts/brotli_dict2cyr.py docs/sources/brotli/dictionary.bin src/brotli_dict.cyr` generates the
  dictionary module. It also accepts the RFC 7932 plain text and parses Appendix A, so the bytes can be
  re-derived from the standard alone. CI regenerates the module and `cmp`s it with the committed copy.
- `tests/tcyr/brotli_decompress.tcyr` renders each runtime table in `tables.txt` line format and
  compares its CRC-32 with the value pinned here. The CRC gate is the authority, not the hex text in
  `src/brotli.cyr`.
- `scripts/brotli_ref_decoder.py` (the strict Python oracle) loads the dictionary, transforms and
  context tables from these files.

Data derived from google/brotli is Copyright (c) 2009, 2010, 2013-2016 by the Brotli Authors, MIT
licence (`LICENSE.brotli`). The sankoch code that uses it is GPL-3.0-only.
