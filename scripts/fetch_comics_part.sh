#!/bin/bash
# Resumable, interruptible download of the first TARGET bytes of the COMICS panel archive.
#
# usage: scripts/fetch_comics_part.sh [TARGET_BYTES] [OUT_FILE] [URL]
#
# The output is always a valid byte prefix of the archive:
#   * Each range request goes to a temp chunk file. It is appended to OUT_FILE only if the server
#     answered "206 Partial Content" with a Content-Range starting exactly at the current size.
#     HTTP errors and ignored ranges are never appended.
#   * SIGINT/SIGTERM: the in-flight curl is stopped (SIGTERM). The bytes it already wrote are a correct
#     prefix, so they are verified and appended. The script then exits with code 130.
#     Re-run the same command to resume from the current size.
# Extract with:  tar -xzf OUT_FILE --skip-old-files  (the truncated final book is expected).
set -u
TARGET=${1:-3500000000}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
WS=${CPT_WORKSPACE:-$ROOT/workspace}
F=${2:-$WS/data/comics/raw_panel_images.part.tar.gz}
URL=${3:-https://obj.umiacs.umd.edu/comics/raw_panel_images.tar.gz}
CHUNK="$F.chunk"
HDR="$F.hdr"
STOP=0
CURL_PID=""
on_signal() {
  STOP=1
  echo "stop requested: finishing current chunk, then exiting" >&2
  # SIGTERM, not SIGINT: non-interactive bash starts background jobs with SIGINT ignored. curl has no
  # graceful mode; whatever it already wrote to the chunk file is a valid prefix and is kept.
  [ -n "$CURL_PID" ] && kill -TERM "$CURL_PID" 2>/dev/null
}
trap on_signal INT TERM

append_verified() {  # $1 = expected start offset
  [ -s "$CHUNK" ] || return 0
  if grep -qiE "^HTTP/[0-9.]+ 206" "$HDR" && grep -qiE "^content-range: bytes $1-" "$HDR"; then
    cat "$CHUNK" >> "$F"
  else
    echo "unexpected response, discarding chunk: $(head -1 "$HDR")" >&2
  fi
  rm -f "$CHUNK" "$HDR"
}

touch "$F"
rm -f "$CHUNK" "$HDR"
for i in $(seq 1 500); do
  S=$(stat -c %s "$F")
  [ "$S" -ge "$TARGET" ] && break
  [ "$STOP" -eq 1 ] && break
  curl -s -f --max-time 900 -r "$S-$((TARGET - 1))" -D "$HDR" -o "$CHUNK" "$URL" &
  CURL_PID=$!
  wait "$CURL_PID" 2>/dev/null
  while kill -0 "$CURL_PID" 2>/dev/null; do wait "$CURL_PID" 2>/dev/null; done  # wait is interrupted by traps
  CURL_PID=""
  append_verified "$S"
done
echo "$(stat -c %s "$F") bytes in $F"
[ "$STOP" -eq 1 ] && exit 130
exit 0
