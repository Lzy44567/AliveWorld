"""Deterministic ComfyUI-compatible service for browser acceptance tests."""

from __future__ import annotations

import base64
import uuid
from threading import Lock
from typing import Any

from fastapi import FastAPI, Response


app = FastAPI(title="AliveWorld deterministic fake ComfyUI")
_jobs: dict[str, dict[str, Any]] = {}
_submission_count = 0
_lock = Lock()

# 1x1 opaque PNG. The browser test only verifies the task lifecycle and file delivery.
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


@app.get("/system_stats")
def system_stats():
    return {"system": {"os": "aliveworld-tests"}}


@app.get("/object_info/CheckpointLoaderSimple")
def checkpoint_loader_info():
    return {
        "CheckpointLoaderSimple": {
            "input": {"required": {"ckpt_name": [["fake-e2e.safetensors"]]}}
        }
    }


@app.post("/prompt")
def submit_prompt(payload: dict[str, Any]):
    global _submission_count
    with _lock:
        _submission_count += 1
        job_id = f"fake_job_{uuid.uuid4().hex[:10]}"
        # The first real submission fails. A retry must create a new provider job,
        # which succeeds and returns a downloadable image.
        _jobs[job_id] = {"failed": _submission_count == 1, "payload": payload}
    return {"prompt_id": job_id}


@app.get("/history/{job_id}")
def job_history(job_id: str):
    with _lock:
        job = _jobs.get(job_id)
    if not job:
        return {}
    if job["failed"]:
        return {job_id: {"status": {"status_str": "error"}, "outputs": {}}}
    return {
        job_id: {
            "status": {"status_str": "success"},
            "outputs": {
                "9": {
                    "images": [
                        {"filename": "aliveworld-e2e.png", "subfolder": "", "type": "output"}
                    ]
                }
            },
        }
    }


@app.get("/view")
def view_image():
    return Response(content=_PNG, media_type="image/png")


@app.post("/queue")
def update_queue(payload: dict[str, Any]):
    return {"status": "ok", "payload": payload}
