# Automated Generation of Intrusion Detection Rules Using Generative AI in a Rule-Based IDS Deployment

An interim report submitted in partial fulfilment of the requirements for the award of the degree of Bachelor of Information Technology

**Group 13**

| Student | ID |
|---------|-----|
| Bigyan Siwakoti | S386010 |
| Irab Baral | S387115 |
| Binay Siwakoti | S387596 |
| Shashwat Acharya | [Student ID] |

**Supervisor:** Prof. Bharanidharan Shanmugam

CHARLES DARWIN UNIVERSITY
FACULTY OF SCIENCE AND TECHNOLOGY
September 2026

---

## Declaration

We hereby declare that the work herein, now submitted as an interim report for the degree of Bachelor of Information Technology at Charles Darwin University, is the result of our own investigations, and all references to ideas and work of other researchers have been specifically acknowledged. We hereby certify that the work embodied in this interim report has not already been accepted in substance for any degree, and is not being currently submitted in candidature for any other degree.

Signature: _______________
Date: 16 September 2026

---

## List of Abbreviations

| Abbreviation | Definition |
|---|---|
| AI | Artificial Intelligence |
| API | Application Programming Interface |
| C2 | Command and Control |
| CIC | Canadian Institute for Cybersecurity |
| CVE | Common Vulnerabilities and Exposures |
| DDoS | Distributed Denial of Service |
| DoS | Denial of Service |
| ET | Emerging Threats |
| FTP | File Transfer Protocol |
| HIDS | Host-based Intrusion Detection System |
| IDS | Intrusion Detection System |
| IDPS | Intrusion Detection and Prevention System |
| LLM | Large Language Model |
| ML | Machine Learning |
| NDJSON | Newline-Delimited JSON |
| NIDS | Network-based Intrusion Detection System |
| NIST | National Institute of Standards and Technology |
| pcap | Packet Capture |
| SID | Signature Identifier |
| SMB | Server Message Block |
| SOC | Security Operations Centre |
| SSH | Secure Shell |
| SSE | Server-Sent Events |
| TLS | Transport Layer Security |
| XSS | Cross-Site Scripting |

---

## Abstract

Network intrusion detection systems rely on human analysts to investigate alerts, author detection rules, and tune sensor configurations — a labour-intensive process that creates a structural bottleneck between attack identification and detection capability. This project investigates whether a generative language model can automate this analyst workflow within a rule-based intrusion detection deployment, preserving the deterministic and inspectable nature of signature-based detection while substantially reducing the human effort required.

We present an agentic triage engine that connects hosted language model APIs to a Suricata IDS deployment, providing the model with investigative tools to query alert data, correlate network flows, author detection rules, and validate them through engine replay. The system was evaluated against the CIC-IDS2017 dataset across all four attack days using three model configurations (Claude Opus 5, DeepSeek V3, and DeepSeek V4 Pro). The system produced 24 AI-authored detection rules (22 retained), and identified 12 of 14 confirmed attack categories in the dataset — including brute force, denial of service, cross-site scripting, SQL injection, reverse shell infiltration, and port scanning — and closed multiple coverage gaps in the stock community ruleset. The two undetected categories (DoS GoldenEye and Bot/ARES) represent gaps that are themselves a finding, informing future work on detection coverage.

**Keywords:** intrusion detection system, generative AI, Suricata, rule generation, CIC-IDS2017, agentic triage

---

## I. Introduction

### Background

Intrusion detection systems (IDS) are a core component of network security infrastructure, responsible for monitoring network traffic and identifying indicators of malicious activity. Among the approaches to intrusion detection, signature-based systems remain the dominant open-source deployment model. These systems match network traffic against databases of human-authored rules, offering deterministic behaviour, inspectable alerts, and low false-positive rates when properly configured (Roesch 1999; Khraisat et al. 2019).

However, this approach carries a structural limitation: if no rule exists for an attack pattern, the attack passes undetected regardless of how sophisticated the detection engine may be. The detection capability of a signature-based IDS is entirely bounded by the rules available to it. This dependency was identified as early as Anderson's (1980) foundational work on computer security threat monitoring and remains the principal weakness of misuse detection systems three decades later (Khraisat et al. 2019).

When a new attack is identified — whether through alert investigation, threat intelligence, or incident response — the process of translating that identification into a detection rule is manual. An analyst must examine the traffic, identify distinguishing characteristics, author a rule in engine-specific syntax, validate it against both attack and benign traffic, and deploy it to production sensors. Scarfone and Mell (2007) describe this cycle as requiring hours to days and specialised expertise that is scarce in the cybersecurity workforce. This bottleneck represents a significant operational risk, particularly for organisations that lack dedicated security operations centre (SOC) staffing.

This project investigates whether a generative language model can automate this cycle — not by replacing the detection engine, but by replacing the human analyst in the alert-handling loop. Detection remains fully rule-based and inspectable throughout; the model authors rules that the deterministic engine evaluates.

### Project Scope

The project uses Suricata 8.0.6 in offline packet capture (pcap) replay mode against the CIC-IDS2017 dataset (Sharafaldin, Habibi Lashkari & Ghorbani 2018). An AI triage engine connects to hosted model APIs and is equipped with tools to query alert data, read configurations, write detection rules, and execute Suricata for validation. The model does not classify traffic directly — it authors rules that the deterministic engine evaluates. Machine learning is excluded by design, in accordance with the project's commitment to inspectable, rule-based detection.

### Aim and Objectives

The primary research question is: *Can a large language model replace the human analyst in the alert-handling loop of a rule-based IDS, and what context does it need to do that job well?*

To address this question, the project pursues two objectives:

1. **Design and implement an agentic triage engine** that provides a generative language model with the investigative tools and procedural guidance necessary to perform the full analyst workflow — from initial alert assessment through to rule authoring and validation.

2. **Evaluate the system's detection capability** across multiple attack categories by comparing AI-authored rules against the stock community ruleset, measuring coverage gaps closed, and assessing whether different models produce equivalent findings.

### Structure of Report

The remainder of this report is organised as follows. Section II presents a review of the relevant literature, examining the landscape of intrusion detection systems, the rule-authoring bottleneck, and the emerging application of generative AI to security operations. Section III describes the approach taken, including the system architecture and design decisions. Section IV details the execution of the triage engine across all four attack days of the CIC-IDS2017 dataset and presents preliminary results. Section V analyses and discusses the findings, including model comparison, rule quality, and the implications of raw versus suppressed alert data. Section VI summarises the work completed to date, and Section VII outlines future work.

---

## II. Literature Review

### Introduction

This review examines three intersecting domains: the taxonomy and foundations of intrusion detection systems, the knowledge-acquisition bottleneck in rule-based detection, and the emerging application of generative AI to security rule authoring. The review is organised thematically, progressing from foundational concepts through the limitations that motivate this project to recent work that directly informs the approach. The aim is to establish the gap this project addresses: the application of generative AI not merely to rule generation in isolation, but to the complete analyst workflow within a network IDS deployment.

### Intrusion Detection Systems: Taxonomy and Foundations

The concept of automated intrusion detection was first formalised by Denning (1987), who proposed a model for real-time detection based on monitoring audit records for deviations from established user profiles. This foundational work established the two principal approaches that persist in modern systems: misuse detection, which matches observed activity against known attack patterns, and anomaly detection, which flags deviations from a baseline of normal behaviour.

Intrusion detection systems are broadly classified into three categories: signature-based (misuse detection), anomaly-based, and specification-based (Khraisat et al. 2019). Signature-based systems such as Snort (Roesch 1999) and its multi-threaded successor Suricata match network traffic against databases of known attack patterns. Their principal advantage is determinism — every alert traces to a human-readable rule — making them the preferred choice for environments requiring auditability and forensic clarity (Scarfone & Mell 2007). Paxson (1999) reinforced this principle with the Bro network monitor (now Zeek), demonstrating that real-time semantic analysis of network traffic could support both signature matching and policy-based detection at operational scale.

[INSERT FIGURE: Fig. 2-1 — IDS taxonomy diagram showing signature-based, anomaly-based, and specification-based approaches with their characteristics]

Anomaly-based systems establish a baseline of normal behaviour and flag deviations. While capable of detecting novel attacks, they suffer from high false-positive rates and produce classifications that are difficult to interpret or audit (Liao et al. 2013; Garcia-Teodoro et al. 2009). This interpretability gap is significant in regulated environments where incident response requires demonstrable reasoning chains. Aljanabi, Ismail and Ali (2021) identify this as a persistent challenge, noting that despite advances in machine-learning classifiers, the inability to explain detection decisions remains a barrier to operational deployment. Axelsson (2000) further demonstrated the base-rate fallacy problem: even a highly accurate anomaly detector produces an overwhelming number of false positives when the base rate of intrusions is low relative to normal traffic, rendering the system operationally impractical.

Sommer and Paxson (2010) provided a comprehensive analysis of why machine learning has struggled to gain traction in network intrusion detection, identifying fundamental challenges including the difficulty of obtaining representative training data, the high cost of errors in security contexts, and the semantic gap between statistical anomalies and actionable security findings. Their work argued that the most productive role for automated techniques was to support human analysts rather than replace their judgement entirely — a position that directly informs the design philosophy of this project.

Specification-based detection, first formalised by Ko, Ruschitzka and Levitt (1997), defines acceptable system behaviour through explicit specifications and flags violations. Sekar et al. (2002) extended this to network intrusion detection, demonstrating that specification-based approaches combine the low false-positive rates of signature detection with some ability to detect novel attacks that violate specifications. However, specification maintenance is labour-intensive — the specification must be updated whenever the protected system changes, which has limited practical adoption.

### The Rule-Authoring Bottleneck

The structural limitation of signature-based IDS is well documented in the literature. Khraisat et al. (2019) identified the dependence on human-authored signatures as the primary weakness: zero-day attacks and novel variants pass undetected until a rule is written. Scarfone and Mell (2007) described the analyst workflow — traffic analysis, invariant identification, rule authoring, syntax validation, behavioural testing, and deployment — as a multi-hour to multi-day process requiring specialised knowledge of both attack techniques and engine rule syntax.

This bottleneck is fundamentally a knowledge-acquisition problem. The analyst possesses tacit expertise in identifying what distinguishes attack traffic from legitimate traffic, and must translate that understanding into the formal syntax of the detection engine. The window between an attack becoming identifiable and becoming detectable is a labour constraint rather than a technical one, representing a significant operational risk in resource-constrained environments. Buczak and Guven (2016) noted in their survey of machine learning for cyber intrusion detection that the scarcity of domain expertise remains one of the primary obstacles to effective IDS deployment, regardless of the detection methodology employed.

The Emerging Threats (ET) Open ruleset, maintained by Proofpoint, addresses this partially through community-sourced rule development, providing over 52,000 rules covering known attack signatures. However, community rulesets are necessarily reactive — they cover known attacks observed in the wild — and coverage gaps exist for specific attack variants and deployment contexts, as demonstrated in our preliminary results where the stock ruleset missed entire attack categories present in the evaluation dataset.

### Generative AI for Security Operations

The emergence of large language models (LLMs) capable of generating structured text has opened new possibilities for automating security operations tasks that were previously considered exclusively human. The transformer architecture (Vaswani et al. 2017) that underpins modern LLMs enables these models to process and generate formally structured outputs, including code, configuration files, and — as this project demonstrates — intrusion detection rules.

Recent work has begun exploring generative language models for automating security rule authoring specifically. Zhang et al. (2025) demonstrated automated generation of detection rules for malicious software packages using large language models, achieving syntactically valid rules that detected known malware patterns. Their work focused on package-level signatures rather than network-level detection rules, but established that LLMs can produce formally structured security rules when given appropriate context and examples.

Hadi, Yasmin and Shoker (2026) directly addressed IDS rule generation with GenTI, a benchmark for evaluating LLM performance in autonomous IDPS rule generation for unseen attacks. Their benchmark showed that baseline LLM-generated rules detected 45% of unseen attacks, rising to 87.4% with CTI mapping and iterative refinement. GenTI generates rules from curated payload corpora; this project instead gives the model investigative access to sensor output, enabling it to author rules from the traffic patterns it discovers during triage rather than from pre-assembled threat descriptions.

Ferrag et al. (2020) surveyed deep learning techniques for cybersecurity, cataloguing approaches across intrusion detection, malware analysis, and network traffic classification. While their focus was on neural network-based detection rather than rule generation, their analysis of the limitations of purely automated approaches — particularly the need for interpretable outputs and the challenge of adapting to novel attack patterns — reinforces the design decision in this project to keep the model in an advisory and authoring role rather than a classification one.

The agentic paradigm — where a language model is given tools and pursues goals through iterative tool use rather than single-shot generation — represents a significant departure from earlier approaches to AI-assisted security. Rather than asking the model to generate a rule from a description, the agentic approach provides the model with the same investigative capabilities available to a human analyst and allows it to conduct its own investigation before authoring rules. This approach is informed by the broader shift in AI systems design from prompt-response patterns to tool-augmented reasoning (Anthropic 2025).

### Summary

The literature establishes that rule-based detection is effective but bottlenecked by human authoring; machine-learning alternatives sacrifice the interpretability that operational environments require; and generative AI for rule authoring is an emerging field with demonstrated potential but limited work specifically on network IDS triage. The gap this project addresses is the application of generative AI not merely to rule generation in isolation, but to the complete analyst workflow — investigation, correlation, decision-making, and rule authoring — within a network IDS deployment. The agentic approach, where the model drives its own investigation using provided tools, distinguishes this work from prior efforts that treated rule generation as a single-shot translation task.

---

## III. Approach

In this section, we describe the system architecture, the design decisions that shaped the implementation, and the changes made from the original project plan as understanding deepened through iterative development.

### System Architecture

The system follows a pipeline architecture with clear separation between the detection engine and the AI triage layer.

[INSERT FIGURE: Fig. 3-1 — System architecture diagram showing Suricata → eve.json → AI Triage Engine → Detection Rules / Suppress Proposals, with the Web UI for real-time streaming]

**Stage 1 — Detection.** Suricata 8.0.6 (OISF 2026) processes pcap files against the ET Open community ruleset (Proofpoint 2026; 52,647 rules) and writes all events — alerts, DNS queries, TLS handshakes, HTTP transactions, and flow records — to `eve.json` in newline-delimited JSON (NDJSON) format. A baseline is established by processing benign traffic (CIC-IDS2017 Monday, 529,918 flows, all labelled BENIGN) and suppressing all false positives. This produced 80 documented suppress rules in `threshold.config`, mirroring real SOC practice. After tuning, Monday produces zero alerts.

**Stage 2 — Triage.** The AI triage engine processes attack-day alerts using eight tools: alert counting, NDJSON aggregation via a purpose-built `count_by` function, arbitrary `jq` queries on `eve.json`, file reading, file writing, file appending, Suricata execution for rule validation, and directory listing. The model follows a six-step triage procedure encoded in the system prompt: (1) establish the big picture, (2) categorise alerts, (3) investigate each category, (4) deep-dive into specific flows, (5) take action, and (6) report findings.

**Stage 3 — Output.** The model produces two categories of output, governed by a safety asymmetry. For confirmed threats, the model writes Suricata detection rules to a designated directory; these are deployed automatically. For false positives, the model proposes suppressions that require human approval before application. This asymmetry prevents the model from silently degrading sensor coverage — an over-alerting IDS is wrong-way-safe, whereas a blind IDS is wrong-way-unsafe.

### Agentic Loop Architecture

Hosted language models such as Claude and DeepSeek are, at their core, text-generation systems — they accept a prompt and return a completion. They do not inherently possess the ability to query databases, read files, or execute programs. To transform such a model into an autonomous investigative agent, the system implements a tool-calling loop that mediates between the model and the operating environment.

The loop operates as follows. On each turn, the engine sends the model the conversation history together with a schema describing every available tool (its name, parameters, and purpose). Instead of generating a plain-text reply, the model may return a structured tool-call request — for example, `count_by(eve_path="logs/tuesday/eve.json", field=".alert.signature")`. The engine validates the request, executes the corresponding Python function, and appends the result to the conversation as a new tool-result message. The model then inspects that result and decides its next action: issue another tool call, reason about the findings, or produce a final report. This cycle repeats until the model emits a text-only response (indicating it has finished) or a configurable turn limit is reached.

This architecture is significant for two reasons. First, it preserves the model's reasoning capabilities while granting it controlled access to real data — the model decides *what* to investigate and *in what order*, but every interaction with the filesystem or the detection engine passes through a validated tool interface. Second, it makes the system model-agnostic: any model that supports tool-calling can drive the same investigation loop, enabling fair comparison across providers without rewriting the triage logic.

The system prompt encodes a six-step triage procedure (establish the big picture, categorise alerts, investigate each category, deep-dive into specific flows, take action, report findings) that guides the model's use of tools. This procedural guidance structures the investigation so the model follows a methodology comparable to a human analyst's workflow.

### Provider Adapter Pattern

A provider adapter pattern enables the same triage loop to work with Claude (Anthropic API) and DeepSeek (OpenAI-compatible API), ensuring fair model comparison. Both providers receive identical system prompts, identical tool definitions, and identical triage procedures. The adapter translates between the two API formats transparently, so the agentic engine operates without knowledge of which model is driving the investigation.

### Tool Design

A critical finding during development was that tool design matters as much as model choice. DeepSeek V3 failed completely on initial triage runs because it attempted to use `jq` aggregation operations (`group_by`, `unique`, `min_by`, `max_by`) that are incompatible with NDJSON streaming format. The model exhausted its turn limit without completing triage. The solution was a purpose-built `count_by` tool that performs aggregation in Python using `collections.Counter`, avoiding the NDJSON limitation entirely. After this addition, DeepSeek completed triage successfully. This demonstrates that providing appropriately shaped tools can compensate for model limitations — a lower-cost model with better tools can match a more capable model with generic tools.

### Web Interface

A web interface built with FastAPI and Server-Sent Events (SSE) streams the entire triage process in real-time, allowing observation of the model's investigative decisions, tool calls, and reasoning. The interface supports concurrent triage sessions across multiple browser tabs, enabling parallel analysis of different datasets or model comparisons. During evaluation, four simultaneous triage runs were executed successfully through a single server instance.

[INSERT FIGURE: Fig. 3-2 — Web UI screenshot showing model selection dropdown, run selector, and live triage streaming panel]

### Changes from Original Project Plan

As understanding deepened through iterative development, several design improvements were made:

1. **Pass rules replaced with alert-only rules.** The original plan included Suricata `pass` rules for whitelisting known-good traffic. Investigation revealed that a `pass` match on a TCP connection passes the entire flow, and Suricata stops scanning it — an attacker whose opening packets appear normal receives uninspected passage for the remainder of the connection. All rules are now `alert` only.

2. **Custom normality rules replaced with ET Open plus threshold suppression.** The original approach required writing detection rules from scratch for every service. Starting from a mature community ruleset and tuning through suppressions mirrors real SOC workflow, produces wider detection surface immediately, and is more defensible methodologically.

3. **Scope broadened from rule generation to full triage automation.** Rather than generating rules from individual alerts, the system performs the complete analyst workflow: investigation, correlation, decision-making, and rule authoring.

4. **CIC-IDS2017 replaced the purpose-built test environment.** The labelled dataset provides reproducible ground truth for evaluation, enabling systematic comparison rather than anecdotal demonstration.

### Summary

The approach centres on providing a generative language model with the investigative tools and procedural guidance necessary to perform the full analyst triage workflow. The system preserves rule-based detection throughout, maintains a safety asymmetry between detection and suppression, and supports fair model comparison through a provider adapter pattern. The design prioritises inspectability — every rule the system produces is human-readable, every investigation step is logged, and every detection decision traces to a specific rule.

---

## IV. Execution and Preliminary Results

This section describes the execution of the triage engine across all four attack days of the CIC-IDS2017 dataset and presents the results obtained. Each attack day was processed in at least two configurations: a tuned pass with Monday baseline suppressions applied, and a raw pass with no suppressions, enabling comparison of triage effectiveness under different noise conditions.

### Evaluation Dataset

The CIC-IDS2017 dataset (Sharafaldin, Habibi Lashkari & Ghorbani 2018) was produced by the Canadian Institute for Cybersecurity at the University of New Brunswick. It contains five consecutive days of network traffic captured between 3–7 July 2017 in a purpose-built testbed that simulates a realistic enterprise environment with both normal user activity and staged attacks.

**Testbed topology.** The victim network occupies 192.168.10.0/24 and comprises: a web server at 192.168.10.50 running the DVWA (Damn Vulnerable Web Application); an Ubuntu server at 192.168.10.51 running TLS services on non-standard ports; a Windows domain controller at 192.168.10.3 (domain Testbed1.ca); and several workstations including .8, .12, .25, and others. The external attacker operates from 172.16.0.1, and a command-and-control server is located at 205.174.165.73. This topology is referenced throughout the results.

**Capture structure.** The first day (Monday, `Monday-WorkingHours.pcap`) contains only benign traffic — 529,918 flows, all labelled BENIGN in the ground truth — and serves as the corpus for baseline sensor tuning. The remaining four days each stage specific attack families against the testbed alongside normal background traffic.

**Ground truth labels.** Each capture has a corresponding CSV file generated by CICFlowMeter containing 85 columns of per-flow features. The `Label` column (column 85) classifies each flow as either BENIGN or a specific attack category. These labels serve as the ground truth for evaluating detection coverage. Table 4-1 summarises the dataset structure.

| Weekday | Dataset Filename | Attack Categories | Labelled Attack Flows |
|---------|-----------------|-------------------|----------------------|
| Monday | `Monday-WorkingHours` | None (benign baseline) | 0 |
| Tuesday | `Tuesday-WorkingHours` | FTP-Patator, SSH-Patator | 7,938 + 5,897 |
| Wednesday | `Wednesday-workingHours` | DoS Hulk, DoS GoldenEye, DoS Slowloris, DoS Slowhttptest, Heartbleed | 231,073 + 10,293 + 5,796 + 5,499 + 11 |
| Thursday | `Thursday-WorkingHours` | Web Attack Brute Force, Web Attack XSS, Web Attack SQL Injection, Infiltration | 1,507 + 652 + 21 + 36 |
| Friday | `Friday-WorkingHours` | DDoS, PortScan, Bot (ARES) | 128,027 + 158,930 + 1,966 |

*Table 4-1: CIC-IDS2017 dataset structure — captures, attack categories, and ground-truth flow counts.*

**Why this dataset.** CIC-IDS2017 is selected because it provides labelled ground truth at the flow level, covers a broad taxonomy of attack types (brute force, denial of service, web application attacks, infiltration, DDoS, port scanning, and botnet), includes realistic background traffic, and is publicly available for reproducibility. Its limitations — the traffic is nine years old and the attack tools are dated — are accepted; the purpose is to evaluate the triage methodology, not to claim coverage of contemporary threats.

### Credential Brute Force

This capture (`Tuesday-WorkingHours` in the dataset) produced 2,404 alerts across two signatures after baseline suppression. The ground truth labels indicate 7,938 FTP-Patator and 5,897 SSH-Patator attack flows.

Both Claude Opus 5 and DeepSeek V3 independently identified:

- **FTP brute force** from attacker 172.16.0.1 to victim 192.168.10.50: 11,891 failed login attempts (response code 530) and exactly one successful login (response code 230) using password "1234". Post-login activity consisted solely of a SYST command followed by session timeout — no data exfiltration occurred.
- **SSH brute force** using the paramiko 2.0.0 toolkit: approximately 2,980 flows to port 22, with no confirmed successful authentication.

Claude wrote two campaign-level threshold rules (SID 9500001–9500002). DeepSeek wrote five rules including a stateful two-stage detection chain using Suricata's `hostbits` facility (SID 9000001–9000005) — the chain flags an attacker IP after repeated failures, then triggers a higher-severity alert when that flagged host achieves a successful login.

[INSERT FIGURE: Fig. 4-1 — Web UI screenshot showing the triage engine during a live investigation, with tool calls and model reasoning visible in the streaming panel (illustrative run captured for this figure; not part of the evaluation set)]

### Denial of Service and Heartbleed Exploitation

Two passes were conducted on this capture (`Wednesday-workingHours` in the dataset). The tuned pass used DeepSeek V3; the raw pass used DeepSeek V4 Pro.

**Tuned pass (381 alerts, DeepSeek V3).** The model identified Slowloris/Slowhttptest denial-of-service activity comprising 167,552 HTTP requests from 172.16.0.1 to 192.168.10.50, including 867 FAKEVERB requests and 1,054 requests carrying the slowhttptest toolkit referer. HeartBleed probing (CVE-2014-0160) was also identified on a non-standard TLS port (444) targeting 192.168.10.51. V3 authored three detection rules (SID 3000001–3000003) covering the slowhttptest toolkit fingerprint, sustained referer bursts, and FAKEVERB method requests.

**Raw pass (2,310,105 alerts, DeepSeek V4 Pro).** Despite 99.97% of alerts being engine noise, the model identified the same attacks and additionally discovered a Hulk-style HTTP GET cache-busting flood (149,703 requests) that had no dedicated rule in the stock ET Open ruleset. A new rule (SID 3000004) was written and validated at 95 hits. During this pass, V4 Pro also observed V3's earlier rules firing in the raw data: SID 3000001 (Slowloris toolkit fingerprint) fired 187 times versus the stock ET rule's 3 hits. V4 Pro discovered a bug in SID 3000003 (FAKEVERB detection) and diagnosed the root cause — Suricata's HTTP parser does not expose non-standard HTTP methods to the `http.method` detection buffer — then rewrote the rule using raw TCP payload matching at `depth:8`, achieving 463 hits. However, V4 Pro also deleted SID 3000001 and 3000002 from the rules file, claiming they were stock ET Open rules — a claim that was incorrect (see Section V, Model Errors).

The model also performed forensic analysis of the Heartbleed exploitation, determining that the attacker sent 1.9 MB of crafted heartbeat requests and received 81.5 MB of server memory in return — compared to normal TLS handshake sizes of 350–850 bytes. V4 Pro authored three Heartbleed-specific rules (SID 7600101–7600103), covering the exploit itself, the reconnaissance burst preceding it, and probing of non-standard TLS ports.

### Web Application Attacks and Network Infiltration

This capture (`Thursday-WorkingHours` in the dataset) contains web application attacks and network infiltration. Triage was conducted in both tuned (25,399 alerts) and raw (1,346,596 alerts) configurations.

**Web attacks (172.16.0.1 → 192.168.10.50).** The model identified three distinct attack phases against the DVWA web application:

1. **HTTP login brute force:** 1,826 POST requests to `/dv/login.php` at a sustained rate of 47–48 requests per minute, producing 1,820 failures and 6 successful logins. The stock ET ruleset did not fire any brute-force signature for this attack — a significant coverage gap.

2. **Reflected cross-site scripting:** Suricata SID 2009714 fired 891 times on this traffic; the triage model reported over 1,801 script probes to the same endpoint in its rule documentation. The discrepancy between alert count and HTTP request count is unresolved pending Experiment 2. All contained `<script>` payloads that executed successfully (HTTP 200 responses). Stock ET SID 2009714 correctly detected these.

3. **Union-based SQL injection:** 15 requests to `/dv/vulnerabilities/sqli/` including `union select database(), user()`, `union select null, table_name from information_schema.tables`, and `union select user, password from users`. All returned HTTP 200 with data — the extraction succeeded. Stock ET rules 2010963, 2017808, and 2016672 detected these.

**Infiltration (192.168.10.8 compromised).** The model traced a complete post-compromise kill chain from the compromised internal host 192.168.10.8:

1. **Reverse shell:** Five outbound TCP sessions to external command-and-control server 205.174.165.73 on port 444, carrying 15.2 MB of interactive Windows `cmd.exe` session data.

2. **Lateral movement:** Systematic SMB NEGOTIATE_PROTOCOL sweep across six internal hosts (.9, .12, .16, .17, .19, .50), followed by SYSVOL GPO template reads and DCE/RPC SAMR/LSARPC domain enumeration against the domain controller.

3. **Data staging:** 44 FTP uploads of hex-named `.txt` files to 192.168.10.50 using credentials obtained from the credential brute force attack on Tuesday (iscxtap/1234).

4. **Internal scanning:** Broad SYN sweep from .8 targeting .5, .14, and .15 with approximately 28,000 flows at peak rates of 2,000 SYNs per minute.

**Raw pass additional finding:** A second reverse shell victim (192.168.10.25) was identified communicating with the same C2 server, with 13.6 MB uploaded. Stock ET produced no alert for this host — the detection was only possible through flow-level analysis in the raw data.

Six detection rules were authored (SID 7600001–7600006) covering web login brute force, SMB lateral sweep, reverse shell C2 communication, FTP data staging, SYSVOL GPO reconnaissance, and DCE/RPC enumeration. An additional rule (SID 7600007) was authored from the raw pass to detect internal SYN sweeps.

### Distributed Denial of Service, Port Scanning, and Botnet

This capture (`Friday-WorkingHours` in the dataset) contains distributed denial-of-service attacks, port scanning, and botnet activity. Triage was conducted in both tuned (525 alerts) and raw (1,412,449 alerts) configurations.

**Port scan (172.16.0.1 → 192.168.10.50).** A broad TCP SYN sweep covering approximately 1,000 distinct ports with over 160,000 inbound flows, including banner grabbing of discovered services (FTP, SMB, SSH). Stock ET SCAN rules detected only the fixed known-port subset (MySQL, PostgreSQL, Oracle, VNC).

**SSH brute force.** 526 flow records to port 22 with 62 SSH banner exchanges from the known attacker host (172.16.0.1). SID 9500002, authored by Claude during the credential brute force triage (Tuesday), fired 48 times on this traffic. Whether these flows carry an SSH-Patator label in the ground truth or fall under the broader PortScan/BENIGN labels awaits the label join in Experiment 2.

**HTTP GET flood (04:26–04:47).** 189,188 terse GET requests with no User-Agent header at a sustained rate of approximately 160 requests per second. All 189,128 responses returned HTTP 200, confirming the web server was overwhelmed with legitimate-looking requests. The stock ET rule 2019348 fired only 40 times for this 189,000-request campaign.

**Raw pass additional findings.** The complete kill chain was mapped: reconnaissance → ICMP discovery → SSH brute force → broad port scan → HTTP DDoS. Two detection rules were authored (SID 9600001–9600002) for sustained HTTP GET floods and broad SYN sweeps, validated at 11 and 13 hits respectively on replay.

### Summary

Across all four attack days, the AI triage engine identified 12 of 14 confirmed attack categories present in the CIC-IDS2017 dataset. Two categories were not detected: DoS GoldenEye on Wednesday (10,293 labelled flows, possibly subsumed under the broader Hulk DoS detection but not separately named) and Bot/ARES on Friday morning (1,966 labelled flows, which produced no stock alerts and were not surfaced during triage). A total of 24 detection rules were authored across all sessions (22 retained in the repository; two deleted by a model error documented in Section V), closing multiple coverage gaps in the stock ET Open ruleset. The raw passes consistently revealed findings invisible to the tuned passes, demonstrating that while baseline suppression substantially reduces cost overheads, it can mask detection opportunities. Table 4-2 summarises the execution results.

| Capture | Model(s) | Tuned Alerts | Raw Alerts | Attack Categories Found | Rules Retained | Key Gaps Closed |
|---------|----------|-------------|------------|------------------------|---------------|-----------------|
| Tuesday | Claude Opus 5, DeepSeek V3 | 2,404 | — | FTP brute force, SSH brute force | 7 (SID 9000001–9000005, 9500001–9500002) | Stateful brute force chain |
| Wednesday | DeepSeek V3, V4 Pro | 381 | 2,310,105 | DoS Hulk, Slowloris, Slowhttptest, Heartbleed | 5 (SID 3000003–3000004, 7600101–7600103) | FAKEVERB DoS, Hulk flood, Heartbleed |
| Thursday | DeepSeek V4 Pro | 25,399 | 1,346,596 | HTTP brute force, XSS, SQLi, Infiltration (reverse shell, lateral movement, data staging) | 7 (SID 7600001–7600007) | Web login brute force, SMB sweep, 2nd reverse shell victim |
| Friday | DeepSeek V4 Pro | 525 | 1,412,449 | DDoS, PortScan | 3 (SID 9500003, 9600001–9600002) | HTTP GET flood campaign, broad SYN sweep |

*Table 4-2: Execution summary — captures, models used, alert volumes, attack categories identified, and coverage gaps closed by AI-authored rules.*

---

## V. Analysis and Discussion

This section analyses the findings from the triage execution, examining model comparison, the quality of AI-authored rules relative to stock community rules, the implications of raw versus suppressed data, and the observed cross-day generalisation behaviour.

### Introduction

The results presented in Section IV demonstrate that the AI triage engine successfully performed the analyst workflow across all four attack days. This section examines what those results reveal about the research question: whether a generative language model can replace the human analyst in the alert-handling loop, and under what conditions.

### Model Comparison

On the credential brute force capture (Tuesday) — the only capture both model families were run against — Claude Opus 5 and DeepSeek V3 reached identical substantive conclusions on every attack category. No confirmed attack was found by one model and missed by the other. DeepSeek V3 was used for the Wednesday tuned pass; DeepSeek V4 Pro was used for the Wednesday raw pass, Thursday, and Friday. The models differed in efficiency, cost, and rule sophistication.

| Metric | Claude Opus 5 | DeepSeek V3 | DeepSeek V4 Pro |
|--------|---------------|-------------|-----------------|
| Captures triaged | Tuesday | Tuesday, Wednesday (tuned) | Wednesday (raw), Thursday, Friday |
| Turns (Tuesday tuned) | Not logged (CLI run) | 44 | — |
| Turns (Wednesday) | — | 38 (tuned) | 81 (raw, incl. V3 rule validation) |
| Turns (Thursday) | — | — | 62 (tuned), 47 (raw) |
| Turns (Friday) | — | — | 58 (tuned), 63 (raw) |
| Key findings (Tuesday) | FTP + SSH brute force | FTP + SSH brute force (identical) | — |
| Rules written | 2 (SID 9500001–9500002) | 8 (SID 9000001–9000005, 3000001–3000003; 3000001–3000002 later deleted — §V) | 14 new (SID 3000004, 7600001–7600007, 7600101–7600103, 9500003, 9600001–9600002); also rewrote V3's SID 3000003 |
| Rule approach | Campaign-level thresholds | Stateful chains, tool fingerprints | Forensic analysis, parser workarounds |

*Table 5-1: Model comparison across triage runs. Turn counts are from session transcripts.*

DeepSeek V4 Pro demonstrated a notable capability that neither Claude nor DeepSeek V3 exhibited: diagnosing and working around a Suricata parser limitation. When the FAKEVERB detection rule produced zero hits, V4 Pro identified that Suricata's HTTP parser does not expose non-standard methods to the `http.method` buffer, then rewrote the rule using raw TCP payload matching — achieving 463 hits where the previous approach achieved none.

The model-agnostic nature of the approach is its most significant practical finding. On Tuesday — the only capture where both model families were tested — both reached equivalent conclusions, suggesting that the value lies in the tool-augmented workflow rather than any single model's capabilities. A formal cost comparison requires citing each provider's published pricing and controlling for input/output token ratios, which is deferred to the final report.

### AI-Authored Rules vs Stock Community Rules

AI-authored rules outperformed stock ET Open rules in several specific areas, as summarised in Table 5-2.

| Attack | Stock ET Alerts | AI Rule Alerts | Improvement |
|--------|----------------|----------------|-------------|
| Slowloris/Slowhttptest | 3 (SID 2014103) | 187 (SID 3000001, later removed — see §V Model Errors) | 62× |
| FAKEVERB DoS method | 0 (no rule) | 463 (SID 3000003) | New detection |
| Hulk GET flood | 0 (no rule) | 95 (SID 3000004) | New detection |
| HTTP login brute force | 0 (no rule) | Authored (SID 7600001); replay validation pending (Experiment 2) | New coverage |
| Reverse shell (.25) | 0 (missed) | Authored (SID 7600003); replay validation pending (Experiment 2) | New coverage |
| SMB lateral sweep | Parser noise only | Authored (SID 7600002); replay validation pending (Experiment 2) | New coverage |
| Friday HTTP DDoS | 40 (SID 2019348) | 11 campaign confirmations (SID 9600001) | Campaign-level |
| Friday SYN sweep | Known ports only | 13 confirmations (SID 9600002) | Broader coverage |

The improvements fall into three categories. First, **quantitative improvement** where the AI rule detects substantially more instances of the same attack (Slowloris: 187 vs 3, a 62× improvement). Second, **new coverage** where the stock ruleset has no detection for the attack category — with validated hit counts for FAKEVERB and Hulk flood, and rules authored but awaiting replay validation for HTTP brute force, reverse shell (.25), and SMB lateral sweep. Third, **campaign-level detection** where the AI rule provides context-aware detection that the stock rule's per-packet approach cannot (stateful brute force chains, sustained flood confirmation).

### Raw vs Suppressed Data

A consistent finding across all days was that the raw (unsuppressed) pass revealed detections invisible to the tuned pass. The second reverse shell victim on Thursday (192.168.10.25) produced no stock alert and was only identified through flow-level analysis that the tuned pass's smaller dataset did not prompt the model to undertake. Similarly, the Wednesday Hulk flood was discovered through the raw pass when the model investigated the high-volume noise signatures that the tuned pass had filtered out.

This presents a practical trade-off. Suppressed data substantially reduces cost overheads by limiting the token volume processed by the model — a tuned Wednesday pass processes 381 alerts versus 2,310,105 in the raw pass. However, the raw pass provides the model with complete visibility, enabling the discovery of coverage gaps that are structurally invisible when the noise floor is pre-filtered. For production deployments, this suggests a two-pass strategy: an initial tuned pass for cost-efficient routine triage, followed by periodic raw passes for coverage gap discovery.

### Cross-Day Generalisation

SID 9500002, authored by Claude during the credential brute force triage (Tuesday), fired 48 times on Friday traffic from the known attacker host. This suggests that the AI-authored rules may capture generalisable attack behaviours rather than dataset-specific artefacts, though formal confirmation awaits the label join in Experiment 2 — the Friday ground truth labels do not include an SSH-Patator category, so these 48 firings may correspond to PortScan or BENIGN-labelled flows rather than confirmed SSH brute force.

Similarly, the FTP credentials obtained during the credential brute force (iscxtap/1234) were reused by the compromised host in the infiltration capture (Thursday) for data staging via FTP uploads — a cross-capture correlation the model identified during triage, connecting the brute force outcome to the infiltration campaign.

### Model Errors and Rule Provenance

The triage logs reveal an instructive error in model reliability. DeepSeek V3 originally authored three rules for the Wednesday Slowloris campaign (SID 3000001–3000003) during the tuned pass. When DeepSeek V4 Pro subsequently ran the raw pass — which loaded V3's rules alongside the stock ruleset — and observed SID 3000001 and 3000002 firing, it deleted both rules from the file, asserting in its output that they were stock ET Open rules that should not be redeclared. This claim was false — `grep -c 'sid:3000001' rules/suricata.rules` and `grep -c 'sid:3000002' rules/suricata.rules` both return zero matches. The SID range 3000001–3000002 does not exist in the ET Open ruleset; both rules were authored by V3 and deleted by V4 Pro on the basis of a hallucinated provenance claim.

V4 Pro also rewrote SID 3000003 in place (changing from `http.method` to raw TCP `depth:8` matching), contrary to the project convention that generated rules are never hand-edited — modifications are a finding to record, not a correction to apply silently. The original V3 rule text for all three SIDs is preserved in the triage transcripts (authoring: `triage-2026-09-04-04-10-26.txt`; deletion: `triage-2026-09-15-11-26-28.txt`).

This episode is significant for two reasons. First, it demonstrates that models can make confident but incorrect claims about external system state (the content of a 44 MB ruleset) that are difficult to verify in real time. Second, the deleted rules were among the most effective detections produced — SID 3000001 fired 187 times on Slowloris traffic where the nearest stock rule fired 3 times. The total count of AI-authored rules is therefore 24 authored across all sessions, with 22 retained in the repository after V4 Pro's deletions.

### Summary

The analysis demonstrates that the AI triage engine produces detection rules that fire substantially more on attack traffic than stock community rules for the specific attacks present in the evaluation dataset. On Tuesday, the only day both model families were run, both produced equivalent findings, suggesting the approach is not dependent on a single model. Raw data analysis reveals coverage gaps invisible to suppressed passes. The critical engineering insight is that tool design is as important as model capability — purpose-built tools for NDJSON aggregation transformed a failing model into a successful one. The model error documented above — where V4 Pro deleted effective rules on a false premise — demonstrates that autonomous rule management requires safeguards against hallucinated claims about external system state. Two attack categories (DoS GoldenEye and Bot/ARES) were not detected, indicating that the system's coverage is not complete and that further investigation is needed into why these categories did not surface.

---

## VI. Summary

This section draws together the findings from the work completed to date.

The triage engine successfully performed the analyst workflow across all four attack days, identifying 12 of 14 confirmed attack categories in the CIC-IDS2017 dataset — including brute force, denial of service, cross-site scripting, SQL injection, reverse shell infiltration, lateral movement, DDoS, and port scanning. Two categories were not identified: DoS GoldenEye (10,293 flows on Wednesday, potentially subsumed under the broader Hulk DoS detection but not separately distinguished) and Bot/ARES (1,966 flows on Friday morning, producing no stock alerts and not investigated by the triage engine). These gaps are themselves informative — they indicate scenarios where neither the stock ruleset nor the AI-driven investigation surfaced the attack, and they define targets for future detection work.

Twenty-four AI-authored detection rules were produced across all sessions (22 retained; two deleted by a model error — see Section V, Model Errors), closing multiple coverage gaps in the stock ET Open community ruleset. AI-authored rules fired substantially more on attack traffic than stock rules for specific attack categories, with improvements of 62× for Slowloris detection to entirely new detection capabilities for attacks the stock ruleset does not cover. Formal evaluation of rule precision and recall against ground-truth labels is pending (see Future Work, Experiment 2).

Detection remains fully rule-based and inspectable throughout. The safety asymmetry preventing autonomous suppression is implemented — the model proposes suppressions but cannot apply them without human approval — though it has not yet been formally tested through deliberate adversarial probing.

Three findings have practical implications beyond the immediate project scope. First, tool design matters as much as model choice: a model that failed completely was made successful by providing a purpose-built aggregation tool, suggesting that investment in tool engineering may yield better returns than investment in more capable models. Second, raw data analysis reveals coverage gaps invisible to suppressed passes, motivating a two-pass triage strategy for production deployments. Third, preliminary evidence suggests AI-authored rules may generalise across captures, though formal validation against ground-truth labels is required. Fourth, models can make confident but false claims about external system state — the deletion of effective rules on a hallucinated premise highlights the need for safeguards in any autonomous rule management workflow.

---

## VII. Future Work

This section outlines the remaining work required to complete the project. Remaining work falls into three categories: formal experimentation, system evaluation, and production architecture.

**Experiment 1 — Does context matter?** The current system provides the model with tool access to all eve.json event types (alerts, DNS, TLS, HTTP, flow records), but the full context bundle described in the design (Section III) — comprising 30-day source history, destination asset context, concurrent activity within a ±5 minute window, and rule firing history — has not yet been implemented. Building this bundle and conducting a controlled experiment comparing triage accuracy with bare alert data versus the full context bundle will determine whether structured enrichment materially improves detection outcomes, or whether raw tool access to eve.json is sufficient.

**Experiment 2 — Quantitative rule evaluation.** All 24 AI-authored rules — including the two recovered from the triage transcript — will be formally evaluated against CIC-IDS2017 ground truth labels, measuring precision, recall, and false-positive rate. This evaluation will provide quantitative evidence of rule quality rather than the qualitative assessment presented in this interim report.

**Experiment 3 — Convergence testing.** Replaying benign traffic over N triage cycles with the suppression and detection loop enabled will determine whether alert volume decreases across iterations — a falling curve would demonstrate that the system improves its detection posture iteratively without machine learning.

**Production deployment architecture.** The current system operates in offline pcap replay mode. Extending to live deployment would require several architectural additions:

- **Time-windowed alert batching.** Rather than processing a complete pcap file, the system would accumulate alerts over a configurable time window (e.g. 5–15 minutes) and trigger triage on each batch. This converts the current batch-oriented pipeline to a near-real-time continuous operation.
- **Automated triage scheduling.** Triage runs would be triggered automatically when the alert batch reaches a configurable threshold (count or time), rather than requiring manual initiation through the web interface.
- **Live rule reloading.** Suricata supports rule reload via its Unix control socket (`suricatasc -c reload-rules`) without restarting the engine. AI-authored rules would be deployed immediately to the running sensor, closing the detection gap within minutes of identification rather than waiting for the next scheduled update.
- **Multi-sensor and multi-model routing.** Enterprise deployments typically operate multiple sensors at network boundaries. The triage engine would route alerts from each sensor to the appropriate model based on traffic volume, criticality, and cost constraints — for example, using a lower-cost model for routine triage and a more capable model for deep investigation of high-severity alerts.
- **SOC analyst dashboard.** A web-based dashboard presenting the model's suppress proposals for human approval, with the full reasoning chain visible for each recommendation. This implements the safety asymmetry (Section III) in a production workflow.

**Performance optimisation at scale.** The current system's per-query latency is dominated by `jq` scanning the full eve.json file for each tool call. At enterprise scale, three optimisations would substantially reduce triage time: (1) pre-splitting eve.json by event type (alerts, HTTP, flow, TLS, DNS) so each query scans only the relevant subset; (2) pre-computing the big-picture statistics (alert counts by signature, by source IP, by destination) and injecting them as the first triage turn, saving 3–5 model turns per run; and (3) implementing a "raw minus capture artefacts" tier that removes decoder noise (such as checksum validation alerts that constituted 98.8% of Wednesday raw alerts) while preserving all threat-relevant traffic. These changes require no modification to the triage engine or model — they are preprocessing optimisations that reduce the data volume presented to the same agentic loop.

The triage engine itself requires no architectural changes for the live deployment transition — the same agentic loop, tools, and prompt operate identically on live-captured alerts. This is a deliberate consequence of the tool-based design: the model interacts with data through tool calls, and replacing a file-backed tool with a database-backed one is transparent to the model.

---

## VIII. References

Anderson, JP 1980, *Computer security threat monitoring and surveillance*, Technical report, James P. Anderson Company, Fort Washington, Pennsylvania.

Aljanabi, M, Ismail, MA & Ali, AH 2021, 'Intrusion detection systems, issues, challenges, and needs', *International Journal of Computational Intelligence Systems*, vol. 14, no. 1, pp. 560–571.

Anthropic 2025, 'Tool use and agentic workflows', *Claude Documentation*, viewed 15 September 2026, <https://docs.anthropic.com/en/docs/build-with-claude/tool-use>.

Axelsson, S 2000, 'The base-rate fallacy and the difficulty of intrusion detection', *ACM Transactions on Information and System Security*, vol. 3, no. 3, pp. 186–205.

Buczak, AL & Guven, E 2016, 'A survey of data mining and machine learning methods for cyber security intrusion detection', *IEEE Communications Surveys & Tutorials*, vol. 18, no. 2, pp. 1153–1176.

Denning, DE 1987, 'An intrusion-detection model', *IEEE Transactions on Software Engineering*, vol. SE-13, no. 2, pp. 222–232.

Ferrag, MA, Maglaras, L, Moschoyiannis, S & Janicke, H 2020, 'Deep learning for cyber security intrusion detection: Approaches, datasets, and comparative study', *Journal of Information Security and Applications*, vol. 50, p. 102419.

Garcia-Teodoro, P, Diaz-Verdejo, J, Macia-Fernandez, G & Vazquez, E 2009, 'Anomaly-based network intrusion detection: Techniques, systems and challenges', *Computers & Security*, vol. 28, no. 1, pp. 18–28.

Hadi, HJ, Yasmin, R & Shoker, A 2026, 'GenTI: Benchmarking LLMs for Autonomous IDPS Rule Generation for Unseen Attacks', arXiv preprint, arXiv:2606.05844.

Khraisat, A, Gondal, I, Vamplew, P & Kamruzzaman, J 2019, 'Survey of intrusion detection systems: techniques, datasets and challenges', *Cybersecurity*, vol. 2, no. 1, p. 20.

Ko, C, Ruschitzka, M & Levitt, K 1997, 'Execution monitoring of security-critical programs in distributed systems: A specification-based approach', in *Proceedings 1997 IEEE Symposium on Security and Privacy*, pp. 175–187, IEEE.

Liao, HJ, Lin, CHR, Lin, YC & Tung, KY 2013, 'Intrusion detection system: A comprehensive review', *Journal of Network and Computer Applications*, vol. 36, no. 1, pp. 16–24.

OISF 2026, *Suricata 8.0.6 documentation*, Open Information Security Foundation, viewed 15 September 2026, <https://docs.suricata.io/en/suricata-8.0.6/>.

Paxson, V 1999, 'Bro: A system for detecting network intruders in real-time', *Computer Networks*, vol. 31, no. 23, pp. 2435–2463.

Proofpoint 2026, *Emerging Threats Open ruleset*, Proofpoint Inc., viewed 15 September 2026, <https://rules.emergingthreats.net/open/>.

Roesch, M 1999, 'Snort: Lightweight intrusion detection for networks', in *Proceedings of the 13th USENIX Conference on System Administration (LISA '99)*, pp. 229–238.

Scarfone, K & Mell, P 2007, *Guide to intrusion detection and prevention systems (IDPS)*, NIST Special Publication 800-94, National Institute of Standards and Technology, Gaithersburg, MD.

Sekar, R, Gupta, A, Frullo, J, Shanbhag, T, Tiwari, A, Yang, H & Zhou, S 2002, 'Specification-based anomaly detection: a new approach for detecting network intrusions', in *Proceedings of the 9th ACM Conference on Computer and Communications Security*, pp. 265–274.

Sharafaldin, I, Habibi Lashkari, A & Ghorbani, AA 2018, 'Toward generating a new intrusion detection dataset and intrusion traffic characterization', in *Proceedings of the 4th International Conference on Information Systems Security and Privacy*, pp. 108–116.

Sommer, R & Paxson, V 2010, 'Outside the closed world: On using machine learning for network intrusion detection', in *2010 IEEE Symposium on Security and Privacy*, pp. 305–316, IEEE.

Vaswani, A, Shazeer, N, Parmar, N, Uszkoreit, J, Jones, L, Gomez, AN, Kaiser, Ł & Polosukhin, I 2017, 'Attention is all you need', in *Advances in Neural Information Processing Systems*, vol. 30, pp. 5998–6008.

Zhang, X, Du, X, Chen, H, He, Y, Niu, W & Li, Q 2025, 'Automatically generating rules of malicious software packages via large language model', in *2025 55th Annual IEEE/IFIP International Conference on Dependable Systems and Networks (DSN)*, pp. 734–747, IEEE.

---

## Appendix A: Turnitin Similarity Report

[Upload interim report to Turnitin via Learnline and insert the generated similarity report here.]

## Appendix B: AI Declaration Form

[Insert completed AI Declaration Form.]

## Appendix C: Data and Source Code

The complete source code and configuration files are available at: [INSERT GITHUB REPOSITORY LINK]

See the README.md in the repository for setup instructions, environment requirements, and how to run the system. The CIC-IDS2017 dataset is not included due to size — download from https://www.unb.ca/cic/datasets/ids-2017.html

## Appendix D: AI-Authored Detection Rules

Twenty-two AI-authored detection rules are preserved in `rules/generated/` within the repository. Two additional rules (SID 3000001–3000002) authored by DeepSeek V3 were deleted by DeepSeek V4 Pro during a subsequent session; their original text is preserved in the triage transcript (see Section V, Model Errors). SID 3000003 was rewritten in place by V4 Pro. The following rule files were produced:

- `tuesday_bruteforce.rules` — 5 rules (SID 9000001–9000005) by DeepSeek V3
- `bruteforce_campaigns.rules` — 2 rules (SID 9500001–9500002) by Claude Opus 5
- `wednesday_slowloris.rules` — 2 rules (SID 3000003–3000004); SID 3000003 originally authored by DeepSeek V3, rewritten by DeepSeek V4 Pro; SID 3000004 by DeepSeek V4 Pro
- `wednesday_heartbleed.rules` — 3 rules (SID 7600101–7600103) by DeepSeek V4 Pro
- `thursday_webattacks_infiltration.rules` — 6 rules (SID 7600001–7600006) by DeepSeek V4 Pro
- `thursday_raw_synsweep.rules` — 1 rule (SID 7600007) by DeepSeek V4 Pro
- `friday_ddos.rules` — 1 rule (SID 9500003) by DeepSeek V4 Pro
- `friday_ddos_portscan.rules` — 2 rules (SID 9600001–9600002) by DeepSeek V4 Pro
