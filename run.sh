#!/bin/zsh
# Relay loop for election night: fetch VA-2 every 60s, push luria.json when results change
# (or every 10 min as a heartbeat). Stops at 08:00 UTC Nov 4 (3 AM ET) or once results are official.
cd "$(dirname "$0")"
END=$(date -j -u -f "%Y-%m-%dT%H:%M:%S" "2026-11-04T08:00:00" +%s)
last_sig=""; last_push=0; fails=0
while [ "$(date +%s)" -lt "$END" ]; do
  if python3 relay.py luria.next.json >> relay.log 2>&1; then
    fails=0
    sig=$(python3 -c "import json;d=json.load(open('luria.next.json'));d.pop('relayedAt');print(hash(json.dumps(d,sort_keys=True)))")
    now=$(date +%s)
    if [ "$sig" != "$last_sig" ] || [ $((now - last_push)) -ge 600 ]; then
      mv luria.next.json luria.json
      git add luria.json && git commit -q -m "chore(data): snapshot $(date -u +%H:%M)" && git push -q >> relay.log 2>&1 && last_push=$now && last_sig=$sig
      echo "$(date -u +%H:%M:%S) pushed" >> relay.log
    fi
    python3 -c "import json,sys;sys.exit(0 if json.load(open('luria.json')).get('official') else 1)" && { echo "official, stopping" >> relay.log; break; }
  else
    fails=$((fails+1)); echo "$(date -u +%H:%M:%S) fetch failed ($fails)" >> relay.log
  fi
  sleep 60
done
echo "$(date -u +%H:%M:%S) relay loop exited" >> relay.log
