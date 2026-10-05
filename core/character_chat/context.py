"""Permission-first, bounded context construction with whole-entry trimming."""
import json
from core.prompt_studio import compose_prompt, plan_model_request, RequestMessagePart
from core.request_budget import budget_report
from .models import CharacterSessionError, profile_projection
from .opening import opening_context
from .world_context import select_world_context, final_world_report
from .memory import select_memory, final_report
from .protocol import contract_for, validate_contract, V2
from .context_contract import M3, validate_context_contract
from .recall import recall_candidates, close_groups, trim_group, public_report, evidence_messages


def build_context(session, pending, budget_options=None, *, preferences=None, contract_id=None, context_contract_id=M3):
    contract_id = validate_contract(contract_id or contract_for(session))
    context_contract_id = validate_context_contract(context_contract_id)
    preferences = [dict(item) for item in (preferences or [])]
    ai = next(p['instance_id'] for p in session['participants'] if p['controller'] == 'ai')
    participants = [{'instance_id': p['instance_id'], 'controller': p['controller'],
                     'profile': profile_projection(p)} for p in session['participants']]
    turns = session['turns'][-20:]
    ledger, memory_candidates = select_memory(session, pending['content'])
    selected_ids = {e['entry_id'] for e in ledger}
    rules, entries, world_report = select_world_context(session, pending['content'])
    task = ('character.reply.m3.v2' if contract_id == V2 else 'character.reply.m3.v1') if context_contract_id == M3 else ('character.reply.v2' if contract_id == V2 else 'character.reply')
    system = compose_prompt(task, {'character.presentation_mode': pending['mode']})
    initial_messages = [m for t in turns for m in (t['user_message'], t['ai_message']) if ai in m['visibility']['audience_instance_ids']]
    groups = recall_candidates(session, ledger, pending['content'], initial_messages) if context_contract_id == M3 else []
    omitted = []
    while True:
        messages = [m for t in turns for m in (t['user_message'], t['ai_message'])
                    if ai in m['visibility']['audience_instance_ids']]
        data = {'reply_contract_id': contract_id, 'participants': participants, 'world_rules': rules, 'world_related_entries': entries,
                'ledger': ledger, 'history': messages,
                'current_user_message': {'message_id': pending['user_message_id'], 'content': pending['content']},
                'current_ai_message_id': pending['ai_message_id'], 'presentation_mode': pending['mode']}
        recalled = close_groups(groups, messages, ledger)
        if context_contract_id == M3:
            data.update(context_contract_id=context_contract_id, recalled_sources=recalled)
        if session.get('opening'):
            data['author_opening'] = opening_context(session['opening'])
        if preferences:
            data['user_preferences'] = preferences
        plan = plan_model_request(system, [RequestMessagePart('character.context', json.dumps(data, ensure_ascii=False))],
                                  temperature=0.8, max_tokens=None, trace_label='character.reply',
                                  mode='json', contract_id=contract_id, context_contract_id=context_contract_id)
        report = budget_report(plan.system_prompt, plan.user_prompt, options=budget_options, manifest=plan.prompt_manifest)
        if report['fits']:
            report['omitted'] = omitted
            report['world_context'] = final_world_report(world_report, sum('world_entry_id' in item for item in omitted))
            report['memory_context'] = final_report(memory_candidates, selected_ids, {e['entry_id'] for e in ledger})
            if context_contract_id == M3:
                report['source_recall'] = public_report(groups)
            return plan, evidence_messages(messages, recalled), {e['entry_id'] for e in ledger}, report
        if preferences:
            preferences.pop()
            omitted.append({'field': 'user_preferences'})
        elif entries:
            omitted.append({'world_entry_id': entries.pop()['id']})
        elif any(p['profile'].get('semantics') == 'role_fields_v1' and p['profile'].get('dialogue_examples') for p in participants):
            p = next(p for p in participants if p['profile'].get('semantics') == 'role_fields_v1' and p['profile'].get('dialogue_examples'))
            p['profile'].pop('dialogue_examples')
            omitted.append({'participant_id': p['instance_id'], 'field': 'dialogue_examples'})
        elif trim_group(groups):
            omitted.append({'field': 'recalled_sources'})
        elif len(turns) > 2:
            omitted.append({'turn_id': turns.pop(0)['turn_id']})
        elif ledger:
            omitted.append({'entry_id': ledger.pop()['entry_id']})
        else:
            raise CharacterSessionError('CONTEXT_LIMIT')
