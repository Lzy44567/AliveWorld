import copy
import tempfile
import unittest

from core.game_session import GameSession
from core.npc_identity import NpcIdentityError
from core.settlement_contract import validate_settlement, SettlementContractError
from core.state_manager import StateManager
from tests.test_effect_progress import SequenceAI


def identity(name, **fields):
    return {'name': name, 'reason': '本回合明确介绍或出入场', **fields}


def rename():
    return {'story_text': '看守介绍自己叫阿林。', 'npc_states': {'阿林': '在门口'},
            'npc_identity_updates': [identity('阿林', previous_name='看守', present=True)]}


class NpcIdentityTests(unittest.TestCase):
    def setUp(self):
        self.manager = StateManager()
        self.manager.apply_updates({'npc_states': {'看守': '在门口'}}, story_text='看守在门口')
        self.ident = self.manager.npc_presence.identities.by_name('看守')['id']

    def apply(self, payload):
        self.manager.apply_updates(payload, story_text=payload.get('story_text', ''))

    def test_rename_leave_mention_return_preserves_identity(self):
        self.apply(rename())
        self.assertEqual(self.manager.state['npcs'], {'阿林': '在门口'})
        self.apply({'npc_identity_updates': [identity('阿林', present=False)]})
        self.apply({'npc_states': {'看守': '在门口'}, 'story_text': '我想起看守。'})
        self.assertEqual(self.manager.state['npcs'], {})
        self.apply({'npc_states': {'阿林': '害怕死亡，但仍在场'},
                    'npc_identity_updates': [identity('阿林', id=self.ident, present=True)]})
        self.assertEqual(list(self.manager.state['npcs']), ['阿林'])
        record = self.manager.npc_presence.identities.by_name('看守')
        self.assertEqual(record['id'], self.ident)
        self.assertEqual(record['aliases'], ['看守'])
        self.assertEqual(record['last_status'], '害怕死亡，但仍在场')
        self.apply({'story_text': '阿林继续交谈。'})
        self.assertEqual(list(self.manager.state['npcs']), ['阿林'])

    def test_conflicts_are_atomic(self):
        self.apply({'npc_states': {'阿林': '另一人'}, 'story_text': '看守和阿林交谈'})
        other = self.manager.npc_presence.identities.by_name('阿林')['id']
        invalid = [rename(),
                   {'npc_identity_updates': [identity('看守', id='unknown')]},
                   {'npc_identity_updates': [identity('看守', id=other, previous_name='看守')]},
                   {'npc_identity_updates': [identity('看守'), identity('看守')]},
                   {'npc_identity_updates': [identity('新名', previous_name='看守')], 'status_deletions': ['看守']},
                   {'npc_identity_updates': [identity('新名', previous_name='看守')],
                    'npc_states': {'看守': 'A', '新名': 'B'}},
                   {'npc_identity_updates': [identity('看守', present=True)]}]
        before = copy.deepcopy((self.manager.state, self.manager.export_metadata()))
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(NpcIdentityError):
                self.apply({**payload, 'status_updates': {'身体': '不可落盘'}})
            self.assertEqual((self.manager.state, self.manager.export_metadata()), before)

    def test_old_alias_property_deletion_does_not_hide_current_person(self):
        self.apply(rename())
        self.apply({'status_deletions': ['看守'], 'story_text': '阿林留在原地'})
        self.assertTrue(self.manager.npc_presence.identities.by_name('阿林')['present'])

    def test_metadata_roundtrip_and_bounded_context(self):
        self.apply(rename())
        self.apply({'npc_identity_updates': [identity('阿林', present=False)]})
        restored = StateManager()
        restored.state = copy.deepcopy(self.manager.state)
        restored.load_metadata(self.manager.export_metadata())
        self.assertEqual(restored.npc_identity_context('查看房间'), [])
        context = restored.npc_identity_context('想起看守')
        self.assertEqual(context[0]['id'], self.ident)
        self.assertEqual(set(context[0]), {'id', 'name', 'aliases', 'present'})
        separate = StateManager()
        separate.apply_updates({'npc_states': {'看守': '在门口'}})
        self.assertNotEqual(separate.npc_presence.identities.by_name('看守')['id'], self.ident)

    def test_model_boundary_validation(self):
        for operations in ('bad', [{'name': 'A'}], [identity('A', present='false')], [identity('A', unknown=1)]):
            with self.assertRaises(SettlementContractError):
                validate_settlement({'story_text': '继续', 'npc_identity_updates': operations})

    def test_session_save_load_reroll_and_undo(self):
        future = {'reactions': [{'description': '介绍身份', 'weight': 1}]}
        ai = SequenceAI([future, rename(), rename(), {'story_text': '坏更新',
                         'npc_identity_updates': [identity('阿林', id='invalid')]}])
        with tempfile.TemporaryDirectory() as path:
            session = GameSession(ai, '人物测试', path, {'entitiesEnabled': False,
                'worldbookCaptureEnabled': False, 'learnUserPreferences': False, 'autoCompressMemory': False})
            session.state_mgr = self.manager
            result = session.process_turn('请看守介绍自己')
            self.assertFalse(result.get('error'), result)
            self.assertIn(self.ident, ai.requests[1][1])
            result = session.reroll_turn()
            self.assertFalse(result.get('error'), result)
            before = copy.deepcopy(session.export_save_data())
            self.assertTrue(session.reroll_turn()['error'])
            self.assertEqual(session.state_mgr.export_metadata(), before['state_meta'])
            loaded = GameSession(ai, '人物测试', path, {})
            loaded.load_save_data(before, save_dir_path=path)
            self.assertEqual(loaded.state_mgr.npc_presence.identities.by_name('阿林')['id'], self.ident)
            self.assertTrue(loaded.rollback())
            self.assertEqual(loaded.state['npcs'], {'看守': '在门口'})
            self.assertEqual(loaded.state_mgr.npc_presence.identities.by_name('看守')['id'], self.ident)


if __name__ == '__main__':
    unittest.main()
