"""Local manuscript drafts; publishing assets is a separate explicit operation."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import yaml
from utils.atomic_yaml import save_yaml_atomic

KINDS = {'worldbooks', 'characters', 'styles', 'entities', 'starter', 'future_notes'}
ORIGINS = {'original', 'suggested', 'missing'}
TEXT_FIELDS = {
    'worldbooks': {'overview'}, 'characters': {'description', 'starting_scene'},
    'styles': {'content'}, 'entities': {'description', 'motive'},
    'starter': {'world_premise', 'opening'}, 'future_notes': {'text'},
}
LIST_FIELDS = {'worldbooks': {'axioms'}, 'entities': {'mechanisms', 'plans'}}


def validate_content(kind, content):
    """Model/editor fields must be renderable and cannot inject asset metadata."""
    texts, lists = TEXT_FIELDS[kind], LIST_FIELDS.get(kind, set())
    allowed = texts | lists | ({'entries'} if kind == 'worldbooks' else set())
    if set(content) - allowed:
        raise ValueError('候选含不支持的字段，请按对应资产格式整理')
    for key, value in content.items():
        if key in texts and not isinstance(value, str):
            raise ValueError(f'{key}必须是文本')
        if key in lists and (not isinstance(value, list) or not all(isinstance(v, str) for v in value)):
            raise ValueError(f'{key}必须是文本列表')
        if key == 'entries':
            if not isinstance(value, list):
                raise ValueError('世界书条目必须是列表')
            for entry in value:
                if (not isinstance(entry, dict) or set(entry) - {'name', 'content', 'keywords'}
                    or not all(isinstance(entry.get(k), str) for k in ('name', 'content'))
                    or not isinstance(entry.get('keywords', []), list)
                    or not all(isinstance(k, str) for k in entry.get('keywords', []))):
                    raise ValueError('世界书条目需要名称、内容和文本关键词列表')


def normalize_candidates(items, source_text):
    """Validate model/editor input once, before replacing a saved draft."""
    if not isinstance(items, list):
        raise ValueError('整理结果需要是候选列表')
    result = []
    for item in items:
        if not isinstance(item, dict) or item.get('kind') not in KINDS:
            raise ValueError('候选资产类型不支持')
        if item.get('origin') not in ORIGINS:
            raise ValueError('请标明原稿已有、推导建议或缺失待补')
        if not isinstance(item.get('name'), str) or not item['name'].strip():
            raise ValueError('候选名称不能为空')
        if not isinstance(item.get('content'), dict):
            raise ValueError('候选内容需要是对象')
        validate_content(item['kind'], item['content'])
        quote = item.get('source_quote', '')
        if not isinstance(quote, str) or (quote and quote not in source_text):
            raise ValueError('来源片段不在选取的原稿中，请重新核对')
        result.append({'id': str(uuid4()), 'kind': item['kind'], 'name': item['name'].strip(),
                       'origin': item['origin'], 'source_quote': quote,
                       'content': deepcopy(item['content']), 'status': 'pending'})
    return result


class ManuscriptProjects:
    def __init__(self, root):
        self.root = Path(root)

    def _path(self, project_id):
        return self.root / f'{UUID(project_id)}.yml'

    def load(self, project_id):
        return yaml.safe_load(self._path(project_id).read_text(encoding='utf-8'))

    def save(self, project):
        value = deepcopy(project)
        value['updated_at'] = datetime.now(timezone.utc).isoformat()
        save_yaml_atomic(self._path(value['id']), value)
        return value

    def create(self, title, source_text):
        if not isinstance(title, str) or not title.strip():
            raise ValueError('请输入项目名称')
        if not isinstance(source_text, str) or not source_text.strip():
            raise ValueError('请先添加手稿')
        return self.save({'id': str(uuid4()), 'title': title.strip(), 'source_text': source_text,
                          'revision': 0, 'candidates': [], 'selected_text': '', 'notes': ''})

    def list(self):
        projects = [self.load(path.stem) for path in self.root.glob('*.yml')]
        return sorted([{'id': p['id'], 'title': p['title'], 'updated_at': p['updated_at']}
                       for p in projects], key=lambda p: p['updated_at'], reverse=True)

    def store_analysis(self, project_id, expected_revision, selected_text, candidates, notes):
        project = self.load(project_id)
        if project['revision'] != expected_revision:
            raise ValueError('项目已修改，请刷新后重新整理')
        if not selected_text or selected_text not in project['source_text']:
            raise ValueError('请选择原稿中的连续文本')
        normalized = normalize_candidates(candidates, selected_text)
        if not isinstance(notes, str):
            raise ValueError('整理说明必须是文本')
        # Append rather than discard previously edited/accepted work.
        project['candidates'].extend(normalized)
        project.update(selected_text=selected_text, notes=notes, revision=expected_revision + 1)
        return self.save(project)

    def review(self, project_id, expected_revision, changes):
        project = self.load(project_id)
        if project['revision'] != expected_revision:
            raise ValueError('项目已修改，请刷新后再审阅')
        by_id = {item['id']: item for item in project['candidates']}
        for change in changes:
            item = by_id.get(change['id'])
            if item is None or item['status'] == 'published':
                raise ValueError('候选不存在或已发布，请在资产工坊编辑已发布内容')
            status = change.get('status', item['status'])
            if status not in {'pending', 'accepted', 'rejected'}:
                raise ValueError('审阅状态无效')
            edited = {**item, 'name': change.get('name', item['name']),
                      'content': change.get('content', item['content'])}
            validated = normalize_candidates([edited], project['source_text'])[0]
            item.update(name=validated['name'], content=validated['content'], status=status)
        project['revision'] += 1
        return self.save(project)
