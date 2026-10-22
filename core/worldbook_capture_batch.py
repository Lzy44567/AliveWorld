"""One capture request, explicit local destinations, existing per-book commits."""
import json
from pathlib import Path

import yaml

from core.ai_engine import robust_json_parse
from core.auto_worldbook import ensure_auto_capture_worldbook
from core.capture_source import source_is_current
from core.worldbook import normalize_worldbook, read_worldbook_bytes, worldbook_revision
from core.worldbook_collaboration import primary_book
from core.worldbook_revisions import reconcile_capture_history
from core.worldbook_capture_routing import ROUTING_PROMPT, route_candidates
from core.world_change_events import confirmed_world_changes


def read_state(save_dir):
    path = Path(save_dir) / 'session_state.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def capture_books(service, save_dir, action, story, *, review_all, world_change_events=None, source_turn=None):
    from core.worldbook_capture import CAPTURE_PROMPT
    if source_turn is not None and not source_is_current(save_dir, source_turn):
        return {'skipped': ['源回合已失效']}
    if world_change_events is not None:
        world_change_events = confirmed_world_changes({'world_change_events': world_change_events, 'story_text': story})
        if not world_change_events:
            return {'skipped': ['无有效世界变化证据']}
    state = read_state(save_dir)
    selection = state.get('worldbook_collaboration', {}).get('primary_book', '')
    books, revisions, paths = {}, {}, {}
    for path in sorted((Path(save_dir) / 'worldbooks').glob('*.yml')):
        raw = read_worldbook_bytes(path)
        book = normalize_worldbook(yaml.safe_load(raw.decode('utf-8')) or {})
        if not book.get('is_active', True):
            continue
        book, _ = reconcile_capture_history(book, state.get('history', {}).get('story_turns', []))
        books[path.stem] = book
        revisions[path.stem] = worldbook_revision(raw)
        paths[path.stem] = path
    if len(books) <= 1:
        path = next(iter(paths.values()), None)
        if path is None:
            path = ensure_auto_capture_worldbook(save_dir)
            if not normalize_worldbook(yaml.safe_load(read_worldbook_bytes(path))).get('is_active', True):
                return {'skipped': ['本局自动设定已关闭']}
        return service.capture(path, action, story, review_all=review_all,
                               world_change_events=world_change_events, source_turn=source_turn, save_dir=save_dir)
    catalog = [{**{k: v for k, v in book.items() if k != 'capture_history'}, 'book_id': key}
               for key, book in books.items()]
    prompt = (f'【世界书目录】\n{json.dumps(catalog, ensure_ascii=False)}\n'
              f'【主书】{primary_book(state.get("worldbook_collaboration", {}), books)}\n'
              f'【已校验世界变化信号】\n{json.dumps(world_change_events, ensure_ascii=False)}\n'
              f'【玩家行动】\n{action}\n【本回合正文】\n{story}')
    raw, error = service.ai_engine.chat_json(CAPTURE_PROMPT + ROUTING_PROMPT, prompt,
                                            temp=0.3, trace_label='世界书异步捕获')
    if error or not raw:
        return {'skipped': [error or '空返回']}
    groups, skipped = route_candidates(robust_json_parse(raw), books)
    results = {}
    for target, candidates in groups.items():
        current = read_state(save_dir)
        if current.get('worldbook_collaboration', {}).get('primary_book', '') != selection:
            skipped.append('主书选择已变化，剩余候选未写入')
            break
        if source_turn is not None and not source_is_current(save_dir, source_turn):
            skipped.append('源回合已失效')
            break
        if target:
            path, revision = paths[target], revisions[target]
        else:
            path = ensure_auto_capture_worldbook(save_dir)
            data = read_worldbook_bytes(path)
            if not normalize_worldbook(yaml.safe_load(data)).get('is_active', True):
                skipped.append('本局自动设定已关闭，未写入兜底候选')
                continue
            revision = worldbook_revision(data)
        results[path.stem] = service.capture(
            path, action, story, review_all=review_all, world_change_events=world_change_events,
            source_turn=source_turn, save_dir=save_dir, expected_revision=revision,
            candidate_payload={'candidates': candidates}, expected_primary=selection)
        skipped.extend(results[path.stem].get('skipped', []))
    return {'books': results, 'skipped': skipped}
