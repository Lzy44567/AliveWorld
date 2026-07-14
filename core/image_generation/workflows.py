"""Safe storage and parameter mapping for ComfyUI API workflows."""

from __future__ import annotations

import copy
import json
import os
import re
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.image_generation.models import ImageTask
from utils.file_io import DATA_DIR


WORKFLOW_DIR = Path(DATA_DIR) / "image_workflows"
REQUIRED_MAPPING = {"checkpoint", "positive", "negative", "width", "height", "seed", "filename_prefix"}


class WorkflowError(ValueError):
    pass


def _safe_id(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value).strip()).strip("_")
    if not result:
        raise WorkflowError("工作流名称无效")
    return result[:80]


@dataclass
class WorkflowDefinition:
    id: str
    name: str
    description: str
    workflow: dict[str, Any]
    mapping: dict[str, list[str]]
    is_template: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, is_template: bool = False) -> "WorkflowDefinition":
        if not isinstance(data.get("workflow"), dict) or not data["workflow"]:
            raise WorkflowError("缺少 ComfyUI API workflow")
        mapping = data.get("mapping")
        if not isinstance(mapping, dict) or not REQUIRED_MAPPING.issubset(mapping):
            missing = sorted(REQUIRED_MAPPING - set(mapping or {}))
            raise WorkflowError(f"工作流参数映射不完整: {', '.join(missing)}")
        normalized_mapping: dict[str, list[str]] = {}
        for key, value in mapping.items():
            if not isinstance(value, list) or len(value) != 2:
                raise WorkflowError(f"参数映射 {key} 必须为 [节点ID, 输入名]")
            node_id, input_name = str(value[0]), str(value[1])
            node = data["workflow"].get(node_id)
            if not isinstance(node, dict) or input_name not in node.get("inputs", {}):
                raise WorkflowError(f"参数映射 {key} 指向不存在的输入")
            normalized_mapping[str(key)] = [node_id, input_name]
        return cls(
            id=_safe_id(data.get("id", data.get("name", ""))),
            name=str(data.get("name", "未命名工作流")).strip() or "未命名工作流",
            description=str(data.get("description", "")).strip(),
            workflow=copy.deepcopy(data["workflow"]),
            mapping=normalized_mapping,
            is_template=is_template,
        )

    def summary(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "description": self.description, "is_template": self.is_template}

    def render(self, task: ImageTask) -> dict[str, Any]:
        checkpoint = str(task.provider_options.get("checkpoint", "")).strip()
        if not checkpoint:
            raise WorkflowError("尚未选择 ComfyUI 生图模型")
        values = {
            "checkpoint": checkpoint,
            "positive": task.prompt.positive,
            "negative": task.prompt.negative,
            "width": task.prompt.width,
            "height": task.prompt.height,
            "seed": task.prompt.seed if task.prompt.seed is not None else secrets.randbelow(2**63),
            "filename_prefix": f"AliveWorld/{task.id}",
            "batch_size": task.prompt.count,
            "steps": task.prompt.steps,
            "cfg": task.prompt.cfg,
        }
        rendered = copy.deepcopy(self.workflow)
        for key, value in values.items():
            if key not in self.mapping:
                continue
            node_id, input_name = self.mapping[key]
            rendered[node_id]["inputs"][input_name] = value
        return rendered


class WorkflowRepository:
    def __init__(self, root: str | Path = WORKFLOW_DIR):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def list(self) -> list[WorkflowDefinition]:
        definitions = []
        for path in sorted(self.root.glob("*.json")):
            try:
                definitions.append(self._load_path(path))
            except (OSError, json.JSONDecodeError, WorkflowError):
                continue
        return definitions

    def get(self, workflow_id: str) -> WorkflowDefinition:
        for definition in self.list():
            if definition.id == workflow_id:
                return definition
        raise WorkflowError("生图工作流不存在")

    def import_definition(self, data: dict[str, Any]) -> WorkflowDefinition:
        if "workflow" not in data and all(isinstance(value, dict) and "class_type" in value for value in data.values()):
            data = {"id": "imported_workflow", "name": "导入的工作流", "workflow": data}
        if not data.get("mapping") and isinstance(data.get("workflow"), dict):
            data = {**data, "mapping": infer_standard_mapping(data["workflow"])}
        definition = WorkflowDefinition.from_dict(data, is_template=False)
        path = self.root / f"{definition.id}.json"
        if path.with_name(f"{definition.id}.template.json").exists():
            raise WorkflowError("不能覆盖内置工作流")
        payload = {
            "id": definition.id,
            "name": definition.name,
            "description": definition.description,
            "version": 1,
            "mapping": definition.mapping,
            "workflow": definition.workflow,
        }
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, path)
        return definition

    @staticmethod
    def _load_path(path: Path) -> WorkflowDefinition:
        data = json.loads(path.read_text(encoding="utf-8"))
        return WorkflowDefinition.from_dict(data, is_template=path.name.endswith(".template.json"))


def infer_standard_mapping(workflow: dict[str, Any]) -> dict[str, list[str]]:
    """Infer only unambiguous mappings from common ComfyUI core nodes."""
    by_type: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for node_id, node in workflow.items():
        if isinstance(node, dict):
            by_type.setdefault(str(node.get("class_type", "")), []).append((str(node_id), node))

    def unique(class_type: str, input_name: str) -> list[str]:
        matches = [(node_id, node) for node_id, node in by_type.get(class_type, []) if input_name in node.get("inputs", {})]
        if len(matches) != 1:
            raise WorkflowError(f"无法唯一识别 {class_type}.{input_name}，请提供参数映射")
        return [matches[0][0], input_name]

    text_nodes = by_type.get("CLIPTextEncode", [])
    positive = []
    negative = []
    for node_id, node in text_nodes:
        title = str(node.get("_meta", {}).get("title", "")).lower()
        if "positive" in title or "正面" in title:
            positive.append([node_id, "text"])
        if "negative" in title or "负面" in title:
            negative.append([node_id, "text"])
    if len(positive) != 1 or len(negative) != 1:
        raise WorkflowError("无法从 CLIPTextEncode 标题唯一识别正面/负面提示词，请保留 Positive Prompt 和 Negative Prompt 节点标题")
    mapping = {
        "checkpoint": unique("CheckpointLoaderSimple", "ckpt_name"),
        "positive": positive[0],
        "negative": negative[0],
        "width": unique("EmptyLatentImage", "width"),
        "height": unique("EmptyLatentImage", "height"),
        "seed": unique("KSampler", "seed"),
        "filename_prefix": unique("SaveImage", "filename_prefix"),
    }
    optional = {
        "batch_size": ("EmptyLatentImage", "batch_size"),
        "steps": ("KSampler", "steps"),
        "cfg": ("KSampler", "cfg"),
    }
    for key, (class_type, input_name) in optional.items():
        try:
            mapping[key] = unique(class_type, input_name)
        except WorkflowError:
            pass
    return mapping
