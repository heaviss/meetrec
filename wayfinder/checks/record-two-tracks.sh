#!/usr/bin/env bash
# Throwaway check: record-two-tracks.sh <seconds> -> ~/Recordings/check-localvqe/<ts>/{me,them}.wav
set -euo pipefail
dir=~/Recordings/check-localvqe/$(date +%Y-%m-%d-%H%M%S)
mkdir -p "$dir"
fmt=(--rate 16000 --channels 1 --format s16 -P '{ application.name=meetrec }')
pw-record "${fmt[@]}" "$dir/me.wav" & me=$!
pw-record "${fmt[@]}" -P '{ stream.capture.sink=true }' "$dir/them.wav" & them=$!
echo "Recording to $dir for $1 s. Talk now."
sleep "$1"
kill -TERM $me $them; wait $me $them 2>/dev/null || true
echo "$dir"
