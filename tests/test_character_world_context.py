"""C1 bounded public matching, safe metadata, budget and transport parity."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
from core.character_chat.context import build_context
from core.character_chat.models import create_session, CharacterSessionError
from core.character_chat.repository import CharacterSessionRepository
from core.character_chat.service import CharacterChatService
from core.character_chat.world_context import select_world_context, public_recent_messages
from core.worldbook import normalize_worldbook
from tests.test_character_chat_lifecycle import FakeTransport


def entry(key, **changes):
    return {'id': key, 'name': '条目' + key, 'keys': key, 'content': '设定' + key, 'tags': [], **changes}


def session(entries):
    value = create_session(str(uuid4()), {'name': '合成角色', 'description': '人设'}, {'kind': 'character', 'key': '合成角色'})
    value['world_binding'] = {'asset_ref': {'kind': 'worldbook', 'key': '合成世界'}, 'source_hash': 'a' * 64,
                              'snapshot': normalize_worldbook({'name': '合成世界', 'axioms': ['规则'], 'entries': entries})}
    return value


def turn(value, user, ai, private=False):
    audience = [p['instance_id'] for p in value['participants']]
    return {'turn_id': str(uuid4()), 'user_message': {'message_id': str(uuid4()), 'content': user, 'visibility': {'audience_instance_ids': audience}},
            'ai_message': {'message_id': str(uuid4()), 'content': ai, 'visibility': {'audience_instance_ids': audience[1:] if private else audience}}}


def pending(content='继续'):
    return {'content': content, 'mode': 'messenger', 'user_message_id': str(uuid4()), 'ai_message_id': str(uuid4())}


class CharacterWorldContextTests(unittest.TestCase):
    def test_current_then_recent_public_ai_and_user_stable_priority(self):
        value = session([entry('OLD'), entry('NEW'), entry('NOW')])
        value['turns'] = [turn(value, 'OLD', '无'), turn(value, '无', 'NEW')]
        before = json.dumps(value, ensure_ascii=False)
        _, selected, report = select_world_context(value, 'now')
        self.assertEqual(['NOW', 'NEW', 'OLD'], [e['id'] for e in selected])
        self.assertEqual([0, 1, 2], [e['turn_distance'] for e in report['entries']])
        self.assertEqual(before, json.dumps(value, ensure_ascii=False))

    def test_four_turn_window_excludes_private_archived_opening_and_ledger(self):
        value = session([entry(key) for key in ['OLDER', 'PRIVATE', 'ARCHIVE', 'OPENING', 'EXAMPLE', 'LEDGER']])
        value['turns'] = [turn(value, 'OLDER', '无')] + [turn(value, '无', 'PRIVATE', True) for _ in range(4)]
        value['archived_turns'] = [turn(value, 'ARCHIVE', '无')]
        value['opening'] = {'content': 'OPENING'}
        value['participants'][1]['profile_snapshot']['description'] = 'EXAMPLE'
        value['ledger'] = [{'content': 'LEDGER'}]
        self.assertEqual([], select_world_context(value, '继续')[1])

    def test_character_window_skips_whole_oversize_and_never_searches_older_turns(self):
        value = session([entry('GIANT'), entry('RECENT'), entry('OLDER')])
        value['turns'] = [turn(value, 'OLDER', '无')] + [turn(value, 'RECENT', 'GIANT' + '😀' * 12000) for _ in range(4)]
        messages = public_recent_messages(value)
        self.assertLessEqual(sum(len(text) for _, text in messages), 12000)
        self.assertEqual(['RECENT'], [e['id'] for e in select_world_context(value, '继续')[1]])

    def test_resident_disabled_pending_retired_comma_and_unicode_keys(self):
        value = session([entry('r', tags=['常驻']), entry('absolute', tags=['绝对规则']),
                         entry('off', is_active=False), entry('pending', tags=['待确认']), entry('retired', tags=['待删除']),
                         entry('unicode', keys='校园， ÄPFEL,😀')])
        rules, selected, report = select_world_context(value, 'off pending retired äpfel')
        self.assertEqual(['r', 'absolute'], [e['id'] for e in rules['entries']])
        self.assertEqual(['unicode'], [e['id'] for e in selected])
        self.assertEqual(2, report['resident_count'])

    def test_limit_preserves_current_match_over_earlier_book_positions(self):
        value = session([entry(f'e{i}', keys='RECENT') for i in range(25)] + [entry('last', keys='NOW')])
        value['turns'] = [turn(value, 'RECENT', '无')]
        _, selected, report = select_world_context(value, 'NOW')
        self.assertEqual(16, len(selected)); self.assertEqual('last', selected[0]['id'])
        self.assertEqual(10, report['omitted_by_limit'])

    def test_budget_report_matches_whole_entry_cuts_and_does_not_enter_prompt(self):
        value = session([entry('a', keys='NOW', content='正文秘密哨兵'), entry('b', keys='NOW')])
        def budget(_, user_prompt, **kwargs):
            return {'fits': len(json.loads(user_prompt)['world_related_entries']) <= 1}
        with patch('core.character_chat.context.budget_report', side_effect=budget):
            plan, messages, evidence, report = build_context(value, pending('NOW'))
        self.assertEqual(['a'], [e['id'] for e in json.loads(plan.user_prompt)['world_related_entries']])
        self.assertEqual([True, False], [e['planned'] for e in report['world_context']['entries']])
        self.assertEqual(1, report['world_context']['omitted_by_budget'])
        serialized = json.dumps(report['world_context'], ensure_ascii=False)
        self.assertNotIn('正文秘密哨兵', serialized); self.assertNotIn('NOW', serialized)
        self.assertNotIn('world_context', json.loads(plan.user_prompt))
        self.assertEqual([], messages); self.assertEqual(set(), evidence)

    def test_no_binding_and_empty_match_metadata(self):
        value = session([])
        self.assertEqual([], select_world_context(value, '继续')[2]['entries'])
        value['world_binding'] = None
        self.assertEqual((None, [], None), select_world_context(value, '继续'))


class CharacterWorldTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_transport_parity_and_undo_regenerate_exclude_withdrawn_keywords(self):
        with tempfile.TemporaryDirectory() as root:
            repo = CharacterSessionRepository(Path(root)); transport = FakeTransport(); service = CharacterChatService(repo, transport)
            value = repo.create(session([entry('月亮')]))
            sid = value['session_id']
            async def run(content=None, operation='send', target=None, delivery='stream'):
                payload = {'client_action_id': str(uuid4()), 'expected_revision': repo.load(sid)['revision'], 'operation': operation, 'delivery': delivery}
                if operation == 'send': payload['content'] = content
                else: payload['target_turn_id'] = target
                start = service.begin(sid, payload)
                if 'job' not in start: return start['existing']
                events = []; result = await service.execute(start['job']['request_id'], lambda name, data: events.append((name, data)))
                self.assertEqual(events[0][1]['world_context_report'], result['world_context_report'])
                return result
            transport.raw = json.dumps({'reply': '看月亮', 'ledger_ops': [], 'memory_annotations': []})
            await run('你好')
            transport.raw = None
            second = await run('继续', delivery='non_stream')
            self.assertEqual('recent', second['world_context_report']['entries'][0]['source'])
            last = repo.load(sid)['turns'][-1]['turn_id']
            await run(operation='undo', target=last)
            first = repo.load(sid)['turns'][-1]['turn_id']
            regenerate = await run(operation='regenerate', target=first)
            self.assertEqual([], regenerate['world_context_report']['entries'])
            after = await run('继续')
            self.assertEqual([], after['world_context_report']['entries'])
            self.assertEqual(4, transport.calls)

    async def test_required_overflow_fails_before_provider_and_keeps_history(self):
        with tempfile.TemporaryDirectory() as root:
            repo = CharacterSessionRepository(Path(root)); transport = FakeTransport(); service = CharacterChatService(repo, transport)
            value = repo.create(session([entry('resident', tags=['常驻'])])); sid = value['session_id']
            with patch('core.character_chat.context.budget_report', return_value={'fits': False}):
                with self.assertRaises(CharacterSessionError):
                    service.begin(sid, {'client_action_id': str(uuid4()), 'expected_revision': 0, 'operation': 'send', 'content': '继续', 'delivery': 'stream'})
            self.assertEqual(0, transport.calls); self.assertEqual([], repo.load(sid)['turns'])
