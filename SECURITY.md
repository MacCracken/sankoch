# Security Policy

## Reporting Vulnerabilities

**Email**: security@agnos.io

Compression libraries are security-critical — malformed input must
never cause crashes, buffer overflows, or unbounded memory allocation.

## Security Considerations

- **Decompression bombs**: Inputs that decompress to enormous output.
  Sankoch enforces a 16 MB output ceiling (`DECOMPRESS_MAX_OUTPUT`)
  on top of the caller-provided `dst_cap`.
- **Buffer overflows**: All buffer accesses are bounds-checked. No
  raw pointer arithmetic without validation. The CI security scan
  rejects stack buffers ≥ 64 KB in `src/`.
- **Infinite loops**: Malformed DEFLATE streams could cause infinite
  decode loops. All loops have iteration limits; the bit-reader
  returns negative error on EOF.
- **Memory exhaustion**: Sliding windows and hash tables have fixed,
  bounded sizes. The streaming encoder's window is 64 KB + 32 KB
  slide-retain, not unbounded.
- **Concurrency**: Every batch public function that touches shared
  mutable state takes `_sankoch_mtx`. Streaming encoders hold the
  mutex for their lifetime (`enc_init` → `enc_finish`). Concurrent
  encoders serialize naturally.
- **Reference-CLI compatibility**: LZ4F output is validated against
  `lz4 -dc`; zlib/gzip output against Python's `zlib.decompress`
  and `gunzip`. Spec-divergent wire format is a correctness bug, not
  just an interop inconvenience (caught v1.6.1 xxHash32 fix).

## Audit History

- `docs/audit/2026-04-15.md` — initial audit. CRIT-01 / CRIT-02 /
  CRIT-03 fixed.
- `docs/audit/2026-04-19.md` — P(-1) before v1.7.0. HIGH-01
  xxHash32 spec fix shipped in v1.6.1.
- `docs/audit/2026-04-19-pre-2.0.0.md` — P(-1) before v2.0.0 cut.
  No CRITICAL/HIGH findings; two LOWs fixed in-pass.
- `docs/audit/2026-05-01-pre-2.2.0.md` — P(-1) for the 2.1.x line.
  1 HIGH (DEFLATE stored-block source-bounds bypass), 1 MEDIUM
  (HLIT spec compliance), 2 LOWs (zlib CINFO, gzip reserved FLG)
  — all fixed in 2.1.3.
- `docs/audit/2026-05-01-pre-2.3.0.md` — P(-1) closeout for the
  2.2.x line. Zero HIGH/MEDIUM/LOW findings; three INFOs
  documented + carried forward.
- `docs/audit/2026-05-23-pre-2.3.0-redux.md` — P(-1) closeout at
  2.2.7 against Cyrius 6.0.1, immediately before opening the
  2.3.0 streaming-decomp arc.
- `docs/audit/2026-06-16-pre-2.4.0.md` — 2.3.8 P(-1) closeout for the
  2.3.x line against Cyrius 6.2.15. Zero HIGH/MEDIUM/LOW findings;
  re-checked the 2.3.3–2.3.7 paths (LZ4F block-max + per-block
  checksum, gzip FHCRC + concatenated streaming, FDICT dict-scratch
  match-copy, alloc-fail propagation).
- `docs/audit/2026-07-18-zstd-decoder-hardening.md` — 2.5.6 zstd decoder
  hardening. An adversarial multi-agent audit of the decode path against
  hostile `.zst` input surfaced **36 reachable issues** (24 crash, 10
  memory-corruption, 2 DoS) plus a sibling OOB in `zstd_frame_content_size`
  — all fixed; new `fuzz/fuzz_zstd.fcyr` decode-survival harness added.

Next periodic audit: the **P(-1) scaffold-hardening closeout** run
before the next minor cut (none currently scheduled — the codec set is
complete through 2.5.x). Most recent run:
`docs/audit/2026-07-18-zstd-decoder-hardening.md` (2.5.6 zstd decoder
hardening — 36 reachable OOB / memory-corruption / DoS issues found and
fixed; decoder now fuzzed). Forward ladder in
[`docs/development/roadmap.md`](docs/development/roadmap.md).

## Supported Versions

| Version | Supported |
|---------|-----------|
| 2.7.x   | Yes       |
| 2.6.x   | Security fixes only |
| < 2.6.0 | No — upgrade |

⚠ If you compress inputs larger than 1 MiB through the one-shot
`deflate_compress` / `zlib_compress` / `gzip_compress` path, upgrade to
**2.7.6 or later** regardless of the table above: earlier releases
re-encoded up to 257 bytes at every 1 MiB block boundary and returned a
stream longer than the input, with no error raised.

**Last Updated**: 2026-08-23
