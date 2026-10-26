# AI-Augmented Intrusion Detection System

An open-source, rule-based intrusion detection system that uses a generative language model to automate the alert-handling work currently done by a human analyst.

**Research question:** Can an LLM replace the human analyst in the alert-handling loop of a rule-based IDS — and what context does it need to do that job well?

**Team:** Bigyan Siwakoti, Irab Baral, Binay Siwakoti, Shashwat Acharya  
**Supervisor:** Prof. Bharanidharan Shanmugam, Charles Darwin University

## How it works

1. **Suricata** processes a pcap file and produces alerts in `eve.json`
2. The **AI triage engine** reads those alerts via tools (jq queries, file reads)
3. The model investigates each alert: checks protocol-level data, correlates IPs, determines attack outcomes
4. For confirmed threats, it **writes detection rules**. For false positives, it **proposes suppressions** (human approval required)
5. A **web UI** streams the entire triage process in real-time

## Prerequisites

- Linux (tested on Ubuntu/WSL2)
- [Suricata 8.0.x](https://suricata.io/) (`sudo add-apt-repository ppa:oisf/suricata-stable && sudo apt install suricata`)
- Python 3.10+
- `jq` (`sudo apt install jq`)
- An [Anthropic API key](https://console.anthropic.com/) and/or a [DeepSeek API key](https://platform.deepseek.com/)

## Setup

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/capstone-ids.git
cd capstone-ids

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Pull the ET Open ruleset (52,647 community detection rules)
sudo suricata-update
sudo cp /var/lib/suricata/rules/suricata.rules rules/
sudo cp /var/lib/suricata/rules/classification.config config/
sudo chown $USER:$USER rules/suricata.rules config/classification.config

# Set your API key (one or both)
export ANTHROPIC_API_KEY="your-key-here"
export DEEPSEEK_API_KEY="your-key-here"   # optional, for DeepSeek V3
```

## Dataset

This project uses [CIC-IDS2017](https://www.unb.ca/cic/datasets/ids-2017.html) from the Canadian Institute for Cybersecurity, UNB.

Download the **pcap files** (not the ML CSVs) and place them in `data/pcaps/`:
- `Monday-WorkingHours.pcap` — benign traffic only (baseline)
- `Tuesday-WorkingHours.pcap` — FTP-Patator + SSH-Patator
- `Wednesday-workingHours.pcap` — DoS attacks
- `Thursday-WorkingHours.pcap` — Web attacks + Infiltration
- `Friday-WorkingHours.pcap` — DDoS + PortScan + Botnet

Download the ground-truth labels and place them in `data/labels/TrafficLabelling/`.

## Running Suricata

```bash
# Run on any pcap
mkdir -p logs/my-run
suricata -r data/pcaps/Tuesday-WorkingHours.pcap \
         -l logs/my-run/ \
         -c config/suricata.yaml
```

## Running the AI triage

### Web UI (recommended)

```bash
source venv/bin/activate
export ANTHROPIC_API_KEY="your-key-here"
python -m src.server
```

Open `http://localhost:8000` in your browser. Select a run from the dropdown, pick your model, and click Start.

### CLI

```bash
source venv/bin/activate
export ANTHROPIC_API_KEY="your-key-here"
python -m src.cli logs/my-run/eve.json --model claude-opus-5
```

## Project structure

```
capstone-ids/
├── CLAUDE.md               # Project decisions and constraints
├── config/
│   ├── suricata.yaml       # Project-local Suricata config
│   └── threshold.config    # 80 suppress rules with documented reasons
├── rules/
│   ├── suricata.rules      # ET Open ruleset (gitignored, regenerate with suricata-update)
│   └── generated/          # Detection rules authored by the AI
├── src/
│   ├── engine.py           # Agentic triage loop (streaming, tool execution)
│   ├── tools.py            # 7 tools the AI can use (jq queries, file I/O, suricata)
│   ├── prompts.py          # System prompt with triage procedure
│   ├── server.py           # FastAPI + SSE web server
│   ├── cli.py              # CLI runner
│   └── static/index.html   # Web UI with real-time streaming and export
├── data/
│   ├── pcaps/              # CIC-IDS2017 pcaps (gitignored)
│   ├── slices/             # Small cuts for fast iteration (gitignored)
│   └── labels/             # Ground truth CSVs (gitignored)
└── logs/                   # Suricata run outputs (gitignored)
```

## Key design decisions

- **Alert-only rules, no `pass`** — pass rules bypass entire TCP flows, creating a structural blind spot
- **ET Open + threshold suppression** — start with 52,647 community rules, suppress false positives on benign traffic
- **The model authors rules, never classifies traffic** — detection stays rule-based and inspectable
- **Two exits from triage** — threats get detection rules (auto-deploy), false positives get suppress proposals (human approval required)
- **Offline pcap replay** — `suricata -r`, no live capture

See `CLAUDE.md` for full rationale behind each decision.

## License

This project is open-source for academic purposes.
