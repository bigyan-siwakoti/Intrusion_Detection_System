# Public demo recordings

`demo/<id>/events.jsonl` (+ `meta.json`, `report.md`, `ai_rules.rules`, `transcript.txt`) is a recorded live run that
the site replays when no newer run has been recorded on the server. `<id>` is `cic` or `unsw` (see `src/demo.py`).
Live runs on the server are recorded to `~/triage-data/runs/<id>/` and the newest completed one is replayed.
