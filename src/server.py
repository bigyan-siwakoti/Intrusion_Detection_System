"""FastAPI server — streams AI triage events to the web UI via SSE.

TRIAGE_PUBLIC=1 turns on the public demo mode used at triage.bigyan.work (src/demo.py): only the two demo runs are
offered, the model is fixed server-side, one live run at a time, plus replay of recorded runs and file downloads.
Without it the server behaves as the local research tool (any run in logs/, any profile and model).
"""

import json
import asyncio
import os
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse

from .engine import run_triage
from .profiles import summary
from . import demo

app = FastAPI(title="IDS Triage Engine")

STATIC_DIR = Path(__file__).parent / "static"
PUBLIC = os.environ.get("TRIAGE_PUBLIC") == "1"
SSE_HEADERS = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


@app.get("/", response_class=HTMLResponse)
async def index():
    return (STATIC_DIR / "index.html").read_text()


@app.get("/api/config")
async def config():
    """Tells the UI whether it is the public demo, and what the demos are."""
    if not PUBLIC:
        return {"public": False}
    report = (Path(__file__).resolve().parent.parent / "demo" / "report" / "Final_Report_Group13.pdf").exists()
    return {"public": True, "model": demo.MODEL, "status": demo.status(), "report": report,
            "demos": [{"id": k, "title": v["title"], "profile": v["profile"]} for k, v in demo.available().items()]}


@app.get("/api/profiles")
async def list_profiles():
    """Experiment profiles the UI can run (src/profiles.py)."""
    profiles = summary()
    if PUBLIC:
        allowed = {d["profile"] for d in demo.available().values()}
        profiles = [p for p in profiles if p["name"] in allowed]
    return profiles


@app.get("/api/triage")
async def triage(request: Request, eve_path: str, profile: str, model: str = "claude-sonnet-5"):
    """SSE endpoint that streams triage events."""
    if PUBLIC:
        return _public_live(request, eve_path)

    async def event_stream():
        loop = asyncio.get_event_loop()
        gen = run_triage(eve_path, model=model, profile=profile)

        while True:
            try:
                event = await loop.run_in_executor(None, next, gen)
                yield _sse(event)
            except StopIteration:
                yield _sse({'type': 'stream_end'})
                break
            except Exception as e:
                yield _sse({'type': 'error', 'message': str(e)})
                break

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=SSE_HEADERS)


def _public_live(request: Request, eve_path: str):
    """Live demo run: the browser only chooses which demo; path, profile and model are fixed server-side."""
    demo_id = demo.demo_for(eve_path)

    async def event_stream():
        if not demo_id:
            yield _sse({"type": "error", "message": "Unknown demo."})
            yield _sse({"type": "stream_end"})
            return
        q, reason = demo.start_live(demo_id, _client_ip(request))
        if reason:
            yield _sse({"type": "error", "message": reason})
            yield _sse({"type": "stream_end"})
            return
        loop = asyncio.get_event_loop()
        while True:
            # The run lives in its own thread; if the visitor leaves, it finishes on its own and is recorded.
            ev = await loop.run_in_executor(None, q.get)
            if ev is None:
                yield _sse({"type": "stream_end"})
                return
            yield _sse(ev)

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=SSE_HEADERS)


@app.get("/api/replay")
async def replay(demo_id: str, speed: float = 1.0):
    """Stream the latest recorded run of a demo, with long pauses shortened."""
    if demo_id not in demo.DEMOS:
        raise HTTPException(404, "Unknown demo.")
    speed = min(max(speed, 0.5), 8.0)

    async def event_stream():
        for delay, ev in demo.replay_events(demo_id, speed=speed):
            if delay:
                await asyncio.sleep(delay)
            yield _sse(ev)
        yield _sse({"type": "stream_end"})

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=SSE_HEADERS)


@app.get("/api/downloads")
async def list_downloads(demo_id: str):
    if demo_id not in demo.DEMOS:
        raise HTTPException(404, "Unknown demo.")
    return demo.downloads(demo_id)


@app.get("/download/{demo_id}/{fname}")
async def download(demo_id: str, fname: str):
    if demo_id not in demo.DEMOS:
        raise HTTPException(404, "Unknown demo.")
    path = demo.download_path(demo_id, fname)
    if not path or not path.exists():
        raise HTTPException(404, "Not available yet.")
    return FileResponse(path, filename=f"{demo_id}-{fname}")


@app.get("/report.pdf")
async def report_pdf():
    path = Path(__file__).resolve().parent.parent / "demo" / "report" / "Final_Report_Group13.pdf"
    if not path.exists():
        raise HTTPException(404, "Report not published yet.")
    return FileResponse(path, media_type="application/pdf")


@app.get("/api/runs")
async def list_runs():
    """List available eve.json files in the logs directory (public mode: the demo runs only)."""
    root = Path(__file__).parent.parent
    if PUBLIC:
        return [{"name": d["title"], "eve_path": d["eve"],
                 "size_mb": round((root / d["eve"]).stat().st_size / 1e6, 1) if (root / d["eve"]).exists() else 0}
                for d in demo.available().values()]
    logs_dir = root / "logs"
    runs = []
    if logs_dir.exists():
        for d in sorted(logs_dir.iterdir()):
            if d.is_dir():
                eve = d / "eve.json"
                if eve.exists():
                    size_mb = eve.stat().st_size / 1_000_000
                    runs.append({
                        "name": d.name,
                        "eve_path": f"logs/{d.name}/eve.json",
                        "size_mb": round(size_mb, 1)
                    })
    return runs


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
