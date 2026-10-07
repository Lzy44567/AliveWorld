"""Old request contracts over true schema2 messages, never synthetic turns."""
import copy

from .models import CharacterSessionError
from .context import _build_context
from .protocol import V1, V2, validate_contract
from .context_contract import LEGACY, C3, C4, validate_context_contract
from .group_records import formal_messages, active_groups
from .contract import reverse_ledger


def legacy_snapshot(action, attempt):
    snapshot = copy.deepcopy(action.get('legacy_retry_snapshot') or attempt.get('legacy_retry_snapshot'))
    if not isinstance(snapshot, dict) or attempt.get('legacy_attempt') is not True:
        raise CharacterSessionError('STALE_RETRY')
    contract = validate_contract(attempt.get('reply_contract_id', V1))
    context = validate_context_contract(attempt.get('context_contract_id', LEGACY))
    if (contract not in {V1, V2} or context == C4
            or snapshot.get('reply_contract_id', contract) != contract
            or snapshot.get('context_contract_id', context) != context
            or bool(snapshot.get('ooc_note')) != (context == C3)):
        raise CharacterSessionError('CONTEXT_CONTRACT_UNSUPPORTED')
    return snapshot, contract, context


def build_legacy_retry_context(session, action, attempt, budget_options=None, *, preferences=None):
    if session.get('schema_version') != 2:
        raise CharacterSessionError('SCHEMA_READ_ONLY')
    pending, contract, context = legacy_snapshot(action, attempt)
    value = copy.deepcopy(session)
    if action['operation'] == 'regenerate':
        target = next((g for g in value['groups'] if g['group_id'] == action.get('target_group_id')), None)
        if target is None or target['status'] != 'complete':
            raise CharacterSessionError('STALE_RETRY')
        reverse_ledger(value, target['ledger_inverse'])
        target['status'] = 'replaced'
        for entry in value['inputs']:
            if entry['input_id'] in target['input_ids']:
                entry['status'] = 'withdrawn'
    execution = attempt.get('legacy_execution')
    cutoff = execution['history_cutoff_seq'] if execution else value['next_seq'] - 1
    groups = [g for g in active_groups(value) if g['status'] in {'complete', 'partial_failed'}
              and all(b['message']['seq'] <= cutoff for b in g['bubbles'][:g['delivered_count']])]
    owned = {mid for g in groups for mid in g['input_ids']}
    value['groups'] = groups
    value['inputs'] = [i for i in value['inputs'] if i['status'] == 'active' and i['input_id'] in owned and i['message']['seq'] <= cutoff]
    formal = formal_messages(value)
    batches = []
    for group in groups:
        ids = set(group['input_ids']) | {b['message']['message_id'] for b in group['bubbles'][:group['delivered_count']]}
        messages = sorted([m for mid, m in formal.items() if mid in ids], key=lambda m: m['seq'])
        batches.append((group['group_id'], messages))
    return _build_context(value, pending, batches, budget_options, preferences=preferences,
                          contract_id=contract, context_contract_id=context)
