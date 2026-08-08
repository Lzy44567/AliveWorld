"""Safe storage, inspection and rendering for ComfyUI API workflows."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.image_generation.models import ImageTask
from core.image_generation.workflow_profiles import PROFILE_DIR, WorkflowProfileRepository, compose_prompt
from utils.file_io import DATA_DIR


WORKFLOW_DIR = Path(DATA_DIR) / "image_workflows"
SEMANTIC_PARAMETERS = (
    "positive", "negative", "width", "height", "batch_size",
    "checkpoint", "seed", "steps", "cfg", "filename_prefix",
)
REQUIRED_FOR_PLAYER_PROMPT = {"positive"}
TITLE_MARKERS = {
    "positive": "aw.positiveprompt",
    "negative": "aw.negativeprompt",
    "width": "aw.width",
    "height": "aw.height",
    "batch_size": "aw.batchsize",
    "checkpoint": "aw.checkpoint",
}


class WorkflowError(ValueError):
    pass


def _safe_id(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value).strip()).strip("_")
    if not result:
        raise WorkflowError("工作流名称无效")
    return result[:80]


def workflow_fingerprint(workflow: dict[str, Any]) -> str:
    raw = json.dumps(workflow, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _validate_graph(workflow: dict[str, Any]) -> None:
    if not isinstance(workflow, dict) or not workflow:
        raise WorkflowError("缺少 ComfyUI API workflow")
    valid_nodes = 0
    for node_id, node in workflow.items():
        if not isinstance(node, dict) or not str(node.get("class_type", "")).strip():
            raise WorkflowError(f"节点 {node_id} 缺少 class_type")
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            raise WorkflowError(f"节点 {node_id} 的 inputs 无效")
        valid_nodes += 1
        for value in inputs.values():
            if (
                isinstance(value, list) and len(value) == 2
                and isinstance(value[0], str) and isinstance(value[1], int)
                and value[0] not in workflow
            ):
                raise WorkflowError(f"节点 {node_id} 引用了不存在的节点 {value[0]}")
    if not valid_nodes:
        raise WorkflowError("工作流中没有可提交的节点")


def normalize_mapping(workflow: dict[str, Any], mapping: Any) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    if not isinstance(mapping, dict):
        return result
    for key, value in mapping.items():
        key = str(key)
        if key not in SEMANTIC_PARAMETERS:
            continue
        if not isinstance(value, list) or len(value) != 2:
            raise WorkflowError(f"参数映射 {key} 必须为 [节点ID, 输入名]")
        node_id, input_name = str(value[0]), str(value[1])
        node = workflow.get(node_id)
        if not isinstance(node, dict) or input_name not in node.get("inputs", {}):
            raise WorkflowError(f"参数映射 {key} 指向不存在的输入")
        result[key] = [node_id, input_name]
    return result


def _mapping_value(workflow: dict[str, Any], mapping: dict[str, list[str]], key: str) -> Any:
    target = mapping.get(key)
    if not target:
        return None
    return copy.deepcopy(workflow[target[0]]["inputs"].get(target[1]))


@dataclass
class WorkflowDefinition:
    id: str
    name: str
    description: str
    workflow: dict[str, Any]
    mapping: dict[str, list[str]]
    is_template: bool = False
    profile_root: Path = PROFILE_DIR

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], *, is_template: bool = False, profile_root: str | Path = PROFILE_DIR
    ) -> "WorkflowDefinition":
        workflow = data.get("workflow")
        _validate_graph(workflow)
        supplied = data.get("mapping")
        mapping = normalize_mapping(workflow, supplied)
        if not mapping:
            mapping = infer_standard_mapping(workflow)
        return cls(
            id=_safe_id(data.get("id", data.get("name", ""))),
            name=str(data.get("name", "未命名工作流")).strip() or "未命名工作流",
            description=str(data.get("description", "")).strip(),
            workflow=copy.deepcopy(workflow),
            mapping=mapping,
            is_template=is_template,
            profile_root=Path(profile_root),
        )

    @property
    def fingerprint(self) -> str:
        return workflow_fingerprint(self.workflow)

    def _profile(self):
        return WorkflowProfileRepository(self.profile_root).get(self.id, self.fingerprint)

    def effective_mapping(self) -> dict[str, list[str]]:
        profile = self._profile()
        return {**self.mapping, **normalize_mapping(self.workflow, profile.mapping_overrides)}

    def defaults(self) -> dict[str, Any]:
        mapping = self.effective_mapping()
        return {key: _mapping_value(self.workflow, mapping, key) for key in mapping}

    def candidates(self, key: str) -> list[dict[str, Any]]:
        names = {
            "positive": {"text"}, "negative": {"text"}, "width": {"width"},
            "height": {"height"}, "batch_size": {"batch_size"},
            "checkpoint": {"ckpt_name"}, "seed": {"seed", "noise_seed"},
            "steps": {"steps"}, "cfg": {"cfg"}, "filename_prefix": {"filename_prefix"},
        }.get(key, set())
        result = []
        for node_id, node in self.workflow.items():
            for input_name, value in node.get("inputs", {}).items():
                if input_name not in names:
                    continue
                result.append({
                    "target": [str(node_id), str(input_name)],
                    "node_id": str(node_id),
                    "input_name": str(input_name),
                    "title": str(node.get("_meta", {}).get("title", "")) or str(node.get("class_type", "")),
                    "default": copy.deepcopy(value),
                })
        return result

    def mapping_report(self) -> dict[str, Any]:
        mapping = self.effective_mapping()
        parameters = []
        for key in SEMANTIC_PARAMETERS:
            mapped = key in mapping
            severity = "ok" if mapped else ("risk" if key in REQUIRED_FOR_PLAYER_PROMPT else "notice")
            parameters.append({
                "key": key,
                "mapped": mapped,
                "target": mapping.get(key),
                "default": _mapping_value(self.workflow, mapping, key),
                "severity": severity,
                "candidates": self.candidates(key),
            })
        return {
            "can_submit": True,
            "can_inject_prompt": "positive" in mapping,
            "parameters": parameters,
            "warnings": [item["key"] for item in parameters if item["severity"] != "ok"],
        }

    def summary(self) -> dict[str, Any]:
        report = self.mapping_report()
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "is_template": self.is_template,
            "fingerprint": self.fingerprint,
            "mapping_report": report,
        }

    def render(self, task: ImageTask, *, allow_original_prompt: bool = False) -> dict[str, Any]:
        profile = self._profile()
        mapping = self.effective_mapping()
        if "positive" not in mapping and task.prompt.positive and not allow_original_prompt:
            raise WorkflowError("此工作流未映射正向提示词；只能按工作流原样测试，不能注入 AI 或玩家提示词")

        rendered = copy.deepcopy(self.workflow)
        defaults = self.defaults()
        positive = compose_prompt(defaults.get("positive"), task.prompt.positive, profile.player_positive)
        negative = compose_prompt(defaults.get("negative"), task.prompt.negative, profile.player_negative)
        values: dict[str, Any] = {
            "positive": positive,
            "negative": negative,
            "seed": task.prompt.seed if task.prompt.seed is not None else secrets.randbelow(2**63),
            "filename_prefix": f"AliveWorld/{task.id}",
        }

        # The bundled starter workflow intentionally has no model. Preserve its
        # beginner-friendly controls; imported workflows keep their own defaults.
        if self.is_template:
            values.update({
                "checkpoint": str(task.provider_options.get("checkpoint", "")).strip(),
                "width": task.prompt.width,
                "height": task.prompt.height,
                "batch_size": task.prompt.count,
                "steps": task.prompt.steps,
                "cfg": task.prompt.cfg,
            })
            if "checkpoint" in mapping and not values["checkpoint"]:
                raise WorkflowError("内置基础工作流尚未选择生图模型")

        if profile.allow_overrides:
            values.update(profile.overrides)

        for key, value in values.items():
            if key not in mapping or value in (None, ""):
                continue
            node_id, input_name = mapping[key]
            rendered[node_id]["inputs"][input_name] = value
        return rendered


class WorkflowRepository:
    def __init__(self, root: str | Path = WORKFLOW_DIR, profile_root: str | Path | None = None):
        self.root = Path(root)
        self.profile_root = Path(profile_root) if profile_root else (PROFILE_DIR if self.root == WORKFLOW_DIR else self.root / ".profiles")
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
        definition = WorkflowDefinition.from_dict(data, is_template=False, profile_root=self.profile_root)
        path = self.root / f"{definition.id}.json"
        if path.with_name(f"{definition.id}.template.json").exists():
            raise WorkflowError("不能覆盖内置工作流")
        payload = {
            "id": definition.id,
            "name": definition.name,
            "description": definition.description,
            "version": 2,
            "mapping": definition.mapping,
            "workflow": definition.workflow,
        }
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, path)
        return definition

    def _load_path(self, path: Path) -> WorkflowDefinition:
        data = json.loads(path.read_text(encoding="utf-8"))
        return WorkflowDefinition.from_dict(
            data, is_template=path.name.endswith(".template.json"), profile_root=self.profile_root
        )


def infer_standard_mapping(workflow: dict[str, Any]) -> dict[str, list[str]]:
    """Infer unambiguous common fields; missing optional mappings are allowed."""
    by_type: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    mapping: dict[str, list[str]] = {}
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        by_type.setdefault(str(node.get("class_type", "")), []).append((str(node_id), node))
        title = str(node.get("_meta", {}).get("title", "")).strip().lower()
        for key, marker in TITLE_MARKERS.items():
            if title == marker:
                input_name = {
                    "positive": "text", "negative": "text", "width": "width",
                    "height": "height", "batch_size": "batch_size", "checkpoint": "ckpt_name",
                }[key]
                if input_name in node.get("inputs", {}):
                    mapping[key] = [str(node_id), input_name]

    def unique(key: str, class_type: str, input_name: str) -> None:
        if key in mapping:
            return
        matches = [node_id for node_id, node in by_type.get(class_type, []) if input_name in node.get("inputs", {})]
        if len(matches) == 1:
            mapping[key] = [matches[0], input_name]

    text_nodes = by_type.get("CLIPTextEncode", [])
    for key, words in (("positive", ("positive", "正面", "正向")), ("negative", ("negative", "负面", "负向"))):
        if key in mapping:
            continue
        matches = []
        for node_id, node in text_nodes:
            title = str(node.get("_meta", {}).get("title", "")).lower()
            if any(word in title for word in words) and "text" in node.get("inputs", {}):
                matches.append(node_id)
        if len(matches) == 1:
            mapping[key] = [matches[0], "text"]

    unique("checkpoint", "CheckpointLoaderSimple", "ckpt_name")
    unique("width", "EmptyLatentImage", "width")
    unique("height", "EmptyLatentImage", "height")
    unique("batch_size", "EmptyLatentImage", "batch_size")
    unique("seed", "KSampler", "seed")
    unique("steps", "KSampler", "steps")
    unique("cfg", "KSampler", "cfg")
    unique("filename_prefix", "SaveImage", "filename_prefix")
    return mapping
