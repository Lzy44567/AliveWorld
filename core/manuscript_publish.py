"""Publish explicitly accepted manuscript candidates through existing asset writers."""
from pathlib import Path
import yaml
from core.asset_lifecycle import filename_for_asset, find_yaml_asset, normalize_asset_name
from core.asset_workshop import normalize_asset
from core.character_asset_write import write_character
from core.worldbook import normalize_worldbook, save_worldbook_atomic
from core.session_manager import mutation_guard
from core.world_packages.identity import asset_id_from_data
from utils.atomic_yaml import save_yaml_atomic


def publish_candidates(repo, data_root, project_id, expected_revision, candidate_ids):
    project = repo.load(project_id)
    if project['revision'] != expected_revision:
        raise ValueError('项目已修改，请刷新后发布')
    by_id = {item['id']: item for item in project['candidates']}
    if not candidate_ids or len(set(candidate_ids)) != len(candidate_ids) or any(i not in by_id for i in candidate_ids):
        raise ValueError('请选择有效且不重复的候选')
    results = []
    for candidate_id in candidate_ids:
        item = by_id[candidate_id]
        if item['kind'] in {'starter', 'future_notes'}:
            results.append({'id': candidate_id, 'status': 'project_only', 'message': '保留为项目资料，不写入全局资产'})
            continue
        if item['status'] == 'published':
            results.append({'id': candidate_id, 'status': 'published', 'name': item['name']})
            continue
        if item['status'] != 'accepted':
            results.append({'id': candidate_id, 'status': 'error', 'message': '请先审阅并接受此候选'})
            continue
        try:
            name = normalize_asset_name(item['name'])
            directory = Path(data_root) / item['kind']
            path = directory / filename_for_asset(name)
            asset_id = 'awasset_' + candidate_id.replace('-', '')
            with mutation_guard('manuscript-asset', str(path.resolve()).casefold()):
                existing = find_yaml_asset(directory, name)
                if existing:
                    current = yaml.safe_load(existing.read_text(encoding='utf-8'))
                    if asset_id_from_data(current) != asset_id:
                        raise ValueError('已有同名资产，请修改候选名称；不会覆盖')
                else:
                    content = {**item['content'], 'name': name}
                    asset = normalize_worldbook({key: value for key, value in content.items()
                        if key in {'name', 'overview', 'axioms', 'entries', 'tags'}}) if item['kind'] == 'worldbooks' else normalize_asset(item['kind'], content)
                    asset['_aliveworld'] = {'asset_id': asset_id}
                    if item['kind'] == 'characters':
                        write_character(path, asset, overwrite=False)
                    elif item['kind'] == 'worldbooks':
                        save_worldbook_atomic(path, asset)
                    else:
                        save_yaml_atomic(path, asset)
            item.update(status='published', name=name)
            results.append({'id': candidate_id, 'status': 'published', 'name': name})
        except (ValueError, OSError) as exc:
            results.append({'id': candidate_id, 'status': 'error', 'message': str(exc) if isinstance(exc, ValueError) else '资产写入失败，候选保留'})
        project['revision'] += 1
        project = repo.save(project)
        by_id = {item['id']: item for item in project['candidates']}
    return {'project': project, 'results': results}
