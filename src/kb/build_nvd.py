"""Build a local, searchable NVD vulnerability knowledge base (SQLite FTS5) for the research tool.

Downloads NVD CVE JSON 2.0 yearly feeds 2002-2016 (the attacks in the evaluation data pre-date 2016).
The knowledge base contains only NVD records, so it cannot contain any evaluation-dataset material.

Usage: python -m src.kb.build_nvd
"""

import gzip
import json
import sqlite3
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FEEDS = ROOT / "data/kb/nvd"
DB = ROOT / "data/kb/nvd.sqlite"
URL = "https://nvd.nist.gov/feeds/json/cve/2.0/nvdcve-2.0-{year}.json.gz"
YEARS = range(2002, 2017)


def fetch(year: int) -> Path:
    path = FEEDS / f"nvdcve-2.0-{year}.json.gz"
    if not path.exists():
        req = urllib.request.Request(URL.format(year=year), headers={"User-Agent": "capstone-ids-kb/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            path.write_bytes(r.read())
    return path


def cvss(metrics: dict):
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        for m in metrics.get(key, []):
            d = m.get("cvssData", {})
            return f"{d.get('baseScore')} ({key[10:].replace('V', 'v')})"
    return None


def main():
    FEEDS.mkdir(parents=True, exist_ok=True)
    DB.unlink(missing_ok=True)
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE cve (id TEXT PRIMARY KEY, published TEXT, cvss TEXT, cwe TEXT, description TEXT, refs TEXT)")
    con.execute("CREATE VIRTUAL TABLE cve_fts USING fts5(id UNINDEXED, description, content='cve', content_rowid='rowid')")
    n = 0
    for year in YEARS:
        data = json.loads(gzip.decompress(fetch(year).read_bytes()))
        rows = []
        for item in data.get("vulnerabilities", []):
            c = item["cve"]
            desc = next((d["value"] for d in c.get("descriptions", []) if d.get("lang") == "en"), "")
            cwe = ",".join(sorted({d["value"] for w in c.get("weaknesses", []) for d in w.get("description", [])}))
            refs = json.dumps([r["url"] for r in c.get("references", [])][:15])
            rows.append((c["id"], c.get("published", "")[:10], cvss(c.get("metrics", {})), cwe, desc, refs))
        con.executemany("INSERT OR REPLACE INTO cve VALUES (?,?,?,?,?,?)", rows)
        n += len(rows)
        print(f"{year}: {len(rows)} records")
    con.execute("INSERT INTO cve_fts(rowid, id, description) SELECT rowid, id, description FROM cve")
    con.commit()
    print(f"Saved {DB.relative_to(ROOT)}: {n} CVE records")


if __name__ == "__main__":
    main()
