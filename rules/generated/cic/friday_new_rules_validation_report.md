# Triage report — logs/friday-validate-new-rules/eve.json
Data: data/pcaps/Friday-WorkingHours.pcap (9,997,874 packets, full Friday capture)
Run: `friday-validate-new-rules`, 2026-09-15 23:37, 265 alerts / 22 signatures
Sensor: HOME_NET 192.168.10.0/24, EXTERNAL_NET = !HOME_NET, 80 baselined suppressions applied
(stock 52,647 ET Open rules + 9 custom rules loaded)

Purpose of the run: re-run the Friday campaign *with the newly written Friday
rules in place* and confirm they fire. They did not. Root cause below (§4).

---

## 1. Alert inventory by tier (265 alerts)

| Count | SID | Signature | Tier |
|---|---|---|---|
| 39 | 2010935 | ET SCAN Suspicious inbound to MSSQL 1433 | **threat** (scan) |
| 39 | 2010936 | ET SCAN Suspicious inbound to Oracle 1521 | **threat** (scan) |
| 39 | 2010937 | ET SCAN Suspicious inbound to mySQL 3306 | **threat** (scan) |
| 39 | 2010939 | ET SCAN Suspicious inbound to PostgreSQL 5432 | **threat** (scan) |
| 24 | 9500002 | CUSTOM SSH "Brute-Force Campaign Confirmed" | **threat** (scan — msg misleading) |
| 20 | 2019348 | ET DOS Terse HTTP GET Likely AnonMafiaIC DDoS tool | **threat** (DoS) |
| 10 | 2100371 | GPL ICMP PING Cisco Type.x | **threat** (recon/DoS, 172.16.0.2) |
| 9 | 2002910 | ET SCAN Potential VNC Scan 5800-5820 | **threat** (scan) |
| 8 | 2100366 | GPL ICMP PING *NIX | **threat** (recon/DoS, 172.16.0.1) |
| 7 | 2001219 | ET SCAN Potential SSH Scan | **threat** (scan) |
| 3 | 2002994/95 | ET SCAN Rapid IMAP/IMAPS brute force | **threat** (scan) |
| 2 | 2002992/93 | ET SCAN Rapid POP3/POP3S brute force | **threat** (scan) |
| 1 | 2001972 | ET SCAN fast Terminal Server traffic (RDP) | **threat** (scan) |
| 1 | 2210007 | SURICATA STREAM 3way handshake SYNACK wrong ack | engine noise (capture artifact) |
| 3 | 2221050 | SURICATA HTTP too many warnings | parser noise |
| 9 | 2012647 | ET INFO Dropbox.com Offsite File Backup | benign (external SaaS) |
| 1 | 2035593 | ET INFO DropBox User Content Domain | benign (external SaaS) |
| 4 | 2011540 | ET INFO OpenSSL Demo CA — Internet Widgits Pty | benign (self-signed certs) |
| 1 | 2013031 | ET INFO Python-urllib/ Suspicious UA | benign (internal automation) |
| 1 | 2014519 | ET INFO EXE - Served Inline HTTP | benign (Fortinet KB download) |

245 of 265 alerts are attacker traffic (231 × 172.16.0.1 → 192.168.10.50,
14 × 172.16.0.1/172.16.0.2 → 192.168.10.51); 20 are third-party/parser noise.

## 2. Confirmed attack — 2017-07-08, 172.16.0.1 → 192.168.10.50 (true positive)

Scoped counts (filter stated for each):

- **Port scan — 255,754 TCP flows** (`event_type=flow AND src_ip=172.16.0.1
  AND proto=TCP`), spread over every 1,000-port bucket from 0–65,000
  (ports 0–999: 119,037; 1000s: 33,760; … 65000s: 480) — a full-range sweep.
  Burst concentrated 03:22–03:27 (03:25 = 34,781 flows/min ≈ 580 flows/s).
  Also 268 UDP flows across ~30 port buckets and 62 SCTP flows — the UDP/SCTP
  half of the sweep produced **no alerts at all**.
  Stock ET SCAN fired on its fixed port list only (176 alerts total).
- **SSH probing — 31 app-layer SSH flows** (`event_type=ssh AND
  src_ip=172.16.0.1`, all banner-only, server OpenSSH_7.2p2), 02:43–02:47 and
  03:39–03:55. `event_type=ssh AND ssh.auth != null` returns **0 events**, i.e.
  no credential exchange is visible; SSH auth is encrypted (known structural
  limit). The ~240 SYN packets implied by the 24 × sid:9500002 alerts are SYN
  retries/passes of the same sweep, not 240 logins. Recommendation: reword
  sid:9500002's message — "brute-force" is not supported by the data; this is
  SSH scanning/banner grabbing.
- **HTTP GET flood — 94,613 HTTP transactions** (`event_type=http AND
  src_ip=172.16.0.1`): 94,570 to 192.168.10.50:80, of which 94,548 were
  answered **HTTP 200**; terse `GET /`, no Host, no User-Agent; 04:26:37–04:47,
  peak 5,047/min (04:36), mean ~75 req/s. Victim kept serving, so this is
  volumetric load, not a completed denial of service. Stock 2019348 fired 20×
  (~1/min, rate-limited) — a 3-order-of-magnitude under-report.
- **ICMP discovery — 172.16.0.2 → .50/.51** (10 × 2100371) and
  172.16.0.1 → .50/.51 (8 × 2100366); bursts of 5 echo requests inside 1 ms.
- **Pre-attack recon**: attacker browsed the victim's DVWA app (`/dv/`,
  `/dv/login.php`, Host `205.174.165.68` then `ip-68-165-174-205.ironcladservers.ca`)
  at 00:17–03:55 (24 transactions). No attack against the app on Friday.

**Verdict:** true positive, single external actor running recon → SSH sweep →
full port sweep/service enumeration → HTTP GET flood against 192.168.10.50.

## 3. Investigated and dismissed (false positives)

- **2014519** — 208.91.113.45 is Fortinet's support portal (`/kb/…`,
  fortinet_logo.gif); 192.168.10.25 fetched `/kb/viewAttachment.do?attachID=fgt2eth.exe`
  (FortiGate-to-Ethernet tool, 102,400 B). Legitimate software download.
- **2012647 / 2035593** — Dropbox file-sync between 162.125.4.5 / 162.125.18.133
  and .5/.8/.9/.14 (corporate SaaS backup).
- **2011540** — self-signed "OpenSSL Demo CA / Internet Widgits Pty" certs from
  195.142.109.125 (.5/.16) and 46.166.142.173 (.9/.17); informational rule.
- **2013031** — internal 192.168.10.25 → 151.101.0.223 (CDN) with Python-urllib UA.
- **2221050** — 3 × malformed external HTTP responses (198.54.12.96/.97 → .9/.16);
  parser housekeeping, no threat rule fired.
- **2210007** — single stream handshake artifact (pcap starts mid-flow).
- 192.168.10.51 ↔ 185.170.48.239:21 — outbound passive-mode FTP session to the
  public "mondorescue" mirror (48 `Failed to open file` replies). Not alerted and
  no credential abuse; noted, not actioned.

## 4. Validation finding — why the new Friday rules did not fire

- This run loaded **52,656 rules = 52,647 stock + 9 custom** (suricata.log),
  consistent with the three generated files named in `config/suricata.yaml`:
  `bruteforce_campaigns.rules` (2), `tuesday_bruteforce.rules` (5),
  `wednesday_slowloris.rules` (2). Neither `friday_ddos_portscan.rules`
  (9600001/9600002) nor `friday_ddos.rules` is in that list, and neither fired.
- **Canary check** (`logs/canary-load-check/`): a new file
  `rules/generated/canary_load_check.rules` containing sid:9900001 was added and
  the pcap re-run — the count stayed at exactly 52,656 and sid:9900001 never
  appeared. **New files under rules/generated/ are not auto-loaded**; the
  `rule-files` list is explicit. (Now reduced to a stub comment.)
- **Rules are not the problem.** Re-running the full Friday pcap with the two
  Friday rules temporarily loaded (`logs/friday-validate-rules-v3/`, 52,658
  rules) gives sid:9600001 ×11 and sid:9600002 ×13 on this same capture.
- **sid:9500003 was mis-tuned even when loaded.** Replica test
  (`logs/validate-9500003-threshold/`, two temporary rules loaded into
  `wednesday_slowloris.rules`, then reverted byte-for-byte):
  sid:9500097 (exact replica: GET "/", 5000/60 s) fired only **4×**
  (04:32, 04:34, 04:36, 04:43) — it needs 83.3 req/s and the flood averages
  ~75 req/s, so most of the 21 minutes are invisible; sid:9500098
  (method-agnostic, 6000/120 s) fired **10×**, evenly spread 04:27–04:45.

## 5. Actions taken / required

Taken (writable paths only):
- `rules/generated/friday_ddos.rules` — retuned sid:9500003 to **rev:2**
  (method-agnostic request flood, 6,000 requests/120 s by source, validated at
  10 alerts on this capture) with the full rationale in the header.
- `rules/generated/canary_load_check.rules` — reduced to a stub; the temporary
  validation rules were removed from `wednesday_slowloris.rules` and that file
  was restored exactly.

Required from the engineer (cannot be done from this session — `suricata.yaml`
is read-only here):
1. Add to `config/suricata.yaml` → `rule-files:`:
   `rules/generated/friday_ddos_portscan.rules` and
   `rules/generated/friday_ddos.rules`.
2. Decide on the overlap: sid:9600001 (GET-specific, 5000/120 s, 11 alerts) vs
   sid:9500003 rev:2 (any-method, 6000/120 s, 10 alerts). Deploying both is
   fine for coverage but produces two alerts per GET flood.
3. Reword sid:9500002 — the capture shows SSH scanning, not a brute-force
   campaign (0 auth events, 31 banner-only exchanges).

## 6. Proposed suppressions (NEED APPROVAL — not written to threshold.config)

Each verified as still alerting in this run, i.e. not already suppressed.
Add under a new "Friday validation run" heading in `config/threshold.config`:

    # Fortinet KB fgt2eth.exe download by 192.168.10.25 — legitimate vendor site
    suppress gen_id 1, sig_id 2014519

    # Dropbox desktop backup (162.125.4.5 / 162.125.18.133 -> HOME_NET) — sanctioned SaaS
    suppress gen_id 1, sig_id 2012647
    suppress gen_id 1, sig_id 2035593

    # Self-signed "OpenSSL Demo CA / Internet Widgits Pty" certs on outbound TLS —
    # informational only, 4 hits, no threat rule correlated
    suppress gen_id 1, sig_id 2011540

    # Internal host 192.168.10.25 using Python-urllib against a CDN — automation
    suppress gen_id 1, sig_id 2013031

    # HTTP parser "too many warnings" — decoder housekeeping, same class as 2221010/2221036
    suppress gen_id 1, sig_id 2221050

    # STREAM SYNACK wrong ack — pcap starts mid-connection, same class as 2210010/2210020
    suppress gen_id 1, sig_id 2210007

Leave unsuppressed: 2019348, all ET SCAN sids (2010935-2010939, 2002910,
2001219, 2992-2995, 2001972), GPL ICMP 2100366/2100371, 9500002, 9600001/9600002,
9500003 — all threat-tier.

## 7. Coverage gaps

1. **UDP/SCTP sweep invisible** — 268 UDP flows over ~30 port buckets and 62
   SCTP flows produced zero alerts. A per-source volume rule cannot catch it
   (only ~7 UDP flows/min because the scanner waits for ICMP unreachables); a
   distinct-port counter is needed, and the hostbits chaining attempted earlier
   was rejected because Suricata applies hostbits side effects regardless of
   threshold. Not written, deliberately — a rule tuned to these numbers would be
   as dead as sid:9500003 rev:1 was.
2. **ET SCAN coverage is a fixed port list** — 255,754 sweep flows produced 176
   alerts, all on ports ET knows. Closed by 9600002 once deployed.
3. **SSH auth outcome unknowable** (encrypted) — attempts are detectable,
   success is not. Restated from the Tuesday investigation; still true here.
4. **Deployed-rule drift** — the ruleset that produced this eve.json is not the
   ruleset in `rules/generated/`. Any triage of a run directory must first check
   the "N rule files processed" line; otherwise "the rule didn't fire" is
   indistinguishable from "the rule wasn't there".
