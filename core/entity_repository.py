"""本局暗流实体的 YAML 持久化边界。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List

import yaml

from core.entities import Entity


class EntityRepository:
    def __init__(self, save_dir_path: str = ""):
        self.save_dir = Path(save_dir_path) if save_dir_path else None

    @property
    def entity_dir(self) -> Path | None:
        return self.save_dir / "entities" if self.save_dir else None

    @staticmethod
    def filename_for(name: str) -> str:
        safe_name = re.sub(r"[^\w\s-]", "", name).strip()
        return f"{safe_name or '未命名变数'}.yml"

    def load(self) -> List[Entity]:
        if not self.entity_dir or not self.entity_dir.exists():
            return []

        entities = []
        for path in sorted(self.entity_dir.glob("*.yml")):
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError):
                continue
            if isinstance(raw, dict):
                entities.append(Entity.from_dict(raw))
        return entities

    def synchronize(self, entities: Iterable[Entity]) -> None:
        """使本局实体目录与给定实体集合一致。

        实体目录只属于当前存档；缺席的实体视为已删除并移除对应文件，保持 v1.0.0 的删除语义。
        """
        if not self.entity_dir:
            return
        self.entity_dir.mkdir(parents=True, exist_ok=True)

        entity_list = list(entities)
        expected_paths = {self.entity_dir / self.filename_for(entity.name) for entity in entity_list}
        for path in self.entity_dir.glob("*.yml"):
            if path not in expected_paths:
                path.unlink()

        for entity in entity_list:
            path = self.entity_dir / self.filename_for(entity.name)
            with path.open("w", encoding="utf-8") as file:
                yaml.safe_dump(entity.to_dict(), file, allow_unicode=True, sort_keys=False)
