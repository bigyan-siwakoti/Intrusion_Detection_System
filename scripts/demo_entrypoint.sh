#!/usr/bin/env bash
# Container start: make sure each demo has its Suricata output (logs/demo-<id>/eve.json), then start the web server.
# logs/ is a persistent volume, so eve.json is generated once and stays identical across restarts and deploys:
# Suricata's alert count varies slightly between replays, and the recorded runs and downloads must match the data.
# It is regenerated only when the capture slice is newer than its eve.json.
set -euo pipefail
cd "$APP"

for id in cic unsw; do
  pcap="data/slices/demo-$id.pcap"
  out="logs/demo-$id"
  if [ -f "$pcap" ] && [ -s "$out/eve.json" ] && [ "$out/eve.json" -nt "$pcap" ]; then
    echo "[entrypoint] $id: keeping existing $out/eve.json ($(grep -c '"event_type":"alert"' "$out/eve.json") alerts)"
  elif [ -f "$pcap" ]; then
    rm -rf "$out" && mkdir -p "$out"
    echo "[entrypoint] replaying $pcap with config/demo/$id.yaml"
    suricata -r "$pcap" -c "config/demo/$id.yaml" -l "$out" >/dev/null 2>&1 \
      || echo "[entrypoint] WARNING: suricata exited non-zero for $id (see $out/suricata.log)"
    echo "[entrypoint] $id: $(grep -c '"event_type":"alert"' "$out/eve.json" 2>/dev/null || echo 0) alerts"
  else
    echo "[entrypoint] $pcap missing - the $id demo will only offer replay"
  fi
done

exec uvicorn src.server:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'
