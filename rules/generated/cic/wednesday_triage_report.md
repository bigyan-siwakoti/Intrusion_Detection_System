# Triage Report — logs/wednesday-raw/eve.json (2017-07-05)

## Scope
- Single eve.json, **2,310,105 alert events** across **76 signatures**.
- HOME_NET: 192.168.10.0/24. Known attacker: 172.16.0.1.
- Raw run had **no threshold.config applied** (suricata.log: `threshold-config: Error opening file: ""`),
  so normally-suppressed baseline noise is present at full volume.

## 1. Big picture
The overwhelming majority is engine/decoder noise, not threat traffic:

| Count | Signature | Tier |
|---|---|---|
| 2,283,035 | SURICATA TCPv4 invalid checksum [2200074] | capture/checksum artifact |
| 8,773 | SURICATA HTTP Response excessive header repetition [2221036] | HTTP parser noise |
| 7,535 | SURICATA Ethertype unknown [2200121] | capture artifact |
| 2,219 | SURICATA STREAM Packet with invalid timestamp [2210044] | stream noise |
| 1,410 | SURICATA STREAM Packet with invalid ack [2210045] | stream noise |
| 1,329 | SURICATA STREAM CLOSEWAIT FIN out of window [2210016] | stream noise |
| 1,323 | SURICATA STREAM SHUTDOWN RST invalid ack [2210046] | stream noise |
| 531 | SURICATA Kerberos 5 weak encryption parameters [2226001] | internal AD policy |
| 294 | ET INFO TLS Handshake Failure [2029340] | informational |
| ... | DNS TLD / STUN / NTLM / APT-UA / USER_AGENTS | informational |

Only two real threat campaigns were present:

- **Slowloris / HTTP DoS** against 192.168.10.50:80
  - ET 3000001 (187), ET 3000002 (6), ET WEB_SERVER 2014103 (3)
- **OpenSSL Heartbleed (CVE-2014-0160)** against 192.168.10.51:444
  - ET EXPLOIT 2018377 (1), SURICATA TLS 2230014 (2)

## 2. Confirmed attack A — Slowloris HTTP DoS (172.16.0.1 -> 192.168.10.50:80)

### Alert/IP scoping
- `select(.event_type=="alert" and .alert.signature_id in (3000001,3000002,2014103))`
  produced 196 alerts, **all** `172.16.0.1 -> 192.168.10.50:80`.
- First Slowloris-specific alert: **22:45:37**, last: **23:14:31** (+0930).

### Application-layer evidence (all scoped to 172.16.0.1 -> 192.168.10.50)
- 167,552 HTTP events: **166,685 GET** and **867 FAKEVERB**.
- 1,054 requests carried `https://github.com/shekyan/slowhttptest/` as referer —
  the slowhttptest toolkit repository.
- 867 `FAKEVERB /dv/login.php` requests — slowhttptest's alternate non-standard verb.
- HTTP status distribution: 164,787x 200, 2,255 null (incomplete/slow requests),
  491x 400, 1x 500 (the 500 occurred on a FAKEVERB request at 22:56:21).
- Flow scoping: 174,598 flows attacker->victim; 162,777 closed, 6,804 new,
  5,017 established to port 80.

### Second phase — Hulk-style cache-busting GET flood
- `select(.event_type=="http" and .src_ip=="172.16.0.1" and .dest_ip=="192.168.10.50" and timestamp 23:15..23:31)`
  produced **149,703 GET requests**, 149,693 returned HTTP 200.
- Peak rate ~10k requests/min; every URI was `/ ?<random>=<random>` (cache-busting).
- Stock rate rule 2014103 only fired 3 times across the whole campaign, so this
  phase was almost invisible to the stock ruleset.

### Verdict
True positive: deliberate multi-phase HTTP DoS using slowhttptest (Slowloris +
FAKEVERB + high-rate cache-busting GET flood).

### Action taken
Updated `rules/generated/wednesday_slowloris.rules`:
- `sid:3000003` catches the FAKEVERB verb via raw TCP payload (`depth:8`) because
  Suricata does not expose that non-standard method in `http.method`/`http.request_line`.
- `sid:3000004` catches the cache-busting GET flood.
- Removed duplicate SIDs 3000001/3000002 (already present in stock ET Open).

Validation (`logs/wednesday-final-validate2`): 3000003 fired 463x, 3000004 fired 95x.

## 3. Confirmed attack B — OpenSSL Heartbleed (172.16.0.1 -> 192.168.10.51:444)

### Recon
- 5x GPL ICMP PING from 172.16.0.1 to 192.168.10.51 (03:29:36-37, 03:39:45-47).
- 8 flows from 172.16.0.1 to 192.168.10.51:444; 6 short TLS handshakes before the
  exploit, all with the same self-signed cert (`Internet Widgits Pty Ltd`) and
  identical JA3 `7c657f99ee40e9602437b4c56bcc4c16`.

### Exploitation
- Flow `172.16.0.1:45022 -> 192.168.10.51:444`, 03:42:15 to 04:02:43:
  - `bytes_toserver = 1,963,593` (~1.9 MB sent)
  - `bytes_toclient = 81,482,031` (~81.5 MB returned)
- A normal TLS handshake to that service was ~350-850 B up / ~0.4-1.6 KB down.
  The 81.5 MB return is the Heartbleed out-of-bounds memory disclosure (repeated
  ~64 KB heartbeat reads).
- Alerts: ET 2018377 fired once (server->attacker large heartbeat response);
  SURICATA 2230014 fired twice.

### Verdict
True positive; exploitation succeeded and exfiltrated ~81.5 MB of server memory.

### Action taken
Updated `rules/generated/wednesday_heartbleed.rules`:
- `sid:7600101` direction-scoped invalid encrypted heartbeat to HOME_NET.
- `sid:7600102` TLS handshake burst recon (count 5 / 300s).
- `sid:7600103` non-standard TLS port probing; fixed port-negation bug so it now
  includes TCP/444 (`$HOME_NET ![443,8443]`).
- The stock rules already fire on this campaign (2018377/2230014); the custom
  rules add direction scoping and recon detection.

## 4. Investigated and dismissed
- Kerberos weak encryption [2226001]: all `192.168.10.3` (internal DC) -> internal
  hosts; normal Windows AD with older ciphers.
- DNS TLD rules (.biz/.cc/.to/.su/.pw): internal clients querying internal DNS
  192.168.10.3; low volume, no confirmed malicious domains.
- TLS Handshake Failure [2029340]: external CDNs/internet hosts to internal hosts;
  normal failed TLS negotiation.
- STUN/NTLM/APT-UA/USER_AGENTS/Telegram/Dropbox/polyfill: informational, benign.
- Java/self-signed/OpenSSL demo CA INFO hits: outbound or internet background
  noise; not the confirmed campaigns.

## 5. Proposed suppressions (NEED ENGINEER APPROVAL — not applied)
The current threshold.config already covers the Monday-baseline noise. Additional
Wednesday-specific stream-engine noise is proposed for suppression:

    # STREAM Packet with invalid timestamp — capture/stream artifact (2,219 in Wednesday raw)
    suppress gen_id 1, sig_id 2210044

    # STREAM SHUTDOWN RST invalid ack — half-close churn artifact (1,323)
    suppress gen_id 1, sig_id 2210046

    # STREAM FIN2 invalid ack — mid-stream capture artifact (72)
    suppress gen_id 1, sig_id 2210036

Leave **unsuppressed**: 2221035 (HTTP Request excessive header repetition) is a
strong Slowloris tell; 3000001/3000002/2014103/2018377/2230014 are threat-tier.

## 6. Coverage gaps identified
- Stock 2014103 only fired 3x despite ~150k cache-busting GET requests in 17 min;
  closed by custom `sid:3000004`.
- Suricata's HTTP parser does not expose the FAKEVERB method to `http.method`
  detection, so the stock rules could not see it; closed by custom `sid:3000003`
  using a raw TCP `depth:8` match.
- Heartbleed's decisive 81.5 MB leak is only visible in cumulative flow bytes,
  which no packet rule can match; custom rules anchor on the heartbeat anomaly and
  recon burst instead.
