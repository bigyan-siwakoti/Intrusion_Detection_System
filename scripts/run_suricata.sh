#!/usr/bin/env bash
# Replay one pcap with a named dataset profile, raw (no suppressions), into logs/<run-name>/.
# Usage: scripts/run_suricata.sh <cic|unsw> <profile> <pcap> <run-name>
#   cic  profiles: config/cic/*.yaml   (the frozen CIC triage config is config/suricata.yaml)
#   unsw profiles: config/unsw/*.yaml  (baseline = frozen UNSW baseline v2)
set -euo pipefail
cd "$(dirname "$0")/.."
dataset=$1 profile=$2 pcap=$3 run=$4
cfg="config/$dataset/$profile.yaml"
[[ -f $cfg ]] || { echo "no profile $cfg; available:"; ls "config/$dataset"; exit 1; }
[[ -f $pcap ]] || { echo "no pcap $pcap"; exit 1; }
out="logs/$run"; rm -rf "$out"; mkdir -p "$out"
suricata -c "$cfg" --set threshold-file= -k none -r "$pcap" -l "$out" > "$out/run.out" 2>&1
echo "$run [$cfg] $(grep -oE '[0-9]+ rules successfully loaded, [0-9]+ rules failed' "$out/suricata.log") $(grep -oE 'Alerts: [0-9]+' "$out/suricata.log" | tail -1)"
