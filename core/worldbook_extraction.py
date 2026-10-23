"""Explicit current-world projection into an independent shareable asset."""
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import yaml

from core.asset_lifecycle import normalize_asset_name, filename_for_asset, find_yaml_asset
from core.worldbook import normalize_worldbook, read_worldbook_bytes, save_worldbook_atomic, worldbook_write_guard
from core.worldbook_revisions import reconcile_capture_history
from core.worldbook_collaboration import fingerprint, rule_catalog, disabled_references
from core.world_packages.identity import assign_new_asset_id
from core.world_packages.privacy import scan_asset


class ExtractionConflict(ValueError):
    pass


def extraction_view(save_dir, turns, collaboration):
    directory = (Path(save_dir) / 'worldbooks').resolve()
    books, revisions = {}, {}
    for path in sorted(directory.glob('*.yml')):
        if path.resolve().parent != directory:
            continue
        content = read_worldbook_bytes(path).decode('utf-8')
        raw = yaml.safe_load(content)
        if not isinstance(raw, dict):
            continue
        revisions[path.stem] = content
        projected, _ = reconcile_capture_history(raw, turns)
        books[path.stem] = normalize_worldbook(projected)
    disabled = disabled_references(collaboration, books, turns)
    excluded = {(r['book_id'], r['item_id']) for ref, r in rule_catalog(books).items() if ref in disabled}
    result = []
    for book_id, book in books.items():
        if not book.get('is_active', True):
            continue
        entries = [
            {key: deepcopy(entry[key]) for key in ('id', 'name', 'keys', 'content', 'tags')}
            for entry in book['entries'] if entry.get('is_active', True)
            and not {'待确认', '待删除'}.intersection(entry['tags'])
            and (book_id, entry['id']) not in excluded
        ]
        result.append({'book_id': book_id, 'name': book['name'], 'overview': book['overview'],
                       'axioms': book['axioms'], 'entries': entries,
                       'excluded_count': len(book['entries']) - len(entries)})
    return {'revision': fingerprint([revisions, turns, collaboration]), 'books': result}


def prepare_extraction(view, *, book_id, expected_revision, name, entry_ids, include_overview, include_axioms):
    if view['revision'] != expected_revision:
        raise ExtractionConflict('故事设定已变化，请刷新预览后重新选择')
    source = next((b for b in view['books'] if b['book_id'] == book_id), None)
    if source is None:
        raise ExtractionConflict('来源世界书已停用或移除，请刷新预览')
    entries = {entry['id']: entry for entry in source['entries']}
    if len(set(entry_ids)) != len(entry_ids) or any(key not in entries for key in entry_ids):
        raise ValueError('所选条目已不存在或重复，请刷新预览')
    selected = [deepcopy(entries[key]) for key in entry_ids]
    for entry in selected:
        entry['id'] = 'entry_' + uuid4().hex
        entry['is_active'] = True
    result = {'name': normalize_asset_name(name), 'overview': source['overview'] if include_overview else '',
              'axioms': deepcopy(source['axioms']) if include_axioms else [], 'entries': selected, 'is_active': True}
    if not result['overview'] and not result['axioms'] and not selected:
        raise ValueError('请至少保留概述、公理或一个条目')
    assign_new_asset_id(result)
    issues = scan_asset('worldbooks/extracted.yml', yaml.safe_dump(result, allow_unicode=True).encode('utf-8'))
    if issues:
        raise ValueError('内容未通过隐私检查，请先编辑来源或取消相关内容：' + '；'.join(i.message for i in issues))
    return result


def save_extraction(directory, book):
    directory = Path(directory)
    target = directory / filename_for_asset(book['name'])
    with worldbook_write_guard(directory / '.extraction'):
        with worldbook_write_guard(target):
            if target.exists() or find_yaml_asset(directory, book['name']):
                raise ExtractionConflict('已存在同名世界书，请使用新的名称；不会覆盖已有资产')
            save_worldbook_atomic(target, book)
    return {'type': 'worldbooks', 'name': book['name'], 'description': book['overview'][:240], 'tags': [], 'is_template': False}
