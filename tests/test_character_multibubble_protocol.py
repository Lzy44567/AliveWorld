import copy
import json
import unittest
from uuid import uuid4

from core.character_chat.contract import parse_result
from core.character_chat.group_stream import GroupPreview
from core.character_chat.message_groups import resolve_local_sources
from core.character_chat.models import CharacterSessionError, create_session
from core.character_chat.protocol import V1, V2, V3, contract_for, attempt_contract
from core.character_chat.stream_json import ReplyPreview


def result(*bodies):
    return {'messages': [{'local_id': f'b{i}', 'text': body} for i, body in enumerate(bodies)],
            'ledger_ops': [], 'memory_annotations': []}


def visible(events):
    bodies = {}
    for event in events:
        if event['kind'] == 'preview_delta':
            bodies[event['ordinal']] = bodies.get(event['ordinal'], '') + event['text']
    return bodies


class MultibubbleProtocolTests(unittest.TestCase):
    def test_v3_exact_protocol_and_unchanged_default_contract(self):
        value = result('第一句', '第二句')
        self.assertEqual(value, parse_result(json.dumps(value), V3))
        for contract in (V1, V2):
            with self.assertRaises(CharacterSessionError):
                parse_result(json.dumps(value), contract)
        self.assertEqual(V1, attempt_contract({}))
        session = create_session(str(uuid4()), {'name': '合成', 'description': '合成人设'}, {'kind': 'character', 'key': 'synthetic'})
        self.assertEqual(V2, contract_for(session))

    def test_shape_local_identity_and_total_codepoint_limit(self):
        bad = [result(), result(*(['a'] * 7)), result(' '), result('x' * 4000, 'y' * 4001),
               dict(result('a'), reply='legacy'), dict(result('a'), hidden='private'),
               {'ledger_ops': [], **result('a')}]
        for messages in (None, {}, ['x'], [{'local_id': 'b1', 'text': 'x'}],
                         [{'local_id': 'b0', 'text': 1}], [{'local_id': 'b0', 'text': 'x', 'extra': 1}],
                         [{'local_id': 'b0', 'text': 'x'}, {'local_id': 'b0', 'text': 'y'}]):
            bad.append(dict(result('a'), messages=messages))
        for value in bad:
            with self.subTest(value=str(value)[:100]), self.assertRaises(CharacterSessionError):
                parse_result(json.dumps(value), V3)
        self.assertEqual(2, len(parse_result(json.dumps(result('🙂' * 4000, '🙂' * 4000), ensure_ascii=False), V3)['messages']))

    def test_final_duplicate_unknown_unicode_truncation_and_nonfinite(self):
        raw = json.dumps(result('x'))
        bad = [raw[:-1], raw + 'tail', raw.replace('"text": "x"', '"text":"x","text":"y"'),
               raw.replace('"local_id": "b0"', '"local_id":"b0","local_id":"b0"'),
               raw.replace('"x"', '"\\ud800"'), raw.replace('"ledger_ops": []', '"ledger_ops":[NaN]'),
               raw.replace('"ledger_ops": []', '"ledger_ops":[1e999]')]
        for body in bad:
            with self.subTest(body=body), self.assertRaises(CharacterSessionError):
                parse_result(body, V3)

    def test_local_sources_only_map_identity_and_leave_input_untouched(self):
        value = result('b0是我说的内容', '晚安')
        value['ledger_ops'] = [{'source': {'message_ids': ['b0', 'formal-id'],
                                         'evidence': [{'message_id': 'b0', 'quote': 'b0是我说的内容'}]},
                                'content': 'b0不得被替换'}]
        before = copy.deepcopy(value)
        ids = [str(uuid4()) for _ in range(6)]
        resolved, mapping = resolve_local_sources(value, ids)
        self.assertEqual(before, value)
        self.assertEqual({'b0': ids[0], 'b1': ids[1]}, mapping)
        self.assertEqual([ids[0], 'formal-id'], resolved['ledger_ops'][0]['source']['message_ids'])
        self.assertEqual('b0是我说的内容', resolved['ledger_ops'][0]['source']['evidence'][0]['quote'])
        self.assertEqual('b0不得被替换', resolved['ledger_ops'][0]['content'])
        for bad_ids in ([], ids[:5], [ids[0]] * 6, ['not-uuid'] * 6):
            with self.assertRaises(CharacterSessionError):
                resolve_local_sources(value, bad_ids)
        for ref in ('b2', 'b99', 'b00', None):
            bad = copy.deepcopy(value)
            bad['ledger_ops'][0]['source']['message_ids'] = [ref]
            with self.assertRaises(CharacterSessionError):
                resolve_local_sources(bad, ids)


class MultibubbleLexerTests(unittest.TestCase):
    def test_every_split_and_single_character_chunks(self):
        value = result('中\n文"反斜\\🙂', '第二条\t来了', '第三条')
        raw = json.dumps(value, ensure_ascii=True)
        expected = {i: m['text'] for i, m in enumerate(value['messages'])}
        for split in range(len(raw) + 1):
            events = []
            lexer = GroupPreview(events.append)
            lexer.feed(raw[:split]); lexer.feed(raw[split:])
            self.assertTrue(lexer.complete)
            self.assertEqual(expected, visible(events), split)
            self.assertEqual([0, 1, 2], [e['ordinal'] for e in events if e['kind'] == 'preview_start'])
            self.assertEqual([0, 1, 2], [e['ordinal'] for e in events if e['kind'] == 'preview_end'])
        events = []
        lexer = GroupPreview(events.append)
        for char in raw:
            lexer.feed(char)
        self.assertEqual(expected, visible(events))

    def test_first_and_later_preview_before_whole_json_arrives(self):
        events = []
        lexer = GroupPreview(events.append)
        lexer.feed('{"messages":[{"local_id":"b0","text":"你')
        self.assertEqual({0: '你'}, visible(events))
        self.assertFalse(lexer.complete)
        lexer.feed('好"},{"local_id":"b1","text":"第二')
        self.assertEqual({0: '你好', 1: '第二'}, visible(events))
        self.assertFalse(lexer.complete)
        lexer.feed('句"}],"ledger_ops":[],"memory_annotations":[]}')
        self.assertTrue(lexer.complete)
        self.assertEqual({0: '你好', 1: '第二句'}, visible(events))

    def test_private_same_name_paths_never_visible_even_with_nested_messages(self):
        value = result('公开')
        value['ledger_ops'] = [{'text': 'PRIVATE', 'content': 'SECRET',
                                'source': {'evidence': [{'text': 'HIDDEN', 'quote': 'PRIVATE'}],
                                           'messages': [{'text': 'LEAK'}]}}]
        value['memory_annotations'] = [{'messages': [{'text': 'NEVER'}]}]
        events = []
        GroupPreview(events.append).feed(json.dumps(value))
        self.assertEqual({0: '公开'}, visible(events))
        self.assertEqual(['preview_start', 'preview_delta', 'preview_end'], [e['kind'] for e in events])
        # Lexical preview is not a source/ledger validator.
        with self.assertRaises(CharacterSessionError):
            parse_result(json.dumps(value), V3)

    def test_lexer_fails_closed_for_grammar_depth_size_and_type(self):
        bad = ['[]', '{"private":0}', '{"ledger_ops":[]}',
               '{"messages":3}', '{"messages":[3]}', '{"messages":[{"text":3}]}',
               '{"messages":[{"local_id":"b0","text":"x","text":"y"}]}',
               '{"messages":[{"local_id":"b0","text":"x","private":"y"}]}',
               '{"messages":[{"local_id":"b0","text":"\\ud83dX"}]}',
               '{"messages":[{"local_id":"b0","text":"\\udc00"}]}',
               '{"messages":[{"local_id":"b0","text":"x"},]}',
               '{"messages":[{"local_id":"b0","text":"x"}],}',
               '{"messages":[{"local_id":"b0","text":"x" "local_id":"b0"}]}',
               json.dumps(result(*(['x'] * 7))), json.dumps(result('x' * 8001)),
               json.dumps(result('x' * 4000, 'y' * 4001)),
               '{"messages":[],"ledger_ops":' + '[' * 13 + '0' + ']' * 13 + '}',
               '{"messages":[],"ledger_ops":["' + 'x' * 65536 + '"]}',
               json.dumps(result('x')) + 'false']
        for raw in bad:
            with self.subTest(body=raw[:90]), self.assertRaises(CharacterSessionError):
                GroupPreview(lambda _: None).feed(raw)

    def test_bad_final_ledger_cannot_become_formal_from_preview(self):
        value = result('可见但未保存')
        value['memory_annotations'] = [{'op_index': 0, 'reason': 'invalid'}]
        events = []
        GroupPreview(events.append).feed(json.dumps(value))
        self.assertEqual({0: '可见但未保存'}, visible(events))
        with self.assertRaises(CharacterSessionError):
            parse_result(json.dumps(value), V3)

    def test_legacy_preview_remains_string_callback(self):
        for protocol in (V1, V2):
            events = []
            value = {'reply': '旧回复', 'ledger_ops': []}
            if protocol == V2:
                value['memory_annotations'] = []
            ReplyPreview(events.append, protocol).feed(json.dumps(value))
            self.assertEqual('旧回复', ''.join(events))


if __name__ == '__main__':
    unittest.main()
