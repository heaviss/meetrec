#!/usr/bin/env bash
# Throwaway check: log who holds the microphone, with timestamps, until Ctrl-C.
# watch-mic.sh [log]  (default ~/Recordings/check-mic-<ts>.log)
log=${1:-~/Recordings/check-mic-$(date +%Y-%m-%d-%H%M%S).log}
snapshot() {
  LC_ALL=C pactl -f json list source-outputs | python3 -I -c '
import json, sys
for o in json.load(sys.stdin):
    p = o["properties"]
    print(" ", o["index"], p.get("application.name"), p.get("application.process.binary"), "source", o["source"], "corked" if o.get("corked") else "")'
}
note() { echo "$(date +%T.%3N) $*" | tee -a "$log"; }
note "start, log $log"; snapshot | tee -a "$log"
LC_ALL=C pactl subscribe | while read -r line; do
  case $line in
    *source-output*) note "$line"; snapshot | tee -a "$log" ;;
  esac
done
