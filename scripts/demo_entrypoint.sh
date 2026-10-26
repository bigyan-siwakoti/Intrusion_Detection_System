#!/usr/bin/env bash
# Container start: replay each demo capture slice through its demo config so logs/demo-<id>/eve.json matches the
# rules actually loaded in this image, then start the web server.
set -euo pipefail
cd "$APP"

for id in cic unsw; do
  pcap="data/slices/demo-$id.pcap"
  out="logs/demo-$id"
  if [ -f "$pcap" ]; then
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
