"""C4-0 prompt assembly, not a claim of real-model conversational quality."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.character_chat.context import build_context
from core.character_chat.context_contract import C3, M3, LEGACY
from core.character_chat.contract import parse_result
from core.character_chat.models import CharacterSessionError
from core.character_chat.prompts import CONVERSATION_GUIDANCE
from core.character_chat.protocol import V1, V2
from core.prompt_studio import PromptOverrideStore, compose_prompt
from tests.test_character_memory import fixture, pending


class ConversationGuidanceTests(unittest.TestCase):
    def test_current_four_tasks_include_guidance_once_in_existing_core(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PromptOverrideStore(Path(directory) / 'overrides.json')
            for family in ('m3', 'c3'):
                for version in (1, 2):
                    task = f'character.reply.{family}.v{version}'
                    result = compose_prompt(task, {'character.presentation_mode': 'messenger'}, store=store)
                    self.assertEqual(1, result.text.count(CONVERSATION_GUIDANCE))
                    self.assertEqual(task + '.core', result.manifest[0]['sliceId'])
                    self.assertEqual('static', result.manifest[0]['cacheClass'])
                    self.assertEqual(4 if family == 'c3' else 3, len(result.manifest))

    def test_legacy_baselines_do_not_silently_gain_guidance(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PromptOverrideStore(Path(directory) / 'overrides.json')
            for task in ('character.reply', 'character.reply.v2'):
                self.assertNotIn(CONVERSATION_GUIDANCE, compose_prompt(
                    task, {'character.presentation_mode': 'roleplay'}, store=store).text)

    def test_explicit_core_override_remains_authoritative_and_contract_stays(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PromptOverrideStore(Path(directory) / 'overrides.json')
            for family in ('m3', 'c3'):
                task = f'character.reply.{family}.v2'
                store.save(task + '.core', 'AUTHOR_CORE')
                result = compose_prompt(task, {'character.presentation_mode': 'messenger'}, store=store)
                self.assertIn('AUTHOR_CORE', result.text)
                self.assertNotIn(CONVERSATION_GUIDANCE, result.text)
                self.assertIn('memory_annotations必填', result.text)
                if family == 'c3':
                    self.assertIn('current_ooc_note', result.text)

    def test_both_modes_and_versions_keep_input_and_evidence_projection_unchanged(self):
        for context in (M3, C3):
            for version in (V1, V2):
                for mode in ('messenger', 'roleplay'):
                    with self.subTest(context=context, version=version, mode=mode):
                        p = pending('coffee')
                        p['mode'] = mode
                        if context == C3:
                            p['ooc_note'] = 'CONTROL_ONLY'
                        value = fixture(25)
                        new = build_context(value, p, contract_id=version, context_contract_id=context)
                        with patch('core.prompt_studio.CONVERSATION_GUIDANCE', ''):
                            old = build_context(value, p, contract_id=version, context_contract_id=context)
                        self.assertEqual(old[0].user_prompt, new[0].user_prompt)
                        self.assertEqual(old[1:3], new[1:3])
                        self.assertEqual(version, new[0].contract_id)
                        self.assertEqual(context, new[0].context_contract_id)
                        self.assertEqual('character.reply', new[0].trace_label)
                        self.assertEqual(1, new[0].system_prompt.count(CONVERSATION_GUIDANCE))
                        self.assertNotIn('CONTROL_ONLY', json.dumps(new[1]))
                        self.assertNotEqual(old[0].prompt_manifest[0]['contentHash'], new[0].prompt_manifest[0]['contentHash'])

    def test_required_guidance_is_counted_by_budget_and_never_optional_trim(self):
        observed = []
        def insufficient(system, user, **kwargs):
            observed.append(system)
            return {'fits': False}
        with patch('core.character_chat.context.budget_report', side_effect=insufficient):
            with self.assertRaises(CharacterSessionError) as caught:
                build_context(fixture(0), pending('hello'))
        self.assertEqual('CONTEXT_LIMIT', caught.exception.code)
        self.assertTrue(observed)
        self.assertTrue(all(CONVERSATION_GUIDANCE in system for system in observed))

    def test_no_new_output_fields_or_multi_bubble_contract(self):
        for version in (V1, V2):
            value = {'reply': '先说到这里，等你回应。', 'ledger_ops': []}
            if version == V2:
                value['memory_annotations'] = []
            self.assertEqual(value, parse_result(json.dumps(value), version))
            for key in ('messages', 'delay', 'end', 'thoughts'):
                with self.assertRaises(CharacterSessionError):
                    parse_result(json.dumps(dict(value, **{key: []})), version)

    def test_core_cache_prefix_does_not_depend_on_player_input(self):
        first = build_context(fixture(0), pending('hello'))[0]
        second = build_context(fixture(0), pending('different input'))[0]
        self.assertEqual(first.prompt_manifest[0], second.prompt_manifest[0])
        self.assertNotEqual(first.user_prompt, second.user_prompt)
