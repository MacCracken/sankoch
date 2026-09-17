#!/bin/sh
# brotli-smoke.sh — differential check of sankoch's Brotli decoder against the reference
# `brotli -d` (1.2.0). Local only (not CI). Builds programs/brotli_smoke.cyr, then:
#
#   1. committed corpus: every tests/data/brotli/MANIFEST.tsv row — sankoch's
#      verdict must equal the manifest's `expect`; ok rows must `cmp` equal to `brotli -dc`; reject
#      rows must also fail under `brotli -d` (except large-window rejects, which the CLI accepts).
#   2. google/brotli v1.2.0 tests/testdata: all 45 *.compressed* streams and their
#      originals, kept in build/brotli-smoke/testdata/ (fetched with curl from
#      raw.githubusercontent.com when missing); every file must match the sha256 list below. Each
#      stream must decode and `cmp` equal to its original.
#   3. sweep: CLI-encoded inputs (text, repetition, random, source, a mix of text + random + records
#      that yields uncompressed and compressed meta-blocks, an ELF binary, and UTF-8 words from the
#      static dictionary) at q 0..11 x w {10,12,16,18,22,24}; sankoch must
#      decode each byte-identically.
#   4. font: if ~/Repos/rekha/fonts/LiberationSans-Regular.ttf is present with the pinned
#      sha256, `brotli -q 11 -w 22` must be the WOFF2-shaped 169,278-byte stream (sha256 pinned) and
#      decode byte-exact (kept as build/brotli-smoke/font.q11w22.br for the bench's font line), then
#      q {0,5,9,10} x w {10,16,24}; otherwise SKIP.
#   5. must reject: `--large_window` streams exit 24 (ERR_UNSUPPORTED_FORMAT).
#   6. trailing/truncation agreement on CLI output (random input: uncompressed meta-blocks) and
#      on alice29.txt.compressed (compressed, dictionary): + 1 zero byte, + 16 garbage
#      bytes, + a second stream, cut at n-1 and at n/2 — sankoch exits 23 and `brotli -d` fails too.
#   7. aarch64 (optional): if qemu-aarch64 and cycc_aarch64 exist, cross-build brotli_smoke
#      and re-run every step-1 row under qemu: same exit code and byte-identical output as x86_64.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
BIN="build/brotli_smoke"
W="build/brotli-smoke"
TD="$W/testdata"
TD_URL="https://raw.githubusercontent.com/google/brotli/v1.2.0/tests/testdata"
FONT="$HOME/Repos/rekha/fonts/LiberationSans-Regular.ttf"
FONT_SHA="baccc64becc3eb7d104b7c84d99f5314a0a1f896e2b3ea6c2f22fc08d2003bee"
FONT_BR_SHA="18cb33bd187269652e12ffe40978c86ae9e17162525a2696ccc0834c1a45886f"
for t in brotli cmp head od awk sha256sum; do
    command -v "$t" >/dev/null 2>&1 || { echo "ERROR: missing '$t'"; exit 1; }
done
V="$(brotli --version 2>&1)"
echo "reference: $V"
case "$V" in *1.2.0*) ;; *) echo "WARNING: expected brotli 1.2.0";; esac

CYRIUS_NO_WARN_PIN_DRIFT=1 CYRIUS_NO_WARN_SHADOW_LIB=1 cyrius build programs/brotli_smoke.cyr "$BIN" >/dev/null 2>&1 \
    || { echo "ERROR: build failed"; exit 1; }
mkdir -p "$W/tmp"

# google/brotli v1.2.0 tests/testdata (git blob SHA-1s checked against the GitHub listing at the tag).
testdata_sums() {
    cat <<'SUMS'
41bd4c895e9fb36d74bc97db5092872a24267e3b0455ff6152b0d262faa00d49  10x10y
d666afc0f6c35d8d7796175aa9a68f16ba59afedee946d4bce9167f6c86e0b84  10x10y.compressed
be4d3ed1fc5f5cfa00735b28605a975f3293fa235d23abb1d9dea380fba0fb87  64x
f0273c38c6a55c1d9ccb047da04bacdc4bb07acc44ff83871e6b3490dfc2c313  64x.compressed
7467306ee0feed4971260f3c87421154a05be571d944e9cb021a5713700c38f0  alice29.txt
69e902ef5cd9247302e4f66c313271bcff32eeb38e5eec7ca7744cf98106d5c2  alice29.txt.compressed
eaa3526fe53859f34ecdf255712f9ecf0b2c903451d4755b2edaa2e2599cb0fc  asyoulik.txt
605f6bdf129de59fb490f55180f3183e44ff7e2eab88ee931bd51a3757434404  asyoulik.txt.compressed
a6dbac2165542001c574fe1d5ed6ca646203660c228cac57b47a9fec68c20217  backward65536
757a524ce5fb43ea5e150b919ff635fd494142508d779f39e48e29ba1f61fb86  backward65536.compressed
69e902ef5cd9247302e4f66c313271bcff32eeb38e5eec7ca7744cf98106d5c2  compressed_file
ee6a6e2c37f742596f6fd5a11f186c70687b60b46f4998795d4e8f33d14eccb0  compressed_file.compressed
9538e078cb2d9493befede2c004dafcfcbf5a3caf0329285e7d4d49b48da0734  compressed_repeated
5839e626bc601d2d7e121408a0af76676369de5dc5102329ffc05ef16f0b16b7  compressed_repeated.compressed
0817dfe4fe7b6e29e63bbb048a785f7cbe67dc3188f96df5b5bc69826ca2a6e6  cp1251-utf16le
d69e14971ccd758e47ba4e6bb13df1b23fcfd3d9586674bd4b46130accffeca5  cp1251-utf16le.compressed
37465d3004d504c3d4320de2f821fa42f79a10917421cf1872ace46cfb152c42  cp852-utf8
38f328ac5b0228a304ce18a7a81bd69dfbfd8d28baa7106e0d107e9eef4e6cee  cp852-utf8.compressed
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  empty
67586e98fad27da0b9968bc039a1ef34c939b9b8e523a8bef89d478608c5ecf6  empty.compressed
67586e98fad27da0b9968bc039a1ef34c939b9b8e523a8bef89d478608c5ecf6  empty.compressed.00
ac38783f6a3b2fe3b579718d6ba8493a456d800665b4433a0e7c823cff90a603  empty.compressed.01
ef1534d0c6cfe8a961a19e64689dc8ba07d92b0498121852cc77c7fab995e9e2  empty.compressed.02
433a0fdd4ca1453e5a512cfbbea0a51b8fd138de3198e064f8ed8f23f6b83572  empty.compressed.03
e25be31e89368225296188140d8db9b7c6aef9060329a255bae3ac60b12cc2b1  empty.compressed.04
89e451d0952dc7cef33e71a58cbf816825c210cfb5e9a61e0aa5f98d14b46302  empty.compressed.05
83d9749292117a7555982bfdbec3c4bd6eebc4ccd972e62d55f08e74217a1adb  empty.compressed.06
f8acfa9c2f5dc317a07919235f2c987d7632516e035bd75a41f0e5da8752cf6e  empty.compressed.07
4e07408562bedb8b60ce05c1decfe3ad16b72230967de01f640b7e4729b49fce  empty.compressed.08
ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d  empty.compressed.09
7902699be42c8a8e46fbbb4501726517e86b22c56a189f7625a6da49081b2451  empty.compressed.10
19581e27de7ced00ff1ce50b2047e7a567c76b1cbaebabe5ef03f7c3017bb5b7  empty.compressed.11
41b805ea7ac014e23556e98bb374702a08344268f92489a02f0880849394a1e4  empty.compressed.12
380918b946a526640a40df5dced6516794f3d97bbd9e6bb553d037c4439f31c3  empty.compressed.13
8a8de823d5ed3e12746a62ef169bcf372be0ca44f0a1236abc35df05d96928e1  empty.compressed.14
58f7b0780592032e4d8602a3e8690fb2c701b2e1dd546e703445aabd6469734d  empty.compressed.15
592b1bea772c8f6478bbf8ee7965c9697887d68fbbe07224c5d1680056cbe6de  empty.compressed.16
95a77d2d0275fa7d30042c567a78025d5b79ed96967873de8d57e1d152b890c4  empty.compressed.17
1f3710654b87dc9a31778bfb09d476dca2dc96ac63f0d0ef9f6de17f363a1b2b  empty.compressed.18
5314ba1dbb03f471df88bec6cd120a938ef60d0fd3511c5c1dce61bf7463245f  lcet10.txt
0b35d0fdd8513ccceee08d5a4a0e771aa0ed6b8647ffeba75ac956b1b6e9fd44  lcet10.txt.compressed
bf076e57b5e6a8b648f1f0f1d7815cafcdf36c636ec08a547380b56685458101  mapsdatazrh
a01fb86df686ca38d90aeead4a7c49392937ac05367bed390fb0d878dd5b626b  mapsdatazrh.compressed
937ad127fe0e373e0e267d11905f2bca154f40fe6fd438b6ddcce40de2ddcd99  monkey
37bcdd7a42a6c5b119926d5af0f0d4e9162304592a2ded12c8fe9b06bf3908d9  monkey.compressed
07e2e0b461af78c7c647cb53dab39de560198e16f799b4516eccf0fbd69f764c  plrabn12.txt
9470506129c6e067e36e3c85cd72fc83ee1ec88b01276a89e714ec9b5b47daa4  plrabn12.txt.compressed
d7a8fbb307d7809469ca9abcb0082e4f8d5651e46d3cdb762d02d0bf37c9e592  quickfox
319f52f063ba1fd6b50414d4f7f4ef77694bece4fa41f63968d96a375a8cfb02  quickfox.compressed
254fdc641d1a65d0b1e427e4b0a1e16a96a5242adb98af71833782ba99c3dd82  quickfox_repeated
f732c7cfd6e33481e99352ed901b90647a6177dc3e34f5d1de1658c24e2d6e5a  quickfox_repeated.compressed
3035553aebbac63be49232495f41022bd9de43c6818917f3865e12ce8808b39e  random_org_10k.bin
b20da1957453441b81ecfed5dea559fe00eb1cc89c6647c1c3348dc645830497  random_org_10k.bin.compressed
1fb2529b0c6fbf80a60d2bb4c20efba2fff6cecb0c52d42693d404501064f407  ukkonooa
92f59fc5a282056ef34c9521920baf3bf609ca57c8abd5a286fb4833aede421e  ukkonooa.compressed
4b68ab3847feda7d6c62c1fbcbeebfa35eab7351ed5e78f4ddadea5df64b8015  x
cd094a625b695542a1d37b3a11ea849d8db9584a2f9df4e60cf6158bb39bbf61  x.compressed
69619f0d475e644c35ffeab36b4868a16a7382518d848c3a9a2c91db722c83ae  x.compressed.00
7ff671e6adc5e24be8269e7345ebcf16d94766ffcd95323e137e848c972efe47  x.compressed.01
c8d419e71a8bded7281954eda0a0f3cbe5aeeae31920fd5075b993089ce7cb0a  x.compressed.02
42db916a1a0954936cdb099292d10851228037eba679af5bbe402106ef209aa5  x.compressed.03
7609128715518308672067aab169e24944ead24e3d732aab8a8f0b7013a65564  xyzzy
c3f042a6be42887f842324d0e39dabd0d873e1676cd3dd2d7e2824242b318f14  xyzzy.compressed
8a39d2abd3999ab73c34db2476849cddf303ce389b35826850f9a700589b4a90  zeros
d1236d7fdab24209a747aa471f1bf33765b27adfd676355d4b4b310195dca49f  zeros.compressed
3f54e9caa8aa46d5eafde978d92ab5ebff42bac1396327320430c3b02fdcb77a  zerosukkanooa
be9e662a29166105aa011613bbc1209e584c4e45d738334e69c4eb8626ecfe92  zerosukkanooa.compressed
SUMS
}

err_code() {
    case "$1" in
        ok) echo 0;; ERR_CORRUPT_DATA) echo 23;; ERR_UNSUPPORTED_FORMAT) echo 24;;
        ERR_INVALID_HUFFMAN) echo 28;; ERR_MATCH_OUT_OF_RANGE) echo 29;; ERR_CHECKSUM_MISMATCH) echo 25;;
        *) echo 99;;
    esac
}
sha() { sha256sum "$1" | cut -d' ' -f1; }
run_sankoch() {   # $1 = stream file; sets RC, output in $W/out
    cp "$1" "$W/in.br"
    rm -f "$W/out"
    "$BIN"; RC=$?
}

total=0; pass=0; rc=0
fail() { echo "  FAIL $*"; rc=1; }

# ---- 1. committed corpus ----
c_total=0; c_pass=0
while IFS="$(printf '\t')" read -r path needs expect out_len out_crc sha origin; do
    case "$path" in '#'*|path|'') continue;; esac
    c_total=$((c_total + 1))
    f="tests/data/brotli/$path"
    run_sankoch "$f"
    want=$(err_code "$expect")
    if [ "$RC" -ne "$want" ]; then fail "$path: sankoch exit $RC, manifest $expect ($want)"; continue; fi
    if [ "$expect" = "ok" ]; then
        brotli -dc "$f" > "$W/tmp/ref" 2>/dev/null || { fail "$path: brotli -d rejects an ok row"; continue; }
        if [ "$out_len" -eq 0 ]; then [ -s "$W/out" ] && { fail "$path: non-empty output"; continue; }
        else cmp -s "$W/out" "$W/tmp/ref" || { fail "$path: output differs from brotli -d"; continue; }
        fi
    else
        if brotli -dc "$f" > /dev/null 2>&1; then
            [ "$expect" = "ERR_UNSUPPORTED_FORMAT" ] || { fail "$path: brotli -d accepts a reject row"; continue; }
        fi
    fi
    c_pass=$((c_pass + 1))
done < tests/data/brotli/MANIFEST.tsv
echo "  corpus: $c_pass/$c_total rows agree"
total=$((total + c_total)); pass=$((pass + c_pass))

# ---- 2. google testdata ----
mkdir -p "$TD"
testdata_sums > "$W/tmp/testdata.sha256"
g_total=0; g_pass=0; g_fetch=0; g_files=0
while read -r sum name; do
    f="$TD/$name"
    if [ ! -f "$f" ] || [ "$(sha "$f")" != "$sum" ]; then
        if command -v curl >/dev/null 2>&1 && curl -fsSL -o "$f.part" "$TD_URL/$name"; then
            mv "$f.part" "$f"; g_fetch=$((g_fetch + 1))
        else
            rm -f "$f.part"
        fi
    fi
    if [ ! -f "$f" ] || [ "$(sha "$f")" != "$sum" ]; then fail "testdata $name: missing or sha256 mismatch"; continue; fi
    g_files=$((g_files + 1))
done < "$W/tmp/testdata.sha256"
for name in $(awk '$2 ~ /\.compressed/ { print $2 }' "$W/tmp/testdata.sha256"); do
    g_total=$((g_total + 1))
    orig="$TD/$(printf '%s' "$name" | sed 's/\.compressed\(\.[0-9][0-9]*\)\{0,1\}$//')"
    [ -f "$TD/$name" ] && [ -f "$orig" ] || { fail "testdata $name: stream or original missing"; continue; }
    run_sankoch "$TD/$name"
    if [ "$RC" -ne 0 ]; then fail "testdata $name: sankoch exit $RC"; continue; fi
    if [ -s "$orig" ]; then cmp -s "$W/out" "$orig" || { fail "testdata $name: output differs from the original"; continue; }
    else [ -s "$W/out" ] && { fail "testdata $name: non-empty output"; continue; }
    fi
    g_pass=$((g_pass + 1))
done
echo "  google testdata: $g_pass/$g_total streams decode to their originals ($g_files files verified, $g_fetch fetched)"
total=$((total + g_total)); pass=$((pass + g_pass))

# ---- 3. sweep ----
seq 1 20000 | tr '\n' ' '                                         > "$W/tmp/text.bin"
yes 'AGNOS-the-sovereign-operating-system-0123' | head -c 300000   > "$W/tmp/repeat.bin"
head -c 200000 /dev/urandom                                       > "$W/tmp/rand.bin"
cat src/*.cyr                                                     > "$W/tmp/source.bin"
{ head -c 2048 "$W/tmp/source.bin"; head -c 1100 /dev/urandom; seq 1 900; } > "$W/tmp/mixed.bin"
cp "$BIN" "$W/tmp/elf.bin"
tr '\000' ' ' < docs/sources/brotli/dictionary.bin                > "$W/tmp/utf8.bin"
QS="0 1 2 3 4 5 6 7 8 9 10 11"
s_total=0; s_pass=0
for inp in rand text repeat source mixed elf utf8; do
    for q in $QS; do
        for w in 10 12 16 18 22 24; do
            s_total=$((s_total + 1))
            brotli -c -q "$q" -w "$w" "$W/tmp/$inp.bin" > "$W/tmp/sweep.br" || { fail "encode $inp q$q w$w"; continue; }
            run_sankoch "$W/tmp/sweep.br"
            if [ "$RC" -ne 0 ]; then fail "sweep $inp q$q w$w: sankoch exit $RC"; continue; fi
            cmp -s "$W/out" "$W/tmp/$inp.bin" || { fail "sweep $inp q$q w$w: output differs"; continue; }
            s_pass=$((s_pass + 1))
        done
    done
done
echo "  sweep: $s_pass/$s_total byte-identical"
total=$((total + s_total)); pass=$((pass + s_pass))

# ---- 4. font ----
if [ -f "$FONT" ] && [ "$(sha "$FONT")" = "$FONT_SHA" ]; then
    f_total=0; f_pass=0
    for qw in "11 22" "0 10" "0 16" "0 24" "5 10" "5 16" "5 24" "9 10" "9 16" "9 24" "10 10" "10 16" "10 24"; do
        set -- $qw
        f_total=$((f_total + 1))
        brotli -c -q "$1" -w "$2" "$FONT" > "$W/tmp/font.br" || { fail "font encode q$1 w$2"; continue; }
        if [ "$1" = 11 ]; then
            n=$(wc -c < "$W/tmp/font.br")
            [ "$n" -eq 169278 ] && [ "$(sha "$W/tmp/font.br")" = "$FONT_BR_SHA" ] \
                || { fail "font q11 w22: $n B, not the pinned 169,278-byte stream"; continue; }
            cp "$W/tmp/font.br" "$W/font.q11w22.br"   # bench input (tests/bcyr/sankoch.bcyr)
        fi
        run_sankoch "$W/tmp/font.br"
        if [ "$RC" -ne 0 ]; then fail "font q$1 w$2: sankoch exit $RC"; continue; fi
        cmp -s "$W/out" "$FONT" || { fail "font q$1 w$2: output differs"; continue; }
        f_pass=$((f_pass + 1))
    done
    echo "  font: $f_pass/$f_total LiberationSans streams byte-identical (q11 w22 = 169,278 B)"
    total=$((total + f_total)); pass=$((pass + f_pass))
else
    echo "  SKIP font ($FONT absent or not the pinned file)"
fi

# ---- 5. must reject: large window ----
l_pass=0
for lw in 25 30; do
    total=$((total + 1))
    brotli -c -q 11 --large_window="$lw" "$W/tmp/rand.bin" > "$W/tmp/lw.br"
    run_sankoch "$W/tmp/lw.br"
    if [ "$RC" -eq 24 ]; then pass=$((pass + 1)); l_pass=$((l_pass + 1)); else fail "large_window=$lw: exit $RC, want 24"; fi
done
echo "  large window: $l_pass/2 rejected with exit 24"

# ---- 6. trailing data and truncation agreement ----
brotli -c -q 5 -w 16 "$W/tmp/rand.bin" > "$W/tmp/base_rand.br"
BASES="base_rand"
if [ -f "$TD/alice29.txt.compressed" ]; then
    cp "$TD/alice29.txt.compressed" "$W/tmp/base_alice.br"
    BASES="base_rand base_alice"
fi
t_total=0; t_pass=0
for b in $BASES; do
    n=$(wc -c < "$W/tmp/$b.br")
    printf 'A' | tr 'A' '\000' | cat "$W/tmp/$b.br" - > "$W/tmp/t_zero.br"
    head -c 16 /dev/urandom | cat "$W/tmp/$b.br" - > "$W/tmp/t_garbage.br"
    cat "$W/tmp/$b.br" "$W/tmp/$b.br" > "$W/tmp/t_second.br"
    head -c $((n - 1)) "$W/tmp/$b.br" > "$W/tmp/t_cut1.br"
    head -c $((n / 2)) "$W/tmp/$b.br" > "$W/tmp/t_cut50.br"
    for c in t_zero t_garbage t_second t_cut1 t_cut50; do
        t_total=$((t_total + 1))
        run_sankoch "$W/tmp/$c.br"
        if brotli -dc "$W/tmp/$c.br" > /dev/null 2>&1; then fail "$b $c: brotli -d accepts"; continue; fi
        if [ "$RC" -eq 23 ]; then t_pass=$((t_pass + 1)); else fail "$b $c: sankoch exit $RC, want 23"; fi
    done
done
echo "  trailing / truncation: $t_pass/$t_total rejected with exit 23 and by brotli -d ($BASES)"
total=$((total + t_total)); pass=$((pass + t_pass))

# ---- 7. aarch64 under qemu ----
if command -v qemu-aarch64 >/dev/null 2>&1 && command -v cycc_aarch64 >/dev/null 2>&1; then
    A64="build/brotli_smoke-aarch64"
    if CYRIUS_NO_WARN_PIN_DRIFT=1 CYRIUS_NO_WARN_SHADOW_LIB=1 cyrius build --aarch64 programs/brotli_smoke.cyr "$A64" >/dev/null 2>&1; then
        a_total=0; a_pass=0
        while IFS="$(printf '\t')" read -r path needs expect rest; do
            case "$path" in '#'*|path|'') continue;; esac
            a_total=$((a_total + 1))
            run_sankoch "tests/data/brotli/$path"
            xrc=$RC
            if [ -f "$W/out" ]; then mv "$W/out" "$W/tmp/x86.out"; else rm -f "$W/tmp/x86.out"; fi
            rm -f "$W/out"
            qemu-aarch64 "$A64"; arc=$?
            if [ "$arc" -ne "$xrc" ]; then fail "aarch64 $path: exit $arc, x86_64 $xrc"; continue; fi
            if [ -f "$W/tmp/x86.out" ]; then
                cmp -s "$W/out" "$W/tmp/x86.out" || { fail "aarch64 $path: output differs from x86_64"; continue; }
            fi
            a_pass=$((a_pass + 1))
        done < tests/data/brotli/MANIFEST.tsv
        echo "  aarch64: $a_pass/$a_total corpus rows match x86_64 under qemu"
        total=$((total + a_total)); pass=$((pass + a_pass))
    else
        fail "aarch64 cross-build of programs/brotli_smoke.cyr"
    fi
else
    echo "  SKIP aarch64 (qemu-aarch64 or cycc_aarch64 not found)"
fi

echo ""
if [ "$rc" -eq 0 ]; then
    echo "brotli-smoke: PASS — $pass/$total"
else
    echo "brotli-smoke: FAIL — $pass/$total"
fi
exit $rc
