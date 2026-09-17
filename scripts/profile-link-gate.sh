#!/usr/bin/env bash
# profile-link-gate.sh — prove every distlib bundle LINKS and RUNS, not just that it is current.
#
# CI's dist gate (`cyrius distlib <p>` + a byte diff) proves a bundle matches src/. It says
# nothing about whether a consumer can build a program that CALLS into it, and 2.7.10–2.7.15
# shipped that gap in every profile: runtime.cyr's arena guard called `_sankoch_reset_tables`,
# which only the full bundle defined, so a probe that reached `zlib_decompress_capped` through
# dist/sankoch-zlib.cyr got "refusing to emit binary with 1 reachable undefined function(s)"
# (docs/development/issues/archived/2026-09-15-profile-bundles-call-sankoch-reset-tables-outside-their-closure.md).
#
# For EVERY profile in cyrius.cyml — `[lib]` (dist/sankoch.cyr) and each `[lib.<name>]`
# (dist/sankoch-<name>.cyr) — this gate:
#   1. REGISTRATION: if the bundle carries the arena guard, it must define
#      `_sankoch_reset_tables` exactly once, and that function must call exactly the
#      `_<module>_reset_tables` the bundle defines (rule: src/runtime.cyr). A module reset
#      left unregistered is a memoized pointer that survives an alloc_reset().
#   2. LINK: builds a probe (the [deps] stdlib includes + the bundle) that calls real public
#      entries of that profile on a reachable path. ANY "undefined function" line — including
#      "(call site may be unreachable)" — any "refusing to emit", or a non-zero build fails.
#   3. RUN: the probe decodes known vectors made by the reference CLIs (python zlib/gzip/
#      tarfile/zipfile, xz, bzip2, zstd, lz4) and round-trips generated data; then, for every
#      alloc-bearing profile, calls alloc_reset(), hands the whole previous arena to a victim
#      buffer, and runs the same calls again: output must still be exact, the victim must be
#      untouched, and the arena canary must have moved (proof the profile's reset path ran).
#   4. AGNOS: for every alloc-bearing profile, builds the same probe with `--agnos` (any
#      undefined function fails), then a LOCK-ONLY probe — the bundle plus
#      `_sankoch_lock(); _sankoch_unlock();` — under DCE, and fails if `_sankoch_arena_guard`
#      or `_sankoch_reset_tables` is listed dead: the lock path itself must reach the reset on
#      AGNOS (2.7.10–2.7.15: _sankoch_lock returned before the guard there). The full probe
#      cannot show that: 2.8.0's unlocked public builders (checksum, lz77, huffman) call the
#      guard directly and keep it alive whatever the lock does (review 2.8.0: the old check
#      caught that regression in 2 of 11 profiles). Build only: AGNOS syscalls do not run here.
#   A profile present in cyrius.cyml with no probe mapping below FAILS the gate — a new
#   `[lib.<name>]` forces a `probe_body_<name>`. A `[lib...]` header the parser cannot read
#   also fails, rather than silently skipping that profile.
#
# WHAT THIS GATE DOES NOT PROVE: that a module's `_<module>_reset_tables` zeroes EVERY global
# the module memoizes. The RUN check only notices a surviving pointer that the probe's own
# calls write through (measured: of 171 single-global omissions, 41 fail this gate). The
# per-global safety net is the inventory cell in tests/tcyr/arena_reset.tcyr — a new lazy
# global must be added to its module's reset AND to that cell.
#
# Usage: scripts/profile-link-gate.sh [--bundle-dir DIR] [--out DIR] [--manifest FILE] [--list-profiles]
#   --list-profiles  print the parsed profile names (`full` for [lib]) one per line and exit;
#                 CI's dist gate and release.yml loop over this so the list lives only in cyrius.cyml.
#   --bundle-dir  where sankoch*.cyr live (default: dist). Must be inside the repo: cycc
#                 rejects absolute include paths.
#   --out         probe/scratch dir (default: build/profile-link-gate). Not committed.
#   --manifest    manifest to read profiles + [deps] from (default: cyrius.cyml).
#
# The known-vector hex below was produced once with the reference tools (xz 5.x, bzip2 1.0.8,
# zstd -19, lz4 --content-size, brotli -q 11 -w 22, CPython zlib/gzip/tarfile/zipfile) over PG_TEXT x 4; it is
# static so CI needs none of those tools.
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 2

BUNDLE_DIR="dist"
OUT="build/profile-link-gate"
MANIFEST="cyrius.cyml"
LIST=0
while [ $# -gt 0 ]; do
    case "$1" in
        --list-profiles) LIST=1; shift ;;
        --bundle-dir) BUNDLE_DIR="$2"; shift 2 ;;
        --out) OUT="$2"; shift 2 ;;
        --manifest) MANIFEST="$2"; shift 2 ;;
        *) echo "usage: $0 [--bundle-dir DIR] [--out DIR] [--manifest FILE] [--list-profiles]" >&2; exit 2 ;;
    esac
done
case "$BUNDLE_DIR" in
    "$ROOT"/*) BUNDLE_DIR="${BUNDLE_DIR#"$ROOT"/}" ;;
    /*) echo "ERROR: --bundle-dir must be inside $ROOT (cycc rejects absolute includes)" >&2; exit 2 ;;
esac
BUNDLE_DIR="${BUNDLE_DIR%/}"

# --- manifest ---------------------------------------------------------------------------
# Every `[lib]` / `[lib.<name>]` table header, tolerating trailing blanks and a `#` comment.
# A header whose name is not [A-Za-z0-9_-]+ is reported as BAD and fails below — it must not
# silently drop out of the checked set.
PROFILES=$(awk '
    {
        line = $0
        sub(/[[:space:]]*#.*$/, "", line)
        sub(/[[:space:]]+$/, "", line)
    }
    line == "[lib]" { print "full"; next }
    line ~ /^\[lib\./ {
        n = substr(line, 6)
        if (n ~ /^[A-Za-z0-9_-]+\]$/) { print substr(n, 1, length(n) - 1) }
        else { print "BAD:" line }
    }
' "$MANIFEST")
NHEAD=$(grep -cE '^[[:space:]]*\[lib[].]' "$MANIFEST")
STDLIB=$(awk '
    /^\[deps\]/ { indeps = 1; next }
    /^\[/ { indeps = 0 }
    indeps && /^stdlib/ { inlist = 1; next }
    inlist && /\]/ { inlist = 0 }
    inlist { gsub(/[",[:space:]]/, ""); if ($0 != "") print }
' "$MANIFEST")
[ -n "$PROFILES" ] || { echo "ERROR: no [lib] profiles parsed from $MANIFEST" >&2; exit 2; }
[ -n "$STDLIB" ] || { echo "ERROR: no [deps] stdlib parsed from $MANIFEST" >&2; exit 2; }
if printf '%s\n' "$PROFILES" | grep -q '^BAD:'; then
    printf '%s\n' "$PROFILES" | grep '^BAD:' | while IFS= read -r bad; do
        echo "ERROR: unparseable profile header in $MANIFEST: ${bad#BAD:}" >&2
    done
    exit 1
fi
NPARSED=$(printf '%s\n' "$PROFILES" | grep -c .)
if [ "$NPARSED" != "$NHEAD" ]; then
    echo "ERROR: $MANIFEST has $NHEAD [lib...] headers but $NPARSED parsed as profiles" >&2
    exit 1
fi
if [ "$LIST" = 1 ]; then
    printf '%s\n' "$PROFILES"
    exit 0
fi
mkdir -p "$OUT"

# --- probe source -----------------------------------------------------------------------
# Shared helpers. PG_N = 332 = strlen(PG_TEXT) * 4, the payload every vector decodes to.
probe_prelude() {
    cat <<'CYR'
var PG_N = 332;
var _pg_len = 0;

fn pg_fail(msg): i64 {
    syscall(1, 2, "PROBE FAIL: ", 12);
    syscall(1, 2, msg, strlen(msg));
    syscall(1, 2, "\n", 1);
    syscall(60, 1);
    return 0;
}

fn pg_nib(c): i64 {
    if (c >= 97) { return c - 87; }
    if (c >= 65) { return c - 55; }
    return c - 48;
}

# Decode a hex literal into a fresh buffer; length in _pg_len.
fn pg_hex(hex): i64 {
    var n = strlen(hex) / 2;
    var out = alloc(n + 1);
    if (out == 0) { pg_fail("alloc"); }
    var i = 0;
    while (i < n) {
        store8(out + i, (pg_nib(load8(hex + i * 2)) << 4) | pg_nib(load8(hex + i * 2 + 1)));
        i = i + 1;
    }
    _pg_len = n;
    return out;
}

fn pg_payload(): i64 {
    var t = "sankoch profile link gate: the quick brown fox jumps over the lazy dog 0123456789. ";
    var tl = strlen(t);
    var p = alloc(tl * 4 + 1);
    var k = 0;
    while (k < 4) {
        memcpy(p + k * tl, t, tl);
        k = k + 1;
    }
    return p;
}

# 24 KB of skewed-alphabet text with short back-references: dynamic Huffman trees, real
# match finders, entropy-coded literals — the paths whose tables are lazily memoized.
fn pg_gen(n): i64 {
    var p = alloc(n);
    var r = 12345;
    var i = 0;
    while (i < n) {
        r = (r * 1103515245 + 12345) & 0x7FFFFFFF;
        var k = (r >> 16) & 255;
        if (i >= 64 && (k & 7) == 0) {
            store8(p + i, load8(p + i - 1 - ((r >> 8) % 60)));
        } else {
            store8(p + i, 97 + ((k * k) >> 11));
        }
        i = i + 1;
    }
    return p;
}

# `len` is what the call returned; `buf` must hold exactly `want_len` bytes equal to `want`.
fn pg_expect(len, buf, want, want_len, what): i64 {
    if (len != want_len) { pg_fail(what); }
    if (memeq(buf, want, want_len) != 1) { pg_fail(what); }
    return 0;
}
CYR
}

# Per-profile bodies: each emits `pg_body()`, the calls main runs twice. Whether the second
# pass is preceded by alloc_reset() is decided from the bundle itself (does it carry
# runtime.cyr's arena guard?), not from the profile name.
probe_body_core() {
    cat <<CYR
fn pg_body(): i64 {
    var P = pg_payload();
    var out = alloc(PG_N + 64);
    var f = pg_hex("__LZ4F__");
    pg_expect(lz4f_decompress(f, _pg_len, out, PG_N + 64), out, P, PG_N, "core: lz4f_decompress (lz4 CLI vector)");
    # A literal-only LZ4 block: token 0xF0, length 15 + 255 + 62 = 332, then the bytes.
    var blk = alloc(PG_N + 3);
    store8(blk, 0xF0); store8(blk + 1, 255); store8(blk + 2, 62);
    memcpy(blk + 3, P, PG_N);
    pg_expect(lz4_decompress(blk, PG_N + 3, out, PG_N + 64), out, P, PG_N, "core: lz4_decompress (literal block)");
    if (xxhash32(P, PG_N) != xxhash32(out, PG_N)) { pg_fail("core: xxhash32"); }
    return 0;
}
CYR
}

# Round-trip helper text shared by the codec profiles: $1 = compress call, $2 = decompress
# call, $3 = label. Uses `G`/`GN` (generated input), `c`, `o`.
pg_rt() {
    cat <<CYR
    c = alloc(GN * 2 + 4096);
    cl = $1;
    if (cl <= 0) { pg_fail("$3: compress"); }
    o = alloc(GN + 64);
    pg_expect($2, o, G, GN, "$3: round-trip");
CYR
}

# Streaming round-trip: $1 = codec prefix (zlib/gzip). Two write chunks each way, so the
# streaming-only slabs (deflate_dec_*'s code-length scratch, the deflate_enc window) are
# memoized before the reset and exercised after it.
pg_stream() {
    cat <<CYR
    c = alloc(GN * 2 + 4096);
    var se$1 = $1_enc_init(6, c, GN * 2 + 4096);
    if (se$1 == 0) { pg_fail("$1 stream: enc_init"); }
    if ($1_enc_write(se$1, G, GN / 2) < 0) { pg_fail("$1 stream: enc_write 1"); }
    if ($1_enc_write(se$1, G + GN / 2, GN - GN / 2) < 0) { pg_fail("$1 stream: enc_write 2"); }
    cl = $1_enc_finish(se$1);
    if (cl <= 0) { pg_fail("$1 stream: enc_finish"); }
    o = alloc(GN + 64);
    var sd$1 = $1_dec_init(o, GN + 64);
    if (sd$1 == 0) { pg_fail("$1 stream: dec_init"); }
    if ($1_dec_write(sd$1, c, cl / 2) < 0) { pg_fail("$1 stream: dec_write 1"); }
    if ($1_dec_write(sd$1, c + cl / 2, cl - cl / 2) < 0) { pg_fail("$1 stream: dec_write 2"); }
    pg_expect($1_dec_finish(sd$1), o, G, GN, "$1 stream: round-trip");
CYR
}

pg_body_open() {
    cat <<'CYR'
fn pg_body(): i64 {
    var P = pg_payload();
    var GN = 24000;
    var G = pg_gen(GN);
    var out = alloc(PG_N + 64);
    var v = 0;
    var c = 0;
    var cl = 0;
    var o = 0;
CYR
}

probe_body_zlib() {
    pg_body_open
    cat <<CYR
    v = pg_hex("__ZLIB__");
    pg_expect(zlib_decompress_capped(v, _pg_len, out, PG_N + 64, 1048576), out, P, PG_N, "zlib_decompress_capped (python zlib vector)");
CYR
    pg_rt "zlib_compress(G, GN, c, GN * 2 + 4096)" "zlib_decompress(c, cl, o, GN + 64)" "zlib"
    pg_stream zlib
    printf '    return 0;\n}\n'
}

probe_body_gzip() {
    pg_body_open
    cat <<CYR
    v = pg_hex("__GZIP__");
    pg_expect(gzip_decompress(v, _pg_len, out, PG_N + 64), out, P, PG_N, "gzip_decompress (python gzip vector)");
CYR
    pg_rt "gzip_compress(G, GN, c, GN * 2 + 4096)" "gzip_decompress(c, cl, o, GN + 64)" "gzip"
    pg_stream gzip
    printf '    return 0;\n}\n'
}

probe_body_xz() {
    pg_body_open
    cat <<CYR
    v = pg_hex("__XZ__");
    pg_expect(xz_decompress(v, _pg_len, out, PG_N + 64), out, P, PG_N, "xz_decompress (xz CLI vector)");
CYR
    pg_rt "xz_compress(G, GN, c, GN * 2 + 4096)" "xz_decompress(c, cl, o, GN + 64)" "xz"
    printf '    return 0;\n}\n'
}

probe_body_bzip2() {
    pg_body_open
    cat <<CYR
    v = pg_hex("__BZ2__");
    pg_expect(bzip2_decompress(v, _pg_len, out, PG_N + 64), out, P, PG_N, "bzip2_decompress (bzip2 CLI vector)");
CYR
    pg_rt "bzip2_compress(G, GN, c, GN * 2 + 4096)" "bzip2_decompress(c, cl, o, GN + 64)" "bzip2"
    printf '    return 0;\n}\n'
}

probe_body_zstd() {
    pg_body_open
    cat <<CYR
    v = pg_hex("__ZST__");
    pg_expect(zstd_decompress(v, _pg_len, out, PG_N + 64), out, P, PG_N, "zstd_decompress (zstd -19 vector)");
CYR
    pg_rt "zstd_compress(G, GN, c, GN * 2 + 4096)" "zstd_decompress(c, cl, o, GN + 64)" "zstd L6"
    pg_rt "zstd_compress_level(G, GN, c, GN * 2 + 4096, 9)" "zstd_decompress(c, cl, o, GN + 64)" "zstd L9"
    printf '    return 0;\n}\n'
}

# ZIP read of a CPython archive + write/read round-trip. $1 = extract fn, then extra methods.
pg_zip_common() {
    cat <<CYR
    v = pg_hex("__ZIP__");
    var z = zip_open(v, _pg_len);
    if (z == 0) { pg_fail("zip_open (python zipfile vector)"); }
    var zi = zip_find(z, "gate/payload.txt");
    if (zi < 0) { pg_fail("zip_find (python zipfile vector)"); }
    pg_expect($1(z, zi, out, PG_N + 64), out, P, PG_N, "$1 (python zipfile, DEFLATE)");
CYR
}

pg_zip_rt() {
    # $1 = add fn, $2 = extract fn, $3 = method, $4 = label
    cat <<CYR
    c = alloc(GN * 2 + 4096);
    var w$3 = zip_writer_init(c, GN * 2 + 4096);
    if (w$3 == 0) { pg_fail("$4: zip_writer_init"); }
    if ($1(w$3, "gen.bin", G, GN, $3) < 0) { pg_fail("$4: add"); }
    cl = zip_writer_finish(w$3);
    if (cl <= 0) { pg_fail("$4: finish"); }
    var z$3 = zip_open(c, cl);
    if (z$3 == 0) { pg_fail("$4: reopen"); }
    o = alloc(GN + 64);
    pg_expect($2(z$3, zip_find(z$3, "gen.bin"), o, GN + 64), o, G, GN, "$4: round-trip");
CYR
}

probe_body_zip() {
    pg_body_open
    pg_zip_common zip_extract
    pg_zip_rt zip_add zip_extract 8 "zip DEFLATE"
    printf '    return 0;\n}\n'
}

probe_body_zipall() {
    pg_body_open
    pg_zip_common zip_extract_any
    cat <<CYR
    v = pg_hex("__ZIPBZ2__");
    var zb = zip_open(v, _pg_len);
    if (zb == 0) { pg_fail("zip_open (python zipfile bzip2 vector)"); }
    pg_expect(zip_extract_any(zb, 0, out, PG_N + 64), out, P, PG_N, "zip_extract_any (python zipfile, method 12)");
CYR
    pg_zip_rt zip_add_any zip_extract_any 8 "zipall DEFLATE"
    pg_zip_rt zip_add_any zip_extract_any 12 "zipall bzip2"
    pg_zip_rt zip_add_any zip_extract_any 93 "zipall zstd"
    pg_zip_rt zip_add_any zip_extract_any 95 "zipall xz"
    printf '    return 0;\n}\n'
}

# tar_open_auto over one reference archive per envelope; $1 = hex marker, $2 = label.
pg_tar() {
    cat <<CYR
    v = pg_hex("$1");
    var t$2 = tar_open_auto(v, _pg_len);
    if (t$2 == 0) { pg_fail("tar_open_auto ($2)"); }
    if (tar_next(t$2) != 1) { pg_fail("tar_next ($2)"); }
    if (streq(tar_path(t$2), "gate/payload.txt") != 1) { pg_fail("tar_path ($2)"); }
    pg_expect(tar_size(t$2), tar_data(t$2), P, PG_N, "tar member ($2)");
CYR
}

probe_body_tar() {
    pg_body_open
    pg_tar __TGZ__ gz
    pg_tar __TXZ__ xz
    pg_tar __TBZ__ bz2
    pg_tar __TZST__ zst
    printf '    return 0;\n}\n'
}

# Brotli has no encoder, so its probes are decode-only: the link-gate vector below (a
# dictionary + context-map stream) through both public entries, plus a 16-byte uncompressed
# meta-block that allocates nothing. Both run in each pass, so the second pass decodes after
# alloc_reset() with the old workspace slab owned by the victim buffer.
pg_brotli() {
    cat <<CYR
    v = pg_hex("__BR__");
    pg_expect(brotli_decompress_capped(v, _pg_len, out, PG_N + 64, PG_N + 64), out, P, PG_N, "$1: brotli_decompress_capped (brotli -q 11 -w 22 vector)");
    pg_expect(brotli_decompress(v, _pg_len, out, PG_N + 64), out, P, PG_N, "$1: brotli_decompress (brotli -q 11 -w 22 vector)");
    if (brotli_decompress_capped(v, _pg_len, out, PG_N + 64, PG_N - 1) != 0 - ERR_OUTPUT_LIMIT) { pg_fail("$1: brotli_decompress_capped ceiling"); }
CYR
}

probe_body_brotli() {
    pg_body_open
    pg_brotli brotli
    printf '    return 0;\n}\n'
}

# [lib.woff]: WOFF 1.0 (zlib) and WOFF2 (Brotli) from ONE bundle, in both passes — the
# second after alloc_reset(), so reset_woff.cyr must reset the zlib closure AND Brotli.
probe_body_woff() {
    pg_body_open
    cat <<CYR
    v = pg_hex("__ZLIB__");
    pg_expect(zlib_decompress_capped(v, _pg_len, out, PG_N + 64, PG_N + 64), out, P, PG_N, "woff: zlib_decompress_capped (python zlib vector)");
CYR
    pg_brotli woff
    pg_rt "zlib_compress(G, GN, c, GN * 2 + 4096)" "zlib_decompress(c, cl, o, GN + 64)" "woff zlib"
    printf '    return 0;\n}\n'
}

probe_body_full() {
    pg_body_open
    cat <<CYR
    v = pg_hex("__ZLIB__");
    pg_expect(decompress(FORMAT_ZLIB, v, _pg_len, out, PG_N + 64), out, P, PG_N, "decompress(ZLIB vector)");
    v = pg_hex("__GZIP__");
    pg_expect(decompress(FORMAT_GZIP, v, _pg_len, out, PG_N + 64), out, P, PG_N, "decompress(GZIP vector)");
    v = pg_hex("__XZ__");
    pg_expect(decompress(FORMAT_XZ, v, _pg_len, out, PG_N + 64), out, P, PG_N, "decompress(XZ vector)");
    v = pg_hex("__BZ2__");
    pg_expect(decompress(FORMAT_BZIP2, v, _pg_len, out, PG_N + 64), out, P, PG_N, "decompress(BZIP2 vector)");
    v = pg_hex("__ZST__");
    pg_expect(decompress(FORMAT_ZSTD, v, _pg_len, out, PG_N + 64), out, P, PG_N, "decompress(ZSTD vector)");
    v = pg_hex("__LZ4F__");
    pg_expect(decompress(FORMAT_LZ4F, v, _pg_len, out, PG_N + 64), out, P, PG_N, "decompress(LZ4F vector)");
    v = pg_hex("__BR__");
    pg_expect(decompress(FORMAT_BROTLI, v, _pg_len, out, PG_N + 64), out, P, PG_N, "decompress(BROTLI vector)");
    if (compress(FORMAT_BROTLI, P, PG_N, out, PG_N + 64) != 0 - ERR_UNSUPPORTED_FORMAT) { pg_fail("compress(BROTLI) must be unsupported"); }
CYR
    pg_brotli full
    for f in LZ4 LZ4F DEFLATE ZLIB GZIP XZ BZIP2 ZSTD; do
        pg_rt "compress_level(FORMAT_$f, G, GN, c, GN * 2 + 4096, 9)" \
              "decompress(FORMAT_$f, c, cl, o, GN + 64)" "full $f"
    done
    pg_stream zlib
    pg_stream gzip
    pg_tar __TGZ__ gz
    pg_zip_common zip_extract_any
    printf '    return 0;\n}\n'
}

probe_main() {
    if [ "$PG_ALLOC" = 1 ]; then
        cat <<'CYR'

fn pg_fill(p, words): i64 {
    var i = 0;
    while (i < words) { store64(p + i * 8, 0x5A5AC3C3A5A53C3C); i = i + 1; }
    return 0;
}

fn pg_bad(p, words): i64 {
    var bad = 0;
    var i = 0;
    while (i < words) {
        if (load64(p + i * 8) != 0x5A5AC3C3A5A53C3C) { bad = bad + 1; }
        i = i + 1;
    }
    return bad;
}

fn main(): i64 {
    pg_body();
    # Every memoized table is now built. Rewind the arena under the library and give
    # every byte of it to a caller before the second pass.
    var words = (alloc_used() + 64) / 8;
    var canary = _sankoch_canary;
    alloc_reset();
    var victim = alloc(words * 8);
    if (victim == 0) { pg_fail("victim alloc"); }
    pg_fill(victim, words);
    pg_body();
    if (pg_bad(victim, words) != 0) { pg_fail("caller memory clobbered after alloc_reset (a memoized pointer survived)"); }
    if (_sankoch_canary == canary) { pg_fail("arena guard never re-armed: the profile reset path did not run"); }
    return 0;
}
CYR
    else
        cat <<'CYR'

fn main(): i64 {
    pg_body();
    pg_body();
    return 0;
}
CYR
    fi
    cat <<'CYR'

var pg_rc = main();
if (pg_rc == 0) { println("PROBE OK"); }
syscall(60, pg_rc);
CYR
}

# --- known vectors (hex) -----------------------------------------------------------------
VECZLIB="789ce5ccc90d80201405c0565e05c67deb061510413e82b8556f621b9e2799c0aca67186f32494e130ca6a48b6f31efbccb145356a0c9e4e0b411796b8ba003ab8ffd8b0e7c644126996176555376d9720fcb57c0116277155"
VECGZIP="1f8b08000000000000ffe5ccc90d80201405c0565e05c67deb061510413e82b8556f621b9e2799c0aca67186f32494e130ca6a48b6f31efbccb145356a0c9e4e0b411796b8ba003ab8ffd8b0e7c644126996176555376d9720fcb57c01877d25934c010000"
VECXZ="fd377a585a000004e6d6b44604c05bcc0221011600000000000000006eefa9c8e0014b00535d0039984a218f0958e3b8083be54fd0d435533110464ddf68208cb599a4ce423bc70d516cc9ce09d911c55937f80b7829e9a7d20caa31e7e33d04a1d593e103125d7fb425e7f55c1fd268196e3bc8c565ff3f40000000a04cfac6bd920a93000177cc02000000f5249e53b1c467fb020000000004595a"
VECBZ2="425a6839314159265359fd96df54000091998040017ff03ffffff03000b80c1a68d34c26264c040d30c1a68d34c26264c040d302aaa7947a86834d1e880c868da899d0a1e0894398c4ec44a8c4b8b8dc6f2b38161c4e44cb4b8acb0b8c0de7a30225a68207c3234922040c0d0323d9ac9122f1136103494339e8f25e626a226d227d204cc8fa40ce544050a13337e247f177245385090fd96df540"
VECZST="28b52ffd0468b50200f284121860ad0e2f6d5b9c8635755df40c82308e90a1aba2244110f0f78092208751108310fc7573aa5ad3b6a87feb939d4fed4ea5b6cc258b197a83f84bc3eb5dd238df66746deb216b49d70d0200ea56a096a25550e1b666f7"
VECLZ4F="04224d186440a75d000000f12a73616e6b6f63682070726f66696c65206c696e6b20676174653a2074686520717569636b2062726f776e20666f78206a756d7073206f7665721f00ff066c617a7920646f6720303132333435363738392e205300e1503738392e2000000000bdf3e485"
VECTGZ="1f8b08000000000002ffedd2410e82301085e11e654e80ad82a8b7a98a882045280a9ede461317ee65c3ff6d5e322f99d94c6e7db668ec58397b8cfce0d51fe8601dc7ef0c7e5327e6db7de6c6e82455a2d504facedb369c57f3d4d9ba7487b334ad3b1555265551979287a7d8893f6772eb8b4329fbd63d6a39b9412efdb5e9c4ddb3f65d57f639cad1e5a2cd721527eb74b38d64b62b15000000000000000000000000004ce805edc2754500280000"
VECTXZ="fd377a585a000004e6d6b44604c0b8018050210116000000000000003416d56fe027ff00b05d0033984aeeebb109943a5b80fa5f4abfcb1ad36908857b074b5e9f8c3199e655401b42d8dd4cd524a626241aa7273bb31b6dd273229851eea4423ee9f736ab420022d1791f45c6c5318fdd6526ebcedb1c98a2433ef6aaccff997f8f3553710dd623ac424f3b9adb8fca525b58fc59b3a8622860388194f19f594dd33d34c282c8aba755d0b21931d922d08a3653b8916bf992e63aa52ec9507c1c73702166490c70ba6dfa39f5abe62a8f8210911d370000c43f0651394acae10001d40180500000df3b7ff6b1c467fb020000000004595a"
VECTBZ="425a68393141592653591549997c0000bf5b82cc804001fff040007ffffff0040008083000f8030069a1a34623201a003430c01a6868d188c806800d0c0aa4536a3d48d320683644c98984c9e93857b4a510315810f1e19aa9775708848ef9e9361d4de4cea6b1ccda4cc7194b8b8fba7a66466921aa70c07cac85d32d33cf4e92eb0c58eb0c268351e051c739aad872e279984e06ec05a509158743114245f338941d4e6632850da2664246ec47f16194aef369b0c64cc872c0752457e0ce7424591db372d1585072bcbcbed234762b0d6883fc5dc914e14240552665f0"
VECTZST="28b52ffd04684d040002881a18707903502b1fa14e89902609faff93074dd2668054ffe1a5cbc06114047c83e09ae52fac6d3e69bc9eab29b21ece9e61097b9a30a43816c5b1a98cc4ea9221c9991ca7c33c9db8511e92bcdaeea55e2b6b9bb780ed5c6fef73b07bdf237a6b5681c57f6a3e05b1ba0c0a202031f6b0e478d16e91580a2d9ca70e2879c305020605b0300930fb8ebb62"
VECZIP="504b030414000000080000002100877d2593530000004c01000010000000676174652f7061796c6f61642e747874e5ccc90d80201405c0565e05c67deb061510413e82b8556f621b9e2799c0aca67186f32494e130ca6a48b6f31efbccb145356a0c9e4e0b411796b8ba003ab8ffd8b0e7c644126996176555376d9720fcb57c01504b0102140314000000080000002100877d2593530000004c010000100000000000000000000000800100000000676174652f7061796c6f61642e747874504b050600000000010001003e000000810000000000"
# brotli 1.2.0 `-q 11 -w 22` over PG_TEXT x 4 (75 B): one compressed last meta-block, UTF8
# context mode, a literal context map with RLE + IMTF, 7 static-dictionary references
# (transforms 0, 2, 41, 51). Byte-identical to a fresh `brotli -q 11 -w 22`; decodes exactly
# under `brotli -dc` and scripts/brotli_ref_decoder.py.
VECBR="1b4b01408d946ee62210b661aa0b49ce6f5939a068b09c0a7b830d38602f817df15168f090952a33ed9139d6d8b92390852f38ee8f94935a5f8ae510fbcda6ff281b5269639d0f3109cc00"
VECZIPBZ2="504b03042e0000000c0000002100877d25939b0000004c01000010000000676174652f7061796c6f61642e747874425a6839314159265359fd96df54000091998040017ff03ffffff03000b80c1a68d34c26264c040d30c1a68d34c26264c040d302aaa7947a86834d1e880c868da899d0a1e0894398c4ec44a8c4b8b8dc6f2b38161c4e44cb4b8acb0b8c0de7a30225a68207c3234922040c0d0323d9ac9122f1136103494339e8f25e626a226d227d204cc8fa40ce544050a13337e247f177245385090fd96df540504b01022e032e0000000c0000002100877d25939b0000004c010000100000000000000000000000800100000000676174652f7061796c6f61642e747874504b050600000000010001003e000000c90000000000"

fill_vectors() {
    sed \
        -e "s/__ZLIB__/$VECZLIB/g" \
        -e "s/__GZIP__/$VECGZIP/g" \
        -e "s/__XZ__/$VECXZ/g" \
        -e "s/__BZ2__/$VECBZ2/g" \
        -e "s/__ZST__/$VECZST/g" \
        -e "s/__LZ4F__/$VECLZ4F/g" \
        -e "s/__TGZ__/$VECTGZ/g" \
        -e "s/__TXZ__/$VECTXZ/g" \
        -e "s/__TBZ__/$VECTBZ/g" \
        -e "s/__TZST__/$VECTZST/g" \
        -e "s/__ZIP__/$VECZIP/g" \
        -e "s/__ZIPBZ2__/$VECZIPBZ2/g" \
        -e "s/__BR__/$VECBR/g" \
        -
}

# --- registration check -----------------------------------------------------------------
check_registration() {
    local bundle="$1"
    if ! grep -q '^fn _sankoch_arena_guard(' "$bundle"; then
        if sed 's/#.*//' "$bundle" | grep -qE '_[a-z0-9_]+_reset_tables\('; then
            echo "  REGISTRATION: reset functions in a bundle with no arena guard"
            return 1
        fi
        return 0
    fi
    local ndef
    ndef=$(grep -c '^fn _sankoch_reset_tables(' "$bundle")
    if [ "$ndef" != 1 ]; then
        echo "  REGISTRATION: bundle carries _sankoch_arena_guard but defines _sankoch_reset_tables $ndef times (want 1)"
        return 1
    fi
    local defined called
    # Module names may contain `_` (zip_methods, lz4_decode). Calls are matched with `#`
    # comments stripped, so a commented-out registration counts as missing.
    defined=$(grep -oE '^fn _[a-z0-9_]+_reset_tables\(' "$bundle" | sed -e 's/^fn //' -e 's/($//' \
        | grep -v '^_sankoch_reset_tables$' | sort -u)
    called=$(awk '/^fn _sankoch_reset_tables\(/ { inb = 1; next } inb && /^}/ { inb = 0 } inb' "$bundle" \
        | sed 's/#.*//' | grep -oE '_[a-z0-9_]+_reset_tables\(' | sed 's/($//' | sort -u)
    if [ "$defined" != "$called" ]; then
        echo "  REGISTRATION: module resets defined vs called by _sankoch_reset_tables differ:"
        diff <(printf '%s\n' "$defined") <(printf '%s\n' "$called") | sed 's/^/    /'
        echo "    (< defined but never called: a memoized pointer that survives alloc_reset)"
        echo "    (> called but not defined in this bundle: an unresolvable call)"
        return 1
    fi
    return 0
}

# --- run ---------------------------------------------------------------------------------
fail=0
nprof=0
for prof in $PROFILES; do
    nprof=$((nprof + 1))
    if [ "$prof" = full ]; then bundle="$BUNDLE_DIR/sankoch.cyr"; else bundle="$BUNDLE_DIR/sankoch-$prof.cyr"; fi
    echo "=== [$prof] $bundle"
    if ! declare -F "probe_body_$prof" >/dev/null; then
        echo "  FAIL: profile [lib.$prof] has no probe — add probe_body_$prof to $0"
        fail=1
        continue
    fi
    if [ ! -f "$bundle" ]; then echo "  FAIL: bundle missing (cyrius distlib $prof)"; fail=1; continue; fi
    pfail=0
    check_registration "$bundle" || pfail=1

    PG_ALLOC=0
    grep -q '^fn _sankoch_arena_guard(' "$bundle" && PG_ALLOC=1

    dir="$OUT/$prof"
    mkdir -p "$dir"
    probe="$dir/probe.cyr"
    {
        echo "# generated by scripts/profile-link-gate.sh — [$prof] against $bundle"
        for m in $STDLIB; do echo "include \"lib/$m.cyr\""; done
        echo "include \"$bundle\""
        echo
        probe_prelude
        echo
        "probe_body_$prof"
    } | fill_vectors > "$probe"
    probe_main | fill_vectors >> "$probe"

    env -u CYRIUS_DCE cyrius build "$probe" "$dir/probe.bin" > "$dir/build.log" 2>&1
    brc=$?
    if [ $brc -ne 0 ] || grep -qE 'undefined function|refusing to emit' "$dir/build.log"; then
        echo "  LINK: FAIL (build rc=$brc)"
        grep -E 'undefined function|refusing to emit|error' "$dir/build.log" | sort | uniq -c | sed 's/^/    /'
        pfail=1
    else
        timeout 60 "$dir/probe.bin" > "$dir/run.log" 2>&1
        rrc=$?
        if [ $rrc -ne 0 ] || ! grep -qx 'PROBE OK' "$dir/run.log"; then
            echo "  RUN: FAIL (exit $rrc)"
            sed 's/^/    /' "$dir/run.log" | head -20
            pfail=1
        fi
    fi
    if [ "$PG_ALLOC" = 1 ]; then
        env CYRIUS_DCE=1 CYRIUS_DCE_VERBOSE=1 cyrius build --agnos "$probe" "$dir/probe-agnos.bin" \
            > "$dir/build-agnos.log" 2>&1
        arc=$?
        if [ $arc -ne 0 ] || grep -qE 'undefined function|refusing to emit' "$dir/build-agnos.log"; then
            echo "  AGNOS: FAIL (build rc=$arc)"
            grep -E 'undefined function|refusing to emit|error' "$dir/build-agnos.log" | sort | uniq -c | sed 's/^/    /'
            pfail=1
        elif grep -qE 'dead: (_sankoch_arena_guard|_sankoch_reset_tables)$' "$dir/build-agnos.log"; then
            echo "  AGNOS: FAIL — the arena-reset path is dead code under --agnos:"
            grep -E 'dead: (_sankoch_arena_guard|_sankoch_reset_tables)$' "$dir/build-agnos.log" | sed 's/^/    /'
            pfail=1
        fi
        lock="$dir/lock.cyr"
        {
            echo "# generated by scripts/profile-link-gate.sh — [$prof] lock-only AGNOS probe"
            for m in $STDLIB; do echo "include \"lib/$m.cyr\""; done
            echo "include \"$bundle\""
            printf 'fn main(): i64 {\n    _sankoch_lock();\n    _sankoch_unlock();\n    return 0;\n}\n'
            printf 'var pg_rc = main();\nsyscall(60, pg_rc);\n'
        } > "$lock"
        env CYRIUS_DCE=1 CYRIUS_DCE_VERBOSE=1 cyrius build --agnos "$lock" "$dir/lock-agnos.bin" \
            > "$dir/lock-agnos.log" 2>&1
        lrc=$?
        if [ $lrc -ne 0 ] || grep -qE 'undefined function|refusing to emit' "$dir/lock-agnos.log"; then
            echo "  AGNOS: FAIL (lock-only probe build rc=$lrc)"
            grep -E 'undefined function|refusing to emit|error' "$dir/lock-agnos.log" | sort | uniq -c | sed 's/^/    /'
            pfail=1
        elif grep -qE 'dead: (_sankoch_arena_guard|_sankoch_reset_tables)$' "$dir/lock-agnos.log"; then
            echo "  AGNOS: FAIL — _sankoch_lock does not reach the arena-reset path under --agnos:"
            grep -E 'dead: (_sankoch_arena_guard|_sankoch_reset_tables)$' "$dir/lock-agnos.log" | sed 's/^/    /'
            pfail=1
        elif ! grep -q 'dead: ' "$dir/lock-agnos.log"; then
            echo "  AGNOS: FAIL — no DCE dead list in the lock-only build log (CYRIUS_DCE_VERBOSE output changed?)"
            pfail=1
        fi
    fi
    if [ $pfail -eq 0 ]; then
        if [ "$PG_ALLOC" = 1 ]; then echo "  ok: registered, links, runs, survives alloc_reset, reset reachable on agnos"
        else echo "  ok: links, runs (alloc-free profile)"; fi
    else
        fail=1
    fi
done

if [ $fail -ne 0 ]; then
    echo "profile link gate: FAILED"
    exit 1
fi
echo "profile link gate: all $nprof profiles link and run"
