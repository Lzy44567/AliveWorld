"""Extract one exact version section from the human-facing changelog."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")


def extract_release_notes(changelog: str, version: str) -> str:
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"无效版本号：{version}")
    heading = re.compile(rf"^## \[v{re.escape(version)}\].*$", re.MULTILINE)
    matches = list(heading.finditer(changelog))
    if len(matches) != 1:
        raise ValueError(f"更新日志中必须且只能存在一个 v{version} 标题，实际为 {len(matches)} 个")
    start = matches[0].end()
    next_heading = re.search(r"^## \[", changelog[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(changelog)
    notes = changelog[start:end].strip()
    if not notes:
        raise ValueError(f"v{version} 更新日志为空")
    return notes + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--changelog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    notes = extract_release_notes(args.changelog.read_text(encoding="utf-8-sig"), args.version)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(notes, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
