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

# Build a real package with the same exporter used by production. Playwright
# uploads this file through the player UI, so the scenario covers ZIP parsing,
# installation, story materialization, asset activation, and persistence.
from core.world_packages import AssetSource, WorldPackageExporter, new_package_id  # noqa: E402
from core.world_packages.identity import ensure_yaml_asset_id  # noqa: E402
from core.world_packages.models import new_asset_id  # noqa: E402

fixture_root = RUNTIME / "e2e-fixtures"
fixture_root.mkdir()
fixture_assets = {
    "worldbooks": ("世界包测试世界.yml", {"name": "世界包测试世界", "overview": "【AWTEST:世界包世界书】世界包法则就绪", "entries": []}),
    "characters": ("世界包测试角色.yml", {"name": "世界包测试角色", "description": "【AWTEST:世界包角色】角色上下文就绪", "is_player": True}),
    "styles": ("世界包测试文风.yml", {"name": "世界包测试文风", "content": "【AWTEST:世界包文风】使用清晰自然段"}),
    "entities": ("世界包测试实体.yml", {"name": "世界包测试实体", "motive": "【AWTEST:世界包实体】观察世界包测试", "is_active": True}),
}
sources = []
entrypoints = {}
for asset_type, (filename, content) in fixture_assets.items():
    path = fixture_root / filename
    path.write_text(yaml.safe_dump(content, allow_unicode=True, sort_keys=False), encoding="utf-8")
    asset_id = ensure_yaml_asset_id(path)
    sources.append(AssetSource(asset_type, path))
    if asset_type == "worldbooks":
        entrypoints["main_worldbook"] = asset_id
starter_path = fixture_root / "starter.json"
starter_path.write_text(json.dumps({
    "world_premise": "世界包自动验收梗概",
    "opening": "【世界包自动验收】内容已准备完毕。",
    "story_settings": {"aiSuggestions": True},
}, ensure_ascii=False), encoding="utf-8")
starter_id = new_asset_id()
entrypoints["starter"] = starter_id
sources.append(AssetSource("starter", starter_path, name="自动验收起点", asset_id=starter_id))
WorldPackageExporter().export(
    RUNTIME / "e2e-world.aliveworld",
    package={
        "package_id": new_package_id(),
        "version": "1.0.0",
        "name": "自动验收世界包",
        "author": "AliveWorld Test",
        "description": "验证导入、一键开始与资产注入。",
        "tags": ("自动验收",),
        "entrypoints": entrypoints,
    },
    assets=sources,
)

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
