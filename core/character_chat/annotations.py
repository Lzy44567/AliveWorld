"""Derived automatic memory grades; no independent fact storage or model calls."""
import json
import unicodedata

GRADES = {'explicit_preference': 'important', 'explicit_boundary': 'important',
          'commitment': 'important', 'relationship_turn': 'highlight',
          'goal_turn': 'highlight', 'conflict_repair': 'highlight'}


def validate_annotation(value, entry, user_id):
    if not isinstance(value, dict) or set(value) != {'version', 'reason'} or type(value['version']) is not int or value['version'] != 1:
        raise ValueError('Invalid annotation version')
    reason = value['reason']
    if not isinstance(reason, str) or reason not in GRADES:
        raise ValueError('Invalid annotation reason')
    source, kind, about = entry['source']['type'], entry['kind'], entry.get('about_instance_id')
    if reason in {'explicit_preference', 'explicit_boundary'}:
        valid = source == 'player_statement' and about == user_id
    elif reason == 'commitment':
        valid = source in {'player_statement', 'dialogue_event'}
    elif reason == 'goal_turn':
        valid = (source == 'dialogue_event' and kind == 'experience') or (source == 'model_inference' and kind in {'intent', 'belief'})
    else:
        valid = (source == 'dialogue_event' and kind == 'experience') or (source == 'model_inference' and kind == 'relationship' and about == user_id)
    if not valid:
        raise ValueError('Invalid annotation evidence')
    return dict(value)


def parse_annotations(values, ops):
    if not isinstance(values, list) or len(values) > 6:
        raise ValueError('Invalid annotations')
    indexed = {}
    for item in values:
        if not isinstance(item, dict) or set(item) != {'op_index', 'reason'}:
            raise ValueError('Invalid annotation keys')
        index = item['op_index']
        if type(index) is not int or not 0 <= index < len(ops) or index in indexed:
            raise ValueError('Invalid annotation index')
        if not isinstance(item['reason'], str) or item['reason'] not in GRADES:
            raise ValueError('Invalid annotation reason')
        indexed[index] = {'version': 1, 'reason': item['reason']}
    return indexed


def chain_root(entry, session):
    by_id = {e['entry_id']: e for e in session['ledger']}
    current, seen = entry, set()
    for _ in range(2048):
        eid = current['entry_id']
        if eid in seen:
            return None
        seen.add(eid)
        previous_id = current.get('supersedes_entry_id')
        if previous_id is None:
            return eid
        previous = by_id.get(previous_id)
        if previous is None or previous.get('status') != 'superseded' or any(previous.get(k) != entry.get(k) for k in ('subject_instance_id', 'kind', 'about_instance_id')):
            return None
        if not set(current['visibility']['audience_instance_ids']) <= set(previous['visibility']['audience_instance_ids']):
            return None
        current = previous
    return None


def evidence_key(entry):
    annotation = entry.get('memory_annotation')
    if not annotation:
        return None
    normalized = lambda text: unicodedata.normalize('NFKC', text).casefold()
    return json.dumps([entry['subject_instance_id'], entry['kind'], entry.get('about_instance_id'),
                       annotation['reason'], sorted(entry['source']['message_ids']),
                       sorted({(e['message_id'], normalized(e['quote'])) for e in entry['source']['evidence']})], ensure_ascii=False)


def automatic_grades(session, candidates, dismissed):
    candidate_ids = {e['entry_id'] for e in candidates}
    grades, keys = {}, set()
    for entry in session['ledger']:
        if entry['entry_id'] not in candidate_ids or not entry.get('memory_annotation'):
            continue
        root = chain_root(entry, session)
        key = evidence_key(entry)
        if root is None or key in keys:
            continue
        keys.add(key)
        if root in dismissed:
            continue
        grades[entry['entry_id']] = GRADES[entry['memory_annotation']['reason']]
    return grades
