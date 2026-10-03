"""B2 synthetic structure authority, cross-entry CAS and publication recovery."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import yaml
from core.asset_workshop import AssetWorkshop, AssetWorkshopError, asset_revision, normalize_asset
from core.asset_workshop_agent import AssetWorkshopAgent
from core.character_asset_write import CharacterWriteError, character_revision, write_character
from core.character_profiles import coordinate_character_write
from api.v1.streaming import workshop_chat_transaction
from tests.test_asset_workshop import FakeEngine
from tests.test_character_card_semantics import card, fields


class CharacterFieldsEditingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.path = self.root / 'card.yml'
        self.original = card(); self.path.write_text(yaml.safe_dump(self.original, allow_unicode=True), encoding='utf-8')
        self.workshop = AssetWorkshop('b2', 'characters', self.path, self.original)

    def read(self):
        return yaml.safe_load(self.path.read_text(encoding='utf-8'))

    def test_old_workshop_revision_upgrades_only_for_unchanged_target(self):
        data = self.workshop.to_dict(); data.pop('revision_kind')
        data['source_revision'] = asset_revision(normalize_asset('characters', self.original))
        restored = AssetWorkshop.from_dict(data)
        self.assertEqual(character_revision(self.original), restored.source_revision)
        changed = {**self.original, 'tags': ['changed']}
        self.path.write_text(yaml.safe_dump(changed), encoding='utf-8')
        conflicting = AssetWorkshop.from_dict(data)
        self.assertEqual(data['source_revision'], conflicting.source_revision)
        with self.assertRaisesRegex(AssetWorkshopError, '已更新'):
            conflicting.publish(self.root / 'sessions')

    def test_structured_edit_revision_and_metadata_merge_source_preserved(self):
        revised = copy.deepcopy(self.original['role_fields']); revised['dialogue_examples'] = '新行为示例'
        before = self.path.read_bytes()
        with self.assertRaisesRegex(CharacterWriteError, 'ASSET_REVISION_REQUIRED'):
            write_character(self.path, {'role_fields': revised})
        self.assertEqual(before, self.path.read_bytes())
        result = write_character(self.path, {'role_fields': revised}, expected_revision=character_revision(self.original))
        for key in revised:
            if key != 'dialogue_examples': self.assertEqual(self.original['role_fields'][key], result['role_fields'][key])
        self.assertEqual(self.original['_external_import'], result['_external_import'])
        with self.assertRaisesRegex(CharacterWriteError, 'ASSET_REVISION_CONFLICT'):
            write_character(self.path, {'tags': ['stale']}, expected_revision=character_revision(self.original))
        result = write_character(self.path, {'tags': ['current']})
        self.assertEqual(revised, result['role_fields'])

    def test_ai_authority_matches_prompt_and_preserves_unmodified_fields(self):
        changed = copy.deepcopy(self.original['role_fields']); changed['dialogue_examples'] = '情景：雨夜\n行为：递伞\n对白：慢一点。'
        engine = FakeEngine({'message': '提案', 'operations': [{'op': 'update_fields', 'changes': {'role_fields': changed}}]})
        AssetWorkshopAgent(engine).respond(self.workshop, '只改示例', 'refine', commit_changes=False)
        self.assertIn('【可编辑字段】role_fields, tags', engine.last_prompt)
        self.assertEqual(self.original['role_fields'], self.workshop.draft['role_fields'])
        self.workshop.apply_operations(self.workshop.proposed)
        self.assertEqual(changed, self.workshop.draft['role_fields'])
        self.workshop.undo(); self.assertEqual(self.original['role_fields'], self.workshop.draft['role_fields'])
        for changes in ({'description': 'old'}, {'role_fields': None}, {'role_fields': {**changed, 'version': 2}}, {'portrait': {}}):
            with self.subTest(changes=changes), self.assertRaises(AssetWorkshopError):
                self.workshop.apply_operations([{'op': 'update_fields', 'changes': changes}], actor='ai')

    def test_free_card_ai_cannot_upgrade_but_player_can(self):
        original = {'name': '合成', 'description': '人设', 'starting_scene': '旧情景'}
        workshop = AssetWorkshop('free', 'characters', self.path, original)
        proposed = fields(description='人设', scenario='旧情景', first_message='')
        with self.assertRaises(AssetWorkshopError): workshop.apply_operations([{'op': 'update_fields', 'changes': {'role_fields': proposed}}], actor='ai')
        workshop.apply_operations([{'op': 'update_fields', 'changes': {'role_fields': proposed}}])
        self.assertEqual('', workshop.draft['starting_scene']); self.assertIn('旧情景', workshop.draft['description'])
        workshop.apply_operations([{'op': 'update_fields', 'changes': {'role_fields': None}}])
        self.assertIsNone(workshop.draft['role_fields'])

    def test_invalid_later_operation_leaves_entire_batch_untouched(self):
        before = copy.deepcopy(self.workshop.to_dict())
        with self.assertRaises(AssetWorkshopError):
            self.workshop.apply_operations([{'op': 'update_fields', 'changes': {'tags': ['new']}},
                                           {'op': 'update_fields', 'changes': {'role_fields': {}}}])
        self.assertEqual(before, self.workshop.to_dict())

    def test_draft_save_failure_preserves_memory_and_file(self):
        before = copy.deepcopy(self.workshop.to_dict())
        with patch.object(AssetWorkshop, 'save_session', side_effect=OSError('synthetic')):
            with self.assertRaises(OSError):
                workshop_chat_transaction(self.workshop, self.root, lambda candidate: candidate.apply_operations([{'op': 'update_fields', 'changes': {'tags': ['new']}}]))
        self.assertEqual(before, self.workshop.to_dict()); self.assertEqual(self.original, self.read())

    def test_two_workshops_and_editor_share_conflict_boundary(self):
        other = AssetWorkshop('other', 'characters', self.path, self.original)
        self.workshop.apply_operations([{'op': 'update_fields', 'changes': {'tags': ['first']}}]); self.workshop.publish(self.root / 'drafts')
        other.apply_operations([{'op': 'update_fields', 'changes': {'tags': ['second']}}])
        with self.assertRaises(AssetWorkshopError): other.publish(self.root / 'drafts')
        with self.assertRaises(CharacterWriteError): write_character(self.path, {'role_fields': fields()}, expected_revision=character_revision(self.original))
        self.assertEqual(['first'], self.read()['tags'])

    def test_target_replace_failure_then_recovery_allows_safe_retry(self):
        self.workshop.apply_operations([{'op': 'update_fields', 'changes': {'tags': ['new']}}])
        directory = self.root / 'drafts'
        with patch('core.asset_workshop.save_yaml_atomic', side_effect=OSError('synthetic')):
            with self.assertRaises(OSError): self.workshop.publish(directory)
        self.assertEqual(self.original, self.read())
        restored = AssetWorkshop.from_dict(json.loads((directory / 'b2.json').read_text(encoding='utf-8')))
        restored.recover_publication(directory); self.assertIsNone(restored.publication_intent)
        restored.publish(directory); self.assertEqual(['new'], self.read()['tags'])

    def test_final_session_save_failure_recovers_without_rewriting_target(self):
        self.workshop.apply_operations([{'op': 'update_fields', 'changes': {'tags': ['new']}}])
        directory = self.root / 'drafts'; original_save = AssetWorkshop.save_session; calls = []
        def save(instance, target):
            calls.append(1)
            if len(calls) == 2: raise OSError('final receipt failed')
            return original_save(instance, target)
        with patch.object(AssetWorkshop, 'save_session', save):
            with self.assertRaises(OSError): self.workshop.publish(directory)
        self.assertFalse(self.workshop.published); self.assertTrue(self.workshop.publication_intent)
        before = self.path.read_bytes()
        restored = AssetWorkshop.from_dict(json.loads((directory / 'b2.json').read_text(encoding='utf-8')))
        with patch('core.asset_workshop.save_yaml_atomic', side_effect=AssertionError('must not rewrite')):
            restored.recover_publication(directory)
        self.assertTrue(restored.published); self.assertIsNone(restored.publication_intent)
        self.assertEqual(before, self.path.read_bytes())

    def test_recovery_conflict_keeps_intent_and_external_asset(self):
        self.workshop.publication_intent = {'target_path': str(self.path.resolve()), 'base_revision': 'other', 'output_hash': 'other'}
        before = copy.deepcopy(self.workshop.to_dict()); file_before = self.path.read_bytes()
        with self.assertRaises(AssetWorkshopError): self.workshop.recover_publication(self.root)
        self.assertEqual(before, self.workshop.to_dict()); self.assertEqual(file_before, self.path.read_bytes())

    def test_shared_target_gate_blocks_editor_without_mutation(self):
        from core.character_asset_write import character_write_guard
        before = self.path.read_bytes()
        with character_write_guard(self.path):
            with self.assertRaisesRegex(CharacterWriteError, 'ASSET_BUSY'): write_character(self.path, {'tags': ['new']})
        self.assertEqual(before, self.path.read_bytes())
