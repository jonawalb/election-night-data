#!/bin/zsh
# National relay loop: fetch NBC/AP Senate, House and governor results every 60s and push
# national.json when it changes (or every 10 min as a heartbeat). Stops at 12:00 UTC Nov 5.
cd "$(dirname "$0")"
END=$(date -j -u -f "%Y-%m-%dT%H:%M:%S" "2026-11-05T12:00:00" +%s)
last_sig=""; last_push=0; fails=0
while [ "$(date +%s)" -lt "$END" ]; do
  if python3 national.py national.next.json >> national.log 2>&1; then
    fails=0
    sig=$(python3 -c "import json,hashlib;d=json.load(open('national.next.json'));d.pop('relayedAt');print(hashlib.md5(json.dumps(d,sort_keys=True).encode()).hexdigest())")
    now=$(date +%s)
    if [ "$sig" != "$last_sig" ] || [ $((now - last_push)) -ge 600 ]; then
      mv national.next.json national.json
      git add national.json && git commit -q -m "chore(data): national snapshot $(date -u +%H:%M)"; git pull -q --rebase -X theirs >> national.log 2>&1; git push -q >> national.log 2>&1 && last_push=$now && last_sig=$sig
      echo "$(date -u +%H:%M:%S) pushed" >> national.log
    fi
  else
    fails=$((fails+1)); echo "$(date -u +%H:%M:%S) fetch failed ($fails)" >> national.log
  fi
  sleep 60
done
echo "$(date -u +%H:%M:%S) national loop exited" >> national.log
