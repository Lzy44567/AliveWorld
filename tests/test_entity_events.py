import json
import unittest
from unittest.mock import patch

from core.entities import Entity
from core.entity_events import classify_event
from core.undercurrent import UndercurrentEngine
from tests.test_entity_domain import FakeAIEngine


class EntityEventTests(unittest.TestCase):
    def run_event(self, kind):
        response = {
            'undercurrent_events': [{'entity': '商会', 'kind': kind, 'action': '明日运送药材',
                'basis': '商会收到订单，仓库有药材', 'known_to': ['商会'], 'status': '已送达'}],
            'new_influences': [{'summary': '药材运输', 'source_links': [{'entity': '商会'}],
                                'condition': '玩家到码头', 'effect': '遇见车队'}],
        }
        engine = UndercurrentEngine(FakeAIEngine(json.dumps(response, ensure_ascii=False)))
        engine.entities = [Entity('商会', status='尚未出发')]
        with patch('core.undercurrent.load_system_prompts', return_value={'overseer_prompt': '推演'}):
            engine.tick('玩家在旅馆', world_time='第一日')
        return engine

    def test_plan_does_not_execute_or_create_influence(self):
        engine = self.run_event('plan')
        self.assertEqual(engine.entities[0].plans, ['明日运送药材'])
        self.assertEqual(engine.entities[0].recent_actions, [])
        self.assertEqual(engine.entities[0].status, '尚未出发')
        self.assertEqual(engine.causal_ledger.export(), [])
        self.assertIn('计划，尚未执行', engine.get_ledger_context())

    def test_action_keeps_basis_time_knowledge_after_reload(self):
        engine = self.run_event('action')
        restored = UndercurrentEngine(FakeAIEngine('{}'))
        restored.load_state(engine.export_state())
        record = restored.ledger.entries[0]
        self.assertEqual(record.details['entity_id'], restored.entities[0].id)
        self.assertEqual(record.details['world_time'], '第一日')
        self.assertEqual(record.details['known_to'], ['商会'])
        self.assertEqual(len(restored.causal_ledger.active()), 1)
        context = restored.get_ledger_context()
        self.assertIn('已执行行动，不代表目标成功', context)
        self.assertIn('不等于玩家角色或其他实体已知', context)
        self.assertIn('商会收到订单', context)

    def test_fact_is_not_another_execution(self):
        engine = self.run_event('fact')
        self.assertEqual(engine.causal_ledger.export(), [])
        self.assertEqual(engine.entities[0].status, '尚未出发')
        self.assertIn('已发生事实', engine.get_ledger_context())

    def test_boundary_and_legacy_defaults(self):
        self.assertEqual(classify_event({}), ('action', '', []))
        for event in ({'kind': 'maybe'}, {'basis': {}}, {'known_to': 'everyone'}):
            with self.assertRaises(ValueError):
                classify_event(event)

    def test_entity_summary_exposes_constraints_not_other_entities_secrets(self):
        entity = Entity.from_dict({'name': '商会', 'knowledge': '只知道订单',
                                   'abilities': '贸易', 'resources': '一辆车', 'personality': '谨慎'})
        summary = entity.prompt_summary()
        for value in ('只知道订单', '贸易', '一辆车', '谨慎', entity.id, '未执行'):
            self.assertIn(value, summary)
