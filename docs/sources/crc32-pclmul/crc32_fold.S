# crc32_fold.S — the x86_64 PCLMULQDQ fold behind sankoch's _crc32_clmul (src/checksum.cyr).
#
# The bytes of this routine are what src/checksum.cyr's asm block emits, after the four
# param_load lines that put the arguments in rdi / rsi / rdx / rcx / r8 (scripts/crc32-clmul-asm.sh
# assembles this file and checks the transcription). Intel syntax, GNU as.
#
#   rdi = crc   running CRC-32 register (reflected 0xEDB88320, pre-inversion), low 32 bits
#   rsi = data  input, len >= 64 (no alignment needed: every load is movdqu)
#   rdx = len   bytes available; the routine consumes len - (len % 16)
#   rcx = keys  32 bytes: K1 | K2 (4-block fold), K3 | K4 (1-block fold), low qword first
#   r8  = out   16 bytes: the folded 128-bit remainder
#
# Afterwards CRC_reg(data[0..len)) == CRC_0(out[0..16) || data[len - len % 16 .. len)), which the
# caller finishes with the slice-by-8 table. Only xmm0..xmm5 and rax/rcx/rdx/rsi/rdi/r8 are touched
# (xmm6..15 are callee-saved on Win64; so are rdi and rsi, which src/checksum.cyr pushes around the block). Folding scheme: Gopal et al., "Fast CRC Computation for
# Generic Polynomials Using PCLMULQDQ Instruction" (Intel, 2009); constants as in Linux
# arch/x86/crypto/crc32-pclmul_asm.S (crc32_pclmul_le_16) for the reflected CRC-32 polynomial.

        .intel_syntax noprefix
        .text
        .globl  crc32_fold
crc32_fold:
        movdqu  xmm0, [rsi]             # x3
        movdqu  xmm1, [rsi + 16]        # x2
        movdqu  xmm2, [rsi + 32]        # x1
        movdqu  xmm3, [rsi + 48]        # x0
        movd    xmm5, edi
        pxor    xmm0, xmm5              # fold the running register into the first 4 bytes
        add     rsi, 64
        sub     rdx, 64
        movdqu  xmm4, [rcx]             # K1 | K2
        cmp     rdx, 64
        jb      2f
1:                                      # 4 x 16 bytes per iteration
        movdqa  xmm5, xmm0
        pclmulqdq xmm0, xmm4, 0x00
        pclmulqdq xmm5, xmm4, 0x11
        pxor    xmm0, xmm5
        movdqu  xmm5, [rsi]
        pxor    xmm0, xmm5
        movdqa  xmm5, xmm1
        pclmulqdq xmm1, xmm4, 0x00
        pclmulqdq xmm5, xmm4, 0x11
        pxor    xmm1, xmm5
        movdqu  xmm5, [rsi + 16]
        pxor    xmm1, xmm5
        movdqa  xmm5, xmm2
        pclmulqdq xmm2, xmm4, 0x00
        pclmulqdq xmm5, xmm4, 0x11
        pxor    xmm2, xmm5
        movdqu  xmm5, [rsi + 32]
        pxor    xmm2, xmm5
        movdqa  xmm5, xmm3
        pclmulqdq xmm3, xmm4, 0x00
        pclmulqdq xmm5, xmm4, 0x11
        pxor    xmm3, xmm5
        movdqu  xmm5, [rsi + 48]
        pxor    xmm3, xmm5
        add     rsi, 64
        sub     rdx, 64
        cmp     rdx, 64
        jae     1b
2:                                      # fold the four lanes into one
        movdqu  xmm4, [rcx + 16]        # K3 | K4
        movdqa  xmm5, xmm0
        pclmulqdq xmm0, xmm4, 0x00
        pclmulqdq xmm5, xmm4, 0x11
        pxor    xmm0, xmm5
        pxor    xmm0, xmm1
        movdqa  xmm5, xmm0
        pclmulqdq xmm0, xmm4, 0x00
        pclmulqdq xmm5, xmm4, 0x11
        pxor    xmm0, xmm5
        pxor    xmm0, xmm2
        movdqa  xmm5, xmm0
        pclmulqdq xmm0, xmm4, 0x00
        pclmulqdq xmm5, xmm4, 0x11
        pxor    xmm0, xmm5
        pxor    xmm0, xmm3
3:                                      # then 16 bytes at a time
        cmp     rdx, 16
        jb      4f
        movdqa  xmm5, xmm0
        pclmulqdq xmm0, xmm4, 0x00
        pclmulqdq xmm5, xmm4, 0x11
        pxor    xmm0, xmm5
        movdqu  xmm5, [rsi]
        pxor    xmm0, xmm5
        add     rsi, 16
        sub     rdx, 16
        jmp     3b
4:
        movdqu  [r8], xmm0              # no ret: the Cyrius function epilogue follows the asm block
