import asyncio
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import yaml
from core.character_profiles import (CharacterProfileError, compatibility_fields,
    coordinate_character_write, validate_role_fields)
from core.external_formats.adapters import adapt_character_card
from core.external_formats import ExternalFormatError
from core.character_chat.models import create_session, profile_projection, CharacterSessionError, validate_session
from core.character_chat.repository import CharacterSessionRepository
from core.character_chat.context import build_context
from core.character_chat.service import CharacterChatService, session_view
from core.asset_workshop import AssetWorkshop, AssetWorkshopError
from tests.test_character_chat_lifecycle import FakeTransport


def fields(**changes):
    return {'version': 1, 'description': '谨慎守约的修复师', 'personality': '保留自己的利益与判断',
            'scenario': '刚到车站，尚未相识', 'dialogue_examples': '样例：玩家已承诺交出秘密【非历史哨兵】',
            'first_message': '【作者开场哨兵】你已拥抱我', **changes}


def card(**changes):
    value = fields(**changes)
    desc, scene = compatibility_fields(value)
    return {'name': '合成修复师', 'description': desc, 'starting_scene': scene, 'role_fields': value,
            '_external_import': {'source': {'system_prompt': '【外部系统哨兵】', 'extensions': {'script': '【脚本哨兵】'}}}}


def pending():
    return {'content': '你好', 'mode': 'messenger', 'user_message_id': str(uuid4()), 'ai_message_id': str(uuid4())}


class CharacterSemanticsTests(unittest.TestCase):
    def session(self, profile=None):
        return create_session(str(uuid4()), profile or card(), {'kind': 'character', 'key': '合成卡'})

    def test_external_versions_empty_fields_and_source_preserved(self):
        for spec in (None, 'chara_card_v2', 'chara_card_v3'):
            data = {'name': '合成卡', 'description': '人设', 'personality': '性格', 'scenario': '场景',
                    'mes_example': '示例', 'first_mes': '开场', 'system_prompt': '仅保留'}
            source = {'spec': spec, 'data': data} if spec else data
            preview = adapt_character_card(source)
            self.assertEqual(source, preview.mapped_asset['_external_import']['source'])
            self.assertEqual('示例', preview.mapped_asset['role_fields']['dialogue_examples'])
            self.assertIn('非历史', ' '.join(preview.mapped_fields))
        empty = adapt_character_card({'name': '简单', 'description': '普通自由描述'}).mapped_asset
        self.assertEqual('', empty['role_fields']['personality'])

    def test_strict_fields_versions_unicode_limits_and_no_truncation(self):
        for bad in (fields(version=True), fields(version=2), fields(personality=[]),
                    fields(extra='unknown'), {'version': 1}, fields(description='中' * 16001),
                    fields(description='中' * 16000, personality='中' * 8000, scenario='中' * 8000)):
            with self.subTest(bad_type=type(bad)), self.assertRaises(CharacterProfileError):
                validate_role_fields(bad)
        self.assertEqual('😀', validate_role_fields(fields(description='😀'))['description'])
        with self.assertRaises(ExternalFormatError):
            adapt_character_card({'name': '非法', 'description': ['not text']})

    def test_projection_whitelist_and_no_opening_duplicate(self):
        value = self.session(); ai = value['participants'][1]
        self.assertEqual('role_fields_v1', ai['profile_semantics'])
        profile = profile_projection(ai)
        self.assertEqual({'name', 'semantics', 'description', 'personality', 'scenario', 'dialogue_examples'}, set(profile))
        plan, messages, entries, _ = build_context(value, pending())
        data = json.loads(plan.user_prompt)
        self.assertEqual([], data['history']); self.assertEqual([], messages); self.assertEqual(set(), entries)
        self.assertNotIn('【作者开场哨兵】', plan.user_prompt)
        self.assertNotIn('【性格】', plan.user_prompt)
        self.assertNotIn('【外部系统哨兵】', plan.system_prompt + plan.user_prompt)
        self.assertNotIn('【脚本哨兵】', plan.user_prompt)
        self.assertIn('【作者开场哨兵】', json.dumps(session_view(value), ensure_ascii=False))

    def test_old_unmarked_snapshot_keeps_legacy_even_with_invalid_extension(self):
        value = self.session()
        for p in value['participants']:
            p.pop('profile_semantics')
        value['participants'][1]['profile_snapshot']['role_fields'] = {'version': 999}
        validate_session(value)
        self.assertEqual({'name', 'description', 'starting_scene'}, set(profile_projection(value['participants'][1])))
        with tempfile.TemporaryDirectory() as temp:
            repo = CharacterSessionRepository(temp); repo.create(value)
            path = Path(temp) / (value['session_id'] + '.json'); before = path.read_bytes()
            session_view(repo.load(value['session_id']))
            self.assertEqual(before, path.read_bytes())

    def test_legacy_mixed_participants_and_unknown_marker_fail_safe(self):
        mixed = create_session(str(uuid4()), card(), {'kind': 'character', 'key': 'AI'},
                               user_profile={'name': '玩家', 'description': '自由文本'},
                               user_asset_ref={'kind': 'character', 'key': '玩家'})
        validate_session(mixed)
        self.assertEqual(['legacy', 'role_fields_v1'], [p['profile_semantics'] for p in mixed['participants']])
        value = self.session({'name': '原生', 'description': '自由文本'})
        self.assertEqual('legacy', value['participants'][1]['profile_semantics'])
        self.assertEqual({'name', 'description', 'starting_scene'}, set(profile_projection(value['participants'][1])))
        value['participants'][1]['profile_semantics'] = 'future'
        with self.assertRaises(CharacterSessionError):
            validate_session(value)
        with self.assertRaises(CharacterSessionError):
            self.session(card(version=9))

    def test_optional_example_removed_whole_before_history(self):
        value = self.session(card(dialogue_examples='中' * 7000))
        plan, _, _, report = build_context(value, pending(), {'context_window': 8192, 'output_reserve': 4096})
        profile = json.loads(plan.user_prompt)['participants'][1]['profile']
        self.assertNotIn('dialogue_examples', profile)
        self.assertEqual('保留自己的利益与判断', profile['personality'])
        self.assertEqual('dialogue_examples', report['omitted'][0]['field'])
        self.assertNotIn('中', json.dumps(report['omitted']))
        self.assertEqual(7000, len(value['participants'][1]['profile_snapshot']['role_fields']['dialogue_examples']))

    def test_write_authority_tags_tombstone_and_source(self):
        original = card()
        self.assertEqual(original['role_fields'], coordinate_character_write(original, {'tags': ['新标签']})['role_fields'])
        self.assertEqual(original['role_fields'], coordinate_character_write(original, {'description': original['description']})['role_fields'])
        edited = coordinate_character_write(original, {'description': '新自由文本', '_external_import': {'source': 'spoof'}})
        self.assertIsNone(edited['role_fields']); self.assertEqual(original['_external_import'], edited['_external_import'])
        structured = coordinate_character_write(original, {'role_fields': fields(description='新结构'), 'description': '过期描述'})
        self.assertTrue(structured['description'].startswith('新结构'))
        self.assertIsNone(coordinate_character_write(original, {'role_fields': None})['role_fields'])

    def test_workshop_downgrade_undo_and_stale_structure_conflict(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'card.yml'; original = card(); path.write_text(yaml.safe_dump(original, allow_unicode=True), encoding='utf-8')
            workshop = AssetWorkshop('test', 'characters', path, original)
            workshop.apply_operations([{'op': 'update_fields', 'changes': {'description': 'AI新描述'}}], actor='ai')
            self.assertIsNone(workshop.draft['role_fields']); workshop.undo()
            self.assertEqual(original['role_fields'], workshop.draft['role_fields'])
            workshop.apply_operations([{'op': 'update_fields', 'changes': {'description': '新描述'}}])
            workshop.publish(); saved = yaml.safe_load(path.read_text(encoding='utf-8'))
            self.assertIsNone(saved['role_fields']); self.assertEqual(original['_external_import'], saved['_external_import'])
            path.write_text(yaml.safe_dump(original, allow_unicode=True), encoding='utf-8')
            stale = AssetWorkshop('stale', 'characters', path, original)
            altered = coordinate_character_write(original, {'role_fields': fields(personality='新性格')})
            path.write_text(yaml.safe_dump(altered, allow_unicode=True), encoding='utf-8')
            with self.assertRaises(AssetWorkshopError): stale.publish()

    def test_atomic_failure_preserves_old_card(self):
        from utils.atomic_yaml import save_yaml_atomic
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'card.yml'; save_yaml_atomic(path, card()); before = path.read_bytes()
            with patch('utils.atomic_yaml.os.replace', side_effect=OSError('synthetic')):
                with self.assertRaises(OSError): save_yaml_atomic(path, {'name': 'changed'})
            self.assertEqual(before, path.read_bytes()); self.assertEqual([], list(Path(temp).glob('*.tmp')))

    def test_quality_fixtures_preserve_profiles_without_claiming_model_quality(self):
        fixture = json.loads((Path(__file__).parent / 'fixtures' / 'character_quality_i1.json').read_text(encoding='utf-8'))
        self.assertEqual(6, len(fixture['cases']))
        for role in fixture['roles']:
            for structured in (False, True):
                for mode in ('messenger', 'roleplay'):
                    profile = card(**{key: fixture[key] for key in ('scenario', 'dialogue_examples', 'first_message')},
                                   description=role['description'], personality=role['personality'])
                    profile['name'] = role['name']
                    if not structured: profile.pop('role_fields')
                    session = create_session(str(uuid4()), profile, {'kind': 'character', 'key': role['name']}, presentation_mode=mode)
                    for case in fixture['cases']:
                        request = {**pending(), 'content': case['input'], 'mode': mode}
                        plan, _, _, _ = build_context(session, request, {})
                        payload = json.loads(plan.user_prompt)
                        sent = payload['participants'][1]['profile']
                        self.assertIn(role['description'], sent['description'])
                        self.assertIn(role['personality'], json.dumps(sent, ensure_ascii=False))
                        self.assertEqual([], session['turns'])
                        self.assertEqual([], session['ledger'])
                        if structured:
                            self.assertNotIn('first_message', sent)
                            self.assertEqual(fixture['dialogue_examples'], sent['dialogue_examples'])

    def test_workshop_tags_and_undo_publish_preserve_structure(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'card.yml'; original = card()
            path.write_text(yaml.safe_dump(original, allow_unicode=True), encoding='utf-8')
            workshop = AssetWorkshop('tags', 'characters', path, original)
            workshop.apply_operations([{'op': 'update_fields', 'changes': {'tags': ['合成']}}])
            workshop.publish()
            self.assertEqual(original['role_fields'], yaml.safe_load(path.read_text(encoding='utf-8'))['role_fields'])
            workshop = AssetWorkshop('undo', 'characters', path, yaml.safe_load(path.read_text(encoding='utf-8')))
            workshop.apply_operations([{'op': 'update_fields', 'changes': {'description': '临时修改'}}])
            workshop.undo(); workshop.publish()
            saved = yaml.safe_load(path.read_text(encoding='utf-8'))
            self.assertEqual(original['role_fields'], saved['role_fields'])
            self.assertEqual(original['_external_import'], saved['_external_import'])

    def test_global_and_local_legacy_edit_entrypoints(self):
        from api.v1 import lobby_routes, local_asset_routes
        from core.session_manager import active_sessions
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); directory = root / 'characters'; directory.mkdir(); path = directory / '合成卡.yml'
            path.write_text(yaml.safe_dump(card(), allow_unicode=True), encoding='utf-8')
            with patch.object(lobby_routes, 'resolve_asset_path', return_value=path), patch.object(lobby_routes, 'resolve_template_path', return_value=None):
                asyncio.run(lobby_routes.save_asset('characters', '合成卡', lobby_routes.AssetPayload(parsed_data={'description': '全局新文本'}, overwrite=True)))
            self.assertIsNone(yaml.safe_load(path.read_text(encoding='utf-8'))['role_fields'])
            path.write_text(yaml.safe_dump(card(), allow_unicode=True), encoding='utf-8')
            active_sessions['i1-test'] = SimpleNamespace(save_dir_path=str(root))
            try:
                local_asset_routes.update_local_asset('i1-test', 'characters', '合成卡', local_asset_routes.LocalAssetUpdatePayload(parsed_data={'starting_scene': '局内新开场'}, overwrite=True))
                self.assertIsNone(yaml.safe_load(path.read_text(encoding='utf-8'))['role_fields'])
            finally: active_sessions.pop('i1-test', None)


class CharacterSemanticsLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_sample_cannot_become_ledger_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = CharacterSessionRepository(temp); value = repo.create(create_session(str(uuid4()), card(), {'kind': 'character', 'key': '合成卡'}))
            transport = FakeTransport(); service = CharacterChatService(repo, transport)
            ai, user = value['participants'][1]['instance_id'], value['participants'][0]['instance_id']
            transport.raw = json.dumps({'reply': '安全回复', 'ledger_ops': [{'op': 'add', 'kind': 'experience', 'content': '假的承诺',
                'source': {'type': 'dialogue_event', 'message_ids': ['00000000-0000-4000-8000-000000000001'], 'evidence': [{'message_id': '00000000-0000-4000-8000-000000000001', 'quote': '样例：玩家已承诺交出秘密【非历史哨兵】'}]},
                'visibility': {'audience_instance_ids': [ai, user]}}]}, ensure_ascii=False)
            started = service.begin(value['session_id'], {'client_action_id': str(uuid4()), 'operation': 'send', 'expected_revision': 0, 'content': '你好'})
            result = await service.execute(started['job']['request_id'], lambda *_: None)
            current = repo.load(value['session_id']); self.assertEqual([], current['turns']); self.assertEqual([], current['ledger']); self.assertEqual(1, transport.calls)

    async def test_required_persona_overflow_zero_call(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = CharacterSessionRepository(temp); value = repo.create(create_session(str(uuid4()), card(description='中' * 16000), {'kind': 'character', 'key': '合成卡'}))
            class Small(FakeTransport):
                def snapshot(self): return {'budget_options': {'context_window': 8192, 'output_reserve': 4096}}
            transport = Small(); service = CharacterChatService(repo, transport)
            with self.assertRaises(CharacterSessionError):
                service.begin(value['session_id'], {'client_action_id': str(uuid4()), 'operation': 'send', 'expected_revision': 0, 'content': '你好'})
            self.assertEqual(0, transport.calls); self.assertEqual([], repo.load(value['session_id'])['turns'])
