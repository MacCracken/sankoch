#!/usr/bin/env python3
"""brotli_ref_decoder.py -- strict RFC 7932 Brotli reference decoder (stdlib only) with feature stats.

Dev-time oracle for sankoch's Brotli corpus (scripts/brotli-manifest.py); never run by CI.
Static data comes from the committed authority files: docs/sources/brotli/dictionary.bin and
docs/sources/brotli/tables.txt (transforms, context LUTs), both derived from google/brotli
v1.2.0 (MIT, docs/sources/brotli/LICENSE.brotli) and RFC 7932.

Second oracle for the sankoch Brotli corpus: it decodes a stream, mirrors the
reference C decoder's strictness checks (exuberant nibbles, padding bits, prefix-code
space, transform id range, distance validity, trailing bits), and records which
format features the stream exercises, so the corpus can be audited for coverage.

usage: brotli_ref_decoder.py FILE [--stats] [--out OUT] [--mutant NAME]
exit 0 = decoded, 1 = rejected (message on stderr).

Mutants (decode(data, stats, mutant=NAME); scripts/brotli-manifest.py records which committed rows
each one changes, so a rule with no witness in the corpus is visible):
  M1     block-type history starts at prev = 0 instead of 1 (RFC 7932 §6)
  M2     every literal block type uses the context mode of block type 0 (§7.1)
  M3     block-type state is not reset at a compressed meta-block (carried from the previous one)
  E6977  an implicit distance (insert-and-copy codes 0..127) also steps the distance block count
         and may switch the distance block type (the reading RFC errata 6977 rules out)
  D1     a static dictionary reference whose distance came from an explicit distance code >= 1 pushes
         that distance onto the last-4-distances ring, as an LZ copy does (RFC 7932 §4: only
         backward references update it; decode.c 2190 compensates the ring index for dictionary words)
  D2     the same, but only for dictionary references reached through a short distance code 4..15
"""
import os, re, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'docs', 'sources', 'brotli')


def _table(name):
    cur = None
    for ln in open(os.path.join(DATA, 'tables.txt')):
        if ln.startswith('# ' + name + ' '):
            cur = name
            continue
        if cur and ln.strip() and not ln.startswith('#'):
            return [int(x) for x in ln.strip().split(',')]
    raise SystemExit('table %s not found in tables.txt' % name)


class BrotliError(Exception):
    pass


# ---------------------------------------------------------------- static data
def _load_dict():
    with open(os.path.join(DATA, 'dictionary.bin'), 'rb') as f:
        d = f.read()
    if len(d) != 122784:
        raise SystemExit('dictionary.bin must be 122784 bytes')
    return d


DICT = _load_dict()
NDBITS = [0, 0, 0, 0, 10, 10, 11, 11, 10, 10, 10, 10, 10, 9, 9, 8, 7, 7, 8, 7, 7, 6, 6, 5, 5]
DOFFSET = [0, 0, 0, 0, 0, 4096, 9216, 21504, 35840, 44032, 53248, 63488, 74752, 87040,
           93696, 100864, 104704, 106752, 108928, 113536, 115968, 118528, 119872, 121280, 122016]

PREFIX_SUFFIX = (b"\1 \2, \10 of the \4 of \2s \1.\5 and \4 "
                 b"in \1\"\4 to \2\">\1\n\2. \1]\5 for \3 a \6 "
                 b"that \1\'\6 with \6 from \4 by \1(\6. T"
                 b"he \4 on \4 as \4 is \4ing \2\n\t\1:\3ed "
                 b"\2=\"\4 at \3ly \1,\2=\'\5.com/\7. This \5"
                 b" not \3er \3al \4ful \4ive \5less \4es"
                 b"t \4ize \2\xc2\xa0\4ous \5 the \2e \0")
PS_MAP = [0x00, 0x02, 0x05, 0x0E, 0x13, 0x16, 0x18, 0x1E, 0x23, 0x25,
          0x2A, 0x2D, 0x2F, 0x32, 0x34, 0x3A, 0x3E, 0x45, 0x47, 0x4E,
          0x55, 0x5A, 0x5C, 0x63, 0x68, 0x6D, 0x72, 0x77, 0x7A, 0x7C,
          0x80, 0x83, 0x88, 0x8C, 0x8E, 0x91, 0x97, 0x9F, 0xA5, 0xA9,
          0xAD, 0xB2, 0xB7, 0xBD, 0xC2, 0xC7, 0xCA, 0xCF, 0xD5, 0xD8]
assert len(PREFIX_SUFFIX) == 217


def _load_transforms():
    pre, typ, suf = _table('TRANSFORM_PREFIX_ID'), _table('TRANSFORM_TYPE'), _table('TRANSFORM_SUFFIX_ID')
    out = list(zip(pre, typ, suf))
    assert len(out) == 121, len(out)
    return out


TRANSFORMS = _load_transforms()


def _ps(i):
    off = PS_MAP[i]
    n = PREFIX_SUFFIX[off]
    return PREFIX_SUFFIX[off + 1:off + 1 + n]


def _upper(b, i):
    c = b[i]
    if c < 0xC0:
        if 97 <= c <= 122:
            b[i] ^= 32
        return 1
    if c < 0xE0:
        if i + 1 < len(b):
            b[i + 1] ^= 32
        return 2
    if i + 2 < len(b):
        b[i + 2] ^= 5
    return 3


def transform_word(word, tid):
    pre, t, suf = TRANSFORMS[tid]
    w = bytearray(word)
    if 1 <= t <= 9:
        w = w[:max(0, len(w) - t)]
    elif 12 <= t <= 20:
        w = w[t - 11:]
    if t == 10 and w:
        _upper(w, 0)
    elif t == 11:
        i = 0
        while i < len(w):
            i += _upper(w, i)
    return _ps(pre) + bytes(w) + _ps(suf)


def _load_ctx():
    nums = []
    for mode in ('LSB6', 'MSB6', 'UTF8', 'SIGNED'):
        nums += _table('CONTEXT_LUT_' + mode)
    assert len(nums) == 2048
    return nums


CTX = _load_ctx()

INS_BASE = [0, 1, 2, 3, 4, 5, 6, 8, 10, 14, 18, 26, 34, 50, 66, 98, 130, 194, 322, 578, 1090, 2114, 6210, 22594]
INS_EXTRA = [0, 0, 0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 7, 8, 9, 10, 12, 14, 24]
CPY_BASE = [2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14, 18, 22, 30, 38, 54, 70, 102, 134, 198, 326, 582, 1094, 2118]
CPY_EXTRA = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 7, 8, 9, 10, 24]
CELLS = [(0, 0, True), (0, 8, True), (0, 0, False), (0, 8, False), (8, 0, False), (8, 8, False),
         (0, 16, False), (16, 0, False), (8, 16, False), (16, 8, False), (16, 16, False)]
BL_BASE = [1, 5, 9, 13, 17, 25, 33, 41, 49, 65, 81, 97, 113, 145, 177, 209, 241, 305, 369, 497,
           753, 1265, 2289, 4337, 8433, 16625]
BL_EXTRA = [2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 6, 6, 7, 8, 9, 10, 11, 12, 13, 24]
CL_ORDER = [1, 2, 3, 4, 0, 5, 17, 6, 16, 7, 8, 9, 10, 11, 12, 13, 14, 15]


# ---------------------------------------------------------------- bit reader
class BitReader:
    def __init__(self, data):
        self.d = data
        self.pos = 0  # bit position

    def bits(self, n):
        v = 0
        for i in range(n):
            byte = self.pos >> 3
            if byte >= len(self.d):
                raise BrotliError('truncated input')
            v |= ((self.d[byte] >> (self.pos & 7)) & 1) << i
            self.pos += 1
        return v

    def align(self, what):
        while self.pos & 7:
            if self.bits(1):
                raise BrotliError('non-zero padding bits (%s)' % what)


# ---------------------------------------------------------------- prefix codes
class Code:
    def __init__(self, lengths):
        # lengths: dict symbol -> length (length 0 allowed only for single-symbol codes)
        self.single = None
        nz = {s: l for s, l in lengths.items() if l > 0}
        if len(lengths) == 1 and not nz:
            self.single = next(iter(lengths))
            return
        self.table = {}
        code = 0
        prev_len = 0
        for s, l in sorted(nz.items(), key=lambda x: (x[1], x[0])):
            code <<= (l - prev_len)
            prev_len = l
            self.table[(l, code)] = s
            code += 1
        self.maxlen = prev_len

    def decode(self, br):
        if self.single is not None:
            return self.single
        code = 0
        for l in range(1, self.maxlen + 1):
            code = (code << 1) | br.bits(1)
            s = self.table.get((l, code))
            if s is not None:
                return s
        raise BrotliError('invalid prefix code word')


def read_prefix_code(br, alphabet_size, stats, kind):
    hskip = br.bits(2)
    if hskip == 1:
        nsym = br.bits(2) + 1
        nbits = (alphabet_size - 1).bit_length()
        syms = []
        for _ in range(nsym):
            s = br.bits(nbits)
            if s >= alphabet_size:
                raise BrotliError('simple prefix code symbol %d >= alphabet %d (%s)' % (s, alphabet_size, kind))
            syms.append(s)
        if len(set(syms)) != nsym:
            raise BrotliError('duplicate symbol in simple prefix code (%s)' % kind)
        if nsym == 1:
            lens = [0]
            key = 'simple1'
        elif nsym == 2:
            lens = [1, 1]
            key = 'simple2'
        elif nsym == 3:
            lens = [1, 2, 2]
            key = 'simple3'
        else:
            tsel = br.bits(1)
            lens = [1, 2, 3, 3] if tsel else [2, 2, 2, 2]
            key = 'simple4t%d' % tsel
        stats['prefix_codes'][key] = stats['prefix_codes'].get(key, 0) + 1
        return Code(dict(zip(syms, lens)))
    # complex
    stats['prefix_codes']['complex'] = stats['prefix_codes'].get('complex', 0) + 1
    if hskip:
        stats['prefix_codes']['hskip%d' % hskip] = stats['prefix_codes'].get('hskip%d' % hskip, 0) + 1
    cl_lens = [0] * 18
    space = 32
    num = 0
    for i in range(hskip, 18):
        v = br.bits(2)
        if v == 0:
            l = 0
        elif v == 1:
            l = 4
        elif v == 2:
            l = 3
        else:
            if br.bits(1) == 0:
                l = 2
            elif br.bits(1) == 0:
                l = 1
            else:
                l = 5
        cl_lens[CL_ORDER[i]] = l
        if l:
            space -= 32 >> l
            num += 1
            if space <= 0:
                break
    if not (num == 1 or space == 0):
        raise BrotliError('code-length code %s (space=%d, codes=%d) (%s)' %
                          ('over-subscribed' if space < 0 else 'incomplete', space, num, kind))
    if num == 1:
        clc = Code({CL_ORDER_IDX: 0 for CL_ORDER_IDX in [cl_lens.index(max(cl_lens))]})
    else:
        clc = Code({s: l for s, l in enumerate(cl_lens) if l})
    lens = {}
    sym = 0
    prev = 8
    rep = 0
    rep_len = 0
    space = 32768
    while sym < alphabet_size and space > 0:
        p = clc.decode(br)
        if p < 16:
            rep = 0
            if p:
                lens[sym] = p
                prev = p
                space -= 32768 >> p
            sym += 1
        else:
            extra = 2 if p == 16 else 3
            new_len = prev if p == 16 else 0
            if rep_len != new_len:
                rep = 0
                rep_len = new_len
            old = rep
            if rep > 0:
                rep = (rep - 2) << extra
            rep += br.bits(extra) + 3
            delta = rep - old
            if sym + delta > alphabet_size:
                raise BrotliError('code-length repeat past alphabet end (%s)' % kind)
            for _ in range(delta):
                if rep_len:
                    lens[sym] = rep_len
                sym += 1
            if rep_len:
                space -= delta << (15 - rep_len)
    if space != 0:
        raise BrotliError('prefix code %s (space=%d) (%s)' %
                          ('over-subscribed' if space < 0 else 'incomplete', space, kind))
    return Code(lens)


def read_var256(br):
    if br.bits(1) == 0:
        return 1
    n = br.bits(3)
    if n == 0:
        return 2
    return 1 + (1 << n) + br.bits(n)


def read_block_len(br, code):
    s = code.decode(br)
    return BL_BASE[s] + br.bits(BL_EXTRA[s])


def read_context_map(br, size, ntrees, stats):
    rlemax = br.bits(4) + 1 if br.bits(1) else 0
    if rlemax:
        stats['features'].add('cmap_rle')
    code = read_prefix_code(br, ntrees + rlemax, stats, 'context map')
    m = []
    while len(m) < size:
        s = code.decode(br)
        if s == 0:
            m.append(0)
        elif s <= rlemax:
            reps = (1 << s) + br.bits(s)
            if len(m) + reps > size:
                raise BrotliError('context map RLE run past end')
            m.extend([0] * reps)
        else:
            m.append(s - rlemax)
    if br.bits(1):
        stats['features'].add('cmap_imtf')
        mtf = list(range(256))
        for i in range(size):
            idx = m[i]
            v = mtf[idx]
            m[i] = v
            if idx:
                del mtf[idx]
                mtf.insert(0, v)
    for v in m:
        if v >= ntrees:  # unreachable per alphabet bound, kept as a guard
            raise BrotliError('context map tree index out of range')
    return m


MUTANTS = ('M1', 'M2', 'M3', 'E6977', 'D1', 'D2')


class BlockSwitch:
    def __init__(self, br, stats, cat, mutant=None, carry=None):
        self.n = read_var256(br)
        self.type = 0
        self.last = 0
        self.prev = 1
        if mutant == 'M1':
            self.prev = 0
        if mutant == 'M3' and carry is not None:
            self.type, self.last, self.prev = carry.type, carry.last, carry.prev
        if self.n >= 2:
            stats['features'].add('nbltypes_%s>1' % cat)
            self.tcode = read_prefix_code(br, self.n + 2, stats, 'block type ' + cat)
            self.ccode = read_prefix_code(br, 26, stats, 'block count ' + cat)
            self.left = read_block_len(br, self.ccode)
        else:
            self.left = 1 << 28

    def step(self, br):
        if self.left == 0:
            s = self.tcode.decode(br)
            if s == 0:
                t = self.prev
            elif s == 1:
                t = self.last + 1
            else:
                t = s - 2
            if t >= self.n:
                t -= self.n
            self.prev = self.last
            self.last = t
            self.type = t
            self.left = read_block_len(br, self.ccode)
        self.left -= 1


# ---------------------------------------------------------------- decoder
def decode(data, stats=None, mutant=None):
    if stats is None:
        stats = {}
    if mutant is not None and mutant not in MUTANTS:
        raise SystemExit('unknown mutant %r' % mutant)
    carry = {}
    stats['phase'] = 1   # 1 frame, 2 codes (compressed header), 3 cmds (command loop), 4 dict
    stats.update({'prefix_codes': {}, 'features': set(), 'cmodes': set(), 'meta_blocks': [],
                  'transforms': set(), 'dict_refs': 0, 'npostfix': set(), 'ndirect': set(),
                  'ntrees_l_max': 0, 'ntrees_d_max': 0, 'max_distance': 0})
    br = BitReader(data)
    if br.bits(1) == 0:
        wbits = 16
    else:
        n = br.bits(3)
        if n:
            wbits = 17 + n
        else:
            n = br.bits(3)
            if n == 1:
                raise BrotliError('invalid WBITS (large-window marker in RFC 7932 stream)')
            wbits = 8 + n if n else 17
    stats['wbits'] = wbits
    wsize = (1 << wbits) - 16
    out = bytearray()
    dist_rb = [16, 15, 11, 4]  # dist_rb[-1] = last
    while True:
        islast = br.bits(1)
        if islast:
            if br.bits(1):
                stats['meta_blocks'].append('last-empty')
                break
        mn = br.bits(2)
        if mn == 3:
            if br.bits(1):
                raise BrotliError('reserved bit set in metadata header')
            nbytes = br.bits(2)
            skip = 0
            for i in range(nbytes):
                b = br.bits(8)
                if i + 1 == nbytes and nbytes > 1 and b == 0:
                    raise BrotliError('exuberant metadata length byte')
                skip |= b << (8 * i)
            if nbytes:
                skip += 1
            br.align('metadata header')
            start = br.pos >> 3
            if start + skip > len(data):
                raise BrotliError('truncated input (metadata)')
            br.pos += skip * 8
            stats['meta_blocks'].append('metadata:%d%s' % (skip, ':last' if islast else ''))
            if islast:
                break
            continue
        nib = mn + 4
        mlen = 0
        for i in range(nib):
            v = br.bits(4)
            if i + 1 == nib and nib > 4 and v == 0:
                raise BrotliError('exuberant nibble in MLEN')
            mlen |= v << (4 * i)
        mlen += 1
        unc = 0 if islast else br.bits(1)
        if unc:
            br.align('uncompressed header')
            start = br.pos >> 3
            if start + mlen > len(data):
                raise BrotliError('truncated input (uncompressed)')
            out += data[start:start + mlen]
            br.pos += mlen * 8
            stats['meta_blocks'].append('uncompressed:%d' % mlen)
            continue
        stats['meta_blocks'].append('compressed:%d%s' % (mlen, ':last' if islast else ''))
        stats['phase'] = max(stats['phase'], 2)
        bL = BlockSwitch(br, stats, 'L', mutant, carry.get('L'))
        bI = BlockSwitch(br, stats, 'I', mutant, carry.get('I'))
        bD = BlockSwitch(br, stats, 'D', mutant, carry.get('D'))
        carry.update(L=bL, I=bI, D=bD)
        npostfix = br.bits(2)
        ndirect = br.bits(4) << npostfix
        stats['npostfix'].add(npostfix)
        stats['ndirect'].add(ndirect)
        cmodes = [br.bits(2) for _ in range(bL.n)]
        stats['cmodes'].update(cmodes)
        ntl = read_var256(br)
        stats['ntrees_l_max'] = max(stats['ntrees_l_max'], ntl)
        cmap_l = read_context_map(br, 64 * bL.n, ntl, stats) if ntl >= 2 else [0] * (64 * bL.n)
        ntd = read_var256(br)
        stats['ntrees_d_max'] = max(stats['ntrees_d_max'], ntd)
        cmap_d = read_context_map(br, 4 * bD.n, ntd, stats) if ntd >= 2 else [0] * (4 * bD.n)
        hl = [read_prefix_code(br, 256, stats, 'literal') for _ in range(ntl)]
        hi = [read_prefix_code(br, 704, stats, 'insert&copy') for _ in range(bI.n)]
        dalpha = 16 + ndirect + (48 << npostfix)
        hd = [read_prefix_code(br, dalpha, stats, 'distance') for _ in range(ntd)]
        if 'hdr1' not in stats:
            # First compressed meta-block header, fully parsed: the state a header-only decode must
            # reproduce (bit position after the last tree; initial block counts, 0 when NBLTYPES = 1).
            stats['hdr1'] = {'bitpos': br.pos, 'nbltypes': [bL.n, bI.n, bD.n],
                             'blen': [b.left if b.n >= 2 else 0 for b in (bL, bI, bD)],
                             'npostfix': npostfix, 'ndirect': ndirect, 'ntrees': [ntl, ntd],
                             'maps': bytes(cmodes) + bytes(cmap_l) + bytes(cmap_d)}
        rem = mlen
        stats['phase'] = max(stats['phase'], 3)
        pmask = (1 << npostfix) - 1
        while rem > 0:
            bI.step(br)
            cmd = hi[bI.type].decode(br)
            ioff, coff, dz = CELLS[cmd >> 6]
            ic = ioff + ((cmd >> 3) & 7)
            cc = coff + (cmd & 7)
            ilen = INS_BASE[ic] + br.bits(INS_EXTRA[ic])
            clen = CPY_BASE[cc] + br.bits(CPY_EXTRA[cc])
            for _ in range(ilen):
                bL.step(br)
                p1 = out[-1] if len(out) >= 1 else 0
                p2 = out[-2] if len(out) >= 2 else 0
                mode = cmodes[0 if mutant == 'M2' else bL.type]
                ctx = CTX[mode * 512 + p1] | CTX[mode * 512 + 256 + p2]
                out.append(hl[cmap_l[64 * bL.type + ctx]].decode(br))
                rem -= 1
                if rem < 0:
                    raise BrotliError('insert length exceeds meta-block length')
            if rem == 0:
                break
            if dz:
                if mutant == 'E6977':
                    bD.step(br)
                dist = dist_rb[-1]
                dcode = 0
            else:
                bD.step(br)
                dctx = 3 if clen > 4 else clen - 2
                dcode = hd[cmap_d[4 * bD.type + dctx]].decode(br)
                if dcode < 16:
                    if dcode < 4:
                        dist = dist_rb[3 - dcode]
                    else:
                        base = dist_rb[3] if dcode < 10 else dist_rb[2]
                        k = dcode - 4 if dcode < 10 else dcode - 10
                        delta = (k >> 1) + 1
                        dist = base - delta if (k & 1) == 0 else base + delta
                    if dist <= 0:
                        raise BrotliError('invalid distance (<= 0) from short code %d' % dcode)
                elif dcode < 16 + ndirect:
                    dist = dcode - 15
                else:
                    x = dcode - ndirect - 16
                    ndb = 1 + (x >> (npostfix + 1))
                    hcode = x >> npostfix
                    lcode = x & pmask
                    offset = ((2 + (hcode & 1)) << ndb) - 4
                    dist = ((offset + br.bits(ndb)) << npostfix) + lcode + ndirect + 1
            maxd = min(len(out), wsize)
            if dist > maxd:
                if 4 <= clen <= 24:
                    stats['phase'] = 4
                    stats.setdefault('first_dict_pos', len(out))   # output bytes before the first reference
                    wid = dist - maxd - 1
                    nb = NDBITS[clen]
                    idx = wid & ((1 << nb) - 1)
                    tid = wid >> nb
                    if tid >= 121:
                        raise BrotliError('invalid dictionary transform id %d' % tid)
                    word = DICT[DOFFSET[clen] + idx * clen:DOFFSET[clen] + (idx + 1) * clen]
                    w = transform_word(word, tid)
                    stats['dict_refs'] += 1
                    stats['transforms'].add(tid)
                    out += w
                    rem -= len(w)
                    if rem < 0:
                        raise BrotliError('dictionary word exceeds meta-block length')
                    if (mutant == 'D1' and dcode != 0) or (mutant == 'D2' and 4 <= dcode <= 15):
                        dist_rb = dist_rb[1:] + [dist]
                else:
                    raise BrotliError('distance %d beyond window (max %d) with copy length %d' % (dist, maxd, clen))
            else:
                stats['max_distance'] = max(stats['max_distance'], dist)
                if dcode != 0:
                    dist_rb = dist_rb[1:] + [dist]
                start = len(out) - dist
                for j in range(clen):
                    out.append(out[start + j])
                rem -= clen
                if rem < 0:
                    raise BrotliError('copy length exceeds meta-block length')
        if islast:
            break
    br.align('stream end')
    stats['consumed_bytes'] = br.pos >> 3
    stats['trailing_bytes'] = len(data) - (br.pos >> 3)
    return bytes(out)


def jsonable_stats(st):
    def conv(v):
        if isinstance(v, set):
            return sorted(v)
        if isinstance(v, (bytes, bytearray)):
            return v.hex()
        if isinstance(v, dict):
            return {k: conv(x) for k, x in v.items()}
        return v
    o = {}
    for k, v in st.items():
        o[k] = conv(v)
    mb = st.get('meta_blocks', [])
    if len(mb) > 12:
        kinds = {}
        for m in mb:
            kk = m.split(':')[0]
            kinds[kk] = kinds.get(kk, 0) + 1
        o['meta_blocks'] = kinds
    return o


def main():
    args = sys.argv[1:]
    path = args[0]
    data = open(path, 'rb').read()
    st = {}
    mutant = args[args.index('--mutant') + 1] if '--mutant' in args else None
    try:
        out = decode(data, st, mutant)
    except BrotliError as e:
        print('REJECT: %s' % e, file=sys.stderr)
        sys.exit(1)
    if '--out' in args:
        open(args[args.index('--out') + 1], 'wb').write(out)
    if st['trailing_bytes']:
        print('REJECT: %d trailing bytes after stream end' % st['trailing_bytes'], file=sys.stderr)
    if '--stats' in args:
        print(json.dumps(jsonable_stats(st)))
    sys.exit(1 if st['trailing_bytes'] else 0)


if __name__ == '__main__':
    main()
