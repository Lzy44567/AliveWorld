"""Run AliveWorld and deterministic model services against isolated test data."""

from __future__ import annotations

import json
import os
import shutil
import sys
import threading
from pathlib import Path

import uvicorn
import yaml


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "build" / "e2e-runtime"
if RUNTIME.exists():
    if RUNTIME.parent.resolve() != (ROOT / "build").resolve():
        raise RuntimeError("拒绝清理非 build 目录中的 E2E 数据")
    shutil.rmtree(RUNTIME)
RUNTIME.mkdir(parents=True)
(RUNTIME / "legacy_migration.json").write_text(
    json.dumps({"completed": True, "source": "e2e"}), encoding="utf-8"
)
(RUNTIME / "config.yml").write_text(yaml.safe_dump({
    "api_key": "aliveworld-e2e-only",
    "base_url": "http://127.0.0.1:18765/v1",
    "model": "fake-story",
    "image_api_url": "http://127.0.0.1:18767",
}, allow_unicode=True, sort_keys=False), encoding="utf-8")

os.environ["ALIVEWORLD_USER_DIR"] = str(RUNTIME)
os.environ["ALIVEWORLD_RESOURCE_DIR"] = str(ROOT)
os.environ["ALIVEWORLD_FRONTEND_DIST"] = str(ROOT / "aliveworld-ui" / "dist")
sys.path.insert(0, str(ROOT))

from tests.fakes.fake_openai_app import app as fake_openai_app  # noqa: E402
from tests.fakes.fake_comfyui_app import app as fake_comfyui_app  # noqa: E402


def run_fake_model():
    uvicorn.run(fake_openai_app, host="127.0.0.1", port=18765, log_level="warning")


def run_fake_comfyui():
    uvicorn.run(fake_comfyui_app, host="127.0.0.1", port=18767, log_level="warning")


threading.Thread(target=run_fake_model, name="aliveworld-e2e-fake-llm", daemon=True).start()
threading.Thread(target=run_fake_comfyui, name="aliveworld-e2e-fake-comfyui", daemon=True).start()

from main import create_app  # noqa: E402


if __name__ == "__main__":
    uvicorn.run(
        create_app(frontend_dist=ROOT / "aliveworld-ui" / "dist", cors_origins=[]),
        host="127.0.0.1", port=18766, log_level="warning",
    )
