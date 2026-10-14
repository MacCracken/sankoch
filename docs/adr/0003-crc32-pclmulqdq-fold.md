# 0003 — CRC-32 folds with PCLMULQDQ on x86_64 only, finishes on the slice-by-8 table, and is enabled by CPUID plus a known-answer check

- **Status**: Accepted
- **Date**: 2026-10-13
- **Deciders**: sankoch maintainers

## Context

CRC-32 (reflected 0xEDB88320) checks every gzip member and ZIP entry, both directions. Since 2.3.4
it has been a portable slice-by-8 table, about 730 MB/s on the reference machine. The roadmap's 2.8.5
item asked for a carry-less-multiply fold (Gopal et al., Intel 2009) with one bar: it must not
regress and must be provably bit-exact, because a wrong CRC either rejects good archives or, worse,
writes archives every other tool rejects.

What was already true:

- Cyrius has no SSE mnemonics and no carry-less-multiply builtin. An `asm { }` block emits raw bytes;
  `param_load(reg, idx)` is the only operand helper. Every instruction would be machine code.
- There is no CPU-feature API beyond `simd_has_avx2` / `simd_has_fma` in `lib/simd.cyr`.
- On aarch64 the PMULL / CRC32 extensions are optional in ARMv8.0. The supported way for userland to
  ask is AT_HWCAP, which the stdlib reads from `/proc/self/auxv` (`lib/dynlib.cyr`). `src/` does no file
  I/O (the CI security scan rejects `sys_open` there), and AGNOS has no auxv.
- The `cx` backend refuses asm mnemonics and would emit raw bytes as bytecode.

## Decision

**x86_64 only; fold the bulk with PCLMULQDQ; finish the 128-bit remainder and the tail on the
existing table; enable per process after CPUID and a known-answer check; take the machine code
from GNU as, never from hand.**

- **In scope**:
  - `_crc32_fold` dispatches: `len >= 64` (the fold's minimum, and already faster than the table
    there: 44 vs 95 ns) and `_crc32_hw == 1` take `_crc32_fold_hw`, else `_crc32_fold_table`
    (slice-by-8, unchanged). `crc32`, `crc32_update`, gzip and zip all go through it.
  - **The fold** (`_crc32_clmul`, `docs/sources/crc32-pclmul/crc32_fold.S`): four 128-bit lanes over
    64-byte blocks, merged into one, then 16-byte blocks. Constants K1..K4 as in Linux
    `arch/x86/crypto/crc32-pclmul_asm.S`. Only xmm0..xmm5 (Win64 keeps xmm6..15), all loads `movdqu`.
  - **The finish**: the routine leaves the remainder R with the invariant `CRC_reg(data) == CRC_0(R ||
    tail)`, so the table computes the last 16 + (len mod 16) bytes. No 128→64→32 reduction and no
    Barrett step.
  - **The gate**: CPUID leaf 1 ECX bit 1, then `_crc32_fold_hw == _crc32_fold_table` on a 1,077-byte
    pattern that runs every stage (15 four-lane iterations, the merge, 3 one-lane iterations, a 5-byte
    tail). Either failing leaves slice-by-8. `_crc32_hw` doubles as the test switch.
  - **Provenance**: `scripts/crc32-clmul-asm.sh --check` re-assembles the `.S` and requires the
    bytes between the `BEGIN` / `END crc32_fold.S` markers in `src/checksum.cyr` to match it, then
    links the `.S` into `check.c` and compares fold + table finish against a bitwise CRC-32 on 20,000
    buffers.
- **Out of scope**: aarch64 (explicit slice-by-8 fallback, as the roadmap allowed), VPCLMULQDQ /
  AVX-512 wide folds, Adler-32 SIMD, CRC-64/XZ and CRC-32/BZIP2 (not on a hot path).

## Consequences

- **Positive**
  - CRC-32 is 15–21× faster where the fold runs (256 KiB: 358 → 16.7 µs, about 15.7 GB/s); gzip
    decode of a 4 KiB member 1.12×, streaming gzip encode of 128 KiB 1.05×.
  - Bit-exactness does not rest on the fold's reduction math: the table that has always been right
    computes the result from the fold's remainder, and the fold is checked three ways (native against
    bitwise, in-process known answer, a differential suite + fuzzer against the table).
  - A CPU, hypervisor or emulator that executes PCLMULQDQ wrongly gets the table, not a wrong CRC.
- **Negative**
  - 67 instructions of machine code that only the provenance script, not the compiler, keeps honest.
    Editing them by hand is the failure the script exists to catch.
  - aarch64 gets no speed-up. A PMULL or CRC32-instruction path needs a feature check that does not
    read a file (Linux emulates `mrs` of `ID_AA64ISAR0_EL1` for userland; macOS and AGNOS do not), so
    it is a separate decision.
  - The fold is gated per process: a test or embedder that sets `_crc32_hw = 1` on a CPU without
    PCLMULQDQ gets SIGILL. The tests force it only when CPUID says yes.
- **Neutral**
  - `_crc32_hw` and the constants are BSS, not arena memory, so `alloc_reset()` leaves them valid and
    `_checksum_reset_tables` does not touch them.

## Alternatives considered

- **The full Intel / Linux reduction (128 → 64 → 32 bits, then Barrett).** Lost: about 15 more
  instructions, two more constants (K5, μ / P') and a step whose published variants disagree with the
  paper (crc32fast documents the divergence). The table finish costs two slice-by-8 steps plus the
  tail per call, and is right by construction.
- **Hand-assembled bytes, verified only by tests.** Lost: the tests catch a wrong result, but a byte
  edited by hand that happens to produce right results on the tested CPUs (an encoding with an
  undefined REX bit, say) would not be visible. Assembling from source makes the bytes reviewable as
  instructions.
- **No runtime check, compile-time only.** Lost: `CYRIUS_ARCH_X86` says nothing about the CPU. Every
  x86_64 CPU since 2010 has PCLMULQDQ, but some hypervisors mask it.
- **PMULL on aarch64 now.** Lost for 2.8.5 on the feature-check problem above; `qemu-aarch64` was
  available, so the fallback path was run there (it computes the zlib reference values with the fold
  off).
- **Threshold above 64 bytes.** Measured and rejected: the fold is faster at every length it handles
  (64 B 44 vs 95 ns, 128 B 46 vs 178 ns, 4 KiB 287 vs 5,513 ns).

## References

- V. Gopal et al., "Fast CRC Computation for Generic Polynomials Using PCLMULQDQ Instruction"
  (Intel, 2009).
- Linux `arch/x86/crypto/crc32-pclmul_asm.S` (`crc32_pclmul_le_16`): the reflected CRC-32 constants.
- `src/checksum.cyr`, `docs/sources/crc32-pclmul/`, `scripts/crc32-clmul-asm.sh`,
  `tests/tcyr/checksum.tcyr`, `fuzz/fuzz_crc32.fcyr`; [architecture 006](../architecture/006-crc32-pclmul-asm.md).
