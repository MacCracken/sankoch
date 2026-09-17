#!/usr/bin/env python3
"""brotli-manifest.py -- (re)generate tests/data/brotli/MANIFEST.tsv from the committed corpus.

    python3 scripts/brotli-manifest.py            # write tests/data/brotli/MANIFEST.tsv
    python3 scripts/brotli-manifest.py --check    # regenerate in memory, exit 1 if it differs

Dev-time only (needs /usr/bin/brotli 1.2.0); CI never runs it -- tests/tcyr/brotli_decompress.tcyr
reads the committed MANIFEST.tsv. Every stream under tests/data/brotli/{google,synth,probe,
crafted,small}/ becomes one row. Two oracles must agree on every verdict:

  * `brotli -dc` (the reference CLI): accept/reject and the output bytes;
  * scripts/brotli_ref_decoder.py (strict RFC 7932 Python decoder): the rejection reason, which
    maps to the sankoch ERR_* class (the REASONS table below), and the stage the stream needs.

The single documented disagreement is Large Window Brotli: the CLI always enables large window
and accepts those streams; RFC 7932 (and sankoch) reject them (ERR_UNSUPPORTED_FORMAT).
Trailing bytes after the final padding are a rejection (the CLI agrees).

Format:
    #brotli-manifest<TAB>v1<TAB>rows=<N><TAB>flipdigests=<M><TAB>headers=<K><TAB>kills=<J>
    path<TAB>needs<TAB>expect<TAB>out_len<TAB>out_crc32<TAB>stream_sha256<TAB>origin
    #flip<TAB><path><TAB><dst_cap><TAB><crc32 hex>
    #header<TAB><path><TAB><bitpos><TAB><nbl>,<nbi>,<nbd><TAB><blenl>,<bleni>,<blend><TAB>
        <npostfix>,<ndirect><TAB><ntreesl>,<ntreesd><TAB><maps crc32 hex>
    #kills<TAB><path><TAB><mutant>[,<mutant>...]

#header (one per row whose needs is cmds or dict): the reference decoder's state right after the
first compressed meta-block header -- the bit position after its last prefix code, NBLTYPES and
initial block counts per category (count 0 when NBLTYPES = 1), NPOSTFIX / NDIRECT, NTREES, and the
CRC-32 of the context modes followed by the literal and distance context maps. The tcyr checks a
header-only decode (test hook) against it from stage 2.

#kills (one per row that some reference-decoder mutant decodes differently -- verdict or output;
see scripts/brotli_ref_decoder.py MUTANTS): the corpus's witnesses for the block-switching rules
(M1 type history starts at prev = 1, M2 per-type context mode, M3 reset per compressed meta-block,
E6977 implicit distances leave the distance block count alone) and for the ring rule of static
dictionary references (D1 a dictionary reference with an explicit distance code >= 1 pushes the ring,
D2 the same through short codes 4..15 only). The block-switching mutants can only kill rows with
NBLTYPES > 1 in some category and the dictionary mutants only rows with a dictionary reference, so
each runs on those rows. Every stream scripts/brotli-craft.py registers in KILLS must be killed by
its named mutants, or generation stops. The tcyr does not read these lines.

needs: frame < codes < cmds < dict -- the highest decoder stage the stream exercises (for a
reject: the stage reached when the error is detected). The tcyr skips rows above its stage.

Flip digest (per #flip row): for bit i = 0..8n-1 (LSB-first per byte), decode the stream with bit
i flipped and dst_cap bytes of output room, appending to a running CRC-32 either byte 0x00
(rejected) or byte 0x01 + the 4-byte little-endian output length + the output bytes. A
large-window header counts as a reject; every accepted output must fit dst_cap.
"""
import hashlib
import importlib.util
import os
import struct
import subprocess
import sys
import zlib

sys.dont_write_bytecode = True     # dev tool: no __pycache__ next to the committed scripts

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
CORPUS = os.path.join(ROOT, 'tests', 'data', 'brotli')
DIRS = ['google', 'synth', 'probe', 'crafted', 'small']
ORIGIN = {
    'google': 'google/brotli v1.2.0 tests/testdata (MIT)',
    'synth': 'google/brotli v1.2.0 js/decode_synth_test.ts (MIT)',
    'probe': 'sankoch scripts/brotli-craft.py probe set (GPL-3.0)',
    'crafted': 'sankoch scripts/brotli-craft.py (GPL-3.0)',
    'small': 'brotli 1.2.0 CLI output',
}
FLIPS = [('small/hello.q0.br', 65536), ('small/records_4k.q5w12.br', 65536)]
STAGES = {1: 'frame', 2: 'codes', 3: 'cmds', 4: 'dict'}

# Reference-decoder reason prefix -> sankoch error class. An unmapped reason
# stops the generator: a new rejection kind needs a deliberate classification.
REASONS = [
    ('invalid WBITS', 'ERR_UNSUPPORTED_FORMAT'),
    ('truncated input', 'ERR_CORRUPT_DATA'),
    ('reserved bit set', 'ERR_CORRUPT_DATA'),
    ('exuberant', 'ERR_CORRUPT_DATA'),
    ('non-zero padding bits', 'ERR_CORRUPT_DATA'),
    ('trailing bytes', 'ERR_CORRUPT_DATA'),
    ('simple prefix code symbol', 'ERR_INVALID_HUFFMAN'),
    ('duplicate symbol in simple prefix code', 'ERR_INVALID_HUFFMAN'),
    ('code-length code', 'ERR_INVALID_HUFFMAN'),
    ('code-length repeat past alphabet', 'ERR_INVALID_HUFFMAN'),
    ('prefix code ', 'ERR_INVALID_HUFFMAN'),
    ('context map RLE run past end', 'ERR_CORRUPT_DATA'),
    ('insert length exceeds', 'ERR_CORRUPT_DATA'),
    ('copy length exceeds', 'ERR_CORRUPT_DATA'),
    ('dictionary word exceeds', 'ERR_CORRUPT_DATA'),
    ('invalid distance', 'ERR_MATCH_OUT_OF_RANGE'),
    ('invalid dictionary transform id', 'ERR_MATCH_OUT_OF_RANGE'),
    ('distance ', 'ERR_MATCH_OUT_OF_RANGE'),
]


def load_ref():
    spec = importlib.util.spec_from_file_location(
        'brotli_ref_decoder', os.path.join(ROOT, 'scripts', 'brotli_ref_decoder.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


REF = load_ref()


def load_craft_kills():
    spec = importlib.util.spec_from_file_location('brotli_craft', os.path.join(ROOT, 'scripts', 'brotli-craft.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.KILLS


BLOCK_MUTANTS = ('M1', 'M2', 'M3', 'E6977')
DICT_MUTANTS = ('D1', 'D2')
if set(BLOCK_MUTANTS + DICT_MUTANTS) != set(REF.MUTANTS):
    raise SystemExit('brotli-manifest.py: reference-decoder MUTANTS changed; classify the new mutant here')


def mutant_kills(data, expect, out, mutants):
    """Mutants whose verdict or output differs from the reference decoder's on this stream."""
    kills = []
    for m in mutants:
        st = {}
        try:
            mout = REF.decode(data, st, m)
            same = expect == 'ok' and not st['trailing_bytes'] and mout == out
        except Exception:                     # BrotliError, or a carried block type indexing past a tree list
            same = expect != 'ok'
        if not same:
            kills.append(m)
    return kills


def cli(data):
    p = subprocess.run(['brotli', '-dc'], input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode == 0, p.stdout


def classify(reason):
    for prefix, err in REASONS:
        if reason.startswith(prefix):
            return err
    raise SystemExit('unmapped reference-decoder reason: %r' % reason)


LAST = {}


def ref(data):
    """(expect, output, phase, largewin) per the strict reference decoder."""
    st = {}
    LAST.clear()
    LAST['st'] = st
    try:
        out = REF.decode(data, st)
    except REF.BrotliError as e:
        reason = str(e)
        return classify(reason), b'', st.get('phase', 1), reason.startswith('invalid WBITS')
    if st['trailing_bytes']:
        return 'ERR_CORRUPT_DATA', b'', st['phase'], False
    return 'ok', out, st['phase'], False


def verdict(data, label):
    expect, out, phase, largewin = ref(data)
    ok, cout = cli(data)
    if largewin:
        pass                                  # CLI accepts large window; RFC 7932 rejects
    elif ok != (expect == 'ok'):
        raise SystemExit('%s: oracles disagree (brotli -d %s, reference %s)'
                         % (label, 'accepts' if ok else 'rejects', expect))
    elif ok and cout != out:
        raise SystemExit('%s: oracles produce different output' % label)
    return expect, out, phase


def flip_digests(path, cap):
    data = open(os.path.join(CORPUS, path), 'rb').read()
    crc = 0
    for i in range(len(data) * 8):
        b = bytearray(data)
        b[i >> 3] ^= 1 << (i & 7)
        expect, out, phase = verdict(bytes(b), '%s bit %d' % (path, i))
        if expect == 'ok' and len(out) > cap:
            raise SystemExit('%s bit %d: accepted output %d B exceeds dst_cap %d'
                             % (path, i, len(out), cap))
        if expect == 'ok':
            crc = zlib.crc32(b'\x01' + struct.pack('<I', len(out)) + out, crc)
        else:
            crc = zlib.crc32(b'\x00', crc)
    return ['#flip\t%s\t%d\t%08x' % (path, cap, crc)]


def build():
    rows = []
    headers = []
    kills = []
    required = load_craft_kills()
    for d in DIRS:
        dp = os.path.join(CORPUS, d)
        if not os.path.isdir(dp):
            continue
        for name in sorted(os.listdir(dp)):
            rel = d + '/' + name
            data = open(os.path.join(dp, name), 'rb').read()
            expect, out, phase = verdict(data, rel)
            rows.append('\t'.join([rel, STAGES[phase], expect, str(len(out)),
                                   '%08x' % (zlib.crc32(out) if expect == 'ok' else 0),
                                   hashlib.sha256(data).hexdigest(), ORIGIN[d]]))
            if phase >= 3:
                h = LAST['st']['hdr1']
                headers.append('#header\t%s\t%d\t%s\t%s\t%d,%d\t%s\t%08x' % (
                    rel, h['bitpos'], ','.join(map(str, h['nbltypes'])), ','.join(map(str, h['blen'])),
                    h['npostfix'], h['ndirect'], ','.join(map(str, h['ntrees'])), zlib.crc32(h['maps'])))
            killed = []
            mutants = ()
            if any(f.startswith('nbltypes_') for f in LAST['st'].get('features', ())):
                mutants += BLOCK_MUTANTS
            if LAST['st'].get('dict_refs', 0) > 0:
                mutants += DICT_MUTANTS
            if mutants:
                killed = mutant_kills(data, expect, out, mutants)
                if killed:
                    kills.append('#kills\t%s\t%s' % (rel, ','.join(killed)))
            missing = [m for m in required.get(rel, ()) if m not in killed]
            if missing:
                raise SystemExit('%s: mutant(s) %s survive; brotli-craft.py requires them killed' % (rel, ','.join(missing)))
    flips = []
    for path, cap in FLIPS:
        flips += flip_digests(path, cap)
    head = ['#brotli-manifest\tv1\trows=%d\tflipdigests=%d\theaders=%d\tkills=%d' % (
        len(rows), len(flips), len(headers), len(kills)),
            'path\tneeds\texpect\tout_len\tout_crc32\tstream_sha256\torigin']
    return '\n'.join(head + rows + flips + headers + kills) + '\n'


def main(argv):
    ver = subprocess.run(['brotli', '--version'], stdout=subprocess.PIPE).stdout.decode().strip()
    if '1.2.0' not in ver:
        sys.stderr.write('warning: reference CLI is %r, manifest was built with brotli 1.2.0\n' % ver)
    text = build()
    target = os.path.join(CORPUS, 'MANIFEST.tsv')
    if '--check' in argv:
        same = os.path.exists(target) and open(target).read() == text
        print('MANIFEST.tsv %s' % ('up to date' if same else 'DIFFERS'))
        return 0 if same else 1
    with open(target, 'w', newline='\n') as f:
        f.write(text)
    print('wrote %s' % os.path.relpath(target, ROOT))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
