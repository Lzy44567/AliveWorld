"""C4 request snapshots: independent inputs, whole batches, bounded evidence."""
import copy
import json

from core.prompt_studio import compose_prompt, plan_model_request, RequestMessagePart
from core.request_budget import budget_report
from .models import CharacterSessionError, profile_projection
from .protocol import V3
from .context_contract import C4
from .group_lifecycle import current_attempt, regeneration_context
from .group_records import formal_messages
from .memory import select_memory, final_report
from .world_context import select_world_context, final_world_report
from .recall import recall_candidates, close_groups, trim_group, public_report, evidence_messages
from .opening import opening_context


def request_snapshot(session, request_id):
    if session.get('schema_version') != 2:
        raise CharacterSessionError('REPLY_CONTRACT_UNSUPPORTED')
    action, attempt, group = current_attempt(session, request_id)
    if (attempt.get('reply_contract_id') != V3
            or attempt.get('context_contract_id') != C4):
        raise CharacterSessionError('REPLY_CONTRACT_UNSUPPORTED')
    if (attempt['status'] != 'pending' or group['status'] != 'generating'
            or attempt['context_epoch'] != session['context_epoch']):
        raise CharacterSessionError('REVISION_CONFLICT')
    snapshot = regeneration_context(session, action) if action['operation'] == 'regenerate' else copy.deepcopy(session)
    cutoff = attempt['history_cutoff_seq']
    snapshot['inputs'] = [i for i in snapshot['inputs'] if i['status'] == 'active' and i['message']['seq'] <= cutoff]
    by_id = {i['input_id']: i for i in snapshot['inputs']}
    if not set(attempt['input_ids']) <= set(by_id):
        raise CharacterSessionError('REVISION_CONFLICT')
    claimed = [by_id[mid] for mid in attempt['input_ids']]
    if [i['message']['seq'] for i in claimed] != sorted(i['message']['seq'] for i in claimed):
        raise CharacterSessionError('CONTRACT_INVALID')
    completed = [g for g in snapshot['groups'] if g['status'] in {'complete', 'partial_failed'}
                 and all(b['message']['seq'] <= cutoff for b in g['bubbles'][:g['delivered_count']])]
    # Unclaimed inputs are not context for this request, even if accepted before
    # an oversized queue was split into bounded claims. No fake legacy turns.
    available = {mid for g in completed for mid in g['input_ids']} | set(attempt['input_ids'])
    snapshot['inputs'] = [i for i in snapshot['inputs'] if i['input_id'] in available]
    snapshot['groups'] = completed
    return snapshot, copy.deepcopy(attempt), claimed, group['mode_at_generation']


def build_group_context(session, request_id, budget_options=None, *, preferences=None):
    snapshot, attempt, claimed, mode = request_snapshot(session, request_id)
    ai = next(p['instance_id'] for p in snapshot['participants'] if p['controller'] == 'ai')
    participants = [{'instance_id': p['instance_id'], 'controller': p['controller'],
                     'profile': profile_projection(p)} for p in snapshot['participants']]
    preferences = copy.deepcopy(preferences or [])
    query = '\n'.join(i['message']['content'] for i in claimed)
    current = [copy.deepcopy(i['message']) for i in claimed]
    notes = [{'message_id': i['input_id'], 'content': i['ooc_note']} for i in claimed if i.get('ooc_note')]
    batches = snapshot['groups'][-20:]
    formal = formal_messages(snapshot)

    def history():
        ids = {mid for g in batches for mid in g['input_ids']} | {
            b['message']['message_id'] for g in batches for b in g['bubbles'][:g['delivered_count']]}
        ids -= set(attempt['input_ids'])
        return [copy.deepcopy(m) for m in sorted(formal.values(), key=lambda m: m['seq'])
                if m['message_id'] in ids and ai in m['visibility']['audience_instance_ids']]

    ledger, memory_candidates = select_memory(snapshot, query)
    selected_ids = {e['entry_id'] for e in ledger}
    rules, entries, world_report = select_world_context(snapshot, query)
    system = compose_prompt('character.reply.c4.v3', {'character.presentation_mode': mode})
    recall = recall_candidates(snapshot, ledger, query, [*history(), *current])
    omitted = []
    while True:
        messages = history()
        recalled = close_groups(recall, [*messages, *current], ledger)
        data = {'reply_contract_id': V3, 'context_contract_id': C4, 'participants': participants,
                'world_rules': rules, 'world_related_entries': entries, 'ledger': ledger,
                'history': messages, 'recalled_sources': recalled, 'current_user_messages': current,
                'current_ooc_notes': notes, 'presentation_mode': mode}
        if snapshot.get('opening'):
            data['author_opening'] = opening_context(snapshot['opening'])
        if preferences:
            data['user_preferences'] = preferences
        plan = plan_model_request(system, [RequestMessagePart('character.context', json.dumps(data, ensure_ascii=False))],
                                  temperature=0.8, max_tokens=None, trace_label='character.reply', mode='json',
                                  contract_id=V3, context_contract_id=C4)
        report = budget_report(plan.system_prompt, plan.user_prompt, options=budget_options, manifest=plan.prompt_manifest)
        if report['fits']:
            report.update(omitted=omitted,
                          world_context=final_world_report(world_report, sum('world_entry_id' in i for i in omitted)),
                          memory_context=final_report(memory_candidates, selected_ids, {e['entry_id'] for e in ledger}),
                          source_recall=public_report(recall))
            return plan, evidence_messages([*messages, *current], recalled), {e['entry_id'] for e in ledger}, report
        if preferences:
            preferences.pop(); omitted.append({'field': 'user_preferences'})
        elif entries:
            omitted.append({'world_entry_id': entries.pop()['id']})
        elif any(p['profile'].get('semantics') == 'role_fields_v1' and p['profile'].get('dialogue_examples') for p in participants):
            p = next(p for p in participants if p['profile'].get('semantics') == 'role_fields_v1' and p['profile'].get('dialogue_examples'))
            p['profile'].pop('dialogue_examples'); omitted.append({'participant_id': p['instance_id'], 'field': 'dialogue_examples'})
        elif trim_group(recall):
            omitted.append({'field': 'recalled_sources'})
        elif len(batches) > 2:
            omitted.append({'group_id': batches.pop(0)['group_id']})
        elif ledger:
            omitted.append({'entry_id': ledger.pop()['entry_id']})
        else:
            raise CharacterSessionError('CONTEXT_LIMIT')
