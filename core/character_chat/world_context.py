"""Bounded literal retrieval from the bound book and public formal dialogue only."""
from copy import deepcopy
from core.worldbook import entry_keywords, normalize_entry

RECENT_TURNS = 4
RECENT_CHARS = 12000
RELATED_LIMIT = 16


def public_recent_messages(session):
    audience = {p['instance_id'] for p in session['participants']}
    messages, used = [], 0
    for distance, turn in enumerate(reversed(session['turns'][-RECENT_TURNS:]), 1):
        for key in ('ai_message', 'user_message'):
            message = turn[key]
            if not audience.issubset(message['visibility']['audience_instance_ids']):
                continue
            content = message['content']
            if used + len(content) > RECENT_CHARS:
                continue
            messages.append((distance, content.casefold()))
            used += len(content)
    return messages


def select_world_context(session, current_input):
    binding = session.get('world_binding')
    if not binding:
        return None, [], None
    book = binding['snapshot']
    rules = {key: deepcopy(book.get(key, '')) for key in ('name', 'overview', 'axioms')}
    recent = public_recent_messages(session)
    current = current_input.casefold()
    hits, resident, seen = [], [], set()
    for position, raw in enumerate(book.get('entries', [])):
        entry = normalize_entry(raw)
        if not entry['is_active'] or {'待确认', '待删除'}.intersection(entry['tags']) or entry['id'] in seen:
            continue
        seen.add(entry['id'])
        projected = {key: entry[key] for key in ('id', 'name', 'content', 'tags')}
        if {'常驻', '绝对规则'}.intersection(entry['tags']):
            resident.append(projected)
            continue
        keys = [key.casefold() for key in entry_keywords(entry)]
        distance = 0 if any(key in current for key in keys) else next(
            (distance for distance, content in recent if any(key in content for key in keys)), None)
        if distance is not None:
            hits.append((distance, position, projected))
    if resident:
        rules['entries'] = resident
    hits.sort(key=lambda hit: (hit[0], hit[1]))
    selected = hits[:RELATED_LIMIT]
    report = {'window_turns': RECENT_TURNS, 'resident_count': len(resident),
              'omitted_by_limit': max(0, len(hits) - RELATED_LIMIT), 'omitted_by_budget': 0,
              'entries': [{'entry_id': entry['id'][:64], 'entry_name': entry['name'][:100],
                           'source': 'current' if distance == 0 else 'recent',
                           'turn_distance': distance, 'planned': True}
                          for distance, _, entry in selected]}
    return rules, [entry for _, _, entry in selected], report


def final_world_report(report, omitted_count):
    if report is None:
        return None
    result = deepcopy(report)
    result['omitted_by_budget'] = omitted_count
    # Follow selection order, not truncated diagnostic IDs, when marking cuts.
    if omitted_count:
        for item in result['entries'][-omitted_count:]:
            item['planned'] = False
    return result
