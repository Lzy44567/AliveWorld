import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.worldbook_workshop import WorldbookWorkshop, WorkshopError
from core.worldbook_workshop_agent import WorldbookWorkshopAgent
from api.v1.streaming import workshop_chat_transaction
from tests.test_worldbook_workshop_agent import FakeAI


class CreativeBriefTests(unittest.TestCase):
    def make(self, path=Path('unused.yml')):
        return WorldbookWorkshop('brief', path, {'name': '浮岛', 'entries': []})

    def test_model_initial_brief_persists_beyond_recent_history_without_extra_call(self):
        workshop = self.make()
        ai = FakeAI(json.dumps({'message': '讨论', 'creative_brief': '轻松探索，不写战争', 'operations': []}))
        agent = WorldbookWorkshopAgent(ai)
        agent.respond(workshop, '想做轻松探索，不要战争', 'create')
        workshop.messages.extend([{'role': 'user', 'content': '另一件事'}] * 30)
        agent.respond(workshop, '继续', 'expand')
        self.assertEqual(len(ai.requests), 2)
        self.assertIn('【作者创作目标（不是世界事实）】\n轻松探索，不写战争', ai.requests[-1][1])
        self.assertNotIn('creative_brief', workshop.draft)
        restored = WorldbookWorkshop.from_dict(workshop.to_dict())
        self.assertEqual(restored.creative_brief, workshop.creative_brief)

    def test_manual_override_and_clear_cannot_be_overwritten_by_model(self):
        workshop = self.make()
        ai = FakeAI('{"message":"讨论","creative_brief":"写战争","operations":[]}')
        for text in ['只写经营', '']:
            workshop.set_creative_brief(text)
            WorldbookWorkshopAgent(ai).respond(workshop, '继续', 'expand')
            self.assertEqual(workshop.creative_brief, text)
            self.assertTrue(workshop.brief_edited)

    def test_publish_does_not_export_author_brief_and_undo_does_not_change_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'book.yml'
            workshop = self.make(path)
            workshop.set_creative_brief('作者指导，不是世界事实')
            workshop.apply_operations([{'op': 'update_overview', 'overview': '浮岛世界'}])
            workshop.undo()
            self.assertEqual(workshop.creative_brief, '作者指导，不是世界事实')
            workshop.publish()
            self.assertNotIn('作者指导', path.read_text(encoding='utf-8'))
            with self.assertRaises(WorkshopError):
                workshop.set_creative_brief('修改历史')

    def test_invalid_model_brief_or_save_failure_does_not_commit(self):
        workshop = self.make()
        before = workshop.to_dict()
        with tempfile.TemporaryDirectory() as directory:
            for brief in [[], 'x' * 2001]:
                ai = FakeAI(json.dumps({'message': '讨论', 'creative_brief': brief, 'operations': []}))
                with self.assertRaises(WorkshopError):
                    workshop_chat_transaction(workshop, Path(directory), lambda candidate:
                        WorldbookWorkshopAgent(ai).respond(candidate, '继续', 'expand'))
                self.assertEqual(workshop.to_dict(), before)
            with patch.object(WorldbookWorkshop, 'save_session', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    workshop_chat_transaction(workshop, Path(directory), lambda candidate: candidate.set_creative_brief('new'))
            self.assertEqual(workshop.to_dict(), before)

    def test_old_session_defaults_empty(self):
        restored = WorldbookWorkshop.from_dict({'id': 'old', 'target_path': 'old.yml', 'draft': {}})
        self.assertEqual(restored.creative_brief, '')
        self.assertFalse(restored.brief_edited)
