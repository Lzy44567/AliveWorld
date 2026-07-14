"""ComfyUI HTTP adapter using only the Python standard library."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from core.image_generation.models import ImageTask
from core.image_generation.providers.base import ProviderCapabilities, ProviderJob
from core.image_generation.workflows import WorkflowRepository


class ComfyUIError(RuntimeError):
    pass


class ComfyUIProvider:
    id = "comfyui"

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8188",
        *,
        workflows: WorkflowRepository | None = None,
        output_dir: str | Path | None = None,
        timeout: float = 5.0,
    ):
        self.base_url = str(base_url or "http://127.0.0.1:8188").rstrip("/")
        if not self.base_url.startswith(("http://", "https://")):
            raise ComfyUIError("ComfyUI 地址必须以 http:// 或 https:// 开头")
        self.workflows = workflows or WorkflowRepository()
        self.output_dir = Path(output_dir) if output_dir else None
        self.timeout = timeout
        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)

    def check(self) -> ProviderCapabilities:
        try:
            self._request_json("GET", "/system_stats")
            checkpoints = self.checkpoints()
            return ProviderCapabilities(
                provider_id=self.id,
                connected=True,
                supports_cancel=True,
                supports_progress=False,
                workflows=[item.id for item in self.workflows.list()],
                checkpoints=checkpoints,
                message="ComfyUI 连接正常",
            )
        except ComfyUIError as exc:
            return ProviderCapabilities(provider_id=self.id, connected=False, message=str(exc))

    def checkpoints(self) -> list[str]:
        payload = self._request_json("GET", "/object_info/CheckpointLoaderSimple")
        node = payload.get("CheckpointLoaderSimple", payload) if isinstance(payload, dict) else {}
        required = node.get("input", {}).get("required", {}) if isinstance(node, dict) else {}
        values = required.get("ckpt_name", [[]])
        choices = values[0] if isinstance(values, list) and values and isinstance(values[0], list) else []
        return [str(item) for item in choices]

    def submit(self, task: ImageTask) -> ProviderJob:
        workflow = self.workflows.get(task.workflow_id).render(task)
        payload = self._request_json("POST", "/prompt", {"prompt": workflow, "client_id": uuid4().hex})
        prompt_id = str(payload.get("prompt_id", "")) if isinstance(payload, dict) else ""
        if not prompt_id:
            raise ComfyUIError("ComfyUI 未返回 prompt_id")
        return ProviderJob(id=prompt_id, state="submitted")

    def query(self, provider_job_id: str) -> ProviderJob:
        payload = self._request_json("GET", f"/history/{provider_job_id}")
        history = payload.get(provider_job_id) if isinstance(payload, dict) else None
        if not isinstance(history, dict):
            return ProviderJob(id=provider_job_id, state="running")
        status = history.get("status", {})
        if isinstance(status, dict) and status.get("status_str") == "error":
            return ProviderJob(id=provider_job_id, state="failed", error_code="comfyui_execution", error_message="ComfyUI 工作流执行失败")
        images = []
        for output in history.get("outputs", {}).values():
            if not isinstance(output, dict):
                continue
            for image in output.get("images", []):
                if isinstance(image, dict):
                    images.append(self._fetch_image(image))
        if images:
            return ProviderJob(id=provider_job_id, state="succeeded", progress=1.0, output_images=images)
        return ProviderJob(id=provider_job_id, state="running")

    def cancel(self, provider_job_id: str) -> bool:
        self._request_json("POST", "/queue", {"delete": [provider_job_id]})
        return True

    def _fetch_image(self, image: dict[str, Any]) -> str:
        query = urlencode({
            "filename": str(image.get("filename", "")),
            "subfolder": str(image.get("subfolder", "")),
            "type": str(image.get("type", "output")),
        })
        data = self._request_bytes("GET", f"/view?{query}")
        if not self.output_dir:
            return str(image.get("filename", ""))
        filename = Path(str(image.get("filename", "image.png"))).name
        path = self.output_dir / f"{uuid4().hex[:8]}_{filename}"
        path.write_bytes(data)
        return str(path)

    def _request_json(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(self.base_url + path, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except HTTPError as exc:
            raise ComfyUIError(f"ComfyUI HTTP {exc.code}: {exc.reason}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ComfyUIError(f"无法连接 ComfyUI：{exc}") from exc
        try:
            return json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ComfyUIError("ComfyUI 返回了无法解析的响应") from exc

    def _request_bytes(self, method: str, path: str) -> bytes:
        request = Request(self.base_url + path, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise ComfyUIError(f"无法获取 ComfyUI 图片：{exc}") from exc
