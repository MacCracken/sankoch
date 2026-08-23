#!/bin/sh
# deflate-flush-smoke.sh — validate sankoch's DEFLATE sync flush (2.7.9) against
# Python's zlib, the reference implementation for RFC 7692 `permessage-deflate`.
#
# Both directions, over the same corpus, with context takeover on (one stream,
# never terminated — messages separated only by the sync flush):
#
#   SEND  sankoch frames each message (write + deflate_enc_flush, trailing
#         `00 00 FF FF` stripped); zlib.decompressobj(-15) must decode every
#         frame back to the original message. Run at level 6 (dynamic path)
#         and level 1 (fixed path) — a flush closes the two differently.
#   RECV  Python frames with compressobj(...,-15) + flush(Z_SYNC_FLUSH);
#         sankoch's streaming decoder must reproduce the corpus byte-for-byte.
#
# The self-consistency trap this exists to avoid: a sync flush that sankoch
# both writes and reads can be wrong in the same direction twice and still
# round-trip. Only the reference decoder settles it — the 1.6.1 xxHash32 bug
# is the cautionary tale (see CLAUDE.md § Key Principles).
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/build/deflate_flush_smoke"
for t in python3 cmp; do
    command -v "$t" >/dev/null 2>&1 || { echo "ERROR: missing '$t'"; exit 1; }
done

IN="/tmp/sankoch-flush-in"
OURS="/tmp/sankoch-flush-ours"
OURS_L1="/tmp/sankoch-flush-ours-l1"
PY="/tmp/sankoch-flush-py"
PYDEC="/tmp/sankoch-flush-pydec"
trap 'rm -f "$IN" "$OURS" "$OURS_L1" "$PY" "$PYDEC"' EXIT

# --- corpus: repetitive JSON-RPC, the traffic shape context takeover targets ---
awk 'BEGIN{
  for (i = 0; i < 400; i++)
    printf "{\"jsonrpc\":\"2.0\",\"id\":%d,\"method\":\"tools/call\",\"params\":{\"name\":\"read\",\"n\":%d}}\n", i, i % 13
}' > "$IN"

# --- Python side, direction RECV: produce sync-flushed frames for sankoch ---
python3 - "$IN" "$PY" <<'PYEOF' || { echo "ERROR: python frame generation failed"; exit 1; }
import struct, sys, zlib
MSG = 200
data = open(sys.argv[1], 'rb').read()
co = zlib.compressobj(6, zlib.DEFLATED, -15)
out = bytearray()
for off in range(0, len(data), MSG):
    msg = data[off:off + MSG]
    frame = co.compress(msg) + co.flush(zlib.Z_SYNC_FLUSH)
    assert frame.endswith(b'\x00\x00\xff\xff'), 'reference flush lacks the marker'
    frame = frame[:-4]                       # RFC 7692 §7.2.1 step 3
    out += struct.pack('<I', len(frame)) + frame
open(sys.argv[2], 'wb').write(bytes(out))
PYEOF

CYRIUS_NO_WARN_PIN_DRIFT=1 CYRIUS_NO_WARN_SHADOW_LIB=1 \
    sh -c "cd '$ROOT' && cyrius build programs/deflate_flush_smoke.cyr build/deflate_flush_smoke" \
    >/dev/null 2>&1 || { echo "ERROR: build failed"; exit 1; }
[ -x "$BIN" ] || { echo "ERROR: deflate_flush_smoke not built"; exit 1; }

"$BIN" || { echo "ERROR: deflate_flush_smoke exited $?"; exit 1; }

# --- direction RECV: sankoch's decode of the reference frames ---
if cmp -s "$IN" "$PYDEC"; then
    echo "PASS  recv: sankoch decoded reference Z_SYNC_FLUSH frames ($(wc -c < "$IN") bytes)"
else
    echo "FAIL  recv: sankoch decode of reference frames differs"
    exit 1
fi

# --- direction SEND: the reference decode of sankoch's frames ---
for f in "$OURS" "$OURS_L1"; do
    python3 - "$IN" "$f" <<'PYEOF' || exit 1
import struct, sys, zlib
MSG = 200
data = open(sys.argv[1], 'rb').read()
rec = open(sys.argv[2], 'rb').read()
do = zlib.decompressobj(-15)
rp, off, frames = 0, 0, 0
while rp + 4 <= len(rec):
    (n,) = struct.unpack('<I', rec[rp:rp + 4]); rp += 4
    frame = rec[rp:rp + n]; rp += n
    got = do.decompress(frame + b'\x00\x00\xff\xff')   # RFC 7692 receive
    want = data[off:off + MSG]
    if got != want:
        print("FAIL  send: frame %d differs (%d bytes vs %d)" % (frames, len(got), len(want)))
        sys.exit(1)
    off += len(want); frames += 1
if off != len(data):
    print("FAIL  send: covered %d of %d bytes in %d frames" % (off, len(data), frames))
    sys.exit(1)
print("PASS  send: reference zlib decoded %d sankoch frames (%s, %d bytes -> %d)"
      % (frames, sys.argv[2].rsplit('-', 1)[-1], len(data), len(rec)))
PYEOF
done

echo "deflate-flush-smoke: OK"
