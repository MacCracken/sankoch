# crc32-pclmul — source of the PCLMULQDQ CRC-32 fold (2.8.5)

- `crc32_fold.S` — the fold `src/checksum.cyr`'s `_crc32_clmul` emits as raw bytes (Intel syntax,
  GNU as). The bytes in `src/` are transcribed from this file by `scripts/crc32-clmul-asm.sh`, never
  typed by hand ([architecture 006](../../architecture/006-crc32-pclmul-asm.md)).
- `check.c` — the native proof: links `crc32_fold.S` and checks fold + table finish against a bitwise
  CRC-32 on 20,000 random buffers. Run by `scripts/crc32-clmul-asm.sh --check`.

Method: V. Gopal et al., "Fast CRC Computation for Generic Polynomials Using PCLMULQDQ Instruction"
(Intel, 2009). Folding constants for the reflected CRC-32 polynomial (0xEDB88320) as in Linux
`arch/x86/crypto/crc32-pclmul_asm.S` (`crc32_pclmul_le_16`): K1 = 0x154442bd4, K2 = 0x1c6e41596
(four-lane fold), K3 = 0x1751997d0, K4 = 0x0ccaa009e (one-lane fold). The 128→32-bit reduction of
those implementations is replaced by finishing the remainder on sankoch's own table
([ADR 0003](../../adr/0003-crc32-pclmulqdq-fold.md)).
