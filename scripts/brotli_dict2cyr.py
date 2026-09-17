#!/usr/bin/env python3
"""brotli_dict2cyr -- generate src/brotli_dict.cyr, the FREESTANDING Cyrius data module that
carries the Brotli static dictionary (RFC 7932 Appendix A, 122,784 bytes).

    python3 scripts/brotli_dict2cyr.py docs/sources/brotli/dictionary.bin src/brotli_dict.cyr

The input is either the raw 122,784-byte dictionary (the committed
docs/sources/brotli/dictionary.bin) or the RFC 7932 plain text, whose Appendix A hex dump is
parsed -- so the bytes can be re-derived from the standard alone. Either way they must match
the pinned length / sha256 / CRC-32 or nothing is written. Output is deterministic (no
timestamps, no machine paths) and written atomically (temp file + os.replace). CI regenerates
the module into build/ and `cmp`s it against the committed src/brotli_dict.cyr.

Representation: ONE string literal -- printable ASCII except '"' and '\\' raw, every other byte
as \\xNN. The literal line carries #skip-lint (cyrlint caps lines at 120 columns).

String-interning self-check (cyrius 6.6.4). The lexer interns a new literal L by trying pool
offsets `si` (0, and every offset just after a NUL) and comparing slen+1 bytes; when the window
overlaps L's own storage (d = sstart - si <= slen) a match needs L'[d-1] == 0 and L' to be
d-periodic (L' = L + terminator), and then L aliases storage the next literal overwrites --
silent wrong bytes. A literal with no NUL can never mis-alias. This dictionary has 70 NULs, so
for EVERY NUL position p the generator proves L' is not (p+1)-periodic, and refuses to write
otherwise. The check itself is self-tested on a known-bad literal before it is trusted.

Python stdlib only. The module uses NO stdlib, NO heap, NO syscalls, NO includes.
"""
import hashlib
import os
import re
import sys
import tempfile
import zlib

DICT_LEN = 122784
DICT_SHA256 = '20e42eb1b511c21806d4d227d07e5dd06877d8ce7b3a817f378f313653f35c70'
DICT_CRC32 = 0x5136cb04          # stated in RFC 7932 Appendix A
MASK64 = (1 << 64) - 1

# RFC 7932 section 8: NDBITS[length], length 0..24 (zero for lengths 0..3).
NDBITS = [0, 0, 0, 0, 10, 10, 11, 11, 10, 10, 10, 10, 10, 9, 9, 8, 7, 7, 8, 7, 7, 6, 6, 5, 5]

REGEN = 'python3 scripts/brotli_dict2cyr.py docs/sources/brotli/dictionary.bin src/brotli_dict.cyr'


def fnv1a64(data):
    h = 0xcbf29ce484222325
    for b in data:
        h = ((h ^ b) * 0x100000001b3) & MASK64
    return h


def xxh32(d, seed=0):
    import struct
    p1, p2, p3, p4, p5 = 2654435761, 2246822519, 3266489917, 668265263, 374761393
    m = 0xffffffff

    def rotl(x, r):
        return ((x << r) | (x >> (32 - r))) & m
    n = len(d)
    i = 0
    if n >= 16:
        v = [(seed + p1 + p2) & m, (seed + p2) & m, seed & m, (seed - p1) & m]
        while i + 16 <= n:
            for k in range(4):
                w = struct.unpack_from('<I', d, i)[0]
                i += 4
                v[k] = (rotl((v[k] + w * p2) & m, 13) * p1) & m
        h = (rotl(v[0], 1) + rotl(v[1], 7) + rotl(v[2], 12) + rotl(v[3], 18)) & m
    else:
        h = (seed + p5) & m
    h = (h + n) & m
    while i + 4 <= n:
        h = (rotl((h + struct.unpack_from('<I', d, i)[0] * p3) & m, 17) * p4) & m
        i += 4
    while i < n:
        h = (rotl((h + d[i] * p5) & m, 11) * p1) & m
        i += 1
    h ^= h >> 15
    h = (h * p2) & m
    h ^= h >> 13
    h = (h * p3) & m
    h ^= h >> 16
    return h


def from_rfc_text(text):
    """Parse Appendix A's hex dump out of the RFC 7932 plain-text rendering."""
    head = 'Appendix A.  Static Dictionary Data'
    start = text.rfind(head)          # the first occurrence is the table of contents
    end = text.find('Appendix B.  List of Word Transformations', start)
    if start < 0 or end < 0:
        raise ValueError('Appendix A / Appendix B headings not found')
    hexl = [ln.strip() for ln in text[start:end].splitlines()]
    hexl = [ln for ln in hexl if re.fullmatch(r'[0-9a-f]{2,64}', ln)]
    return bytes.fromhex(''.join(hexl))


def offsets():
    off = [0] * 26
    for ln in range(4, 25):
        off[ln + 1] = off[ln] + ln * (1 << NDBITS[ln])
    return off


def alias_hazards(raw):
    """Return the NUL positions p for which raw + NUL is (p+1)-periodic -- the necessary
    condition for the cyrius 6.6.4 lexer to intern the literal onto overlapping storage.
    An empty list means the literal cannot mis-alias."""
    lp = raw + b'\0'
    slen = len(raw)
    bad = []
    p = raw.find(b'\0')
    while p >= 0:
        d = p + 1
        if lp[d:slen + 1] == lp[0:slen + 1 - d]:
            bad.append(p)
        p = raw.find(b'\0', p + 1)
    return bad


def lit(raw):
    return ''.join(chr(b) if 0x20 <= b <= 0x7e and b not in (0x22, 0x5c) else '\\x%02x' % b
                   for b in raw)


def emit(data):
    off = offsets()
    fnv = fnv1a64(data)
    nd = bytes(NDBITS[4:])
    if b'\0' in nd:
        raise ValueError('NDBITS literal would contain a NUL byte')
    o = []
    w = o.append
    w('# === sankoch -- Brotli static dictionary (GENERATED, do not hand-edit) ===')
    w('#')
    w('# RFC 7932 Appendix A "Static Dictionary Data": %d bytes.' % len(data))
    w('#   sha256    %s' % DICT_SHA256)
    w('#   CRC-32    0x%08x (the value RFC 7932 Appendix A states)' % zlib.crc32(data))
    w('#   xxHash32  0x%08x (seed 0)' % xxh32(data))
    w('#   FNV-1a-64 0x%016x' % fnv)
    w('# Provenance: RFC 7932 Appendix A; byte-identical to google/brotli v1.2.0')
    w('#   c/common/dictionary.bin (MIT -- see docs/sources/brotli/LICENSE.brotli).')
    w('#')
    w('# Regenerate: %s' % REGEN)
    w('# CI regenerates this file and fails if the committed copy differs.')
    w('#')
    w('# String-interning check (cyrius 6.6.4): the dictionary holds %d NUL bytes; the generator'
      % data.count(0))
    w('# proved that for every NUL position p the literal + terminator is NOT (p+1)-periodic, so')
    w('# the lexer cannot intern it onto overlapping storage. Every other literal in sankoch is')
    w('# NUL-free by rule.')
    w('#')
    w('# FREESTANDING: no stdlib, no heap, no syscalls, no includes -- string literals, integer')
    w('# arithmetic and load8 only. A consumer that reads these bytes should run')
    w('# _brotli_dict_verify() once (a compiler that mis-addresses a literal is not hypothetical:')
    w('# cyrius 6.6.3 read >= 64 KB literals from their 2nd byte).')
    w('#')
    w('# Module code GPL-3.0-only; dictionary data MIT (google/brotli, docs/sources/brotli/LICENSE.brotli),')
    w('# as published in RFC 7932 Appendix A.')
    w('#')
    w('# SPDX-License-Identifier: GPL-3.0-only AND MIT')
    w('')
    w("# Size / CRC-32 accessors: diagnostics for tests (DCE drops them from consumers).")
    w('fn _brotli_dict_size() { return %d; }' % len(data))
    w('fn _brotli_dict_crc32() { return 0x%08x; }' % zlib.crc32(data))
    w('fn _brotli_dict_fnv1a() { return 0x%016x; }' % fnv)
    w('')
    w('# RFC 7932 section 8 NDBITS[len] (log2 of the word count per length), len 0..24.')
    w('fn _brotli_dict_ndbits(len) {')
    w('    if (len < 4) { return 0; }')
    w('    if (len > 24) { return 0; }')
    w('    return load8("%s" + len - 4);' % ''.join('\\x%02x' % b for b in nd))
    w('}')
    w('')
    w('# RFC 7932 section 8 DOFFSET[len]: start of the length-len words in the data, len 4..24.')
    w('fn _brotli_dict_offset(len) {')
    w('    if (len < 4) { return 0; }')
    w('    if (len > 24) { return 0; }')
    for ln in range(4, 24):
        w('    if (len == %d) { return %d; }' % (ln, off[ln]))
    w('    return %d;' % off[24])
    w('}')
    w('')
    w('# Address of the contiguous %d dictionary bytes (one literal; NUL-terminated after).' % len(data))
    w('# The literal line carries #skip-lint: cyrlint caps lines at 120 columns.')
    w('fn _brotli_dict_data() { return "%s"; } #skip-lint' % lit(data))
    w('')
    w('# 1 when the %d bytes at p hash to _brotli_dict_fnv1a(), else 0.' % len(data))
    w('fn _brotli_dict_verify(p) {')
    w('    var h = 0xcbf29ce484222325;')
    w('    var i = 0;')
    w('    while (i < %d) {' % len(data))
    w('        h = (h ^ load8(p + i)) * 0x100000001b3;')
    w('        i = i + 1;')
    w('    }')
    w('    if (h == _brotli_dict_fnv1a()) { return 1; }')
    w('    return 0;')
    w('}')
    return '\n'.join(o) + '\n'


def main(argv):
    if len(argv) != 2:
        sys.stderr.write(__doc__)
        return 2
    src, out = argv
    raw = open(src, 'rb').read()
    try:
        data = raw if len(raw) == DICT_LEN else from_rfc_text(raw.decode('ascii', 'replace'))
    except ValueError as e:
        sys.stderr.write('refusing: %s: %s\n' % (src, e))
        return 1
    if len(data) != DICT_LEN:
        sys.stderr.write('refusing: %d bytes, expected %d\n' % (len(data), DICT_LEN))
        return 1
    if hashlib.sha256(data).hexdigest() != DICT_SHA256 or zlib.crc32(data) != DICT_CRC32:
        sys.stderr.write('refusing: sha256/CRC-32 mismatch -- not the RFC 7932 dictionary\n')
        return 1
    if offsets()[25] != DICT_LEN:
        sys.stderr.write('refusing: NDBITS table does not sum to the dictionary length\n')
        return 1
    # Self-test the alias check on the literal that failed in the field (a 22-byte all-NUL
    # chunk: 1-periodic) and on a NUL-free literal, before trusting its verdict.
    if not alias_hazards(b'\0' * 22) or alias_hazards(b'timedownlifeleft'):
        sys.stderr.write('refusing: interning alias self-test failed\n')
        return 1
    bad = alias_hazards(data)
    if bad:
        sys.stderr.write('refusing: literal is (p+1)-periodic at NUL positions %s -- the cyrius '
                         'string-interning bug could alias it\n' % bad[:8])
        return 1
    try:
        text = emit(data)
    except ValueError as e:
        sys.stderr.write('refusing: %s\n' % e)
        return 1
    d = os.path.dirname(os.path.abspath(out))
    fd, tmp = tempfile.mkstemp(prefix='.brotli_dict.', dir=d)
    try:
        with os.fdopen(fd, 'w', encoding='ascii', newline='\n') as f:
            f.write(text)
        os.chmod(tmp, 0o644)
        os.replace(tmp, out)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
