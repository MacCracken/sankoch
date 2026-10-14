# 006 — The PCLMULQDQ CRC-32 fold is machine code: how to change it, and what it must not touch

`src/checksum.cyr`'s `_crc32_clmul` (2.8.5) is 67 x86_64 instructions written as raw bytes inside an
`asm { }` block, because Cyrius has no SSE mnemonics. Nothing in the compiler checks them. Read this
before editing that function, `_crc32_fold`, `_crc32_hw_probe`, or the folding constants. The design
decision is [ADR 0003](../adr/0003-crc32-pclmulqdq-fold.md).

## The bytes come from the assembler, never from hand

The source is `docs/sources/crc32-pclmul/crc32_fold.S` (Intel syntax, GNU as). To change the fold:

1. edit the `.S`;
2. `bash scripts/crc32-clmul-asm.sh > build/clmul/bytes.txt` and paste the lines between the
   `# BEGIN crc32_fold.S` / `# END crc32_fold.S` markers in `src/checksum.cyr`;
3. `bash scripts/crc32-clmul-asm.sh --check`: the transcription must match a fresh assembly, and the
   native check (`check.c` links the `.S`) must agree with a bitwise CRC-32 on 20,000 buffers;
4. `cyrius test tests/tcyr/checksum.tcyr` and the `fuzz_crc32` harness.

The script needs binutils (and gcc + a PCLMULQDQ CPU for the native half); it is local, not CI.

## What the asm may touch

- **Registers**: rax/rcx/rdx/rsi/rdi/r8 and xmm0..xmm5 only. A function containing `asm` never gets
  Cyrius's register allocator, but its *callers* may keep locals in rbx and r12..r14, and r15 is parked
  on Mach-O and AGNOS. Win64 makes xmm6..15 callee-saved. The CPUID helper pushes and pops rbx because
  `cpuid` writes it.
- **No `ret`**: the block falls through to the function's own epilogue. The `.S` ends without one;
  the native check appends it.
- **Arguments** arrive through `param_load(reg, idx)` (the parameter's real prologue slot), never
  through hard-coded `[rbp-N]` offsets, which broke sigil when the prologue changed.
- **Memory**: every load is `movdqu`, so neither the data nor the constants need 16-byte alignment.
  The routine reads `len - len % 16` bytes from `data`, 32 from `keys`, and writes 16 to `out`.

## The contract with its callers

- `_crc32_clmul` requires `len >= 64`. Below that its first loop runs past the end of the buffer:
  `_crc32_fold`'s `len >= _CRC32_CLMUL_MIN` (64) guard is load-bearing (mutation-verified: at 63 the
  suite crashes).
- It leaves the remainder R with `CRC_reg(data[0..len)) == CRC_0(R || data[len - len % 16 .. len))`.
  `_crc32_fold_hw` finishes on the table **from register 0**. Finishing from `crc` instead is wrong
  (the register is already folded into R's first four bytes).
- The four constants live in `_crc32_k` and are written by `crc32_init_table()`, which every CRC-32
  path already requires, **not** by the probe. A forced `_crc32_hw = 1` before any probe must still
  fold correctly (`fuzz_crc32` found the earlier version folding with zero keys this way).
- Every asm block sits under `#ifdef CYRIUS_ARCH_X86`. On aarch64 and `cx` the functions compile
  to `return 0`, `_crc32_hw_probe` leaves `_crc32_hw = 0`, and slice-by-8 does everything.

## How it is checked

| Layer | What it proves |
|---|---|
| `crc32-clmul-asm.sh --check` | `src/` carries exactly the assembled bytes; the fold's math is right (native, bitwise reference) |
| `_crc32_hw_probe` known answer | on *this* CPU, the fold agrees with the table on a pattern that runs every stage, or the table is used |
| `checksum.tcyr` | probe on exactly when CPUID says so; zlib vectors with the fold on and off; every length 0..1,100 × 16 alignments and 2,000 long runs from random registers; chunked `crc32_update` |
| `fuzz_crc32.fcyr` | 6,000 random cases: buffers, offsets, registers, chunkings, bit flips |

A corrupted fold instruction trips the probe (the fold turns itself off) and fails the suite and the
fuzzer when the fold is forced on.
