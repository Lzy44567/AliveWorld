"""Uncommitted public text, separate from game and workshop transactions."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import UUID

from core.json_stream import JSONTextPreview

_capture = ContextVar('generation_recovery', default=None)


def public_text(raw, fields):
    preview = JSONTextPreview(fields, lambda text: None)
    source = raw.strip()
    if source.startswith('```'):
        source = source.split('\n', 1)[-1]
    # Feed complete prefixes so a later malformed key cannot erase earlier prose.
    for index in range(0, len(source), 512):
        try:
            preview.feed(source[index:index + 512])
        except ValueError:
            preview = JSONTextPreview(fields, lambda text: None)
            if index:
                preview.feed(source[:index])
            for char in source[index:index + 512]:
                try:
                    preview.feed(char)
                except ValueError:
                    break
            break
    return preview.visible


@contextmanager
def capture_generation():
    state = {'text': '', 'reason': '', 'blocked': False}
    token = _capture.set(state)
    try:
        yield state
    finally:
        _capture.reset(token)


def capture_response(raw, fields, reason=''):
    state = _capture.get()
    if state is None:
        return
    if reason == 'content_filter':
        state.update(text='', reason=reason, blocked=True)
        return
    if state['blocked']:
        return
    text = public_text(raw, fields)
    if text:
        state['text'] = text
    if reason:
        state['reason'] = reason


def failure_reason(reason, error):
    detail = str(error).lower()
    if reason == 'length' or 'length:' in detail:
        return 'output_limit'
    if any(word in detail for word in ('json', '解析', 'unterminated', 'expecting', 'extra data')):
        return 'format'
    if reason == 'incomplete_stream' or any(word in detail for word in ('timeout', 'connection', 'network')):
        return 'connection'
    return 'generation_or_save'


def save_draft(directory, request_id, state, request_text, operation, error):
    if not state['text'] or state['blocked']:
        return None
    identity = str(UUID(str(request_id)))
    record = {'id': identity, 'created_at': datetime.now(timezone.utc).isoformat(),
              'text': state['text'], 'request': request_text, 'operation': operation,
              'reason': failure_reason(state['reason'], error)}
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f'{identity}.json'
    temporary = directory / f'{identity}.tmp'
    try:
        temporary.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return record


def read_drafts(directories):
    records = []
    for directory in directories:
        for path in Path(directory).glob('*.json'):
            records.append(json.loads(path.read_text(encoding='utf-8')))
    return sorted(records, key=lambda item: item['created_at'], reverse=True)


def delete_draft(directories, request_id):
    identity = str(UUID(str(request_id)))
    for directory in directories:
        (Path(directory) / f'{identity}.json').unlink(missing_ok=True)
