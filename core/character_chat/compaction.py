"""Derived long-chat summaries; original messages remain authoritative."""
import copy
import hashlib
import json
from datetime import datetime, timezone

from core.compaction_plan import plan_compaction
from core.request_budget import estimate_tokens
from .group_records import formal_messages
from .models import CharacterSessionError

KEY = 'character_compaction'
MAX_SEGMENTS = 24
MAX_SUMMARY_CHARS = 1200


def state(session):
    return copy.deepcopy(session.get(KEY, {
        'version': 1, 'enabled': False, 'generation': 0, 'through_seq': 0,
        'segments': [], 'failure': None,
    }))


def validate_stored(session):
    if KEY not in session:
        return
    value = session[KEY]
    def require(condition):
        if not condition:
            raise ValueError()
    try:
        require(set(value) == {'version', 'enabled', 'generation', 'through_seq', 'segments', 'failure'})
        require(value['version'] == 1 and type(value['enabled']) is bool)
        require(all(type(value[k]) is int and value[k] >= 0 for k in ('generation', 'through_seq')))
        require(value['failure'] is None or isinstance(value['failure'], str) and len(value['failure']) <= 80)
        require(isinstance(value['segments'], list) and len(value['segments']) <= MAX_SEGMENTS)
        for segment in value['segments']:
            require(set(segment) == {'sources', 'through_seq', 'summary', 'created_at'})
            require(type(segment['through_seq']) is int and 0 < segment['through_seq'] <= value['through_seq'])
            require(isinstance(segment['summary'], str) and 1 <= len(segment['summary']) <= MAX_SUMMARY_CHARS)
            require(isinstance(segment['sources'], dict) and 1 <= len(segment['sources']) <= 10)
            require(all(isinstance(k, str) and len(k) == 36 and isinstance(v, str) and len(v) == 64
                        for k, v in segment['sources'].items()))
            datetime.fromisoformat(segment['created_at'])
    except (TypeError, ValueError, KeyError):
        raise CharacterSessionError('SESSION_CORRUPT') from None


def units(session):
    """Whole completed groups only, without OOC, candidates or private ledger."""
    formal = formal_messages(session)
    audience = {p['instance_id'] for p in session['participants']}
    result = []
    for group in session['groups']:
        if group['status'] != 'complete' or group['delivered_count'] != len(group['bubbles']):
            continue
        mids = group['input_ids'] + [b['message']['message_id'] for b in group['bubbles']]
        if not mids or any(mid not in formal for mid in mids):
            continue
        messages = [formal[mid] for mid in mids]
        if any(not audience <= set(m['visibility']['audience_instance_ids']) for m in messages):
            continue
        messages = [{k: m[k] for k in ('message_id', 'speaker_instance_id', 'content', 'seq')}
                    for m in sorted(messages, key=lambda m: m['seq'])]
        raw = json.dumps(messages, ensure_ascii=False, sort_keys=True)
        result.append({'group_id': group['group_id'], 'messages': messages,
                       'fingerprint': hashlib.sha256(raw.encode('utf-8')).hexdigest(),
                       'through_seq': messages[-1]['seq'], 'token_estimate': estimate_tokens(raw)})
    return sorted(result, key=lambda unit: unit['through_seq'])


def valid_segments(session, value=None):
    value = value if value is not None else state(session)
    sources = {u['group_id']: u['fingerprint'] for u in units(session)}
    return [s for s in value['segments'] if all(sources.get(gid) == fingerprint
            for gid, fingerprint in s['sources'].items())]


def references(session):
    value = state(session)
    if not value['enabled']:
        return []
    return [{'summary': s['summary'], 'through_seq': s['through_seq']}
            for s in valid_segments(session, value)[-8:]]


def configure(session, enabled, *, acknowledged=False):
    if type(enabled) is not bool or (enabled and acknowledged is not True):
        raise CharacterSessionError('INVALID_REQUEST')
    value = state(session)
    if value['enabled'] == enabled:
        return False
    value['enabled'] = enabled
    value['generation'] += 1
    session[KEY] = value
    return True


def rebuild(session):
    value = state(session)
    if not value['enabled']:
        raise CharacterSessionError('INVALID_REQUEST')
    value.update(generation=value['generation'] + 1, through_seq=0, segments=[], failure=None)
    session[KEY] = value


def prepare(session, *, explicit=False):
    value = state(session)
    if not value['enabled'] or value['failure']:
        return None
    pending = [u for u in units(session) if u['through_seq'] > value['through_seq']]
    if len(pending) <= 10:
        return None
    count_trigger = len(pending) > 20 or explicit
    plan = plan_compaction(pending, high_water=6000, low_water=3000,
                           min_hot_units=10, bridge_tokens=0,
                           force=count_trigger, minimum_force_tokens=1)
    if not plan:
        return None
    candidates = pending[:-10][:10] if count_trigger else plan['archive'][:min(10, len(pending) - 10)]
    archive, total = [], 0
    for unit in candidates:
        if total + unit['token_estimate'] > 12000:
            break
        archive.append(unit)
        total += unit['token_estimate']
    if not archive or (len(archive) < 5 and not explicit and total < 3000):
        return None
    return {'generation': value['generation'], 'sources': {u['group_id']: u['fingerprint'] for u in archive},
            'through_seq': archive[-1]['through_seq'],
            'messages': [m for u in archive for m in u['messages']]}


def current_job(session, job):
    value = state(session)
    if not value['enabled'] or value['generation'] != job['generation']:
        return False
    sources = {u['group_id']: u['fingerprint'] for u in units(session)}
    return all(sources.get(gid) == fingerprint for gid, fingerprint in job['sources'].items())


def parse_summary(raw):
    try:
        result = json.loads(raw)
        summary = result['summary']
        if set(result) != {'summary'} or not isinstance(summary, str) or not 1 <= len(summary.strip()) <= MAX_SUMMARY_CHARS:
            raise ValueError()
        return summary.strip()
    except (ValueError, TypeError, KeyError):
        raise CharacterSessionError('CONTRACT_INVALID') from None


def commit(session, job, summary):
    if not current_job(session, job):
        return False
    value = state(session)
    if value['through_seq'] >= job['through_seq']:
        return False
    value['segments'] = (valid_segments(session, value) + [{
        'sources': job['sources'], 'through_seq': job['through_seq'], 'summary': summary,
        'created_at': datetime.now(timezone.utc).isoformat(),
    }])[-MAX_SEGMENTS:]
    value.update(through_seq=job['through_seq'], failure=None)
    session[KEY] = value
    return True


def failed(session, job, code):
    if not current_job(session, job):
        return False
    value = state(session)
    value['failure'] = code
    session[KEY] = value
    return True


def public_state(session):
    value = state(session)
    valid = valid_segments(session, value)
    return {'enabled': value['enabled'], 'failure': value['failure'],
            'segments': [{k: s[k] for k in ('summary', 'through_seq', 'created_at')}
                         | {'group_ids': list(s['sources'])} for s in valid],
            'invalid_count': len(value['segments']) - len(valid),
            'through_seq': value['through_seq'], 'limit': MAX_SEGMENTS}
