#!/usr/bin/env python3
"""nul-literal-gate.py — fail on any Cyrius string literal that decodes to a NUL byte.

cycc (6.6.4) interns string literals by content, and a periodic literal holding a NUL can be
aliased onto storage the next literal overwrites: wrong bytes, no diagnostic (upstream cyrius issue
2026-09-16-sankoch-string-literal-interning-aliases-overlapping-storage). sankoch's rule
(docs/architecture/004-string-literal-nul-rule.md): no string literal contains NUL, written raw or
as an escape (\\0, \\x00, \\u0000, \\u{0}). The one exemption is src/brotli_dict.cyr, which is
generated, and whose generator (scripts/brotli_dict2cyr.py) proves it cannot alias.

Escapes are decoded as cycc's lexer decodes them; `#` comments (outside literals) and character
literals are skipped. A raw NUL byte anywhere in a scanned file also fails.

Usage: scripts/nul-literal-gate.py [FILE...]
  Default: src/*.cyr programs/*.cyr tests/tcyr/*.tcyr tests/bcyr/*.bcyr fuzz/*.fcyr, plus the
  probes scripts/profile-link-gate.sh generated under build/profile-link-gate/ when present.
Exit: 0 clean, 1 violation(s), 2 usage / read error.

SPDX-License-Identifier: GPL-3.0-only
"""
import glob
import os
import sys

EXEMPT = {"src/brotli_dict.cyr"}
DEFAULT = ["src/*.cyr", "programs/*.cyr", "tests/tcyr/*.tcyr", "tests/bcyr/*.bcyr", "fuzz/*.fcyr",
           "build/profile-link-gate/*/*.cyr"]
SIMPLE = {110: 10, 114: 13, 116: 9, 48: 0, 92: 92, 34: 34, 39: 39, 97: 7, 98: 8, 102: 12, 118: 11}


def hexv(c):
    if 48 <= c <= 57:
        return c - 48
    if 97 <= c <= 102:
        return c - 87
    if 65 <= c <= 70:
        return c - 55
    return 0


def at(buf, p):
    return buf[p] if p < len(buf) else 0


def literals(buf):
    """Yield (line, decoded bytes) for every string literal."""
    p, n, line = 0, len(buf), 1
    while p < n:
        c = buf[p]
        if c == 10:
            line += 1
            p += 1
        elif c == 35 and not buf.startswith(b"#assert", p):      # comment to end of line
            while p < n and buf[p] != 10:
                p += 1
        elif c == 39:                                             # character literal
            p += 1
            p += 2 if at(buf, p) == 92 else 1
            if at(buf, p) == 39:
                p += 1
        elif c == 34:                                             # string literal
            start, out = line, bytearray()
            p += 1
            while p < n and buf[p] != 34:
                sc = buf[p]
                p += 1
                if sc != 92:
                    line += sc == 10
                    out.append(sc)
                    continue
                ec = at(buf, p)
                p += 1
                if ec in SIMPLE:
                    out.append(SIMPLE[ec])
                elif ec == 120:                                   # \xNN
                    out.append((hexv(at(buf, p)) << 4) | hexv(at(buf, p + 1)))
                    p += 2
                elif ec == 117:                                   # \uNNNN or \u{...}
                    cp = 0
                    if at(buf, p) == 123:
                        p += 1
                        while p < n and buf[p] != 125:
                            cp = (cp << 4) | hexv(buf[p])
                            p += 1
                        p += 1
                    else:
                        for k in range(4):
                            cp = (cp << 4) | hexv(at(buf, p + k))
                        p += 4
                    out += chr(min(cp, 0x10FFFF)).encode("utf-8", "surrogatepass")
                else:
                    line += ec == 10
                    out.append(ec)
            p += 1
            yield start, bytes(out)
        else:
            p += 1


def main(argv):
    files = argv or sorted(f for g in DEFAULT for f in glob.glob(g))
    if not files:
        print("nul-literal-gate: no files to scan (run from the repo root)", file=sys.stderr)
        return 2
    bad = nlit = 0
    for f in files:
        rel = os.path.relpath(f)
        try:
            buf = open(f, "rb").read()
        except OSError as e:
            print("nul-literal-gate: %s" % e, file=sys.stderr)
            return 2
        if rel in EXEMPT:
            continue
        if b"\x00" in buf:
            print("FAIL %s: raw NUL byte at offset %d" % (rel, buf.index(b"\x00")))
            bad += 1
        for line, data in literals(buf):
            nlit += 1
            if b"\x00" in data:
                print("FAIL %s:%d: string literal decodes to %d NUL byte(s): %r"
                      % (rel, line, data.count(b"\x00"), data[:40]))
                bad += 1
    if bad:
        print("nul-literal-gate: %d violation(s). Build the bytes at runtime (store8) or use hex text;"
              " see docs/architecture/004-string-literal-nul-rule.md" % bad)
        return 1
    print("nul-literal-gate: %d literals in %d files, none contains NUL (exempt: %s)"
          % (nlit, len(files), ", ".join(sorted(EXEMPT))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
