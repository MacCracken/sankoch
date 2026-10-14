/* check.c — native proof of the fold in crc32_fold.S (run by scripts/crc32-clmul-asm.sh --check).
 * Links crc32_fold.S (with a trailing ret appended) and checks, for 20,000 random buffers of 64 bytes
 * to 70 KB and random initial registers, that folding then finishing the 16-byte remainder and the
 * tail with a byte-wise table equals a bitwise CRC-32 (reflected 0xEDB88320) of the whole buffer.
 * Needs a CPU with PCLMULQDQ. SPDX-License-Identifier: GPL-3.0-only */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
void crc32_fold(uint32_t crc, const uint8_t *data, uint64_t len, const uint64_t *keys, uint8_t *out);
static uint32_t T[256];
static uint32_t tab(uint32_t c, const uint8_t *p, size_t n) { while (n--) c = (c >> 8) ^ T[(c ^ *p++) & 255]; return c; }
static uint32_t bitwise(uint32_t c, const uint8_t *p, size_t n) {
    while (n--) { c ^= *p++; for (int k = 0; k < 8; k++) c = (c >> 1) ^ (0xEDB88320u & -(c & 1)); } return c; }
int main(void) {
    for (uint32_t i = 0; i < 256; i++) { uint32_t c = i; for (int k = 0; k < 8; k++) c = (c >> 1) ^ (0xEDB88320u & -(c & 1)); T[i] = c; }
    static const uint64_t keys[4] = { 0x154442bd4ULL, 0x1c6e41596ULL, 0x1751997d0ULL, 0x0ccaa009eULL };
    uint8_t *buf = malloc(1 << 20); uint8_t out[16]; srand(7);
    long bad = 0, n = 0;
    for (int t = 0; t < 20000; t++) {
        size_t len = 64 + (size_t)(rand() % (t < 10000 ? 600 : 70000));
        for (size_t i = 0; i < len; i++) buf[i] = rand();
        uint32_t reg = (t % 3 == 0) ? 0xFFFFFFFFu : (uint32_t)rand() * 2654435761u;
        size_t done = len - (len % 16);
        crc32_fold(reg, buf, len, keys, out);
        uint32_t got = tab(tab(0, out, 16), buf + done, len - done);
        uint32_t want = bitwise(reg, buf, len);
        if (got != want) { if (bad < 5) printf("MISMATCH len=%zu reg=%08x got=%08x want=%08x\n", len, reg, got, want); bad++; }
        n++;
    }
    printf("%ld cases, %ld mismatches\n", n, bad);
    return bad != 0;
}
