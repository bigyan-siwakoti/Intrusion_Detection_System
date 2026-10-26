# Triage report — logs/friday-raw/eve.json (CIC-IDS2017 Friday Working-Hours)

Analyst: IDS triage pass, 2026-09-21. Scope: one eve.json (1,412,449 alerts, 82 signatures).
Sensor: Suricata 8.0.6, HOME_NET 192.168.10.0/24, known attacker 172.16.0.1.
Raw run context (logs/friday-raw/suricata.log):
`4 rule files processed. 52656 rules successfully loaded` and
`threshold-config: Error opening file: ""` — i.e. **no threshold.config was applied**
in the raw run, so Monday-baseline-suppressed noise is present at full volume.

Every number below is labelled with the filter that produced it.

---

## 1. Big picture

Capture-wide (`count_alerts` on logs/friday-raw/eve.json) the top signatures are engine
artefacts, not threat traffic:

| Count | Signature | SID | Tier |
|---|---|---|---|
| 1,390,304 | SURICATA TCPv4 invalid checksum | 2200074 | capture artefact (offload) |
| 7,359 | SURICATA HTTP Response excessive header repetition | 2221036 | HTTP parser |
| 7,279 | SURICATA Ethertype unknown | 2200121 | capture artefact |
| 1,207 / 1,200 / 1,145 / 718 | SURICATA STREAM * (invalid ack / RST / FIN) | 2210045/46/16/38 | stream engine |
| 569 | SURICATA Kerberos 5 weak encryption | 2226001 | internal AD policy |
| 343 / 192 / 186 / 181 | ET INFO APT-UA / USER_AGENTS / TLS handshake / .to TLD | — | informational |

Of the 1.39M checksum alerts, 191,037 involve the attacker
(filter: `select(.event_type=="alert" and (.src_ip=="172.16.0.1" or .dest_ip=="172.16.0.1"))`)
— scoped evidence that this signature tracks the campaign traffic, but it carries no
detection value (the pcap is captured before NIC checksum insertion).

Only three real campaigns exist in this capture. Two were already known; **one was
completely undetected** (section 3A).

---

## 2. What I investigated

Attack-relevant signatures, scoped to the attacker/victim pair
(filter: `select(.event_type=="alert" and (.src_ip=="172.16.0.1" or .dest_ip=="172.16.0.1"))`):

| Count | Signature | SID |
|---|---|---|
| 39 / 38 / 38 / 35 | ET SCAN inbound to mySQL 3306 / MSSQL 1433 / PostgreSQL 5432 / Oracle 1521 | 2010937/35/39/36 |
| 24 | CUSTOM SSH Brute-Force Campaign Confirmed | 9500002 |
| 20 | ET DOS Terse HTTP GET (AnonMafiaIC) | 2019348 |
| 8 / 7 | ET SCAN VNC scan / Potential SSH Scan | 2002910 / 2001219 |
| 3 / 3 / 2 / 2 / 1 | ET SCAN Rapid IMAPS / IMAP / POP3 / POP3S / Terminal Server | 2002995/94/92/93/2001972 |
| 8 / 10 | GPL ICMP PING (*NIX from .1, Cisco Type.x from .2) | 2100366 / 2100371 |

Flow volume (`event_type=="flow" and src_ip=="172.16.0.1"`): 256,087 flows, of which
256,087−2 go to 192.168.10.50 (2 to .51). The attacker touched **one** internal target.

App-layer inventory for the pair (`select(.src_ip=="172.16.0.1" and .dest_ip=="192.168.10.50")`):
flow 256,087 · http 94,594 · ftp 31 · ssh 31 · smb 37. Everything else is the victim
answering.

---

## 3. Confirmed attacks (all from 172.16.0.1, all true positives)

### 3A. ARES-style botnet C2 — 5 infected internal hosts  ***UNDETECTED***

Filter: `select(.event_type=="alert" and .dest_ip=="205.174.165.73")` → **769 alerts, every
one of them `SURICATA TCPv4 invalid checksum` or `STREAM` noise. Zero signature hits.**
Reverse direction (`src_ip=="205.174.165.73"`) → stream noise only.

Filter: `select(.event_type=="http" and .dest_ip=="205.174.165.73")`:

| Internal host | bot id | GET /api/pop | POST /api/upload | POST /api/report | UA |
|---|---|---|---|---|---|
| 192.168.10.5 | mitacs-pc3 | 96 | 8 | 5 | python-requests/2.14.2 |
| 192.168.10.8 | mitacs-pc2 | 107 | 6 | 4 | python-requests/2.14.2 |
| 192.168.10.9 | mitacs-pc6 | 135 | 10 | 6 | python-requests/2.14.2 |
| 192.168.10.14 | mitacs-pc5 | 124 | 10 | 5 | python-requests/2.18.1 |
| 192.168.10.15 | mitacs-pc4 | 204 | 10 | 6 | python-requests/2.14.2 |

- Window: 2017-07-07 **22:34 → 23:32** (filter: same query, `.timestamp[0:16]`).
- `GET /api/pop?botid=<botid>&sysinfo=Windows%20<ver>` = task polling/check-in (666 total).
- `POST /api/upload` = **exfiltration**: 44 uploads of random-named JPEGs
  (e.g. `rBpRN.jpg`, `SnhXg.jpg`), 41,350–102,102 bytes each ≈ **4 MB of screenshots in <1 h**
  (filter: `select(.event_type=="fileinfo" and .dest_ip=="205.174.165.73")`).
- `POST /api/report` = 26 host reports, 609–5,493 B.
- C2 replies HTTP 200 with an empty or 3/7/10-byte body (task codes)
  (filter: `... and .src_ip|startswith("192.168.10") and .dest_ip=="205.174.165.73"` → `status/len`).
- Same infrastructure as the Thursday reverse shell (205.174.165.73:444) — cross-day attribution.
- The `python-requests` UA from HOME_NET to EXTERNAL_NET occurs **only** for this C2 in the
  whole capture; no stock rule matches `python-requests` at all (ET 2013031 covers `python-urllib`).

### 3B. Broad TCP port scan / SYN sweep (hour 03)

- 256,087 flows 172.16.0.1 → 192.168.10.50 in total; **160,064 of them to non-80 ports**
  (filter: `... and .dest_port!=80`).
- Per-port flow histogram is flat at 160–162 for every port returned (query returned ~380
  ports before the output cap) → ≈**1,000 distinct destination ports**, full 1–65535 range
  (1, 4, 6, 7, 13, 17, 24, 25, 30… 31337, 32771-85, 50003, 65129, 65389 observed).
- Service banner grabs from the same source (filter per protocol):
  FTP 31× `cmd=(vsFTPd 3.0.3)` banner only · SSH 31× banner only · SMB 37× `SMB1_COMMAND_NEGOTIATE_PROTOCOL`.
- Stock coverage: the ET SCAN rules fired 176× total, only for the ports they know about.

### 3C. HTTP GET flood / DoS (04:26–04:47)

- 94,561 terse `GET /` with **no Host and no User-Agent** (filter:
  `select(.event_type=="http" and .src_ip=="172.16.0.1")` grouped by method/host/UA/url).
- 94,564 transactions to 192.168.10.50:80 were answered **HTTP 200** (filter:
  `... and .dest_ip=="192.168.10.50"` grouped by status) → the service stayed up; impact was load.
- Peak minute 04:36 = 5,047 requests (~84 req/s), 21-minute flood.
- Stock ET 2019348 fired only 20× (~1/min, internally rate-limited).

### 3D. Secondary activity

- ICMP host discovery: 172.16.0.1 → .50/.51 (4+4) and **172.16.0.2** → .50/.51 (5+5).
  172.16.0.2 does nothing else in the capture (single query: flows + alerts = ICMP only).
- DVWA recon 00:17–01:36: ~40 HTTP GETs 172.16.0.1 → 192.168.10.50 with
  `Host: 205.174.165.68`, UA Firefox/45.0, URLs `/`, `/dv/`, `/dv/login.php`,
  `/dv/dvwa/css/login.css`. Not covered by any rule (low volume; noted as a minor gap).

---

## 4. Correction to a previous conclusion: there was NO SSH brute force

The earlier Friday triage report (`friday_triage_report.md`) describes a "Phase 3 SSH
brute-force campaign (31 connection attempts … spaced ~2 minutes apart)" and
`friday_ddos_portscan.rules` repeats it. The data does not support this:

- `select(.event_type=="ssh")` grouped by src + client version: 1,081 events from nine
  HOME_NET hosts, **all carrying client software `JSCH-0.1.51`**, versus 31 events from
  172.16.0.1 with **client software ABSENT** (server banner `OpenSSH_7.2p2` only).
  On Tuesday's real SSH-Patator campaign Suricata logged the client fingerprint
  (`paramiko_2.0.0`) on 2,979 events — a real client always identifies itself.
- Flows to :22 from the attacker (filter: `event_type=="flow" … dest_port==22`): 263 total,
  payload buckets 1 pkt/60 B (20), 2 pkt/120 B (109), 3 pkt/206 B (101), 5 pkt/338 B (31).
  Only the 31 five-packet banner reads reach the SSH parser. That is nmap service
  detection during the 3B sweep, not authentication traffic.
- Consequently CUSTOM **9500002 fired 23–24× on scan SYNs** (threshold 10 SYNs/3600 s;
  263 SYNs ÷ 10 ≈ 26 fires) and mislabels them "SSH Brute-Force Campaign Confirmed".
  It is not an attack, and it is not a benign false positive either — it is a mis-scoped
  rule (see proposal 7B).

Verdict: the Friday SSH activity is **scan banner-grabbing**; no SSH auth attempt, no success.

---

## 5. Investigated and dismissed

- DNS TLD alerts (.to/.biz/.cc/.pw/.su/.xxx) — every hit is an internal client → internal
  DNS 192.168.10.3 (e.g. `2027757 | 192.168.10.14 -> 192.168.10.3`); normal browsing.
- TLS SNI inventory (52,303 events) — all legitimate CDN/ad/social/OS-telemetry domains.
- 8.253.104.126 "generating" 113,953 alerts — all `TCPv4 invalid checksum` (capture artefact).
- ET HUNTING JS-obfuscator 2036300 (2): 104.25.71.103 → .8/.14, web content, not attacker traffic.
- 192.168.10.51 → 185.170.48.239:21 (44 failed `RETR`, mondorescue mirror) — benign user download.
- Internal host→host FTP/SMB/SSH (e.g. .5/.12/.14/.16 → 192.168.10.50:21 `STOR`; .5/.8/.9/.14/.15 → DC .3 over SMB2) — normal lab activity.
- Kerberos weak-encryption alerts 2226001 — 192.168.10.50/.19/.17 → DC .3, AD policy.
- `ps13/pubsub.pubnub.com` (04:34) and `telegram.me` (03:47) DNS from 192.168.10.14 — outside
  the 22:34–23:32 C2 window, so not treated as bot C2; noted only.

---

## 6. Actions taken (threat → rule, auto-deployed per project design)

Ruleset arithmetic used to verify deployment (from suricata.log, no config file read needed):
stock = 52,647 rules; raw run = 4 files / 52,656 (= stock + bruteforce_campaigns 2 +
tuesday_bruteforce 5 + wednesday_slowloris 2 = 9 custom). A new file in `rules/generated/`
is **not** auto-loaded (confirmed twice: my first run reported "4 rule files processed …
52,658" with the new file present, and `canary_load_check.rules` documents the same test).

**Written and deployed:** `rules/generated/friday_botnet_c2.rules` (record copy) and the same
three rules appended to `rules/generated/bruteforce_campaigns.rules`, which **is** in the
config's rule-files list, so they are live:

| SID | Detection |
|---|---|
| 9700001 | bot C2 check-in — `GET /api/pop?` + `botid=`, HOME_NET → EXTERNAL_NET |
| 9700002 | bot C2 exfiltration — `POST /api/upload` or `/api/report`, HOME_NET → EXTERNAL_NET |
| 9700003 | `python-requests` UA from HOME_NET to EXTERNAL_NET (botnet client fingerprint) |

`threshold: type limit, track by_src, count 1, seconds 3600` on all three: the beacon repeats
every 1–3 s at peak (666 requests), so per-request alerting would add noise, not information.

**Validation:** re-ran the full capture — `logs/friday-botnet-validate2/`.
`4 rule files processed. 52661 rules successfully loaded, 0 rules failed, 0 rules skipped`
(+3 rules = mine). Result: **9700001 ×5, 9700002 ×5, 9700003 ×5 — one alert per infected host
(.5/.8/.9/.14/.15), first at 22:34, zero false positives.**

**Already-covered campaign detections (verified firing in the same run):**
`sid:9600003` HTTP GET Flood ×10 and `sid:9600004` Inbound SYN sweep ×13. No action needed —
but note the stale duplicate copy of the same logic in `friday_ddos_portscan.rules`
(sids 9600001/9600002, dead code, not loaded). `friday_botnet_ares.rules`
(sids 9600005–9600007) covers the same C2 URIs but port-8080-scoped; my 970000x rules are
the port-agnostic equivalent. **Deploy one botnet rule set, not both.**

---

## 7. Proposals requiring engineer approval (NOT applied)

### 7A. Suppressions (verified still unsuppressed by re-running with the current threshold.config)

    # SURICATA HTTP too many warnings — Suricata's own parser housekeeping warning.
    # 3 events in the Friday raw run; no security content. Filter: capture-wide count_alerts.
    suppress gen_id 1, sig_id 2221050

    # SURICATA STREAM 3way handshake SYNACK with wrong ack — pcap starts mid-connection,
    # stream state artefact. 1 event in the raw run and 1 with the tuned config.
    suppress gen_id 1, sig_id 2210007

Optional, lower value (engine/INFO noise, all benign here, currently unsuppressed):

    # ET INFO OpenSSL Demo CA - Internet Widgits Pty (O) — lab self-signed DVWA certificate. 4 events.
    # suppress gen_id 1, sig_id 2011540

**Deliberately NOT proposed:** `ET INFO Dropbox.com Offsite File Backup` (2012647),
`DropBox User Content Domain in TLS SNI` (2035593), `ET INFO EXE - Served Inline HTTP`
(2014519), `ET INFO Python-urllib/ Suspicious User Agent` (2013031). Low volume (1–9 each),
but the Thursday infiltration used Dropbox and an inline EXE download is a plausible
malware-delivery signal — suppressing these would trade away real detection surface.

### 7B. Fix the mis-scoped SSH rule 9500002 (rule change, not a suppression)

Current `alert tcp … port 22; flags:S; threshold 10/3600s` fires on port-scan SYNs.
Replace the trigger with a real SSH client so Tuesday's campaign still trips it while
scan banner-grabs do not:

    alert ssh $EXTERNAL_NET any -> $HOME_NET 22 ( \
        msg:"CUSTOM SSH Brute-Force Campaign Confirmed - sustained SSH client sessions from one external host"; \
        flow:to_server,established; \
        ssh.software; content:"SSH-"; \
        threshold: type threshold, track by_src, count 10, seconds 3600; \
        classtype:attempted-recon; \
        sid:9500002; rev:2;)

Tuesday's paramiko client banner is present on 2,979 events (would still fire); Friday's
31 banner-reads have no client banner (would not fire). I have not applied this because it
changes the behaviour of a rule Tuesday's detection depends on — say the word and I will
re-validate it against the Tuesday pcap before deploy.

---

## 8. Coverage gaps identified

1. **Botnet C2 over HTTP — was 100% blind.** Closed by 9700001–9700003. Not closed by any
   stock rule, and the Friday-specific `friday_botnet_ares.rules` / `friday_ddos*.rules`
   files are dead code until added to `config/suricata.yaml` (read-only here).
2. **Broad SYN sweep — stock ET SCAN only knows ~11 ports** (176 alerts for a ~1,000-port
   sweep). Covered by 9600004 (fires 13×).
3. **High-rate GET flood — stock 2019348 is rate-limited to ~1/min** (20 alerts for 94,561
   requests). Covered by 9600003 (fires 10×).
4. **Service enumeration / banner grabbing** (FTP/SSH/SMB version probes by an external host)
   has no dedicated rule; only partially implied by the volumes above. Candidate for a
   future "external host completing N service handshakes on distinct ports" rule.
5. **External web-app recon** against DVWA paths (`/dv/…`) is uncovered (40 requests here).
6. No coverage for UDP/ICMP-based discovery beyond the GPL ICMP PING rules (which did fire).
