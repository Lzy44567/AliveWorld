"""Permission-first, bounded context construction with whole-entry trimming."""
import json
import re
from core.prompt_studio import compose_prompt, plan_model_request, RequestMessagePart
from core.request_budget import budget_report
from .models import CharacterSessionError, profile_projection
from .opening import opening_context
from .world_context import select_world_context, final_world_report


def build_context(session, pending, budget_options=None, *, preferences=None):
    preferences = [dict(item) for item in (preferences or [])]
    ai = next(p['instance_id'] for p in session['participants'] if p['controller'] == 'ai')
    participants = [{'instance_id': p['instance_id'], 'controller': p['controller'],
                     'profile': profile_projection(p)} for p in session['participants']]
    turns = session['turns'][-20:]
    visible = [e for e in session['ledger'] if e['status'] == 'active' and ai in e['visibility']['audience_instance_ids']]
    words = set(re.findall(r'\w+', pending['content'].casefold()))
    visible.sort(key=lambda e: (-sum(w in e['content'].casefold() for w in words), -next(
        (i for i, t in enumerate(session['turns']) if t['turn_id'] == e['created_turn_id']), -1), e['entry_id']))
    intents = 0
    ledger = []
    for entry in visible:
        if entry['kind'] == 'intent':
            intents += 1
            if intents > 8:
                continue
        ledger.append(entry)
        if len(ledger) == 32:
            break
    rules, entries, world_report = select_world_context(session, pending['content'])
    system = compose_prompt('character.reply', {'character.presentation_mode': pending['mode']})
    omitted = []
    while True:
        messages = [m for t in turns for m in (t['user_message'], t['ai_message'])
                    if ai in m['visibility']['audience_instance_ids']]
        data = {'participants': participants, 'world_rules': rules, 'world_related_entries': entries,
                'ledger': ledger, 'history': messages,
                'current_user_message': {'message_id': pending['user_message_id'], 'content': pending['content']},
                'current_ai_message_id': pending['ai_message_id'], 'presentation_mode': pending['mode']}
        if session.get('opening'):
            data['author_opening'] = opening_context(session['opening'])
        if preferences:
            data['user_preferences'] = preferences
        plan = plan_model_request(system, [RequestMessagePart('character.context', json.dumps(data, ensure_ascii=False))],
                                  temperature=0.8, max_tokens=None, trace_label='character.reply',
                                  mode='json', contract_id='character.reply.v1')
        report = budget_report(plan.system_prompt, plan.user_prompt, options=budget_options, manifest=plan.prompt_manifest)
        if report['fits']:
            report['omitted'] = omitted
            report['world_context'] = final_world_report(world_report, sum('world_entry_id' in item for item in omitted))
            return plan, messages, {e['entry_id'] for e in ledger}, report
        if preferences:
            preferences.pop()
            omitted.append({'field': 'user_preferences'})
        elif entries:
            omitted.append({'world_entry_id': entries.pop()['id']})
        elif any(p['profile'].get('semantics') == 'role_fields_v1' and p['profile'].get('dialogue_examples') for p in participants):
            p = next(p for p in participants if p['profile'].get('semantics') == 'role_fields_v1' and p['profile'].get('dialogue_examples'))
            p['profile'].pop('dialogue_examples')
            omitted.append({'participant_id': p['instance_id'], 'field': 'dialogue_examples'})
        elif len(turns) > 2:
            omitted.append({'turn_id': turns.pop(0)['turn_id']})
        elif ledger:
            omitted.append({'entry_id': ledger.pop()['entry_id']})
        else:
            raise CharacterSessionError('CONTEXT_LIMIT')
