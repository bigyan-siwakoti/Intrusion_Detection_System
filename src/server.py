"""FastAPI server — streams AI triage events to the web UI via SSE."""

import json
import asyncio
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .engine import run_triage

app = FastAPI(title="IDS Triage Engine")

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/", response_class=HTMLResponse)
async def index():
    return (STATIC_DIR / "index.html").read_text()


@app.get("/api/triage")
async def triage(eve_path: str, model: str = "claude-sonnet-5"):
    """SSE endpoint that streams triage events."""
    async def event_stream():
        loop = asyncio.get_event_loop()
        gen = run_triage(eve_path, model=model)

        while True:
            try:
                event = await loop.run_in_executor(None, next, gen)
                yield f"data: {json.dumps(event)}\n\n"
            except StopIteration:
                yield f"data: {json.dumps({'type': 'stream_end'})}\n\n"
                break
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/api/runs")
async def list_runs():
    """List available eve.json files in the logs directory."""
    logs_dir = Path(__file__).parent.parent / "logs"
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
