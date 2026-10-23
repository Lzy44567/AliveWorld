import unittest
from core.worldbook_activity import activity_page
from core.worldbook_revisions import record_capture_changes
from core.worldbook_review import review_proposals


class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.turn = {'turn_id': 1, 'player': '动作', 'story': '事实'}
        self.entry = {'id': 'e', 'name': '秘密条目', 'content': '隐藏正文', 'tags': ['待确认'], 'is_active': True}
        self.book = record_capture_changes({'entries': []}, {'name': '书', 'entries': [self.entry]}, self.turn)

    def test_default_has_no_entry_content(self):
        page = activity_page({'file': self.book}, [self.turn])
        self.assertEqual(page['pending'], 1)
        self.assertEqual(page['items'][0]['status'], 'pending')
        self.assertNotIn('隐藏正文', str(page))
        self.assertNotIn('秘密条目', str(page))
        self.assertEqual(page['items'][0]['book_id'], 'file')

    def test_details_explicit_and_undo_projection(self):
        page = activity_page({'file': self.book}, [], details=True)
        self.assertEqual(page['pending'], 0)
        self.assertEqual(page['items'][0]['status'], 'reverted')
        self.assertEqual(page['items'][0]['after']['content'], '隐藏正文')
        self.assertEqual(self.book['capture_history'][0]['status'], 'applied')

    def test_review_history_and_qualified_pagination(self):
        reviewed = review_proposals(self.book, [{'id': 'e', 'accept': False}], [self.turn])
        page = activity_page({'a': reviewed, 'b': self.book}, [self.turn], limit=1)
        self.assertEqual(page['total'], 3)
        self.assertEqual(len(set(page['ids'])), 3)
        self.assertEqual(page['next_offset'], 1)
        all_rows = activity_page({'a': reviewed}, [self.turn])['items']
        self.assertIn('rejected', [r['status'] for r in all_rows])

    def test_manual_edit_survives_undo(self):
        self.book['entries'][0] = {**self.entry, 'content': '人工改写'}
        page = activity_page({'file': self.book}, [])
        self.assertEqual(page['items'][0]['status'], 'detached')
