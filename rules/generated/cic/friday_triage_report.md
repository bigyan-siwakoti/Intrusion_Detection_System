# Triage Report — logs/friday-raw/eve.json (2017-07-07/08)

## Scope
- Single eve.json: **1,412,449 alert events** across **82 unique signatures**.
- HOME_NET: 192.168.10.0/24. Known attacker: 172.16.0.1.
- Raw run had **no threshold.config applied** (suricata.log:
  `threshold-config: Error opening file: ""`), so normally-suppressed baseline
  noise is present at full volume.

## 1. Big picture
The overwhelming majority is engine/decoder/parser noise, not threat traffic:

| Count | Signature | Tier |
|---|---|---|
| 1,390,304 | SURICATA TCPv4 invalid checksum [2200074] | capture/checksum artifact |
| 7,359 | SURICATA HTTP Response excessive header repetition [2221036] | HTTP parser noise |
| 7,279 | SURICATA Ethertype unknown [2200121] | capture artifact |
| 1,207 | SURICATA STREAM Packet with invalid ack [2210045] | stream noise |
| 1,200 | SURICATA STREAM SHUTDOWN RST invalid ack [2210046] | stream noise |
| 1,145 | SURICATA STREAM CLOSEWAIT FIN out of window [2210016] | stream noise |
| 718 | SURICATA STREAM FIN out of window [2210038] | stream noise |
| 569 | SURICATA Kerberos 5 weak encryption parameters [2226001] | internal AD policy |
| 343 | ET INFO GNU/Linux APT User-Agent [2013504] | informational |
| ... | DNS TLD / STUN / NTLM / USER_AGENTS / TLS handshake | informational |

Only one real threat campaign was present, from **172.16.0.1 → 192.168.10.50**,
with a secondary ICMP prober **172.16.0.2 → 192.168.10.50/.51**.

## 2. Confirmed attack — multi-phase campaign against 192.168.10.50

### Phase 1 — recon (hours 00–01)
- Attacker browsed the victim's DVWA web app (Host 205.174.165.68, Firefox/45.0
  UA): 19 HTTP transactions to `/dv/`, `/dv/login.php`, `/dv/dvwa/*` (200/302).

### Phase 2 — ICMP host discovery
- GPL ICMP PING rules: 18 alerts — 8x from 172.16.0.1, 10x from 172.16.0.2,
  to 192.168.10.50 and 192.168.10.51.

### Phase 3 — SSH brute-force campaign (02:25–03:55)
- 31 SSH app-layer events, all `172.16.0.1 -> 192.168.10.50:22`, server banner
  OpenSSH_7.2p2 only. Custom sid 9500002 fired 24x.
- **No evidence of success**: every SSH flow is banner-only (~5 pkts / 338 B to
  server, 3–4 pkts / ~247–313 B to client); no post-auth data transfer.

### Phase 4 — TCP port scan + service enumeration (hour 03)
- ~160,000 inbound SYN flows (250,000+ raw SYN packets) to ~1,000 distinct
  destination ports (1-65535 sweep, repeated passes over ~1 hour). Closed
  ports answered RST+ACK.
- Open services then banner-grabbed: 31x FTP (vsFTPd 3.0.3, no commands),
  37x SMB1 NEGOTIATE_PROTOCOL on 139/445, plus repeated SSH (phase 3).
- Stock ET SCAN fired only for known ports: MySQL 3306 (39), PostgreSQL 5432
  (38), MSSQL 1433 (38), Oracle 1521 (35), VNC 5800-5820 (8), SSH (7),
  IMAPS (3), IMAP (3), POP3 (2), POP3S (2), Terminal Server (1) = 176 alerts.

### Phase 5 — HTTP GET flood / DoS tool (04:26–04:47)
- 94,486 terse `GET /` requests from 172.16.0.1 to 192.168.10.50:80 — no Host,
  no User-Agent, HTTP version null. Peak ~4,800 requests/min (~80 req/s).
- Victim answered HTTP 200 to every request (94,551 fileinfo `/` responses).
- Stock ET 2019348 "Terse HTTP GET Likely AnonMafiaIC DDoS tool" fired only
  20x (~1/min, rate-limited), understating the campaign by 3 orders of magnitude.

### Verdict
True positive. Single external attacker executed a textbook kill-chain against
192.168.10.50: recon → discovery → SSH brute force → broad port scan/service
enumeration → HTTP DoS flood. SSH brute force did not succeed; the DoS flood
executed fully (victim still answered 200s, so impact was load-based).

## 3. Investigated and dismissed
- Kerberos weak encryption [2226001]: internal DC (192.168.10.3) traffic;
  normal Windows AD with older ciphers.
- DNS TLD rules (.to/.biz/.cc/.pw/.su/.xxx/.tw), STUN, NTLM, APT-UA,
  USER_AGENTS, Telegram/Dropbox/polyfill/azurewebsites/jsfiddle/ipify/
  freegeoip: informational, low volume, no confirmed malicious domains.
- ET HUNTING Javascript-Obfuscator [2036300] (2): Cloudflare 104.25.71.103 →
  internal hosts; web-content false positive, not attacker traffic.
- PE EXE/EXE-inline/Java ClassID INFO hits: outbound/legitimate downloads by
  internal clients (192.168.10.25), not part of the campaign.

## 4. Proposed suppressions (NEED ENGINEER APPROVAL — not applied)
Most Friday noise is already covered by the Monday baseline in
`config/threshold.config`. Friday-specific stream/parser noise still worth
suppressing (verify against the full 293-line file before adding):

    # STREAM SHUTDOWN RST invalid ack — half-close churn artifact, 1,200 in Friday raw
    suppress gen_id 1, sig_id 2210046

    # Applayer Wrong direction first Data — parser direction artifact, 30
    suppress gen_id 1, sig_id 2260001

    # HTTP too many warnings — parser housekeeping, 3
    suppress gen_id 1, sig_id 2221050

    # STREAM Packet with invalid timestamp — capture/stream artifact, 1
    suppress gen_id 1, sig_id 2210044

    # STREAM 3way handshake SYNACK with wrong ack — capture artifact, 1
    suppress gen_id 1, sig_id 2210007

Leave **unsuppressed**: 2019348 (DoS tool), the ET SCAN sids, 9500002, and the
new 9600001/9600002 rules — these are threat-tier.

## 5. Actions taken
- Wrote `rules/generated/friday_ddos_portscan.rules`:
  - `sid:9600001` — sustained HTTP GET flood (threshold 5,000 GETs/120s by
    source). Validated: fired 11x, all 04:27–04:45, all
    172.16.0.1 → 192.168.10.50.
  - `sid:9600002` — sustained inbound SYN sweep (threshold 15,000 SYNs/300s
    by source). Validated: fired 13x during the scan (03:22–03:25) plus a few
    during the flood's connection churn, all 172.16.0.1 → 192.168.10.50.
- **Deployment note:** the current `config/suricata.yaml` `rule-files` list
  only loads 3 specific generated files (bruteforce_campaigns.rules,
  tuesday_bruteforce.rules, wednesday_slowloris.rules — 4 rule files total
  including stock). `friday_ddos_portscan.rules` must be added to that list
  for the rules to deploy; suricata.yaml is read-only in this exercise.
  Validation was performed by temporarily loading the rules and re-running
  Friday-WorkingHours.pcap (logs/friday-validate-rules-v3).

## 6. Coverage gaps identified
- Stock ET 2019348 only fired 20x despite 94,486 terse GETs; closed by custom
  9600001 aggregate flood rule.
- Stock ET SCAN only alerts on its fixed list of known ports; the ~1,000-port
  SYN sweep was otherwise invisible. Closed by custom 9600002 sweep rule.
- SSH brute force is already covered by existing custom 9500002.
