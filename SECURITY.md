# Security Policy

## Reporting Vulnerabilities

**Email**: security@agnos.io

Compression libraries are security-critical — malformed input must never cause crashes, buffer overflows, or unbounded memory allocation.

## Security Considerations

- **Decompression bombs**: Inputs that decompress to enormous output. Sankoch enforces output size limits.
- **Buffer overflows**: All buffer accesses are bounds-checked. No raw pointer arithmetic without validation.
- **Infinite loops**: Malformed DEFLATE streams could cause infinite decode loops. All loops have iteration limits.
- **Memory exhaustion**: Sliding windows and hash tables have fixed, bounded sizes.

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest | Yes |

**Last Updated**: 2026-04-14
