import copy
import json
import tempfile
import unittest
from pathlib import Path

from core.worldbook_workshop import WorldbookWorkshop, WorkshopError


class WorkshopReviewTests(unittest.TestCase):
    def make(self):
        workshop = WorldbookWorkshop('review', Path('unused.yml'), {'entries': []})
        workshop.propose_operations([
            {'op': 'add_entry', 'operation_id': name, 'entry': {'name': name, 'content': name}}
            for name in ['one', 'two', 'three']])
        return workshop

    def test_partial_accept_then_reject_keeps_unselected(self):
        workshop = self.make()
        workshop.review_operations('proposed', ['two'], accept=True)
        self.assertEqual([e['name'] for e in workshop.draft['entries']], ['two'])
        workshop.review_operations('proposed', ['one'], accept=False)
        self.assertEqual([e['operation_id'] for e in workshop.proposed], ['three'])
        workshop.undo()
        self.assertEqual(workshop.draft['entries'], [])

    def test_stale_selection_does_not_mutate(self):
        workshop = self.make()
        before = copy.deepcopy(workshop.to_dict())
        with self.assertRaises(WorkshopError):
            workshop.review_operations('proposed', ['one', 'missing'], accept=True)
        self.assertEqual(workshop.to_dict(), before)

    def test_conflicting_operations_fail_whole_batch(self):
        workshop = self.make()
        workshop.draft['entries'] = [{'id': 'x', 'name': 'x', 'content': 'x'}]
        workshop.propose_operations([
            {'op': 'delete_entry', 'operation_id': 'a', 'entry_id': 'x'},
            {'op': 'update_entry', 'operation_id': 'b', 'entry_id': 'x', 'changes': {'content': 'new'}}])
        before = copy.deepcopy(workshop.to_dict())
        with self.assertRaises(WorkshopError):
            workshop.review_operations('proposed', ['a', 'b'], accept=True)
        self.assertEqual(workshop.to_dict(), before)

    def test_pending_batch_and_reload(self):
        workshop = self.make()
        workshop.apply_operations([{'op': 'set_axioms', 'axioms': ['rule'], 'operation_id': 'rule'}])
        workshop.review_operations('pending', ['rule'], accept=True)
        self.assertEqual(workshop.draft['axioms'], ['rule'])
        self.assertEqual(workshop.pending, [])
        with tempfile.TemporaryDirectory() as directory:
            workshop.save_session(Path(directory))
            restored = WorldbookWorkshop.from_dict(json.loads((Path(directory) / 'review.json').read_text(encoding='utf-8')))
            self.assertEqual(restored.proposed, workshop.proposed)
            self.assertEqual(restored.draft, workshop.draft)
