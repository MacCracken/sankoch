#!/usr/bin/env python3
"""brotli-craft.py -- rebuild the hand-built Brotli streams committed under tests/data/brotli/.

    python3 scripts/brotli-craft.py            # write every stream
    python3 scripts/brotli-craft.py --check    # rebuild in memory; exit 1 if a committed stream differs
    python3 scripts/brotli-craft.py --list     # one line per stream: set/name, bytes, what it exercises

Dev-time only, stdlib Python; CI never runs it. The small/ CLI streams additionally need the
reference `brotli` 1.2.0 on PATH. This script only BUILDS streams: verdicts, output lengths and
CRC-32s, error classes and decoder stages are decided by scripts/brotli-manifest.py, which runs
every committed stream through `brotli -d` and scripts/brotli_ref_decoder.py (two oracles that
must agree) and writes tests/data/brotli/MANIFEST.tsv. Run it after this script.

Sets (both research craft sets merged, byte-identical to their 2026-09-16 output):
  crafted/  stdlib bit writer + mini-encoder: framing, metadata, uncompressed, simple / complex prefix
            codes, context modes and maps, distances, lengths vs MLEN, dictionary references (70
            streams); plus the command-loop rows (block switching in all three categories with explicit
            type-code choices, per-type context modes, per-meta-block reset; truncation and MLEN
            edges) and the dictionary rows (the first and the largest dictionary address of every word
            length; dictionary references through short distance codes 4..15, which must leave the
            distance ring intact). Every block-switching or ring row names the reference-decoder
            mutants it must kill (scripts/brotli_ref_decoder.py MUTANTS); the build fails if one
            survives.
            Hot path: the adversarial inverse-move-to-front rows (adv_imtf_*, work amplification) and a one-tree
            literal type switching mid-insert to a UTF8 type (the trivial-context fast path).
  probe/    the research probe set (34 streams; their libbrotlidec verdicts were probe-time only).
  small/    `brotli` 1.2.0 CLI output of synthetic inputs generated here (mixed_*, bswitch_records_*) and
            of the first 32,768 B of google/alice29.txt.compressed (alice29_32k.q5w16).
            The other small/ streams are CLI output of inputs kept outside the repo; not rebuilt.

SPDX-License-Identifier: GPL-3.0-only
"""
import importlib.util
import os
import subprocess
import sys

sys.dont_write_bytecode = True     # dev tool: no __pycache__ next to the committed scripts

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
CORPUS = os.path.join(ROOT, 'tests', 'data', 'brotli')


def _load_ref():
    spec = importlib.util.spec_from_file_location(
        'brotli_ref_decoder', os.path.join(ROOT, 'scripts', 'brotli_ref_decoder.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ref = _load_ref()
INS_BASE, INS_EXTRA, CPY_BASE, CPY_EXTRA = ref.INS_BASE, ref.INS_EXTRA, ref.CPY_BASE, ref.CPY_EXTRA
CELLS, CL_ORDER, CTX, NDBITS, DOFFSET, DICT = ref.CELLS, ref.CL_ORDER, ref.CTX, ref.NDBITS, ref.DOFFSET, ref.DICT
BL_BASE, BL_EXTRA = ref.BL_BASE, ref.BL_EXTRA
transform_word = ref.transform_word

STREAMS = []    # (set, name, why, builder) ; builder() -> bytes


def stream(set_, name, why):
    def deco(fn):
        STREAMS.append((set_, name, why, fn))
        return fn
    return deco


# =====================================================================================================
# crafted/ -- bit writer + mini-encoder (research craft set)
# =====================================================================================================
class BW:
    def __init__(self):
        self.bits = []

    def w(self, v, n):
        for i in range(n):
            self.bits.append((v >> i) & 1)

    def huff(self, code, length):  # prefix codes are packed MSB-first
        for i in reversed(range(length)):
            self.bits.append((code >> i) & 1)

    def pad(self, fill=0):
        while len(self.bits) % 8:
            self.bits.append(fill)

    def raw(self, data):
        assert len(self.bits) % 8 == 0
        for b in data:
            self.w(b, 8)

    def tobytes(self, fill=0):
        b = list(self.bits)
        while len(b) % 8:
            b.append(fill)
        return bytes(sum(b[i + j] << j for j in range(8)) for i in range(0, len(b), 8))


def w_wbits(bw, wb):
    if wb == 'largewin':            # 1 000 001 : large-window marker (NOT RFC 7932)
        bw.w(1, 1); bw.w(0, 3); bw.w(1, 3)
    elif wb == 16:
        bw.w(0, 1)
    elif wb >= 18:
        bw.w(1, 1); bw.w(wb - 17, 3)
    elif wb == 17:
        bw.w(1, 1); bw.w(0, 3); bw.w(0, 3)
    else:
        assert 10 <= wb <= 15
        bw.w(1, 1); bw.w(0, 3); bw.w(wb - 8, 3)


def w_mlen(bw, mlen, nibbles=None):
    v = mlen - 1
    n = max(4, (v.bit_length() + 3) // 4)
    if nibbles:
        n = nibbles
    bw.w(n - 4, 2)
    for i in range(n):
        bw.w((v >> (4 * i)) & 15, 4)


def mb_last_empty(bw):
    bw.w(1, 1); bw.w(1, 1)


def mb_metadata(bw, payload, islast=False, reserved=0, nbytes=None, lenbytes=None, pad_fill=0):
    bw.w(1 if islast else 0, 1)
    if islast:
        bw.w(0, 1)
    bw.w(3, 2)
    bw.w(reserved, 1)
    L = len(payload)
    if nbytes is None:
        nbytes = 0 if L == 0 else max(1, ((L - 1).bit_length() + 7) // 8)
    bw.w(nbytes, 2)
    if lenbytes is None:
        lenbytes = [((L - 1) >> (8 * i)) & 255 for i in range(nbytes)]
    for b in lenbytes:
        bw.w(b, 8)
    bw.pad(pad_fill)
    bw.raw(payload)


def mb_uncompressed(bw, data, nibbles=None, pad_fill=0):
    bw.w(0, 1)
    w_mlen(bw, len(data), nibbles)
    bw.w(1, 1)
    bw.pad(pad_fill)
    bw.raw(data)


def w_var256(bw, n):
    if n == 1:
        bw.w(0, 1)
    elif n == 2:
        bw.w(1, 1); bw.w(0, 3)
    else:
        k = (n - 1).bit_length() - 1
        bw.w(1, 1); bw.w(k, 3); bw.w(n - 1 - (1 << k), k)


def canonical(lengths):
    """lengths: dict sym->len (>0). returns dict sym->(code,len)."""
    tab = {}
    code = 0
    prev = 0
    for s, l in sorted(lengths.items(), key=lambda x: (x[1], x[0])):
        code <<= (l - prev)
        prev = l
        tab[s] = (code, l)
        code += 1
    return tab


def balanced_lengths(syms):
    syms = sorted(syms)
    k = len(syms)
    assert k >= 2
    n = k.bit_length() - 1
    if k == 1 << n:
        return {s: n for s in syms}
    deep = 2 * (k - (1 << n))
    out = {}
    for i, s in enumerate(syms):
        out[s] = n if i < k - deep else n + 1
    return out


def w_simple(bw, syms, alpha, tsel=0):
    bw.w(1, 2)
    bw.w(len(syms) - 1, 2)
    nb = (alpha - 1).bit_length()
    for s in syms:
        bw.w(s, nb)
    if len(syms) == 1:
        return {syms[0]: (0, 0)}
    if len(syms) == 2:
        L = [1, 1]
    elif len(syms) == 3:
        L = [1, 2, 2]
    else:
        bw.w(tsel, 1)
        L = [1, 2, 3, 3] if tsel else [2, 2, 2, 2]
    if len(set(syms)) != len(syms):
        return None  # hostile: duplicate symbols
    return canonical(dict(zip(syms, L)))


CLC_VLC = {0: [0, 0], 1: [1, 1, 1, 0], 2: [1, 1, 0], 3: [0, 1], 4: [1, 0], 5: [1, 1, 1, 1]}


def _rle_zeros(reps):
    out = []
    if reps == 11:
        out.append((0, 0, 0)); reps -= 1
    if reps < 3:
        return out + [(0, 0, 0)] * reps
    reps -= 3
    tmp = []
    while True:
        tmp.append((17, reps & 7, 3))
        reps >>= 3
        if reps == 0:
            break
        reps -= 1
    return out + tmp[::-1]


def _rle_value(prev, v, reps):
    out = []
    if prev != v:
        out.append((v, 0, 0)); reps -= 1
    if reps == 7:
        out.append((v, 0, 0)); reps -= 1
    if reps < 3:
        return out + [(v, 0, 0)] * reps
    reps -= 3
    tmp = []
    while True:
        tmp.append((16, reps & 3, 2))
        reps >>= 2
        if reps == 0:
            break
        reps -= 1
    return out + tmp[::-1]


def w_complex(bw, lengths, alpha, rle=False, hskip=0, clc_override=None, to_alpha_end=False, clc_one_len=3):
    """lengths: dict sym->len. Writes a complex prefix code. Returns canonical table (for valid codes)."""
    L = [lengths.get(i, 0) for i in range(alpha)]
    last = max([i for i in range(alpha) if L[i]] + [-1])
    end = alpha if to_alpha_end else last + 1
    seq = []
    if not rle:
        seq = [(L[i], 0, 0) for i in range(end)]
    else:
        i = 0
        prev = 8
        while i < end:
            j = i
            while j < end and L[j] == L[i]:
                j += 1
            run = j - i
            if L[i] == 0:
                seq += _rle_zeros(run)
            else:
                seq += _rle_value(prev, L[i], run)
                prev = L[i]
            i = j
    used = sorted(set(s for s, _, _ in seq))
    if clc_override is not None:
        clc = clc_override
    elif len(used) == 1:
        clc = {used[0]: clc_one_len}
    else:
        clc = balanced_lengths(used)
    bw.w(hskip, 2)
    space = 32
    for i in range(hskip, 18):
        l = clc.get(CL_ORDER[i], 0)
        for b in CLC_VLC[l]:
            bw.w(b, 1)
        if l:
            space -= 32 >> l
            if space <= 0:
                break
    nz = [s for s in clc if clc[s]]
    if clc_override is not None and any(s not in clc for s, _, _ in seq):
        return None  # hostile clc: symbol data unrepresentable; caller pads with zero bytes
    if len(nz) == 1:
        ctab = {nz[0]: (0, 0)}
    else:
        ctab = canonical({s: l for s, l in clc.items() if l})
    for s, e, n in seq:
        c, l = ctab[s]
        bw.huff(c, l)
        bw.w(e, n)
    return canonical({s: l for s, l in lengths.items() if l})


def auto_code(bw, syms, alpha, style=None):
    syms = sorted(set(syms)) or [0]
    style = style or {}
    if style.get('lengths') is not None:
        return w_complex(bw, style['lengths'], alpha, rle=style.get('rle', False), hskip=style.get('hskip', 0),
                         to_alpha_end=style.get('to_alpha_end', False))
    if len(syms) <= 4 and not style.get('complex'):
        order = style.get('order', syms)
        return w_simple(bw, order, alpha, style.get('tsel', 0))
    if len(syms) == 1:
        syms = syms + [syms[0] + 1 if syms[0] + 1 < alpha else syms[0] - 1]
    return w_complex(bw, balanced_lengths(syms), alpha, rle=style.get('rle', False), hskip=style.get('hskip', 0))


def put(bw, tab, s):
    c, l = tab[s]
    bw.huff(c, l)


def len_code(n, base, extra):
    for c in reversed(range(len(base))):
        if base[c] <= n < base[c] + (1 << extra[c]):
            return c, n - base[c]
    raise ValueError(n)


def cmd_symbol(ic, cc, dz):
    for cell, (io, co, z) in enumerate(CELLS):
        if z == dz and io <= ic < io + 8 and co <= cc < co + 8:
            return (cell << 6) | ((ic - io) << 3) | (cc - co)
    raise ValueError((ic, cc, dz))


def dist_code(d, np, nd):
    if 1 <= d <= nd:
        return d + 15, 0, 0
    mask = (1 << np) - 1
    for dc in range(16 + nd, 16 + nd + (48 << np)):
        x = dc - nd - 16
        ndb = 1 + (x >> (np + 1))
        h = x >> np
        lc = x & mask
        off = ((2 + (h & 1)) << ndb) - 4
        r = d - nd - 1 - lc
        if r < 0 or (r & mask):
            continue
        extra = (r >> np) - off
        if 0 <= extra < (1 << ndb):
            return dc, extra, ndb
    raise ValueError(d)


def mb_compressed(bw, out, cmds, *, wbits, islast=False, npostfix=0, ndirect=0, cmode=0, ntrees_l=1,
                  cmap=None, lit_style=None, cmd_style=None, dist_style=None, mlen=None, dist_rb=None,
                  cmap_writer=None):
    """cmds: list of dicts {lits: bytes, copy: int, dist: int|None, dz: bool, dcode: int|None,
    dict: (len, idx, tid)|None}. `out` (bytearray) is the plaintext so far; it is extended in place.
    dist_rb: 4-list ring (shared across meta-blocks), mutated."""
    wsize = (1 << wbits) - 16
    if dist_rb is None:
        dist_rb = [16, 15, 11, 4]
    cmap = cmap or [0] * 64
    # ---- pass 1: simulate
    sim = bytearray(out)
    rb = list(dist_rb)
    lit_syms = [set() for _ in range(ntrees_l)]
    cmd_syms, dist_syms = set(), set()
    plan = []
    for c in cmds:
        lits = c.get('lits', b'')
        trees = []
        for b in lits:
            p1 = sim[-1] if len(sim) >= 1 else 0
            p2 = sim[-2] if len(sim) >= 2 else 0
            ctx = CTX[cmode * 512 + p1] | CTX[cmode * 512 + 256 + p2]
            t = cmap[ctx]
            lit_syms[t].add(b)
            trees.append(t)
            sim.append(b)
        ic, ie = len_code(len(lits), INS_BASE, INS_EXTRA)
        entry = {'lits': lits, 'trees': trees, 'ic': ic, 'ie': ie}
        if c.get('dict'):
            L, idx, tid = c['dict']
            clen = L
            maxd = min(len(sim), wsize)
            dist = maxd + 1 + (idx | (tid << NDBITS[L]))
        else:
            clen = c.get('copy', 4)
            dist = c.get('dist')
        cc, ce = len_code(clen, CPY_BASE, CPY_EXTRA)
        entry.update(cc=cc, ce=ce)
        dz = bool(c.get('dz'))
        entry['dz'] = dz
        entry['end'] = c.get('end', False)  # plaintext ends after lits: no distance read
        if not entry['end']:
            if dz:
                dist = rb[3]
                dcode = 0
                dex = (0, 0)
            elif c.get('dcode') is not None:
                dcode = c['dcode']
                dex = (0, 0)
                if dcode < 4:
                    dist = rb[3 - dcode]
                elif dcode < 16:
                    base = rb[3] if dcode < 10 else rb[2]
                    k = dcode - 4 if dcode < 10 else dcode - 10
                    dist = base - ((k >> 1) + 1) if k % 2 == 0 else base + ((k >> 1) + 1)
                else:
                    raise ValueError('dcode override only for short codes')
            else:
                dcode, e, n = dist_code(dist, npostfix, ndirect)
                dex = (e, n)
            entry.update(dcode=dcode, dex=dex)
            dist_syms.add(dcode)
            maxd = min(len(sim), wsize)
            if dist > maxd:
                if 4 <= clen <= 24 and not c.get('no_sim'):
                    wid = dist - maxd - 1
                    nb = NDBITS[clen]
                    w = DICT[DOFFSET[clen] + (wid & ((1 << nb) - 1)) * clen:][:clen]
                    tid = wid >> nb
                    if tid < 121:
                        sim += transform_word(w, tid)
            elif dist > 0 and not c.get('no_sim'):
                if dcode != 0:
                    rb = rb[1:] + [dist]
                for j in range(clen):
                    sim.append(sim[len(sim) - dist])
        entry['cmd'] = cmd_symbol(ic, cc, dz)
        cmd_syms.add(entry['cmd'])
        plan.append(entry)
    produced = len(sim) - len(out)
    if mlen is None:
        mlen = produced
    # ---- header
    bw.w(1 if islast else 0, 1)
    if islast:
        bw.w(0, 1)
    w_mlen(bw, mlen)
    if not islast:
        bw.w(0, 1)
    for _ in range(3):
        w_var256(bw, 1)             # NBLTYPES L/I/D = 1
    bw.w(npostfix, 2)
    bw.w(ndirect >> npostfix, 4)
    bw.w(cmode, 2)
    w_var256(bw, ntrees_l)
    if ntrees_l >= 2:
        if cmap_writer:
            cmap_writer(bw)
        else:
            bw.w(0, 1)              # RLEMAX = 0
            used = sorted(set(cmap))
            tab = auto_code(bw, used, ntrees_l, {'complex': len(used) > 4})
            for v in cmap:
                put(bw, tab, v)
            bw.w(0, 1)              # IMTF = 0
    w_var256(bw, 1)                 # NTREESD = 1
    lit_tabs = []
    for t in range(ntrees_l):
        st = lit_style[t] if isinstance(lit_style, list) else lit_style
        lit_tabs.append(auto_code(bw, lit_syms[t], 256, st))
    cmd_tab = auto_code(bw, cmd_syms, 704, cmd_style)
    dalpha = 16 + ndirect + (48 << npostfix)
    dist_tab = auto_code(bw, dist_syms, dalpha, dist_style)
    # ---- data
    for e in plan:
        put(bw, cmd_tab, e['cmd'])
        bw.w(e['ie'], INS_EXTRA[e['ic']])
        bw.w(e['ce'], CPY_EXTRA[e['cc']])
        for b, t in zip(e['lits'], e['trees']):
            put(bw, lit_tabs[t], b)
        if not e['end'] and not e['dz']:
            put(bw, dist_tab, e['dcode'])
            bw.w(*e['dex'])
    out[:] = sim
    dist_rb[:] = rb
    return mlen


def textish(n, seed=7, alphabet=b'etaoin shrdlucmfwypvbgkjqxz'):
    x = seed
    o = bytearray()
    for _ in range(n):
        x = (x * 1103515245 + 12345) & 0x7fffffff
        o.append(alphabet[(x >> 16) % len(alphabet)])
    return bytes(o)


def crafted(name, why):
    return stream('crafted', name, why)


# ---- stream framing ---------------------------------------------------------------------------------
for _wb in [10, 11, 12, 13, 14, 15, 16, 17, 18, 24]:
    def _mk(wb=_wb):
        bw = BW(); w_wbits(bw, wb); mb_last_empty(bw); return bw.tobytes()
    crafted('empty_wbits%d' % _wb, 'ISLAST+ISLASTEMPTY only, WBITS=%d header form' % _wb)(_mk)


@crafted('bad_wbits_largewin_marker', 'large-window header + uncompressed "LW" (RFC 7932 rejects; the CLI accepts)')
def _():
    bw = BW(); w_wbits(bw, 'largewin'); bw.w(0, 1); bw.w(16, 6); mb_uncompressed(bw, b'LW'); mb_last_empty(bw)
    return bw.tobytes()


@crafted('bad_trailing_padding_bits', 'non-zero bits after ISLASTEMPTY in final byte')
def _():
    bw = BW(); w_wbits(bw, 16); mb_last_empty(bw); return bw.tobytes(fill=1)


@crafted('bad_no_last_block', 'uncompressed non-last meta-block then EOF (no ISLAST)')
def _():
    bw = BW(); w_wbits(bw, 16); mb_uncompressed(bw, b'abc'); return bw.tobytes()


# ---- metadata -----------------------------------------------------------------------------------------
@crafted('metadata_1byte_then_empty', 'metadata meta-block (MSKIPBYTES=1, 5-byte payload) + last-empty')
def _():
    bw = BW(); w_wbits(bw, 16); mb_metadata(bw, b'\xde\xad\xbe\xef\x00'); mb_last_empty(bw); return bw.tobytes()


@crafted('metadata_empty_then_data', 'empty metadata (MSKIPBYTES=0) + uncompressed + last-empty')
def _():
    bw = BW(); w_wbits(bw, 22); mb_metadata(bw, b''); mb_uncompressed(bw, b'xyz'); mb_last_empty(bw)
    return bw.tobytes()


@crafted('metadata_2byte_len_300', 'metadata MSKIPBYTES=2 (300-byte payload) between two uncompressed blocks')
def _():
    bw = BW(); w_wbits(bw, 16); mb_uncompressed(bw, b'ab'); mb_metadata(bw, bytes(range(256)) + b'm' * 44)
    mb_uncompressed(bw, b'cd'); mb_last_empty(bw); return bw.tobytes()


@crafted('metadata_is_last', 'ISLAST=1, ISLASTEMPTY=0, MNIBBLES=0 metadata ends the stream')
def _():
    bw = BW(); w_wbits(bw, 16); mb_uncompressed(bw, b'Q'); mb_metadata(bw, b'tail', islast=True)
    return bw.tobytes()


@crafted('bad_metadata_reserved_bit', 'reserved bit after MNIBBLES=0 set')
def _():
    bw = BW(); w_wbits(bw, 16); mb_metadata(bw, b'x', reserved=1); mb_last_empty(bw); return bw.tobytes()


@crafted('bad_metadata_exuberant_byte', 'MSKIPBYTES=2 with most-significant length byte 0')
def _():
    bw = BW(); w_wbits(bw, 16); mb_metadata(bw, b'x' * 5, nbytes=2, lenbytes=[4, 0]); mb_last_empty(bw)
    return bw.tobytes()


@crafted('bad_metadata_padding', 'non-zero padding bits before metadata payload')
def _():
    bw = BW(); w_wbits(bw, 16); mb_metadata(bw, b'x', pad_fill=1); mb_last_empty(bw); return bw.tobytes()


@crafted('bad_metadata_truncated', 'metadata length 200 but only 10 payload bytes present')
def _():
    bw = BW(); w_wbits(bw, 16); mb_metadata(bw, b'x' * 200); return bw.tobytes()[:16]


# ---- uncompressed -----------------------------------------------------------------------------------
@crafted('uncompressed_then_empty', 'uncompressed meta-block + last-empty')
def _():
    bw = BW(); w_wbits(bw, 10); mb_uncompressed(bw, b'Hello, RFC 7932!'); mb_last_empty(bw)
    return bw.tobytes()


@crafted('uncompressed_5nibble_70000', 'uncompressed meta-block MLEN=70000 (MNIBBLES=5)')
def _():
    d = textish(70000, 3)
    bw = BW(); w_wbits(bw, 16); mb_uncompressed(bw, d); mb_last_empty(bw); return bw.tobytes()


@crafted('bad_uncompressed_padding', 'non-zero padding after ISUNCOMPRESSED bit')
def _():
    bw = BW(); w_wbits(bw, 16); mb_uncompressed(bw, b'abc', pad_fill=1); mb_last_empty(bw); return bw.tobytes()


@crafted('bad_exuberant_nibble_mlen', 'MNIBBLES=5 with most-significant nibble 0 (MLEN=5)')
def _():
    bw = BW(); w_wbits(bw, 16); mb_uncompressed(bw, b'abcde', nibbles=5); mb_last_empty(bw); return bw.tobytes()


@crafted('bad_uncompressed_truncated', 'uncompressed MLEN=100 with 20 bytes present')
def _():
    bw = BW(); w_wbits(bw, 16); mb_uncompressed(bw, b'z' * 100); return bw.tobytes()[:24]


# ---- simple prefix codes ------------------------------------------------------------------------------
def _simple_lit(n, tsel=0, order=None):
    alph = b'ABCD'[:n]
    text = bytes(alph[(i * 7 + i // 3) % n] for i in range(40))
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    st = {'tsel': tsel}
    if order:
        st['order'] = order
    mb_compressed(bw, out, [{'lits': text, 'copy': 4, 'end': True}], wbits=16, islast=True, lit_style=st)
    return bw.tobytes()


crafted('simple_nsym1_literal', 'literal code NSYM=1 (0-bit symbols); cmd+dist NSYM=1')(lambda: _simple_lit(1))
crafted('simple_nsym2_literal', 'literal code NSYM=2')(lambda: _simple_lit(2))
crafted('simple_nsym3_literal', 'literal code NSYM=3, symbols listed out of order (D,A,B -> lengths 1,2,2)')(
    lambda: _simple_lit(3, order=[67, 65, 66]))
crafted('simple_nsym4_tsel0', 'literal code NSYM=4 tree-select 0 (2,2,2,2)')(lambda: _simple_lit(4, 0, [68, 66, 65, 67]))
crafted('simple_nsym4_tsel1', 'literal code NSYM=4 tree-select 1 (1,2,3,3), unsorted listing')(
    lambda: _simple_lit(4, 1, [66, 68, 67, 65]))


@crafted('bad_simple_duplicate_symbol', 'simple prefix code NSYM=2 lists the same symbol twice')
def _():
    bw = BW(); w_wbits(bw, 16)
    bw.w(1, 1); bw.w(0, 1); w_mlen(bw, 4); w_var256(bw, 1); w_var256(bw, 1); w_var256(bw, 1)
    bw.w(0, 2); bw.w(0, 4); bw.w(0, 2); w_var256(bw, 1); w_var256(bw, 1)
    w_simple(bw, [65, 65], 256)
    return bw.tobytes() + bytes(16)


@crafted('bad_simple_symbol_ge_alphabet', 'insert&copy simple code symbol 1000 >= 704')
def _():
    bw = BW(); w_wbits(bw, 16)
    bw.w(1, 1); bw.w(0, 1); w_mlen(bw, 4); w_var256(bw, 1); w_var256(bw, 1); w_var256(bw, 1)
    bw.w(0, 2); bw.w(0, 4); bw.w(0, 2); w_var256(bw, 1); w_var256(bw, 1)
    w_simple(bw, [65], 256)
    w_simple(bw, [1000], 704)
    return bw.tobytes() + bytes(16)


# ---- complex prefix codes -----------------------------------------------------------------------------
def _complex_block(lit_writer, text=None, extra=64):
    """one last compressed meta-block whose literal code is written by lit_writer(bw) (may be hostile)."""
    text = text or textish(64)
    bw = BW(); w_wbits(bw, 16)
    bw.w(1, 1); bw.w(0, 1); w_mlen(bw, len(text))
    for _ in range(3):
        w_var256(bw, 1)
    bw.w(0, 2); bw.w(0, 4); bw.w(0, 2); w_var256(bw, 1); w_var256(bw, 1)
    lit_writer(bw)
    return bw.tobytes() + bytes(extra)


@crafted('complex_balanced_literals', 'complex literal code, 27 symbols, balanced lengths 4/5, no RLE')
def _():
    t = textish(300)
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    mb_compressed(bw, out, [{'lits': t, 'copy': 4, 'end': True}], wbits=16, islast=True)
    return bw.tobytes()


@crafted('complex_rle_16_17', 'complex codes using repeat codes 16 and 17, incl. chained repeats')
def _():
    t = bytes(range(32, 127)) + textish(200, alphabet=bytes(range(32, 127)))
    lens = balanced_lengths(sorted(set(t)))
    bw = BW(); w_wbits(bw, 18); out = bytearray()
    mb_compressed(bw, out, [{'lits': t, 'copy': 4, 'end': True}], wbits=18, islast=True,
                  lit_style={'lengths': lens, 'rle': True})
    return bw.tobytes()


@crafted('complex_hskip3_and_single_clc', 'HSKIP=3 code-length code; all 256 literals length 8 (0-bit clc path)')
def _():
    t = bytes(range(256)) + textish(100)
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    mb_compressed(bw, out, [{'lits': t, 'copy': 4, 'end': True}], wbits=16, islast=True,
                  lit_style={'lengths': {s: 8 for s in range(256)}, 'hskip': 3})
    return bw.tobytes()


@crafted('bad_complex_oversubscribed', 'literal code lengths 1,2,1 (Kraft sum > 1)')
def _():
    return _complex_block(lambda bw: w_complex(bw, {97: 1, 98: 2, 99: 1}, 256, to_alpha_end=True))


@crafted('bad_complex_incomplete', 'literal code lengths 1,2 then zeros (Kraft sum < 1)')
def _():
    return _complex_block(lambda bw: w_complex(bw, {97: 1, 98: 2}, 256, to_alpha_end=True))


@crafted('bad_complex_single_symbol', 'complex code with exactly one non-zero length')
def _():
    return _complex_block(lambda bw: w_complex(bw, {97: 1}, 256, to_alpha_end=True))


@crafted('bad_clc_oversubscribed', 'code-length code lengths (in CL order) 2,1,1 (over-subscribed)')
def _():
    return _complex_block(lambda bw: w_complex(bw, {97: 1, 98: 1}, 256, clc_override={1: 2, 2: 1, 3: 1}))


@crafted('bad_clc_incomplete', 'code-length code with two symbols of length 2 (incomplete)')
def _():
    return _complex_block(lambda bw: w_complex(bw, {97: 1, 98: 1}, 256, clc_override={1: 2, 0: 2}))


@crafted('bad_clc_repeat_past_alphabet', 'repeat code 17 runs past literal alphabet end (250 zeros + run of 10)')
def _():
    def wr(bw):
        clc = {0: 1, 17: 1}
        ctab = canonical(clc)
        bw.w(0, 2)
        space = 32
        for i in range(18):
            l = clc.get(CL_ORDER[i], 0)
            for b in CLC_VLC[l]:
                bw.w(b, 1)
            if l:
                space -= 32 >> l
                if space <= 0:
                    break
        for _ in range(250):
            put(bw, ctab, 0)
        put(bw, ctab, 17); bw.w(7, 3)
    return _complex_block(wr)


# ---- context modes / context maps ---------------------------------------------------------------------
def _ctx_vec(mode, ntrees=3):
    t = bytes(textish(600, 11, b'Brotli context MODES: lsb6/msb6/utf8/signed 0123456789 \xc3\xa9\xe2\x82\xac\n-+'))
    cm = [(c * 5 + c // 7) % ntrees for c in range(64)]
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    mb_compressed(bw, out, [{'lits': t, 'copy': 4, 'end': True}], wbits=16, islast=True, cmode=mode,
                  ntrees_l=ntrees, cmap=cm)
    return bw.tobytes()


for _m, _n in enumerate(['lsb6', 'msb6', 'utf8', 'signed']):
    crafted('ctxmode_%s_3trees' % _n,
            'CMODE=%d, NTREESL=3, non-trivial context map (tree choice depends on the mode)' % _m)(
        lambda m=_m: _ctx_vec(m))


@crafted('bad_cmap_tree_index_out_of_range', 'NTREESL=3, RLEMAX=0: context-map simple code lists symbol 3')
def _():
    def cw(bw):
        bw.w(0, 1)
        w_simple(bw, [0, 3], 3)
    t = textish(64)
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    mb_compressed(bw, out, [{'lits': t, 'copy': 4, 'end': True}], wbits=16, islast=True, ntrees_l=3,
                  cmap=[0] * 64, cmap_writer=cw)
    return bw.tobytes() + bytes(8)


@crafted('bad_cmap_rle_past_end', 'NTREESL=2, RLEMAX=1: 62 explicit zeros then a zero-run of 3 (65 > 64)')
def _():
    def cw(bw):
        bw.w(1, 1); bw.w(0, 4)          # RLEMAX = 1
        tab = w_simple(bw, [0, 1, 2], 3)
        for _ in range(62):
            put(bw, tab, 0)
        put(bw, tab, 1); bw.w(1, 1)     # run of 2 + 1 = 3
        bw.w(0, 1)
    t = textish(64)
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    mb_compressed(bw, out, [{'lits': t, 'copy': 4, 'end': True}], wbits=16, islast=True, ntrees_l=2,
                  cmap=[0] * 64, cmap_writer=cw)
    return bw.tobytes() + bytes(8)


@crafted('cmap_rle_imtf_valid', 'NTREESL=4 context map with RLEMAX=3 runs and IMTF=1')
def _():
    target = ([0] * 20 + [1] * 12 + [2, 3] * 8 + [0] * 16)
    mtf = list(range(256)); enc = []
    for v in target:
        i = mtf.index(v); enc.append(i); mtf.pop(i); mtf.insert(0, v)
    rlemax = 3

    def cw(bw):
        bw.w(1, 1); bw.w(rlemax - 1, 4)
        items = []
        i = 0
        while i < len(enc):
            if enc[i] == 0:
                j = i
                while j < len(enc) and enc[j] == 0:
                    j += 1
                run = j - i
                while run > 0:
                    if run >= 2:
                        k = min(rlemax, run.bit_length() - 1)
                        take = min(run, (1 << k) + (1 << k) - 1)
                        items.append((k, take - (1 << k), k)); run -= take
                    else:
                        items.append((0, 0, 0)); run -= 1
                i = j
            else:
                items.append((enc[i] + rlemax, 0, 0)); i += 1
        syms = sorted(set(s for s, _, _ in items))
        tab = w_complex(bw, balanced_lengths(syms), 4 + rlemax) if len(syms) > 4 else w_simple(bw, syms, 4 + rlemax)
        for s, e, n in items:
            put(bw, tab, s); bw.w(e, n)
        bw.w(1, 1)  # IMTF
    t = textish(700, 5, b'The quick brown fox, 42 JUMPS over... \n')
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    mb_compressed(bw, out, [{'lits': t, 'copy': 4, 'end': True}], wbits=16, islast=True, cmode=0, ntrees_l=4,
                  cmap=target, cmap_writer=cw)
    return bw.tobytes()


# ---- distances ----------------------------------------------------------------------------------------
@crafted('distance_short_codes_all16', 'distance codes 0..15 (ring-buffer relative) plus implicit-zero-distance cells')
def _():
    base = textish(1200, 9)
    cmds = [{'lits': base, 'copy': 5, 'dist': 100}, {'lits': b'', 'copy': 6, 'dist': 200},
            {'lits': b'x', 'copy': 7, 'dist': 300}, {'lits': b'y', 'copy': 8, 'dist': 400}]
    for dc in range(16):
        cmds.append({'lits': b'-', 'copy': 4 + dc % 5, 'dcode': dc})
    cmds.append({'lits': b'z', 'copy': 9, 'dz': True})       # cell 0/1: implicit last distance
    cmds.append({'lits': b'', 'copy': 12, 'dz': True})
    cmds.append({'lits': b'!', 'copy': 4, 'end': True})
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    mb_compressed(bw, out, cmds, wbits=16, islast=True)
    return bw.tobytes()


for _np, _nd in [(1, 30), (2, 60), (3, 120)]:
    def _mk(np=_np, nd=_nd):
        base = textish(211, 13, bytes(range(40, 90)))
        cmds = [{'lits': base, 'copy': 5800, 'dist': 211}]
        for i, d in enumerate([1, 2, 7, nd - 1, nd, nd + 1, nd + 2, nd + 7, 257, 1000, 4095, 4096, 5999, 6010]):
            cmds.append({'lits': bytes([65 + i % 26]), 'copy': 3 + i % 9, 'dist': d})
        cmds.append({'lits': b'.', 'copy': 4, 'end': True})
        bw = BW(); w_wbits(bw, 16); out = bytearray()
        mb_compressed(bw, out, cmds, wbits=16, islast=True, npostfix=np, ndirect=nd)
        return bw.tobytes()
    crafted('npostfix%d_ndirect%d' % (_np, _nd),
            'NPOSTFIX=%d NDIRECT=%d; direct and postfix distance codes incl. boundaries' % (_np, _nd))(_mk)


@crafted('window_edge_wbits10', 'WBITS=10: copy at distance 1008 (= window) ok; distance 1009 len 10 is dictionary word 0')
def _():
    base = textish(1100, 17, bytes(range(33, 120)))
    cmds = [{'lits': base, 'copy': 10, 'dist': 1008}, {'lits': b'', 'copy': 10, 'dist': 1009},
            {'lits': b'#', 'copy': 4, 'end': True}]
    bw = BW(); w_wbits(bw, 10); out = bytearray()
    mb_compressed(bw, out, cmds, wbits=10, islast=True)
    return bw.tobytes()


@crafted('bad_distance_beyond_window_len3', 'distance 6 at output position 5, copy length 3 (not a dictionary length)')
def _():
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    mb_compressed(bw, out, [{'lits': b'abcde', 'copy': 3, 'dist': 6}], wbits=16, islast=True, mlen=8)
    return bw.tobytes()


@crafted('bad_distance_beyond_window_len25', 'distance 6 at output position 5, copy length 25 (> 24)')
def _():
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    mb_compressed(bw, out, [{'lits': b'abcde', 'copy': 25, 'dist': 6}], wbits=16, islast=True, mlen=30)
    return bw.tobytes()


@crafted('bad_distance_wbits10_1009_len3', 'WBITS=10, 1100 bytes out, distance 1009 len 3 (past window, not dict)')
def _():
    base = textish(1100, 17, bytes(range(33, 120)))
    bw = BW(); w_wbits(bw, 10); out = bytearray()
    mb_compressed(bw, out, [{'lits': base, 'copy': 3, 'dist': 1009}], wbits=10, islast=True, mlen=1103)
    return bw.tobytes()


@crafted('bad_distance_zero_short_code', 'last distance 1, then short code 4 (last-1 = 0)')
def _():
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    mb_compressed(bw, out, [{'lits': b'ab', 'copy': 4, 'dist': 1}, {'lits': b'c', 'copy': 4, 'dcode': 4, 'no_sim': True},
                            {'lits': b'd', 'copy': 4, 'end': True}], wbits=16, islast=True, mlen=12)
    return bw.tobytes()


# ---- lengths vs MLEN --------------------------------------------------------------------------------
@crafted('bad_insert_exceeds_mlen', 'MLEN=5 but the command inserts 8 literals')
def _():
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    mb_compressed(bw, out, [{'lits': b'abcdefgh', 'copy': 4, 'end': True}], wbits=16, islast=True, mlen=5)
    return bw.tobytes()


@crafted('bad_copy_exceeds_mlen', 'MLEN=10: 5 literals + copy 8 at distance 1')
def _():
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    mb_compressed(bw, out, [{'lits': b'abcde', 'copy': 8, 'dist': 1}], wbits=16, islast=True, mlen=10)
    return bw.tobytes() + bytes(4)


@crafted('bad_dict_word_exceeds_mlen', 'MLEN=3: dictionary word of length 4')
def _():
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    mb_compressed(bw, out, [{'lits': b'', 'dict': (4, 0, 0)}], wbits=16, islast=True, mlen=3)
    return bw.tobytes() + bytes(4)


@crafted('mlen_5nibbles_copy_70000', 'two literals + copy 70,000 at distance 2: compressed MLEN=70002 (MNIBBLES=5)')
def _():
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    mb_compressed(bw, out, [{'lits': b'ab', 'copy': 70000, 'dist': 2}], wbits=16, islast=True)
    return bw.tobytes()


@crafted('mlen_6nibbles_copy_1mib', 'one literal + copy of 1,048,576 at distance 1: MNIBBLES=6, copy code 23')
def _():
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    mb_compressed(bw, out, [{'lits': b'Z', 'copy': 1 << 20, 'dist': 1}], wbits=16, islast=True)
    return bw.tobytes()


@crafted('bomb_16mib_max_mlen', 'decompression bomb: 13 bytes -> 16,777,216 x "Z" (MLEN = 2^24, the RFC maximum)')
def _():
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    mb_compressed(bw, out, [{'lits': b'Z', 'copy': (1 << 24) - 1, 'dist': 1}], wbits=16, islast=True)
    assert len(out) == 1 << 24
    return bw.tobytes()


@crafted('multiblock_cross_references', 'uncompressed, compressed non-last, compressed last: copies and context span blocks')
def _():
    bw = BW(); w_wbits(bw, 12); out = bytearray()
    first = textish(500, 21)
    mb_uncompressed(bw, first); out += first
    rb = [16, 15, 11, 4]
    mb_compressed(bw, out, [{'lits': b'<<', 'copy': 40, 'dist': 450}, {'lits': b'>>', 'copy': 4, 'end': True}],
                  wbits=12, dist_rb=rb, cmode=2)
    mb_metadata(bw, b'meta')
    mb_compressed(bw, out, [{'lits': b'', 'copy': 30, 'dcode': 0}, {'lits': b'|', 'copy': 16, 'dist': 530},
                            {'lits': b'.', 'copy': 4, 'end': True}], wbits=12, islast=True, dist_rb=rb, cmode=1)
    return bw.tobytes()


# ---- static dictionary + transforms ---------------------------------------------------------------------
@crafted('dict_transform_120_valid', 'dictionary reference, length 4, word 0, transform id 120 (last valid)')
def _():
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    mb_compressed(bw, out, [{'lits': b'', 'dict': (4, 0, 120)}], wbits=16, islast=True)
    return bw.tobytes()


@crafted('bad_dict_transform_121', 'dictionary reference, length 4, word 0, transform id 121 (out of range)')
def _():
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    mb_compressed(bw, out, [{'lits': b'', 'dict': (4, 0, 121)}], wbits=16, islast=True, mlen=20)
    return bw.tobytes() + bytes(4)


@crafted('bad_dict_transform_121_len24', 'dictionary reference, length 24 (NDBITS 5), transform id 121')
def _():
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    mb_compressed(bw, out, [{'lits': b'hello', 'dict': (24, 31, 121)}], wbits=16, islast=True, mlen=60)
    return bw.tobytes() + bytes(4)


@crafted('dict_all_121_transforms_all_lengths', 'one dictionary ref per transform id 0..120, cycling lengths 4..24')
def _():
    cmds = []
    for tid in range(121):
        L = 4 + tid % 21
        nb = NDBITS[L]
        idx = [0, (1 << nb) - 1, (1 << nb) // 2 + tid][tid % 3] % (1 << nb)
        cmds.append({'lits': b'' if tid % 4 else b'~', 'dict': (L, idx, tid)})
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    mb_compressed(bw, out, cmds, wbits=16, islast=True)
    return bw.tobytes()


@crafted('dict_uppercase_utf8_edges', 'UPPERCASE_FIRST/ALL on 2- and 3-byte UTF-8 words, lead bytes past the word end')
def _():
    upfirst = [i for i, t in enumerate(ref.TRANSFORMS) if t[1] == 10]
    upall = [i for i, t in enumerate(ref.TRANSFORMS) if t[1] == 11]
    upall_nosuf = [i for i in upall if ref.TRANSFORMS[i][2] == 49]
    upall_suf = [i for i in upall if ref.TRANSFORMS[i][2] != 49]
    refs = [(4, 939, upfirst[0]), (6, 628, upfirst[1]), (4, 939, upall_nosuf[0]), (9, 808, upall_nosuf[0]),
            (4, 436, upall_nosuf[0]), (4, 539, upall_suf[0]), (5, 619, upall_nosuf[0]), (8, 1015, upall_nosuf[0]),
            (8, 1015, upall_suf[1]), (24, 22, upall_nosuf[0]), (12, 651, upfirst[2])]
    cmds = [{'lits': b'[', 'dict': r} for r in refs] + [{'lits': b']', 'copy': 4, 'end': True}]
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    mb_compressed(bw, out, cmds, wbits=16, islast=True)
    return bw.tobytes()


# =====================================================================================================
# crafted/ -- block switching (RFC 7932 §6), command-loop edges
# =====================================================================================================
class BlockPlan:
    """One category's block-switch plan. spec: None (NBLTYPES = 1) or {'n': NBLTYPES, 'counts': [initial
    count, count after switch 1, ...], 'codes': [block-type code symbol of switch 1, ...]}. Code symbols
    follow RFC 7932 §6: 0 = the previous type, 1 = current type + 1, k >= 2 = type k - 2 (all mod n)."""

    def __init__(self, spec):
        self.n = spec['n'] if spec else 1
        self.counts = list(spec['counts']) if spec else [1]
        self.codes = list(spec['codes']) if spec else []
        assert len(self.counts) == len(self.codes) + 1
        self.type, self.prev, self.k = 0, 1, 0
        self.left = self.counts[0]
        self.types = []                           # type after each switch (for asserts)

    def step(self):
        """Advance by one symbol of this category; returns the switch event (code, count) to emit first."""
        if self.n < 2:
            return None
        ev = None
        if self.left == 0:
            if self.k >= len(self.codes):
                raise ValueError('block plan exhausted')
            code = self.codes[self.k]
            self.k += 1
            t = self.prev if code == 0 else (self.type + 1 if code == 1 else code - 2)
            if t >= self.n:
                t -= self.n
            self.prev, self.type = self.type, t
            self.left = self.counts[self.k]
            self.types.append(t)
            ev = (code, self.left)
        self.left -= 1
        return ev

    def done(self):
        assert self.k == len(self.codes), 'block plan not consumed: %d of %d switches' % (self.k, len(self.codes))


def w_cmap(bw, values, ntrees, rlemax=0, imtf=False, style=None):
    """NTREES + context map (RFC 7932 §7.3): optional move-to-front, zero runs as RLE codes 1..rlemax."""
    w_var256(bw, ntrees)
    if ntrees < 2:
        return
    enc = list(values)
    if imtf:
        mtf = list(range(256))
        enc = []
        for v in values:
            i = mtf.index(v)
            enc.append(i)
            mtf.pop(i)
            mtf.insert(0, v)
    items = []
    i = 0
    while i < len(enc):
        if enc[i] == 0 and rlemax:
            j = i
            while j < len(enc) and enc[j] == 0:
                j += 1
            run = j - i
            while run > 0:
                if run >= 2:
                    k = min(rlemax, run.bit_length() - 1)
                    take = min(run, (2 << k) - 1)
                    items.append((k, take - (1 << k), k))
                    run -= take
                else:
                    items.append((0, 0, 0))
                    run -= 1
            i = j
        else:
            items.append((enc[i] + rlemax if enc[i] else 0, 0, 0))
            i += 1
    if rlemax:
        bw.w(1, 1); bw.w(rlemax - 1, 4)
    else:
        bw.w(0, 1)
    tab = auto_code(bw, [s for s, _, _ in items], ntrees + rlemax, style)
    for s, e, n in items:
        put(bw, tab, s)
        bw.w(e, n)
    bw.w(1 if imtf else 0, 1)


def mb_blocks(bw, out, cmds, *, wbits, islast=False, npostfix=0, ndirect=0, L=None, I=None, D=None, cmodes=None,
              ntrees_l=1, cmap_l=None, ntrees_d=1, cmap_d=None, cmap_l_fmt=(0, False), cmap_d_fmt=(0, False),
              lit_style=None, cmd_style=None, dist_style=None, dist_rb=None):
    """A compressed meta-block with block switching in all three categories. cmds as mb_compressed
    (lits / copy / dist / dcode / dz / end; no dictionary references, no mlen override). L / I / D: BlockPlan
    specs; cmodes: one context mode per literal block type; cmap_l: 64 x NBLTYPES_L tree ids; cmap_d:
    4 x NBLTYPES_D tree ids; *_fmt = (RLEMAX, IMTF). Literal / distance trees are per tree id, command
    trees per insert-and-copy block type. `out` and `dist_rb` carry across meta-blocks."""
    wsize = (1 << wbits) - 16
    pl, pi, pd = BlockPlan(L), BlockPlan(I), BlockPlan(D)
    cmodes = cmodes or [0] * pl.n
    assert len(cmodes) == pl.n
    cmap_l = cmap_l or [0] * (64 * pl.n)
    cmap_d = cmap_d or [0] * (4 * pd.n)
    assert len(cmap_l) == 64 * pl.n and len(cmap_d) == 4 * pd.n
    sim = bytearray(out)
    rb = list(dist_rb) if dist_rb is not None else [16, 15, 11, 4]
    lit_syms = [set() for _ in range(ntrees_l)]
    cmd_syms = [set() for _ in range(pi.n)]
    dist_syms = [set() for _ in range(ntrees_d)]
    plan = []
    for c in cmds:
        e = {'iev': pi.step(), 'itype': pi.type}
        lits = c.get('lits', b'')
        e['lits'] = []
        for b in lits:
            ev = pl.step()
            p1 = sim[-1] if len(sim) >= 1 else 0
            p2 = sim[-2] if len(sim) >= 2 else 0
            m = cmodes[pl.type]
            t = cmap_l[64 * pl.type + (CTX[m * 512 + p1] | CTX[m * 512 + 256 + p2])]
            lit_syms[t].add(b)
            e['lits'].append((ev, t, b))
            sim.append(b)
        ic, ie = len_code(len(lits), INS_BASE, INS_EXTRA)
        clen = c.get('copy', 4)
        cc, ce = len_code(clen, CPY_BASE, CPY_EXTRA)
        dz = bool(c.get('dz'))
        e.update(ic=ic, ie=ie, cc=cc, ce=ce, dz=dz, end=c.get('end', False))
        e['cmd'] = cmd_symbol(ic, cc, dz)
        cmd_syms[pi.type].add(e['cmd'])
        if not e['end']:
            if dz:
                dist, dcode, dex = rb[3], 0, (0, 0)
            else:
                e['dev'] = pd.step()
                dctx = min(cc, 3)
                e['dtree'] = cmap_d[4 * pd.type + dctx]
                if c.get('dcode') is not None:
                    dcode, dex = c['dcode'], (0, 0)
                    assert dcode < 16
                    if dcode < 4:
                        dist = rb[3 - dcode]
                    else:
                        base = rb[3] if dcode < 10 else rb[2]
                        k = dcode - 4 if dcode < 10 else dcode - 10
                        dist = base - ((k >> 1) + 1) if k % 2 == 0 else base + ((k >> 1) + 1)
                else:
                    dist = c['dist']
                    dcode, x, n = dist_code(dist, npostfix, ndirect)
                    dex = (x, n)
                dist_syms[e['dtree']].add(dcode)
            e.update(dcode=dcode, dex=dex)
            assert 0 < dist <= min(len(sim), wsize), 'mb_blocks: LZ copies only (dist %d)' % dist
            if dcode != 0 and not dz:
                rb = rb[1:] + [dist]
            for _ in range(clen):
                sim.append(sim[len(sim) - dist])
        plan.append(e)
    for p in (pl, pi, pd):
        p.done()
    mlen = len(sim) - len(out)
    # ---- header
    bw.w(1 if islast else 0, 1)
    if islast:
        bw.w(0, 1)
    w_mlen(bw, mlen)
    if not islast:
        bw.w(0, 1)
    sw_tabs = []
    for p in (pl, pi, pd):
        w_var256(bw, p.n)
        if p.n >= 2:
            ttab = auto_code(bw, p.codes, p.n + 2)
            ccodes = [len_code(x, BL_BASE, BL_EXTRA) for x in p.counts]
            ctab = auto_code(bw, [cc for cc, _ in ccodes], 26)
            put(bw, ctab, ccodes[0][0])
            bw.w(ccodes[0][1], BL_EXTRA[ccodes[0][0]])
            sw_tabs.append((ttab, ctab))
        else:
            sw_tabs.append(None)
    bw.w(npostfix, 2)
    bw.w(ndirect >> npostfix, 4)
    for m in cmodes:
        bw.w(m, 2)
    w_cmap(bw, cmap_l, ntrees_l, *cmap_l_fmt)
    w_cmap(bw, cmap_d, ntrees_d, *cmap_d_fmt)
    lit_tabs = [auto_code(bw, lit_syms[t], 256, lit_style) for t in range(ntrees_l)]
    cmd_tabs = [auto_code(bw, cmd_syms[t], 704, cmd_style) for t in range(pi.n)]
    dalpha = 16 + ndirect + (48 << npostfix)
    dist_tabs = [auto_code(bw, dist_syms[t], dalpha, dist_style) for t in range(ntrees_d)]

    def switch(cat, ev):
        if ev is None:
            return
        ttab, ctab = sw_tabs[cat]
        put(bw, ttab, ev[0])
        cc, x = len_code(ev[1], BL_BASE, BL_EXTRA)
        put(bw, ctab, cc)
        bw.w(x, BL_EXTRA[cc])

    # ---- data
    for e in plan:
        switch(1, e['iev'])
        put(bw, cmd_tabs[e['itype']], e['cmd'])
        bw.w(e['ie'], INS_EXTRA[e['ic']])
        bw.w(e['ce'], CPY_EXTRA[e['cc']])
        for ev, t, b in e['lits']:
            switch(0, ev)
            put(bw, lit_tabs[t], b)
        if not e['end'] and not e['dz']:
            switch(2, e['dev'])
            put(bw, dist_tabs[e['dtree']], e['dcode'])
            bw.w(*e['dex'])
    out[:] = sim
    if dist_rb is not None:
        dist_rb[:] = rb
    return {'L': pl.types, 'I': pi.types, 'D': pd.types}


class Lcg:
    def __init__(self, seed):
        self.x = seed & 0x7fffffff

    def next(self, n):
        self.x = (self.x * 1103515245 + 12345) & 0x7fffffff
        return (self.x >> 8) % n


KILLS = {}      # crafted name -> reference-decoder mutants the stream must kill


def must_kill(name, *mutants):
    KILLS['crafted/' + name + '.br'] = mutants


def check_kills(path, data):
    """The stream decodes under the reference decoder, and each named mutant decodes it differently."""
    want = KILLS.get(path)
    if not want:
        return
    base = ref.decode(data, {})
    for m in want:
        try:
            got = ref.decode(data, {}, m)
        except Exception:                        # a mutant that errors (or indexes out of range) is killed
            continue
        if got == base:
            raise SystemExit('%s: mutant %s survives' % (path, m))


def _lits_for(types, alphabets, rng):
    return bytes(alphabets[t][rng.next(len(alphabets[t]))] for t in types)


def _type_sequence(spec, total):
    """Block type of each of `total` symbols under a BlockPlan spec (mirrors BlockPlan.step)."""
    p = BlockPlan(spec)
    seq = []
    for _ in range(total):
        p.step()
        seq.append(p.type)
    p.done()
    return seq


@crafted('bswitch_l3_code0_first', 'NBLTYPES_L=3, one literal tree per type; first switch is code 0 (prev starts at 1)')
def _():
    L = {'n': 3, 'counts': [6, 9, 5, 7, 11, 4, 8, 40], 'codes': [0, 1, 1, 4, 0, 3, 2]}
    nlit = sum(L['counts'][:-1]) + 3
    types = _type_sequence(L, nlit)
    assert types[6] == 1 and types[15] == 2 and types[20] == 0 and types[27] == 2, 'plan types'
    rng = Lcg(31)
    lits = _lits_for(types, [b'abcdefgh', b'XYZ', b'0123'], rng)
    cmds = []
    i = 0
    for n, (cp, d) in zip([4, 7, 2, 9, 5, 8, 6, 10], [(4, 3), (5, 1), (6, 7), (4, 2), (7, 11), (3, 5), (5, 4), (6, 9)]):
        cmds.append({'lits': lits[i:i + n], 'copy': cp, 'dist': d})
        i += n
    cmds.append({'lits': lits[i:], 'copy': 4, 'end': True})
    cmap_l = [0] * 64 + [1] * 64 + [2] * 64
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    got = mb_blocks(bw, out, cmds, wbits=16, islast=True, L=L, cmodes=[0, 0, 0], ntrees_l=3, cmap_l=cmap_l,
                    cmap_l_fmt=(4, True), lit_style={'complex': True})
    assert got['L'] == [1, 2, 0, 2, 0, 1, 0], got
    return bw.tobytes()


must_kill('bswitch_l3_code0_first', 'M1')


@crafted('bswitch_i3_code0_first', 'NBLTYPES_I=3, one insert-and-copy tree per type; first switch is code 0')
def _():
    I = {'n': 3, 'counts': [2, 3, 2, 4, 2, 3, 6], 'codes': [0, 1, 1, 4, 0, 3]}
    ncmd = sum(I['counts'][:-1]) + 2
    types = _type_sequence(I, ncmd)
    shapes = [[(1, 4, False), (2, 5, False), (1, 9, True)], [(3, 6, False), (4, 7, False)],
              [(0, 8, False), (5, 3, False), (2, 12, True)]]
    rng = Lcg(77)
    text = textish(64, 5, b'brotli command loop ')
    cmds = [{'lits': text, 'copy': 5, 'dist': 17}]
    types = types[1:]
    for k, t in enumerate(types):
        il, cl, dz = shapes[t][rng.next(len(shapes[t]))]
        lits = bytes(b'+-*/<>=!'[rng.next(8)] for _ in range(il))
        if k == len(types) - 1:
            cmds.append({'lits': lits + b'.', 'copy': 4, 'end': True})
        elif dz:
            cmds.append({'lits': lits, 'copy': cl, 'dz': True})
        else:
            cmds.append({'lits': lits, 'copy': cl, 'dist': 1 + rng.next(60)})
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    got = mb_blocks(bw, out, cmds, wbits=16, islast=True, I=I)
    assert got['I'] == [1, 2, 0, 2, 0, 1], got
    return bw.tobytes()


must_kill('bswitch_i3_code0_first', 'M1')


@crafted('bswitch_d3_dctx_implicit', 'NBLTYPES_D=3, NTREES_D=3 picked by distance context; implicit distances interleaved (errata 6977)')
def _():
    D = {'n': 3, 'counts': [2, 1, 3, 2, 1, 2, 3, 30], 'codes': [1, 0, 3, 1, 2, 0, 2]}
    rng = Lcg(5)
    text = textish(300, 23, b'distance context map RFC 7932 ')
    cmds = [{'lits': text, 'copy': 6, 'dist': 250}]
    # copy lengths 3 / 4 / 5+ give distance contexts 1 / 2 / 3 (a D switch lands on dctx != 0)
    for k in range(34):
        il = rng.next(3)
        lits = bytes(b'abcdef'[rng.next(6)] for _ in range(il))
        if k % 3 == 1:
            cmds.append({'lits': lits, 'copy': 3 + rng.next(6), 'dz': True})
        else:
            cmds.append({'lits': lits, 'copy': 3 + rng.next(4), 'dist': [1, 2, 3, 5, 8, 13, 21, 34, 55, 89][rng.next(10)]})
    cmds.append({'lits': b'$', 'copy': 4, 'end': True})
    cmap_d = [0, 1, 2, 1,  2, 0, 1, 0,  1, 2, 0, 2]
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    got = mb_blocks(bw, out, cmds, wbits=16, islast=True, D=D, ntrees_d=3, cmap_d=cmap_d, cmap_d_fmt=(1, True),
                    dist_style={'complex': True})
    assert got['D'] == [1, 0, 1, 2, 0, 2, 0], got
    return bw.tobytes()


must_kill('bswitch_d3_dctx_implicit', 'E6977')


def _cmode_mixed(modes, seed):
    L = {'n': 2, 'counts': [37, 41, 29, 53, 400], 'codes': [1, 0, 1, 0]}
    total = sum(L['counts'][:-1]) + 60
    rng = Lcg(seed)
    # UTF-8 text with 2- and 3-byte sequences so p1 / p2 >= 0x80 occur in both block types
    alph = ['a', 'e', 's', ' ', 'Z', '0', 'é', 'ß', '€', 'Ж', ',', '\n']
    chars = ''.join(alph[rng.next(len(alph))] for _ in range(total))
    text = chars.encode('utf-8')[:total]
    cmds = []
    i = 0
    while i < len(text) - 12:
        n = 5 + rng.next(9)
        cmds.append({'lits': text[i:i + n], 'copy': 3 + rng.next(5), 'dist': 1 + rng.next(8)})
        i += n
    cmds.append({'lits': text[i:], 'copy': 4, 'end': True})
    # type 0 contexts -> trees 0 / 1, type 1 contexts -> trees 2 / 3, split differently per id
    cmap_l = [(c * 7 + (c >> 3)) & 1 for c in range(64)] + [2 + ((c * 5 + (c >> 2)) & 1) for c in range(64)]
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    got = mb_blocks(bw, out, cmds, wbits=16, islast=True, L=L, cmodes=modes, ntrees_l=4, cmap_l=cmap_l,
                    cmap_l_fmt=(2, False), lit_style={'complex': True})
    assert got['L'] == [1, 0, 1, 0], got
    return bw.tobytes()


crafted('bswitch_cmode_mixed_lsb6_utf8', 'NBLTYPES_L=2 with context modes LSB6 / UTF8, p1 / p2 >= 0x80')(
    lambda: _cmode_mixed([0, 2], 101))
crafted('bswitch_cmode_mixed_msb6_signed', 'NBLTYPES_L=2 with context modes MSB6 / SIGNED, p1 / p2 >= 0x80')(
    lambda: _cmode_mixed([1, 3], 202))
must_kill('bswitch_cmode_mixed_lsb6_utf8', 'M2')
must_kill('bswitch_cmode_mixed_msb6_signed', 'M2')


@crafted('bswitch_trivial_to_utf8_midinsert', 'NBLTYPES_L=2: a one-tree (trivial map) LSB6 type switches mid-insert to a UTF8 type whose first literal context needs p1 and p2')
def _():
    rng = Lcg(606)
    L = {'n': 2, 'counts': [7, 9, 11, 6, 13, 8, 10, 1000], 'codes': [1] * 7}
    words = [b'the', b'brown', b'fox', b'jumps', b'over', b'a', b'lazy', b'dog', b'Zq', b'x']
    text = bytearray()
    while len(text) < 160:
        text += words[rng.next(len(words))] + b' '
    cmds = []
    i = 0
    for k in range(5):
        cmds.append({'lits': bytes(text[i:i + 25]), 'copy': 4 + rng.next(4), 'dist': 1 + rng.next(6)})
        i += 25
    cmds.append({'lits': bytes(text[i:i + 10]), 'copy': 4, 'end': True})
    cmap_l = [0] * 64 + [1 + ((c * 5 + (c >> 2)) & 1) for c in range(64)]
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    got = mb_blocks(bw, out, cmds, wbits=16, islast=True, L=L, cmodes=[0, 2], ntrees_l=3, cmap_l=cmap_l,
                    lit_style={'complex': True})
    assert got['L'] == [1, 0, 1, 0, 1, 0, 1], got
    return bw.tobytes()


@crafted('bswitch_reset_per_metablock', 'two compressed meta-blocks: the first ends on type 2 (L, I, D); the second switches with codes 0 and 1')
def _():
    rng = Lcg(9)
    bw = BW(); w_wbits(bw, 16); out = bytearray(); rb = [16, 15, 11, 4]
    alph = [b'klmn', b'KLMN', b'5678']

    def block(L, I, D, ncmd, last):
        cmds = []
        for k in range(ncmd):
            lits = bytes(b'qrstuvwxyz'[rng.next(10)] for _ in range(2 + rng.next(4)))
            if not out and k == 0:
                lits = textish(40, 3)
            if k == ncmd - 1:
                cmds.append({'lits': lits, 'copy': 4, 'end': True})
            else:
                cmds.append({'lits': lits, 'copy': 3 + rng.next(5), 'dist': 1 + rng.next(30)})
        # re-draw literals from per-type alphabets so the literal tree of each type is distinct
        nl = sum(len(c['lits']) for c in cmds)
        types = _type_sequence(L, nl)
        lits = _lits_for(types, alph, rng)
        i = 0
        for c in cmds:
            n = len(c['lits'])
            c['lits'] = lits[i:i + n]
            i += n
        return mb_blocks(bw, out, cmds, wbits=16, islast=last, L=L, I=I, D=D, cmodes=[0, 2, 0], ntrees_l=3,
                         cmap_l=[0] * 64 + [1] * 64 + [2] * 64, ntrees_d=3, cmap_d=[0] * 4 + [1] * 4 + [2] * 4,
                         cmap_l_fmt=(3, False), cmap_d_fmt=(0, True), dist_rb=rb)
    L1 = {'n': 3, 'counts': [12, 10, 200], 'codes': [1, 1]}
    I1 = {'n': 3, 'counts': [4, 3, 50], 'codes': [1, 1]}
    D1 = {'n': 3, 'counts': [3, 3, 50], 'codes': [3, 4]}
    got1 = block(L1, I1, D1, 12, False)
    assert got1 == {'L': [1, 2], 'I': [1, 2], 'D': [1, 2]}, got1
    L2 = {'n': 3, 'counts': [9, 8, 200], 'codes': [0, 1]}
    I2 = {'n': 3, 'counts': [3, 4, 50], 'codes': [0, 1]}
    D2 = {'n': 3, 'counts': [2, 3, 50], 'codes': [0, 1]}
    got2 = block(L2, I2, D2, 11, True)
    assert got2 == {'L': [1, 2], 'I': [1, 2], 'D': [1, 2]}, got2
    return bw.tobytes()


must_kill('bswitch_reset_per_metablock', 'M3')


def _nsym1_block(mlen, cmd, body_bits):
    """ISLAST compressed meta-block whose codes are all NSYM=1 (0-bit): literal 'a', insert-and-copy
    symbol `cmd`, and an unused distance code. The header is sized to end on a byte boundary, so a
    stream cut where the body starts is exactly the header; body_bits (value, n) pairs follow."""
    for wb in (16, 18, 17):
        for dsyms in ([0], [0, 1], [0, 1, 2]):
            bw = BW(); w_wbits(bw, wb)
            bw.w(1, 1); bw.w(0, 1); w_mlen(bw, mlen)
            for _ in range(3):
                w_var256(bw, 1)
            bw.w(0, 2); bw.w(0, 4); bw.w(0, 2); w_var256(bw, 1); w_var256(bw, 1)
            w_simple(bw, [97], 256)
            w_simple(bw, [cmd], 704)
            w_simple(bw, dsyms, 64)
            if len(bw.bits) % 8 == 0:
                for v, n in body_bits:
                    bw.w(v, n)
                return bw.tobytes()
    raise SystemExit('_nsym1_block: no byte-aligned header form')


# Symbol 64: insert 0, copy base 10 + 1 extra bit, implicit distance. With extra bits 0 then 1: copy 10 at
# distance 4 from position 0 is dictionary word 3 (length 10), then copy 11 at distance 4 is an LZ copy.
crafted('trunc_nsym1_cmd64_body', 'nsym1_cmd64_body cut where the body starts: the copy extra bit is missing (not 21 invented bytes)')(
    lambda: _nsym1_block(21, 64, []))
crafted('nsym1_cmd64_body', 'MLEN 21 from a 0-bit insert-and-copy code: dictionary word, then an LZ copy (2 body bits)')(
    lambda: _nsym1_block(21, 64, [(0, 1), (1, 1)]))
# Symbol 56: insert code 7 (base 8 + 1 extra bit), copy 2, implicit distance; literals 0-bit. MLEN 5 is
# base - ERR_CORRUPT_DATA: a decoder that added the failed extra-bit read to the base would emit 5
# literals from no input and succeed.
crafted('trunc_nsym1_insert_extra_body', 'MLEN 5, 0-bit insert-and-copy code with an insert extra bit, cut where the body starts')(
    lambda: _nsym1_block(5, 56, []))


@crafted('mlen_4nibbles_max_copy_65536', 'two literals + copy 65,534 at distance 2: MLEN 65,536, the largest 4-nibble MLEN')
def _():
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    mb_compressed(bw, out, [{'lits': b'ab', 'copy': 65534, 'dist': 2}], wbits=16, islast=True)
    assert len(out) == 65536
    return bw.tobytes()


# =====================================================================================================
# crafted/ -- static dictionary references
# =====================================================================================================
@crafted('dict_word_bounds_all_lengths', 'every length 4..24: address 0 (word 0, identity) and 121 x 2^NDBITS - 1 (last word, transform 120)')
def _():
    cmds = []
    for L in range(4, 25):
        last = (1 << NDBITS[L]) - 1
        cmds.append({'lits': b'', 'dict': (L, 0, 0)})
        cmds.append({'lits': b'|', 'dict': (L, last, 120)})
    cmds.append({'lits': b'.', 'copy': 4, 'end': True})
    bw = BW(); w_wbits(bw, 16); out = bytearray()
    mb_compressed(bw, out, cmds, wbits=16, islast=True)
    st = {}
    assert ref.decode(bw.tobytes(), st) == bytes(out) and st['dict_refs'] == 42, st['dict_refs']
    return bw.tobytes()


# Dictionary references reached through short distance codes must not push the ring (only LZ copies with an
# explicit code >= 1 do). WBITS 10: at output position 0 the initial ring (4, 11, 15, 16) puts r0 - 3 and
# r1 - 1 / r1 - 2 past max_distance; once 1,008 bytes exist, LZ copies at distance 1,008 put r0 + 1..3 and
# r1 + 1..3 past it. After each group, code 0 / 1 / 2 LZ copies read the ring back: a decoder that pushed a
# dictionary distance copies from the wrong place or turns the copy into a dictionary word.
@crafted('dict_ring_short_codes', 'dictionary references via short distance codes 8, 12, 10, 5, 7, 9, 11, 13, 15; the ring stays intact')
def _():
    lz = lambda n, **k: dict({'lits': b'', 'copy': n}, **k)
    cmds = [lz(4, dcode=8),                           # pos 0: r0 - 3 = 1 > 0     -> word 0 of length 4
            lz(5, dcode=12),                          # pos 4: r1 - 2 = 9 > 4     -> address 4, length 5
            lz(4, dcode=10),                          # pos 9: r1 - 1 = 10 > 9    -> address 0, length 4
            lz(4, dcode=0), lz(6, dcode=1),           # LZ copies at r0 = 4 and r1 = 11 (the latter pushes 11)
            lz(1000, dist=3), lz(4, dist=1008),       # pos >= 1,008: push 3, then 1,008
            lz(4, dcode=5), lz(6, dcode=7), lz(8, dcode=9),         # r0 + 1..3 -> addresses 0..2
            lz(5, dcode=0),                           # LZ copy at r0 = 1,008
            {'lits': b'#', 'copy': 4, 'dist': 500},   # push 500: r1 = 1,008
            lz(7, dcode=11), lz(9, dcode=13), lz(11, dcode=15),     # r1 + 1..3 -> addresses 0..2
            lz(6, dcode=1), lz(4, dcode=2), lz(5, dcode=0),         # read r1, r2, r0 back
            {'lits': b'!', 'copy': 4, 'end': True}]
    bw = BW(); w_wbits(bw, 10); out = bytearray()
    mb_compressed(bw, out, cmds, wbits=10, islast=True)
    st = {}
    assert ref.decode(bw.tobytes(), st) == bytes(out) and st['dict_refs'] == 9, st['dict_refs']
    return bw.tobytes()


must_kill('dict_ring_short_codes', 'D1', 'D2')


# Codes 4, 6 and 14 subtract from r0 / r1, so they reach the dictionary only while the output is shorter than
# the initial ring values; one of r0 - 1..3 per stream, hence two more rows.
for _codes in ((4, 14), (6,)):
    def _mk(codes=_codes):
        cmds = [{'lits': b'', 'copy': 4 + i, 'dcode': c} for i, c in enumerate(codes)]
        cmds += [{'lits': b'', 'copy': 8, 'dcode': 0}, {'lits': b'', 'copy': 5, 'dcode': 1}, {'lits': b'', 'copy': 6, 'dcode': 0},
                 {'lits': b'!', 'copy': 4, 'end': True}]
        bw = BW(); w_wbits(bw, 16); out = bytearray()
        mb_compressed(bw, out, cmds, wbits=16, islast=True)
        st = {}
        assert ref.decode(bw.tobytes(), st) == bytes(out) and st['dict_refs'] == len(codes), st['dict_refs']
        return bw.tobytes()
    _n = 'dict_ring_short_code' + ('s_' if len(_codes) > 1 else '_') + '_'.join(map(str, _codes))
    crafted(_n, 'dictionary references via short distance code(s) %s at the stream start; the ring stays intact'
            % ', '.join(map(str, _codes)))(_mk)
    must_kill(_n, 'D1', 'D2')



# =====================================================================================================
# crafted/ -- adversarial inverse move-to-front (work amplification, RFC 7932 §7.3)
# =====================================================================================================
def _adv_imtf(cat, full):
    """One ISLAST compressed meta-block of MLEN 16 whose literal (cat 0) or distance (cat 2) category has
    NBLTYPES = 256 and a 256-tree context map of all-255 entries from a 0-bit code, with IMTF: every map
    entry moves the whole list (16,384 x 255 or 1,024 x 255 byte moves) from ~76 B of header. full=False
    stops right after the IMTF bit (the zero padding then reads as NTREES_D = 1 and the first literal tree
    runs off the end: ERR_CORRUPT_DATA after the full IMTF work); full=True adds the trees and a 0-bit body
    of 16 literals 'A'."""
    bw = BW(); w_wbits(bw, 16)
    bw.w(1, 1); bw.w(0, 1); w_mlen(bw, 16)
    for c in range(3):
        if c != cat:
            w_var256(bw, 1)
            continue
        w_var256(bw, 256)
        w_simple(bw, [2], 258)                       # block-type code: one 0-bit symbol
        cc, x = len_code(16, BL_BASE, BL_EXTRA)
        w_simple(bw, [cc], 26)                       # block-count code: one 0-bit symbol
        bw.w(x, BL_EXTRA[cc])
    bw.w(0, 2); bw.w(0, 4)                           # NPOSTFIX 0, NDIRECT 0
    for _ in range(256 if cat == 0 else 1):
        bw.w(0, 2)                                   # CMODE LSB6
    for c in (0, 2):
        if c != cat:
            w_var256(bw, 1)
            continue
        w_var256(bw, 256)                            # NTREES 256
        bw.w(0, 1)                                   # RLEMAX 0
        w_simple(bw, [255], 256)                     # every map entry is 255, 0 bits each
        bw.w(1, 1)                                   # IMTF
        if not full:
            return bw.tobytes()
    ic, ie = len_code(16, INS_BASE, INS_EXTRA)
    cc, ce = len_code(4, CPY_BASE, CPY_EXTRA)
    cmd = cmd_symbol(ic, cc, False)
    for _ in range(256 if cat == 0 else 1):
        w_simple(bw, [65], 256)
    w_simple(bw, [cmd], 704)
    for _ in range(256 if cat == 2 else 1):
        w_simple(bw, [0], 64)
    bw.w(ie, INS_EXTRA[ic]); bw.w(ce, CPY_EXTRA[cc])  # 16 literals from 0-bit codes; MLEN reached
    data = bw.tobytes()
    assert ref.decode(data, {}) == b'A' * 16
    return data


crafted('adv_imtf_256_trunc', 'NBLTYPES_L 256 / NTREES_L 256 all-255 literal map + IMTF (4,177,920 byte moves), cut after the IMTF bit')(
    lambda: _adv_imtf(0, False))
crafted('adv_imtf_256', 'adv_imtf_256_trunc completed: 256 literal trees and 16 literals from 0-bit codes')(
    lambda: _adv_imtf(0, True))
crafted('adv_imtf_dist_256', 'NBLTYPES_D 256 / NTREES_D 256 all-255 distance map + IMTF (261,120 byte moves), then 16 literals')(
    lambda: _adv_imtf(2, True))


# =====================================================================================================
# probe/ -- research probe set
# =====================================================================================================
class PBW:
    def __init__(self):
        self.bits = []

    def w(self, n, v):
        for i in range(n):
            self.bits.append((v >> i) & 1)
        return self

    def pad(self, fill=0):
        while len(self.bits) % 8:
            self.bits.append(fill)
        return self

    def raw(self, data):
        self.pad()
        for b in data:
            self.w(8, b)
        return self

    def bytes(self):
        self.pad()
        out = bytearray()
        for i in range(0, len(self.bits), 8):
            out.append(sum(bit << k for k, bit in enumerate(self.bits[i:i + 8])))
        return bytes(out)


def _p_log2floor(x):
    r = 0
    while x:
        x >>= 1
        r += 1
    return r


def p_simple(bw, alphabet, syms, tree_select=0):
    bw.w(2, 1).w(2, len(syms) - 1)
    nb = _p_log2floor(alphabet - 1)
    for s in syms:
        bw.w(nb, s)
    if len(syms) == 4:
        bw.w(1, tree_select)


def p_mb_header(bw, islast, mlen, npostfix=0, ndirect=0, ntreesl_bits=None):
    bw.w(1, islast)
    if islast:
        bw.w(1, 0)
    bw.w(2, 0).w(16, mlen - 1)            # MNIBBLES=4
    if not islast:
        bw.w(1, 0)                         # ISUNCOMPRESSED=0
    bw.w(1, 0).w(1, 0).w(1, 0)             # NBLTYPESL/I/D = 1
    bw.w(2, npostfix).w(4, ndirect >> npostfix)
    bw.w(2, 0)                             # context mode LSB6
    if ntreesl_bits is None:
        bw.w(1, 0)                         # NTREESL = 1
        bw.w(1, 0)                         # NTREESD = 1


def p_cmd_sym(ins_code, copy_code, implicit):
    assert ins_code < 8 and copy_code < 16
    if implicit:
        return (ins_code << 3) | copy_code if copy_code < 8 else 64 + (ins_code << 3) + copy_code - 8
    return 128 + (ins_code << 3) + copy_code if copy_code < 8 else 192 + (ins_code << 3) + copy_code - 8


def p_clcl(bw, lengths_by_symbol, hskip=0):
    """complex code: write HSKIP then code-length-code lengths in RFC order until space hits 0."""
    order = [1, 2, 3, 4, 0, 5, 17, 6, 16, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    code = {0: "00", 1: "0111", 2: "011", 3: "10", 4: "01", 5: "1111"}
    bw.w(2, hskip)
    space = 32
    for sym in order[hskip:]:
        ln = lengths_by_symbol.get(sym, 0)
        c = code[ln]
        bw.w(len(c), int(c, 2))
        if ln:
            space -= 32 >> ln
            if space <= 0:
                break


def probe(name, why, fn):
    stream('probe', name, why)(fn)


probe('wbits_large_window_escape', 'WBITS escape 0010001 (large window)', lambda: PBW().w(1, 1).w(3, 0).w(3, 1).w(8, 0xFF).bytes())
probe('wbits_10_last_empty', 'WBITS 10 then ISLAST + ISLASTEMPTY', lambda: PBW().w(1, 1).w(3, 0).w(3, 2).w(1, 1).w(1, 1).bytes())
probe('exuberant_nibble_mnibbles5_top0', 'MNIBBLES 5 with a zero top nibble',
      lambda: PBW().w(1, 0).w(1, 1).w(1, 0).w(2, 1).w(20, 0).bytes())
probe('mnibbles5_top_nonzero_truncated', 'MNIBBLES 5, top nibble non-zero, stream ends',
      lambda: PBW().w(1, 0).w(1, 1).w(1, 0).w(2, 1).w(16, 0).w(4, 1).bytes())
probe('metadata_reserved_bit_set', 'metadata reserved bit set', lambda: PBW().w(1, 0).w(1, 0).w(2, 3).w(1, 1).bytes())
probe('exuberant_meta_byte', 'MSKIPBYTES 2 with a zero top byte',
      lambda: PBW().w(1, 0).w(1, 0).w(2, 3).w(1, 0).w(2, 2).w(8, 5).w(8, 0).bytes())
probe('metadata_3_bytes_then_last_empty', '3-byte metadata then ISLASTEMPTY',
      lambda: PBW().w(1, 0).w(1, 0).w(2, 3).w(1, 0).w(2, 1).w(8, 2).raw(b"abc").w(1, 1).w(1, 1).bytes())
probe('metadata_in_last_metablock_mskipbytes0', 'ISLAST metadata with MSKIPBYTES 0',
      lambda: PBW().w(1, 0).w(1, 1).w(1, 0).w(2, 3).w(1, 0).w(2, 0).bytes())
probe('metadata_in_last_metablock_1_byte', 'ISLAST metadata, 1 byte',
      lambda: PBW().w(1, 0).w(1, 1).w(1, 0).w(2, 3).w(1, 0).w(2, 1).w(8, 0).raw(b"Z").bytes())
probe('metadata_nonzero_padding', 'non-zero padding before a metadata payload',
      lambda: PBW().w(1, 0).w(1, 0).w(2, 3).w(1, 0).w(2, 1).w(8, 0).w(1, 1).bytes())
probe('last_empty_nonzero_padding', 'non-zero padding after ISLASTEMPTY', lambda: PBW().w(1, 0).w(1, 1).w(1, 1).w(1, 1).bytes())
probe('uncompressed_3_then_last_empty', 'uncompressed 3 bytes then ISLASTEMPTY',
      lambda: PBW().w(1, 0).w(1, 0).w(2, 0).w(16, 2).w(1, 1).raw(b"xyz").w(1, 1).w(1, 1).bytes())
probe('uncompressed_nonzero_padding', 'non-zero padding before an uncompressed payload',
      lambda: PBW().w(1, 0).w(1, 0).w(2, 0).w(16, 2).w(1, 1).w(1, 1).raw(b"xyz").w(1, 1).w(1, 1).bytes())
probe('uncompressed_no_last_metablock', 'uncompressed meta-block, no ISLAST',
      lambda: PBW().w(1, 0).w(1, 0).w(2, 0).w(16, 2).w(1, 1).raw(b"xyz").bytes())
probe('header_only_no_metablock', 'stream header only', lambda: PBW().w(1, 0).bytes())


def _p_simple_dup():
    b = PBW().w(1, 0); p_mb_header(b, 1, 1)
    p_simple(b, 256, [97, 97])
    return b.bytes()


def _p_simple_ge():
    b = PBW().w(1, 0); p_mb_header(b, 1, 1, ndirect=1)
    p_simple(b, 256, [97]); p_simple(b, 704, [p_cmd_sym(1, 2, False)]); p_simple(b, 65, [100])
    return b.bytes()


def _p_clcl_incomplete():
    b = PBW().w(1, 0); p_mb_header(b, 1, 1)
    b.w(2, 0)
    code = {0: "00", 1: "0111", 2: "011"}
    for sym, ln in zip([1, 2, 3, 4, 0, 5, 17, 6, 16, 7, 8, 9, 10, 11, 12, 13, 14, 15], [2, 2] + [0] * 16):
        c = code[ln]
        b.w(len(c), int(c, 2))
    return b.bytes()


def _p_clcl_over():
    b = PBW().w(1, 0); p_mb_header(b, 1, 1)
    b.w(2, 0)
    for ln in [2, 1, 1]:
        c = {1: "0111", 2: "011"}[ln]
        b.w(len(c), int(c, 2))
    return b.bytes()


def _p_sym_incomplete():
    b = PBW().w(1, 0); p_mb_header(b, 1, 1)
    p_clcl(b, {1: 1, 0: 1})
    b.w(1, 1)
    for _ in range(255):
        b.w(1, 0)
    return b.bytes()


def _p_sym_over():
    b = PBW().w(1, 0); p_mb_header(b, 1, 1)
    p_clcl(b, {2: 1, 3: 1})
    for ln in [3, 2, 2, 2, 2] + [2] * 251:
        b.w(1, 0 if ln == 2 else 1)
    return b.bytes()


def _p_repeat17():
    b = PBW().w(1, 0); p_mb_header(b, 1, 1)
    p_clcl(b, {1: 1, 17: 1})
    for _ in range(3):
        b.w(1, 1).w(3, 7)
    return b.bytes()


def _p_single_clcl16():
    from itertools import product
    b = PBW().w(1, 0); p_mb_header(b, 1, 1)
    p_clcl(b, {16: 1})

    def reach(target):
        for n in range(1, 6):
            for seq in product(range(4), repeat=n):
                r = 0
                for e in seq:
                    r = (4 * (r - 2) if r > 0 else 0) + 3 + e
                if r == target:
                    return seq
    for e in reach(256):
        b.w(2, e)
    p_simple(b, 704, [p_cmd_sym(1, 2, False)]); p_simple(b, 64, [16])
    b.w(8, 0)
    return b.bytes()


def _p_cmap_rle_overflow():
    b = PBW().w(1, 0)
    b.w(1, 1).w(1, 0).w(2, 0).w(16, 0)
    b.w(1, 0).w(1, 0).w(1, 0).w(2, 0).w(4, 0).w(2, 0)
    b.w(1, 1).w(3, 0)
    b.w(1, 1).w(4, 4)
    p_simple(b, 7, [5])
    b.w(5, 31).w(5, 0)
    return b.bytes()


def _p_cmd_stream(mlen, lit, cmds, dists, body, npostfix=0, ndirect=0):
    b = PBW().w(1, 0)
    p_mb_header(b, 1, mlen, npostfix, ndirect)
    p_simple(b, 256, lit)
    p_simple(b, 704, cmds)
    p_simple(b, 16 + ndirect + (48 << npostfix), dists)
    body(b)
    return b.bytes()


def _p_neg_body(b):
    b.w(1, 1)
    b.w(1, 1).w(1, 0)
    b.w(1, 0)
    b.w(1, 0)


def _p_window_stream(distance_extra_code, extra_bits, extra_val):
    b = PBW().w(1, 1).w(3, 0).w(3, 2)
    p_mb_header(b, 1, 1009 + 4)
    p_simple(b, 256, [97])
    p_simple(b, 704, [448 + (3 << 3) + 2])
    p_simple(b, 64, [distance_extra_code])
    b.w(9, 1009 - 578)
    b.w(extra_bits, extra_val)
    return b.bytes()


probe('simple_code_duplicate_symbols', 'simple code lists a symbol twice', _p_simple_dup)
probe('simple_code_symbol_ge_alphabet_dist65', 'distance simple code symbol 100 >= alphabet 65', _p_simple_ge)
probe('complex_clcl_incomplete', 'code-length code incomplete', _p_clcl_incomplete)
probe('complex_clcl_oversubscribed', 'code-length code over-subscribed', _p_clcl_over)
probe('complex_symbols_incomplete_single_len1', 'symbol lengths incomplete (one length-1 code)', _p_sym_incomplete)
probe('complex_symbols_oversubscribed', 'symbol lengths over-subscribed', _p_sym_over)
probe('complex_repeat17_overflows_alphabet', 'repeat code 17 past the alphabet end', _p_repeat17)
probe('complex_single_clcl_16_all_len8_literal0', 'lone code-length symbol 16 repeats 8 to all 256 literals', _p_single_clcl16)
probe('context_map_rle_overflow', 'context-map zero run past the map end', _p_cmap_rle_overflow)
probe('insert_past_mlen', 'insert length past MLEN',
      lambda: _p_cmd_stream(2, [97], [p_cmd_sym(3, 0, True)], [0], lambda b: None))
probe('copy_past_mlen', 'copy length past MLEN',
      lambda: _p_cmd_stream(2, [97], [p_cmd_sym(1, 2, False)], [16], lambda b: b.w(1, 0)))
probe('mlen_reached_after_insert_copy_ignored', 'MLEN reached by literals: copy length ignored',
      lambda: _p_cmd_stream(1, [97], [p_cmd_sym(1, 2, False)], [16], lambda b: None))
probe('dict_ref_shortcode0_len4_word2', 'short code 0 at position 1: dictionary word 2, length 4',
      lambda: _p_cmd_stream(5, [97], [p_cmd_sym(1, 2, False)], [0], lambda b: None))
probe('dict_ref_copy_len3_invalid', 'distance beyond the window with copy length 3',
      lambda: _p_cmd_stream(4, [97], [p_cmd_sym(1, 1, False)], [0], lambda b: None))
probe('dict_ref_transform_127_invalid', 'dictionary reference with transform id 127',
      lambda: _p_cmd_stream(5, [97], [p_cmd_sym(1, 2, False)], [46], lambda b: b.w(16, 0)))
probe('dict_ref_transform_42_zero_length_output_ok', 'transform 42 (OmitLast4) on a 4-byte word: empty output',
      lambda: _p_cmd_stream(2, [97], [p_cmd_sym(1, 2, False)], [42], lambda b: b.w(14, 43010 - 32765)))
probe('short_code_resolves_nonpositive', 'short code 6 resolves to distance -1',
      lambda: _p_cmd_stream(10, [97], [p_cmd_sym(0, 0, False), p_cmd_sym(1, 0, False)], [6, 16], _p_neg_body))
probe('wbits10_distance_1009_is_dictionary', 'WBITS 10: distance 1009 is dictionary word 0',
      lambda: _p_window_stream(31, 8, 1009 - 765))
probe('wbits10_distance_1008_is_lz', 'WBITS 10: distance 1008 is an LZ copy', lambda: _p_window_stream(31, 8, 1008 - 765))


# =====================================================================================================
# small/ -- CLI output of synthetic inputs (needs brotli 1.2.0)
# =====================================================================================================
def _records(n, first=0):
    o = bytearray()
    i = first
    while len(o) < n:
        o += b'%08d,AGNOS,sankoch,brotli,decode,%d,OK\n' % (i, i % 7)
        i += 1
    return bytes(o[:n])


def mixed_7k():
    """2,048 B of word text + 1,100 incompressible bytes + 4,096 B of records: at -w 10 the q0 / q1
    encoders emit 1,024-byte compressed meta-blocks with uncompressed ones for the random span."""
    rng = Lcg(20260916)
    words = [b'the', b'decoder', b'window', b'of', b'bits', b'and', b'meta-block', b'prefix', b'code',
             b'literal', b'copy', b'distance', b'ring', b'context', b'map', b'stream']
    text = bytearray()
    while len(text) < 2048:
        text += words[rng.next(len(words))] + (b'. ' if rng.next(9) == 0 else b' ')
    noise = bytes(rng.next(256) for _ in range(1100))
    return bytes(text[:2048]) + noise + _records(4096)


def bswitch_records_68k():
    """Two alternating 11 KB regions over bytes 0x01..0x1f (no dictionary word can match): counter
    records, then token soup. At -q 11 -w 16 the encoder splits it into two compressed meta-blocks
    with literal, insert-and-copy and distance block switching."""
    rng = Lcg(5)
    toks = [bytes(18 + rng.next(12) for _ in range(5 + rng.next(7))) for _ in range(8)]
    out = bytearray()
    k = 0
    cnt = 0
    while len(out) < 68000:
        end = len(out) + 11000
        while len(out) < end:
            if k % 2 == 0:
                cnt += 1
                out += b'\x01\x02' + bytes(4 + int(c) for c in str(cnt * 7919 % 100000)) + b'\x03'
            else:
                out += b'\x10\x11' + toks[rng.next(8)] + toks[rng.next(3)] + bytes([0x1e, 1 + rng.next(3)])
        k += 1
    return bytes(out[:68000])


def cli_stream(inp, q, w):
    def build():
        p = subprocess.run(['brotli', '-c', '-q', str(q), '-w', str(w)], input=inp(), stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, check=True)
        return p.stdout
    return build


stream('small', 'mixed_7k.q0w10', 'q0: compressed and uncompressed meta-blocks of 1,024 B (brotli 1.2.0 -q 0 -w 10)')(
    cli_stream(mixed_7k, 0, 10))
stream('small', 'mixed_7k.q1w10', 'q1: compressed and uncompressed meta-blocks of 1,024 B (brotli 1.2.0 -q 1 -w 10)')(
    cli_stream(mixed_7k, 1, 10))
stream('small', 'bswitch_records_68k.q11w16', 'q11: two compressed meta-blocks, L/I/D block switching, no dictionary')(
    cli_stream(bswitch_records_68k, 11, 16))
KILLS['small/bswitch_records_68k.q11w16.br'] = ('M3', 'E6977')


def alice29_32k():
    """The first 32,768 B of Canterbury alice29.txt, taken from the committed google/alice29.txt.compressed
    through `brotli -dc`: English text at a mid quality (bench line `brotli d text q5 32K`)."""
    p = subprocess.run(['brotli', '-dc', os.path.join(CORPUS, 'google', 'alice29.txt.compressed')],
                       stdout=subprocess.PIPE, check=True)
    return p.stdout[:32768]


stream('small', 'alice29_32k.q5w16', 'q5: English text, the mid-quality bench stream (brotli 1.2.0 -q 5 -w 16)')(
    cli_stream(alice29_32k, 5, 16))


# =====================================================================================================
def main(argv):
    check = '--check' in argv
    if '--list' not in argv:
        ver = subprocess.run(['brotli', '--version'], stdout=subprocess.PIPE).stdout.decode().strip()
        if '1.2.0' not in ver:
            sys.stderr.write('warning: reference CLI is %r; small/ streams were built with brotli 1.2.0\n' % ver)
    seen = {}
    bad = 0
    for set_, name, why, fn in STREAMS:
        rel = '%s/%s.br' % (set_, name)
        assert rel not in seen, rel
        data = fn()
        seen[rel] = data
        if '--list' in argv:
            print('%-58s %7d  %s' % (rel, len(data), why))
            continue
        check_kills(rel, data)
        path = os.path.join(CORPUS, rel)
        if check:
            old = open(path, 'rb').read() if os.path.exists(path) else None
            if old != data:
                print('DIFFERS %s (%s)' % (rel, 'missing' if old is None else '%d vs %d B' % (len(old), len(data))))
                bad += 1
        else:
            with open(path, 'wb') as f:
                f.write(data)
    if '--list' in argv:
        return 0
    for set_ in ('crafted', 'probe'):
        for n in sorted(os.listdir(os.path.join(CORPUS, set_))):
            if '%s/%s' % (set_, n) not in seen:
                print('NOT BUILT HERE %s/%s' % (set_, n))
                bad += 1
    print('%d streams (%d crafted, %d probe, %d small); kill checks %d; %s' % (
        len(seen), sum(1 for k in seen if k.startswith('crafted/')), sum(1 for k in seen if k.startswith('probe/')),
        sum(1 for k in seen if k.startswith('small/')), len(KILLS),
        ('%d differ' % bad if bad else 'all match the committed corpus') if check else 'written'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
