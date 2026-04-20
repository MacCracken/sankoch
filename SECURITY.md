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

## Supported Versions

| Version | Supported |
|---------|-----------|
| 2.0.x   | Yes       |
| < 2.0.0 | No — upgrade |

**Last Updated**: 2026-04-19
