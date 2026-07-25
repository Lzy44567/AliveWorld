"""Safe one-time import of personal data from an older source checkout."""

from __future__ import annotations

import filecmp
import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from utils.runtime_paths import PATHS, RuntimePaths


MIGRATED_DIRECTORIES = (
    "asset_workshops",
    "characters",
    "entities",
    "image_library",
    "image_workflows",
    "preferences",
    "saves",
    "styles",
    "worldbooks",
    "workshops",
)
IGNORED_FILENAMES = {".gitignore", ".gitkeep"}


@dataclass
class MigrationReport:
    source_root: str
    copied_files: int = 0
    skipped_conflicts: int = 0
    copied_config: bool = False


def _personal_files(data_dir: Path) -> Iterable[Path]:
    for directory_name in MIGRATED_DIRECTORIES:
        directory = data_dir / directory_name
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if (
                path.is_file()
                and not path.is_symlink()
                and path.name not in IGNORED_FILENAMES
                and ".template." not in path.name
            ):
                yield path


def has_personal_data(root: Path) -> bool:
    return any(_personal_files(root / "data"))


def discover_legacy_root(
    *,
    executable: str | Path | None = None,
    environ: dict[str, str] | None = None,
) -> Path | None:
    env = dict(os.environ if environ is None else environ)
    candidates: list[Path] = []
    if env.get("ALIVEWORLD_LEGACY_DIR"):
        candidates.append(Path(env["ALIVEWORLD_LEGACY_DIR"]).expanduser())

    # dev.8/dev.9 preview packages stored data here. Keep this candidate so the
    # first truly portable build can offer a non-destructive one-time import.
    local_appdata = env.get("LOCALAPPDATA")
    if local_appdata:
        candidates.append(Path(local_appdata) / "AliveWorld")

    executable_path = Path(executable or sys.executable).resolve()
    candidates.extend(executable_path.parents)
    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen or candidate in {PATHS.user_root.resolve(), PATHS.resource_root.resolve()}:
            continue
        seen.add(candidate)
        if (candidate / "data").is_dir() and has_personal_data(candidate):
            return candidate
    return None


def _copy_missing_tree(source: Path, target: Path, report: MigrationReport) -> None:
    if not source.is_dir():
        return
    for path in source.rglob("*"):
        if not path.is_file() or path.is_symlink() or path.name in IGNORED_FILENAMES:
            continue
        relative = path.relative_to(source)
        destination = target / relative
        if destination.exists():
            if not filecmp.cmp(path, destination, shallow=False):
                report.skipped_conflicts += 1
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        report.copied_files += 1


def migrate_legacy_data(source_root: Path, paths: RuntimePaths = PATHS) -> MigrationReport:
    source_root = source_root.resolve()
    report = MigrationReport(source_root=str(source_root))
    for directory_name in MIGRATED_DIRECTORIES:
        _copy_missing_tree(
            source_root / "data" / directory_name,
            paths.data_dir / directory_name,
            report,
        )

    source_config = source_root / "config.yml"
    example_config = paths.resource_root / "config.example.yml"
    target_config = paths.config_file
    target_is_example = (
        target_config.is_file()
        and example_config.is_file()
        and filecmp.cmp(target_config, example_config, shallow=False)
    )
    if source_config.is_file() and (not target_config.exists() or target_is_example):
        target_config.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_config, target_config)
        report.copied_config = True

    marker = paths.user_root / "legacy_migration.json"
    marker.write_text(
        json.dumps(
            {
                **asdict(report),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return report
