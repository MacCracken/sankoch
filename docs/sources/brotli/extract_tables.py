#!/usr/bin/env python3
"""Mechanically extract every constant table a Brotli (RFC 7932) decoder needs
from google/brotli v1.2.0 sources, cross-check each against RFC 7932 wherever
the RFC states the table, and emit tables.txt.

stdlib only.  Run from anywhere:  python3 extract_tables.py [--src DIR]
Inputs  : DIR (default: src/ next to this script, not committed) holding a google/brotli v1.2.0
          checkout plus rfc7932.txt -- fetch recipe and sha256 pins in README.md;
          probe/enough_results.tsv (committed)
Outputs : tables.txt next to this script (+ PASS/FAIL lines on stdout; exit 1 on any FAIL)

tables.txt format, one block per table:
    # <NAME>  len=<N>  crc32=<8 hex>  sum=<decimal>  source=<file>
    # <free-text description of layout>
    <v0>,<v1>,...,<vN-1>
crc32 is zlib.crc32 of the ASCII text of the value line (no newline); it lets
a Cyrius port verify a transcription by re-joining its own values.
"""
import os
import re
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
if len(sys.argv) == 3 and sys.argv[1] == "--src":
    SRC = os.path.abspath(sys.argv[2])
elif len(sys.argv) != 1:
    sys.exit("usage: extract_tables.py [--src DIR]")
if not os.path.isfile(os.path.join(SRC, "rfc7932.txt")):
    sys.exit("extract_tables.py: %s has no rfc7932.txt; see README.md for the inputs" % SRC)
RESULTS = []          # (name, ok, detail)
TABLES = []           # (name, values, source, description)


def rd(path, mode="r"):
    with open(os.path.join(SRC, path), mode) as f:
        return f.read()


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def emit(name, values, source, desc):
    TABLES.append((name, list(values), source, desc))


# ----------------------------------------------------------------- C parsing
def strip_c_comments(s):
    s = re.sub(r"/\*.*?\*/", " ", s, flags=re.S)
    s = re.sub(r"//[^\n]*", " ", s)
    return s


def c_array_body(text, name):
    """Return the text between the braces of `name[...] = { ... };`."""
    t = strip_c_comments(text)
    m = re.search(r"\b" + re.escape(name) + r"\s*(?:\[[^\]]*\])?\s*=\s*\{", t)
    if not m:
        raise SystemExit("array %s not found" % name)
    i = m.end()
    depth = 1
    j = i
    while depth:
        if t[j] == "{":
            depth += 1
        elif t[j] == "}":
            depth -= 1
        j += 1
    return t[i:j - 1]


def c_ints(body, enums=None):
    enums = enums or {}
    out = []
    for tok in re.findall(r"(?:-\s*)?(?:0[xX][0-9a-fA-F]+|\d+)|[A-Za-z_]\w*", body):
        tok = tok.replace(" ", "")
        if re.match(r"^-?(0[xX][0-9a-fA-F]+|\d+)$", tok):
            out.append(int(tok, 0))
        elif tok in enums:
            out.append(enums[tok])
        else:
            raise SystemExit("unknown token %r" % tok)
    return out


def c_string_bytes(lit_concat):
    """Decode concatenated C string literals (with escapes) to bytes."""
    out = bytearray()
    for lit in re.findall(r'"((?:[^"\\]|\\.)*)"', lit_concat, flags=re.S):
        i = 0
        while i < len(lit):
            ch = lit[i]
            if ch != "\\":
                out += ch.encode("latin-1")
                i += 1
                continue
            i += 1
            e = lit[i]
            if e in "01234567":
                j = i
                while j < len(lit) and j < i + 3 and lit[j] in "01234567":
                    j += 1
                out.append(int(lit[i:j], 8))
                i = j
            elif e == "x":
                j = i + 1
                while j < len(lit) and lit[j] in "0123456789abcdefABCDEF":
                    j += 1
                out.append(int(lit[i + 1:j], 16) & 0xFF)
                i = j
            else:
                out.append({"n": 10, "t": 9, "r": 13, '"': 34, "'": 39,
                            "\\": 92, "0": 0}[e])
                i += 1
    return bytes(out)


# --------------------------------------------------------------- RFC parsing
def rfc_lines():
    keep = []
    for ln in rd("rfc7932.txt").splitlines():
        ln = ln.replace("\f", "")
        if re.match(r"^RFC 7932\s", ln) or re.match(r"^Alakuijala & Szabadka", ln):
            continue
        keep.append(ln)
    return keep


RFC = rfc_lines()
RFC_TEXT = "\n".join(RFC)


def rfc_between(start_pat, end_pat, start_at=0):
    s = None
    for i in range(start_at, len(RFC)):
        if s is None and re.search(start_pat, RFC[i]):
            s = i
        elif s is not None and re.search(end_pat, RFC[i]):
            return RFC[s:i]
    raise SystemExit("RFC region %r..%r not found" % (start_pat, end_pat))


def rfc_c_string(lit):
    return c_string_bytes(lit)


# ======================================================================
# 1. Block count (block length) prefix code: 26 (offset, nbits)
# ======================================================================
body = c_array_body(rd("c/common/constants.c"), "_kBrotliPrefixCodeRanges")
v = c_ints(body)
blk = [(v[2 * i], v[2 * i + 1]) for i in range(len(v) // 2)]
check("block_count_code: 26 entries in constants.c", len(blk) == 26)
region = rfc_between(r"symbols of the block count code alphabet", r"The first block-switch command")
rfc_blk = {}
for ln in region:
    for m in re.finditer(r"(\d+)\s+(\d+)\s+(\d+)(?:\.\.(\d+)|,(\d+))?", ln):
        code, bits, lo = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hi = int(m.group(4) or m.group(5) or lo)
        rfc_blk[code] = (lo, bits, hi)
ok = len(rfc_blk) == 26 and all(
    rfc_blk[i][0] == blk[i][0] and rfc_blk[i][1] == blk[i][1]
    and rfc_blk[i][2] == blk[i][0] + (1 << blk[i][1]) - 1 for i in range(26))
check("block_count_code vs RFC 7932 s6 table (offset, extra bits, max)", ok)
emit("BLOCK_LEN_OFFSET", [b[0] for b in blk], "c/common/constants.c _kBrotliPrefixCodeRanges",
     "block count code 0..25 -> base value (block count = offset + read(nbits))")
emit("BLOCK_LEN_NBITS", [b[1] for b in blk], "c/common/constants.c _kBrotliPrefixCodeRanges",
     "block count code 0..25 -> number of extra bits")

# ======================================================================
# 2/3. Insert-length and copy-length codes (24 each)
# ======================================================================
pc = rd("c/dec/prefix.c")
ins_bits = c_ints(c_array_body(pc, "kInsertLengthExtraBits"))
cpy_bits = c_ints(c_array_body(pc, "kCopyLengthExtraBits"))
cell_pos = c_ints(c_array_body(pc, "kCellPos"))
ins_off = [0]
cpy_off = [2]
for i in range(23):
    ins_off.append(ins_off[-1] + (1 << ins_bits[i]))
    cpy_off.append(cpy_off[-1] + (1 << cpy_bits[i]))


def parse_len_table(start, end):
    reg = rfc_between(start, end)
    t = {}
    for ln in reg:
        for m in re.finditer(r"(\d+)\s+(\d+)\s+(\d+)(?:\.\.(\d+)|,(\d+))?", ln):
            code, bits, lo = int(m.group(1)), int(m.group(2)), int(m.group(3))
            hi = int(m.group(4) or m.group(5) or lo)
            t[code] = (lo, bits, hi)
    return t


rfc_ins = parse_len_table(r"symbols of the insert length code alphabet", r"symbols of the copy length code alphabet")
rfc_cpy = parse_len_table(r"symbols of the copy length code alphabet", r"To convert an insert-and-copy length code")
for nm, offs, bits, rt in (("insert", ins_off, ins_bits, rfc_ins), ("copy", cpy_off, cpy_bits, rfc_cpy)):
    ok = len(rt) == 24 and all(rt[i] == (offs[i], bits[i], offs[i] + (1 << bits[i]) - 1) for i in range(24))
    check("%s_length_code vs RFC 7932 s5 table (24 codes)" % nm, ok,
          "" if ok else str([(i, rt.get(i), offs[i], bits[i]) for i in range(24)]))
emit("INSERT_LEN_OFFSET", ins_off, "c/dec/prefix.c (derived from kInsertLengthExtraBits)",
     "insert length code 0..23 -> base insert length")
emit("INSERT_LEN_NBITS", ins_bits, "c/dec/prefix.c kInsertLengthExtraBits",
     "insert length code 0..23 -> extra bits")
emit("COPY_LEN_OFFSET", cpy_off, "c/dec/prefix.c (derived from kCopyLengthExtraBits)",
     "copy length code 0..23 -> base copy length")
emit("COPY_LEN_NBITS", cpy_bits, "c/dec/prefix.c kCopyLengthExtraBits",
     "copy length code 0..23 -> extra bits")

# ======================================================================
# 4. Insert&copy command LUT: 704 symbols x 6 fields
# ======================================================================
lut = c_ints(c_array_body(rd("c/dec/prefix_inc.h"), "kCmdLut"))
check("kCmdLut: 704*6 values in prefix_inc.h", len(lut) == 704 * 6)
cmd = [tuple(lut[i * 6:i * 6 + 6]) for i in range(704)]
# (a) regenerate with prefix.c BrotliDecoderInitCmdLut logic (independent code path)
gen = []
for sym in range(704):
    ci = sym >> 6
    cp = cell_pos[ci]
    cc = ((cp << 3) & 0x18) + (sym & 7)
    ic = (cp & 0x18) + ((sym >> 3) & 7)
    ctx = 3 if cpy_off[cc] > 4 else cpy_off[cc] - 2
    gen.append((ins_bits[ic], cpy_bits[cc], -1 if ci >= 2 else 0, ctx, ins_off[ic], cpy_off[cc]))
check("kCmdLut == prefix.c BrotliDecoderInitCmdLut regeneration", gen == cmd)
# (b) derive from the RFC 7932 s5 cell table + s7.2 distance context rule
cells = []
reg = rfc_between(r"To convert an insert-and-copy length code to an insert", r"First, look up the cell")
# RFC grid: rows are insert code ranges, columns copy code ranges
row_ins = None
for ln in reg:
    m = re.match(r"^\s*(\d+)\.\.(\d+)\s*\|(.*)$", ln)
    if m:
        row_ins = int(m.group(1))
        for col, cm in enumerate(re.finditer(r"(\d+)\.\.(\d+)", m.group(3))):
            cells.append((int(cm.group(1)), row_ins, col * 8))
check("RFC s5 insert-and-copy cell grid parsed (11 cells)", len(cells) == 11, str(cells))
rfc_cmd = [None] * 704
for base, ib, cb in cells:
    for k in range(64):
        s = base + k
        ic = ib + ((s >> 3) & 7)
        cc = cb + (s & 7)
        clen_min = rfc_cpy[cc][0]
        ctx = {2: 0, 3: 1, 4: 2}.get(clen_min, 3)
        rfc_cmd[s] = (rfc_ins[ic][1], rfc_cpy[cc][1], 0 if s < 128 else -1, ctx, rfc_ins[ic][0], clen_min)
check("kCmdLut vs RFC 7932 s5 cell table + s7.2 distance context (704 symbols)", rfc_cmd == cmd)
emit("CMD_INSERT_NBITS", [c[0] for c in cmd], "c/dec/prefix_inc.h kCmdLut.insert_len_extra_bits",
     "command symbol 0..703 -> insert extra bits")
emit("CMD_COPY_NBITS", [c[1] for c in cmd], "c/dec/prefix_inc.h kCmdLut.copy_len_extra_bits",
     "command symbol 0..703 -> copy extra bits")
emit("CMD_IMPLICIT_DIST0", [1 if c[2] == 0 else 0 for c in cmd], "c/dec/prefix_inc.h kCmdLut.distance_code",
     "command symbol 0..703 -> 1 if distance is implicit code 0 (symbols 0..127), else 0 (C stores 0 / -1)")
emit("CMD_DIST_CONTEXT", [c[3] for c in cmd], "c/dec/prefix_inc.h kCmdLut.context",
     "command symbol 0..703 -> distance context id 0..3 (copy len 2,3,4,>=5)")
emit("CMD_INSERT_OFFSET", [c[4] for c in cmd], "c/dec/prefix_inc.h kCmdLut.insert_len_offset",
     "command symbol 0..703 -> base insert length")
emit("CMD_COPY_OFFSET", [c[5] for c in cmd], "c/dec/prefix_inc.h kCmdLut.copy_len_offset",
     "command symbol 0..703 -> base copy length")
emit("CMD_INSERT_CODE",
     [(ib + (((s - base) >> 3) & 7)) for s in range(704) for (base, ib, cb) in cells if base <= s < base + 64],
     "RFC 7932 s5 cell grid", "command symbol 0..703 -> insert length code 0..23")
emit("CMD_COPY_CODE",
     [(cb + ((s - base) & 7)) for s in range(704) for (base, ib, cb) in cells if base <= s < base + 64],
     "RFC 7932 s5 cell grid", "command symbol 0..703 -> copy length code 0..23")

# ======================================================================
# 5. Distance short codes (16): ring index back from last, delta
# ======================================================================
short = []
for code in range(16):
    # re-implementation of decode.c TakeDistanceFromRingBuffer (lines 1690-1715)
    if code <= 3:
        back, delta = code, 0
    else:
        base = code - 4 if code < 10 else code - 10
        idx_delta = 3 if code < 10 else 2
        back = 3 - idx_delta          # idx+3 == last (back 0), idx+2 == second-to-last
        delta = ((0x605142 >> (4 * base)) & 0xF) - 3
    short.append((back, delta))
reg = rfc_between(r"The first 16 distance symbols are special", r"The ring buffer of the four last distances")
names = {"last": 0, "second-to-last": 1, "third-to-last": 2, "fourth-to-last": 3}
rfc_short = {}
for ln in reg:
    m = re.match(r"^\s*(\d+):\s*([a-z-]+) distance(?:\s*([-+])\s*(\d+))?\s*$", ln)
    if m:
        d = int(m.group(4) or 0) * (-1 if m.group(3) == "-" else 1)
        rfc_short[int(m.group(1))] = (names[m.group(2)], d)
check("distance short codes (16) decode.c vs RFC 7932 s4", len(rfc_short) == 16 and
      all(rfc_short[i] == short[i] for i in range(16)))
emit("DIST_SHORT_RING_BACK", [s[0] for s in short], "c/dec/decode.c TakeDistanceFromRingBuffer",
     "distance code 0..15 -> which past distance (0=last,1=2nd-to-last,2=3rd,3=4th)")
emit("DIST_SHORT_DELTA", [s[1] for s in short], "c/dec/decode.c TakeDistanceFromRingBuffer (0x605142)",
     "distance code 0..15 -> signed delta added to that past distance")
emit("DIST_RING_INIT", [16, 15, 11, 4], "c/dec/state.c BrotliDecoderStateInit dist_rb[0..3], dist_rb_idx=0",
     "initial ring (slot order); last=4, 2nd=11, 3rd=15, 4th=16")
m = re.search(r"initialized by the\s+values (\d+), (\d+), (\d+), and (\d+)", RFC_TEXT)
check("distance ring init 16,15,11,4 vs RFC 7932 s4",
      m and [int(x) for x in m.groups()] == [16, 15, 11, 4])

# ======================================================================
# 6. Code length code order (18) and static code for code-length code lengths
# ======================================================================
dec = rd("c/dec/decode.c")
order = c_ints(c_array_body(dec, "kCodeLengthCodeOrder"))
m = re.search(r"in the order:\s*([\d,\s]+?)\.\s", RFC_TEXT)
rfc_order = [int(x) for x in re.findall(r"\d+", m.group(1))]
check("code length code order (18) decode.c vs RFC 7932 s3.5", order == rfc_order and len(order) == 18)
emit("CODE_LENGTH_CODE_ORDER", order, "c/dec/decode.c kCodeLengthCodeOrder",
     "order in which the 18 code-length-code lengths are transmitted")

plen = c_ints(c_array_body(dec, "kCodeLengthPrefixLength"))
pval = c_ints(c_array_body(dec, "kCodeLengthPrefixValue"))
reg = rfc_between(r"compressed with the following variable-length code", r"We can now define the format of the complex")
rfc_code = {}
for ln in reg:
    mm = re.match(r"^\s*(\d)\s+([01]{2,4})\s*$", ln)
    if mm:
        rfc_code[int(mm.group(1))] = mm.group(2)
# RFC codes "as they appear in the compressed data, parsed right to left":
# the rightmost char is the first bit read (LSB of the 4-bit peek).
lut_len = [None] * 16
lut_val = [None] * 16
for sym, bits in rfc_code.items():
    n = len(bits)
    first_bits = int(bits, 2)   # string right-to-left == integer LSB-first
    for hi in range(1 << (4 - n)):
        k = first_bits | (hi << n)
        lut_len[k] = n
        lut_val[k] = sym
check("static code-length-code prefix LUT (16) decode.c vs RFC 7932 s3.5 table",
      len(rfc_code) == 6 and lut_len == plen and lut_val == pval)
emit("CLCL_PREFIX_BITS", plen, "c/dec/decode.c kCodeLengthPrefixLength",
     "peek 4 bits (LSB-first) -> number of bits of the code-length-code length symbol")
emit("CLCL_PREFIX_VALUE", pval, "c/dec/decode.c kCodeLengthPrefixValue",
     "peek 4 bits (LSB-first) -> code-length-code length 0..5")

# ======================================================================
# 7. Context LUT: 4 modes x (256 p1 + 256 p2) = 2048
# ======================================================================
ctx = c_ints(c_array_body(rd("c/common/context.c"), "_kBrotliContextLookupTable"))
check("context LUT has 2048 entries", len(ctx) == 2048)


def rfc_lut(name, nxt):
    reg = rfc_between(r"^\s*%s :=" % name, nxt)
    vals = [int(x) for x in re.findall(r"\d+", " ".join(reg[1:]))]
    return vals


lut0 = rfc_lut("Lut0", r"^\s*Lut1 :=")
lut1 = rfc_lut("Lut1", r"^\s*Lut2 :=")
lut2 = rfc_lut("Lut2", r"The lengths and the CRC-32 check values")
crcs = dict(re.findall(r"(Lut\d)\s+256\s+(0x[0-9a-f]+)", RFC_TEXT))
for nm, t in (("Lut0", lut0), ("Lut1", lut1), ("Lut2", lut2)):
    check("RFC %s length 256 and CRC-32 %s" % (nm, crcs.get(nm)),
          len(t) == 256 and zlib.crc32(bytes(t)) == int(crcs[nm], 16))
expect = []
expect += [p & 0x3F for p in range(256)] + [0] * 256            # LSB6
expect += [p >> 2 for p in range(256)] + [0] * 256              # MSB6
expect += lut0 + lut1                                           # UTF8
expect += [x << 3 for x in lut2] + lut2                         # SIGNED
check("context LUT (2048) context.c vs RFC 7932 s7.1 formulas/Lut0-2", expect == ctx)
for mode, nm in enumerate(("LSB6", "MSB6", "UTF8", "SIGNED")):
    emit("CONTEXT_LUT_" + nm, ctx[mode * 512:(mode + 1) * 512], "c/common/context.c _kBrotliContextLookupTable",
         "mode %d: [0..255]=f(p1), [256..511]=g(p2); context id = lut[p1] | lut[256+p2]" % mode)
emit("RFC_LUT0", lut0, "RFC 7932 s7.1", "UTF8 p1 table")
emit("RFC_LUT1", lut1, "RFC 7932 s7.1", "UTF8 p2 table")
emit("RFC_LUT2", lut2, "RFC 7932 s7.1", "SIGNED table (p1 uses <<3)")

# ======================================================================
# 8. Static dictionary: NDBITS, DOFFSET, data checksum
# ======================================================================
dc = rd("c/common/dictionary.c")
m = re.search(r"size_bits_by_length\s*\*/\s*\{([^}]*)\}", dc)
ndbits = c_ints(m.group(1))[:25]
m = re.search(r"offsets_by_length\s*\*/\s*\{([^}]*)\}", dc)
doff = c_ints(m.group(1))[:26]
m = re.search(r"NDBITS :=\s*([\d,\s]+)", RFC_TEXT)
rfc_nd = [int(x) for x in re.findall(r"\d+", m.group(1))]
check("dictionary NDBITS[0..24] dictionary.c vs RFC 7932 Appendix A", rfc_nd == ndbits)
calc = [0]
for L in range(25):
    nw = 0 if L < 4 else (1 << rfc_nd[L])
    calc.append(calc[-1] + L * nw)
check("dictionary DOFFSET[0..24] + DICTSIZE dictionary.c vs RFC 7932 s8 recursion (=122784)",
      calc == doff and calc[25] == 122784, str(calc))
dict_bin = rd("c/common/dictionary.bin", "rb")
m = re.search(r"length is 122,784 bytes and the CRC-32 of the byte sequence is\s+(0x[0-9a-f]+)", RFC_TEXT)
check("dictionary.bin length 122784 and CRC-32 == RFC Appendix A %s" % m.group(1),
      len(dict_bin) == 122784 and zlib.crc32(dict_bin) == int(m.group(1), 16))
reg = rfc_between(r"^Appendix A\.", r"The number of words for each length is given")
hexs = "".join(ln.strip() for ln in reg if re.match(r"^\s+[0-9a-f]{2,64}\s*$", ln))
check("RFC Appendix A hex dump == dictionary.bin byte-for-byte", bytes.fromhex(hexs) == dict_bin)
emit("DICT_NDBITS", ndbits, "c/common/dictionary.c size_bits_by_length", "length 0..24 -> log2(#words)")
emit("DICT_DOFFSET", doff, "c/common/dictionary.c offsets_by_length",
     "length 0..24 -> byte offset in DICT; entry 25 = DICTSIZE 122784")
import hashlib
emit("DICT_DATA_DIGEST", [len(dict_bin), zlib.crc32(dict_bin)] + list(hashlib.sha256(dict_bin).digest()),
     "c/common/dictionary.bin",
     "not the data: [length, crc32 (decimal), sha256 bytes x32]; data = RFC Appendix A = dictionary.bin")

# ======================================================================
# 9. Transforms (121): prefix id / type / suffix id + prefix-suffix pool
# ======================================================================
tc = rd("c/common/transform.c")
th = rd("c/common/transform.h")
enums = {}
for nm, val in re.findall(r"(BROTLI_TRANSFORM_\w+)\s*=\s*(\d+)", th):
    enums[nm] = int(val)
tdata = c_ints(c_array_body(tc, "kTransformsData"), enums)
check("kTransformsData = 121 triplets", len(tdata) == 363)
pmap = c_ints(c_array_body(tc, "kPrefixSuffixMap"))
m = re.search(r"kPrefixSuffix\[(\d+)\]\s*=\s*((?:\s*\"(?:[^\"\\]|\\.)*\"\s*(?:/\*.*?\*/)?)+);", tc, flags=re.S)
declared = int(m.group(1))
pool = c_string_bytes(strip_c_comments(m.group(2))) + b"\x00"   # implicit trailing NUL
check("kPrefixSuffix pool length == declared %d (incl. implicit NUL)" % declared, len(pool) == declared)


def pool_str(i):
    off = pmap[i]
    n = pool[off]
    return pool[off + 1:off + 1 + n]


# RFC Appendix B
rfc_tr = {}
for ln in RFC[RFC.index(next(l for l in RFC if l.startswith("Appendix B."))):]:
    mm = re.match(r'^\s*(\d+)\s+("(?:[^"\\]|\\.)*")\s+(\w+)\s+("(?:[^"\\]|\\.)*")\s*$', ln)
    if mm:
        rfc_tr[int(mm.group(1))] = (rfc_c_string(mm.group(2)), mm.group(3), rfc_c_string(mm.group(4)))
    if ln.startswith("Appendix C."):
        break
check("RFC Appendix B has 121 transforms", len(rfc_tr) == 121)


def c_type_to_rfc(t):
    if t == 0:
        return "Identity"
    if 1 <= t <= 9:
        return "OmitLast%d" % t
    if t == 10:
        return "FermentFirst"
    if t == 11:
        return "FermentAll"
    if 12 <= t <= 20:
        return "OmitFirst%d" % (t - 11)
    return "C-only-%d" % t


def rfc_type_code(name):     # RFC Appendix B serialization numbering
    if name == "Identity":
        return 0
    if name == "FermentFirst":
        return 1
    if name == "FermentAll":
        return 2
    if name.startswith("OmitFirst"):
        return 2 + int(name[9:])
    if name.startswith("OmitLast"):
        return 11 + int(name[8:])
    raise SystemExit(name)


ok = True
bad = []
ser = bytearray()
for i in range(121):
    p, t, s = tdata[3 * i], tdata[3 * i + 1], tdata[3 * i + 2]
    mine = (pool_str(p), c_type_to_rfc(t), pool_str(s))
    if mine != rfc_tr[i]:
        ok = False
        bad.append((i, mine, rfc_tr[i]))
    rp, rt, rs = rfc_tr[i]
    ser += rp + b"\x00" + bytes([rfc_type_code(rt)]) + rs + b"\x00"
check("121 transforms transform.c (pool+map+triplets) vs RFC 7932 Appendix B", ok, str(bad[:3]))
m = re.search(r"length of that sequence is (\d+)\s+bytes, and the CRC-32 is (0x[0-9a-f]+)", RFC_TEXT)
check("RFC Appendix B serialization length %s / CRC-32 %s" % m.groups(),
      len(ser) == int(m.group(1)) and zlib.crc32(bytes(ser)) == int(m.group(2), 16),
      "len=%d crc=%08x" % (len(ser), zlib.crc32(bytes(ser))))
cutoff = c_ints(re.search(r"kBrotliTransforms = \{.*?\{([^}]*)\}\s*\};", strip_c_comments(tc), flags=re.S).group(1))
cut_ok = all(tdata[3 * cutoff[k] + 1] == k and pool_str(tdata[3 * cutoff[k]]) == b""
             and pool_str(tdata[3 * cutoff[k] + 2]) == b"" for k in range(10))
check("cutOffTransforms {0,12,27,23,42,63,56,48,59,64} == ['' OmitLast_k ''] transforms", cut_ok)
emit("TRANSFORM_PREFIX_ID", [tdata[3 * i] for i in range(121)], "c/common/transform.c kTransformsData",
     "transform 0..120 -> index into PREFIX_SUFFIX_MAP for prefix")
emit("TRANSFORM_TYPE", [tdata[3 * i + 1] for i in range(121)], "c/common/transform.c kTransformsData",
     "transform 0..120 -> C type: 0 Identity, 1..9 OmitLast1..9, 10 UppercaseFirst(=FermentFirst), "
     "11 UppercaseAll(=FermentAll), 12..20 OmitFirst1..9")
emit("TRANSFORM_SUFFIX_ID", [tdata[3 * i + 2] for i in range(121)], "c/common/transform.c kTransformsData",
     "transform 0..120 -> index into PREFIX_SUFFIX_MAP for suffix")
emit("PREFIX_SUFFIX_MAP", pmap, "c/common/transform.c kPrefixSuffixMap",
     "id 0..49 -> offset into PREFIX_SUFFIX_POOL of a length-prefixed string")
emit("PREFIX_SUFFIX_POOL", list(pool), "c/common/transform.c kPrefixSuffix",
     "217 bytes: sequence of [len][bytes...]; final byte 0 = empty string (id 49)")
emit("TRANSFORM_CUTOFF", cutoff, "c/common/transform.c kBrotliTransforms.cutOffTransforms",
     "k=0..9 -> transform index of ['' OmitLast_k ''] (k=0: identity)")

# ======================================================================
# 10. WBITS header code (15 values) and NBLTYPES/NTREES var-len uint8
# ======================================================================


def c_decode_wbits(bits):   # bits: LSB-first int; re-implements decode.c DecodeWindowBits (145-179)
    pos = 0

    def take(n):
        nonlocal pos
        v = (bits >> pos) & ((1 << n) - 1)
        pos += n
        return v
    if take(1) == 0:
        return 16, pos
    n = take(3)
    if n != 0:
        return 17 + n, pos
    n = take(3)
    if n == 1:
        return "invalid", pos
    if n != 0:
        return 8 + n, pos
    return 17, pos


reg = rfc_between(r"1\.\.7 bits: WBITS", r"Note that bit pattern 0010001 is invalid")
rfc_wb = {}
for ln in reg:
    mm = re.match(r"^\s*(\d+)\s+([01]{1,7})\s*$", ln)
    if mm:
        rfc_wb[int(mm.group(1))] = mm.group(2)
ok = len(rfc_wb) == 15
for val, pat in rfc_wb.items():
    got = c_decode_wbits(int(pat, 2))
    ok = ok and got == (val, len(pat))
ok = ok and c_decode_wbits(int("0010001", 2))[0] == "invalid"
check("WBITS code (15 values + invalid 0010001) DecodeWindowBits vs RFC 7932 s9.1", ok)
emit("WBITS_BY_PATTERN7", [c_decode_wbits(p)[0] if c_decode_wbits(p)[0] != "invalid" else 0 for p in range(128)],
     "c/dec/decode.c DecodeWindowBits", "7-bit peek (LSB-first) -> WBITS (0 = invalid / large-window escape)")
emit("WBITS_BITS_BY_PATTERN7", [c_decode_wbits(p)[1] for p in range(128)],
     "c/dec/decode.c DecodeWindowBits", "7-bit peek (LSB-first) -> bits consumed (1,4 or 7)")

reg = rfc_between(r"1\.\.11 bits: NBLTYPESL, number of literal block types", r"Prefix code over the block type code alphabet for literal")
ok = True
cnt = 0
for ln in reg:
    mm = re.match(r"^\s*(\d+)(?:\.\.(\d+))?\s+(x*)([01]+)\s*$", ln)
    if not mm:
        continue
    lo, hi = int(mm.group(1)), int(mm.group(2) or mm.group(1))
    nx, fixed = len(mm.group(3)), mm.group(4)
    for xv in range(1 << nx):
        pattern = (xv << len(fixed)) | int(fixed, 2)
        # re-implement decode.c DecodeVarLenUint8 (192-233) then +1
        p = 0

        def tk(n):
            global p
            r = (pattern >> p) & ((1 << n) - 1)
            p += n
            return r
        if tk(1) == 0:
            val = 0
        else:
            b = tk(3)
            val = 1 if b == 0 else (1 << b) + tk(b)
        cnt += 1
        ok = ok and (val + 1 == lo + xv) and p == nx + len(fixed) and val + 1 <= hi
check("NBLTYPES/NTREES var-len code (256 values) DecodeVarLenUint8 vs RFC 7932 s9.2", ok and cnt == 256)

# ======================================================================
# 11. Huffman table sizing (8-bit root)
# ======================================================================
hh = rd("c/dec/huffman.h")
c26 = int(re.search(r"BROTLI_HUFFMAN_MAX_SIZE_26 (\d+)", hh).group(1))
c258 = int(re.search(r"BROTLI_HUFFMAN_MAX_SIZE_258 (\d+)", hh).group(1))
c272 = int(re.search(r"BROTLI_HUFFMAN_MAX_SIZE_272 (\d+)", hh).group(1))
java = c_ints(c_array_body(rd("java/org/brotli/dec/Decode.java"), "MAX_HUFFMAN_TABLE_SIZE"))
check("Java MAX_HUFFMAN_TABLE_SIZE has 23 entries", len(java) == 23)
enough = {}
ep = os.path.join(HERE, "probe", "enough_results.tsv")
if os.path.exists(ep):
    for ln in open(ep):
        a, b = ln.split()
        enough[int(a)] = int(b)
    check("C BROTLI_HUFFMAN_MAX_SIZE_26/258/272 (%d/%d/%d) == zlib enough(26/258/272, root 8, max 15)"
          % (c26, c258, c272), enough.get(26) == c26 and enough.get(258) == c258 and enough.get(272) == c272)
    ok = all(enough.get(32 * i) == java[i] for i in range(1, 23))
    check("Java MAX_HUFFMAN_TABLE_SIZE[i] == enough(32*i, 8, 15) for i=1..22 "
          "(i>=16 via guard-relaxed enough)", ok,
          str([(32 * i, java[i], enough.get(32 * i)) for i in range(1, 23) if enough.get(32 * i) != java[i]]))
    ok = all(v <= k + 376 for k, v in enough.items())
    check("state.c tree-group bound alphabet_size_limit+376 >= enough(n) for all probed n", ok)
else:
    check("probe/enough_results.tsv present", False)
emit("MAX_HUFFMAN_TABLE_SIZE_BY_32", java, "java/org/brotli/dec/Decode.java MAX_HUFFMAN_TABLE_SIZE",
     "index (alphabet_size_limit+31)>>5 -> max root(8)+2nd-level table entries for one prefix code")
emit("MAX_HUFFMAN_TABLE_SIZE_C", [26, c26, 258, c258, 272, c272],
     "c/dec/huffman.h", "pairs (alphabet size, max table entries): block count / block type / context map")
if enough:
    emit("ENOUGH_ROOT8_MAX15", [x for k in sorted(enough) for x in (k, enough[k])], "probe/enough_results.tsv",
         "pairs (n symbols, max table entries) from zlib examples/enough.c")

# ======================================================================
# misc scalar constants
# ======================================================================
ch = rd("c/common/constants.h")


def cdef(name, text=ch):
    return int(re.search(r"#define %s (\w+)" % name, text).group(1).rstrip("uUlL"), 0)


emit("SCALARS",
     [cdef("BROTLI_NUM_LITERAL_SYMBOLS"), cdef("BROTLI_NUM_COMMAND_SYMBOLS"), cdef("BROTLI_NUM_BLOCK_LEN_SYMBOLS"),
      cdef("BROTLI_CONTEXT_MAP_MAX_RLE"), cdef("BROTLI_MAX_NUMBER_OF_BLOCK_TYPES"),
      cdef("BROTLI_NUM_DISTANCE_SHORT_CODES"), cdef("BROTLI_MAX_NPOSTFIX"), cdef("BROTLI_MAX_NDIRECT"),
      cdef("BROTLI_MAX_DISTANCE_BITS"), cdef("BROTLI_WINDOW_GAP"), cdef("BROTLI_MAX_ALLOWED_DISTANCE"),
      cdef("BROTLI_INITIAL_REPEATED_CODE_LENGTH"), 16777216],
     "c/common/constants.h",
     "NUM_LITERAL_SYMBOLS, NUM_COMMAND_SYMBOLS, NUM_BLOCK_LEN_SYMBOLS, CONTEXT_MAP_MAX_RLE, MAX_BLOCK_TYPES, "
     "NUM_DISTANCE_SHORT_CODES, MAX_NPOSTFIX, MAX_NDIRECT, MAX_DISTANCE_BITS, WINDOW_GAP, MAX_ALLOWED_DISTANCE, "
     "INITIAL_REPEATED_CODE_LENGTH, BLOCK_SIZE_CAP(1<<24)")
check("distance alphabet max 16+120+(24<<4) == 520 == enough probe key",
      16 + cdef("BROTLI_MAX_NDIRECT") + (cdef("BROTLI_MAX_DISTANCE_BITS") << (cdef("BROTLI_MAX_NPOSTFIX") + 1)) == 520)

# ----------------------------------------------------------------- output
with open(os.path.join(HERE, "tables.txt"), "w") as f:
    f.write("# Brotli (RFC 7932) decoder tables, extracted from google/brotli v1.2.0 by extract_tables.py\n")
    f.write("# crc32 = zlib.crc32(ASCII of the value line); sum = sum of values\n\n")
    for name, vals, source, desc in TABLES:
        line = ",".join(str(x) for x in vals)
        f.write("# %s  len=%d  crc32=%08x  sum=%d  source=%s\n" % (
            name, len(vals), zlib.crc32(line.encode()), sum(vals), source))
        f.write("# %s\n%s\n\n" % (desc, line))

fails = 0
for name, ok, detail in RESULTS:
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, ("  [" + detail + "]") if (detail and not ok) else ""))
    fails += 0 if ok else 1
print("%d checks, %d failed; %d tables written to tables.txt" % (len(RESULTS), fails, len(TABLES)))
sys.exit(1 if fails else 0)
