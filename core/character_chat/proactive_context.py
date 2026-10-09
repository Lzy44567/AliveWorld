"""Inputless contact planning over bounded, formal, visible conversation context."""
import copy
import json

from core.prompt_studio import compose_prompt, plan_model_request, RequestMessagePart
from core.request_budget import budget_report
from .models import CharacterSessionError, profile_projection
from .group_records import formal_messages
from .memory import select_memory, final_report
from .world_context import select_world_context, final_world_report
from .opening import opening_context
from .contract import parse_result, unique_object
from .protocol import V3

PLAN_CONTRACT = 'character.contact_plan.v1'
CONTEXT_CONTRACT = 'character.contact_context.v1'


def build_contact_context(session, max_contacts, max_delay_seconds, budget_options=None, *, preferences=None):
    ai = next(p['instance_id'] for p in session['participants'] if p['controller'] == 'ai')
    formal = formal_messages(session)
    batches = [g for g in session['groups'] if g['status'] in {'complete', 'partial_failed'}][-20:]
    participants = [{'instance_id': p['instance_id'], 'controller': p['controller'],
                     'profile': profile_projection(p)} for p in session['participants']]
    preferences = copy.deepcopy(preferences or [])
    query = '\n'.join(m['content'] for m in sorted(formal.values(), key=lambda m: m['seq'])[-12:])
    ledger, memory_candidates = select_memory(session, query)
    selected_ids = {e['entry_id'] for e in ledger}
    rules, entries, world_report = select_world_context(session, query)
    system = compose_prompt(PLAN_CONTRACT, {})
    omitted = []
    while True:
        ids = {mid for g in batches for mid in g['input_ids']} | {
            b['message']['message_id'] for g in batches for b in g['bubbles'][:g['delivered_count']]}
        messages = [copy.deepcopy(m) for m in sorted(formal.values(), key=lambda m: m['seq'])
                    if m['message_id'] in ids and ai in m['visibility']['audience_instance_ids']]
        data = {'reply_contract_id': PLAN_CONTRACT, 'context_contract_id': CONTEXT_CONTRACT,
                'participants': participants, 'world_rules': rules, 'world_related_entries': entries,
                'ledger': ledger, 'history': messages, 'presentation_mode': session['presentation_mode'],
                'max_contacts': max_contacts, 'max_delay_seconds': max_delay_seconds}
        if preferences:
            data['user_preferences'] = preferences
        if session.get('opening'):
            data['author_opening'] = opening_context(session['opening'])
        plan = plan_model_request(system, [RequestMessagePart('character.contact_context', json.dumps(data, ensure_ascii=False))],
                                  temperature=0.8, max_tokens=None, trace_label='character.contact', mode='json',
                                  contract_id=PLAN_CONTRACT, context_contract_id=CONTEXT_CONTRACT)
        report = budget_report(plan.system_prompt, plan.user_prompt, options=budget_options, manifest=plan.prompt_manifest)
        if report['fits']:
            report.update(omitted=omitted, world_context=final_world_report(world_report, sum('world_entry_id' in i for i in omitted)),
                          memory_context=final_report(memory_candidates, selected_ids, {e['entry_id'] for e in ledger}))
            return plan, {m['message_id'] for m in messages}, {e['entry_id'] for e in ledger}, report
        if preferences:
            preferences.pop(); omitted.append({'field': 'user_preferences'})
        elif entries:
            omitted.append({'world_entry_id': entries.pop()['id']})
        elif any(p['profile'].get('dialogue_examples') for p in participants):
            p = next(p for p in participants if p['profile'].get('dialogue_examples'))
            p['profile'].pop('dialogue_examples'); omitted.append({'participant_id': p['instance_id'], 'field': 'dialogue_examples'})
        elif len(batches) > 2:
            omitted.append({'group_id': batches.pop(0)['group_id']})
        elif ledger:
            omitted.append({'entry_id': ledger.pop()['entry_id']})
        else:
            raise CharacterSessionError('CONTEXT_LIMIT')


def parse_contact_plan(raw, max_contacts, max_delay_seconds):
    try:
        value = json.loads(raw, object_pairs_hook=unique_object, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(value, dict) or set(value) != {'contacts'} or not isinstance(value['contacts'], list):
            raise ValueError()
        contacts = value['contacts']
        if len(contacts) > max_contacts:
            raise ValueError()
        last, characters = -1, 0
        for contact in contacts:
            if not isinstance(contact, dict) or set(contact) != {'delay_seconds', 'reply'}:
                raise ValueError()
            delay = contact['delay_seconds']
            if type(delay) is not int or not 0 <= delay < max_delay_seconds or delay < last:
                raise ValueError()
            last = delay
            contact['reply'] = parse_result(json.dumps(contact['reply'], ensure_ascii=False), V3)
            characters += sum(len(m['text']) for m in contact['reply']['messages'])
        if characters > 8000:
            raise ValueError()
        return contacts
    except (ValueError, TypeError, KeyError, RecursionError):
        raise CharacterSessionError('CONTRACT_INVALID') from None
