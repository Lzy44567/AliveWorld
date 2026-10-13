import copy
import unittest

from core.worldbook_revisions import record_capture_changes, reconcile_capture_history


def turn(number, message):
    return {'turn_id': number, 'player': '继续', 'story': '设定成立', 'source_message_ids': [message]}


def entry(text='原规则', active=True):
    return {'id': 'rule_1', 'name': '规则', 'content': text, 'is_active': active}


class WorldbookRevisionTests(unittest.TestCase):
    def test_add_is_removed_but_history_retained_and_idempotent(self):
        source = turn(1, 'first')
        book = record_capture_changes({'entries': []}, {'entries': [entry()]}, source)
        restored, report = reconcile_capture_history(book, [])
        self.assertEqual(restored['entries'], [])
        self.assertEqual(len(report['reverted']), 1)
        self.assertEqual(restored['capture_history'][0]['after'], entry())
        self.assertEqual(reconcile_capture_history(restored, [])[0], restored)
        self.assertEqual(book['entries'], [entry()])

    def test_update_then_retire_reverts_in_reverse_order(self):
        first, second = turn(1, 'first'), turn(2, 'second')
        initial = {'entries': [entry()]}
        changed = record_capture_changes(initial, {'entries': [entry('新规则')]}, first)
        retired = record_capture_changes(changed, {**changed, 'entries': [entry('新规则', False)]}, second)
        midway, _ = reconcile_capture_history(retired, [first])
        self.assertEqual(midway['entries'], [entry('新规则')])
        restored, _ = reconcile_capture_history(retired, [])
        self.assertEqual(restored['entries'], initial['entries'])

    def test_reused_turn_number_is_not_same_source(self):
        source = turn(1, 'first')
        book = record_capture_changes({'entries': []}, {'entries': [entry()]}, source)
        self.assertEqual(reconcile_capture_history(book, [source])[0], book)
        self.assertEqual(reconcile_capture_history(book, [turn(1, 'rerolled')])[0]['entries'], [])

    def test_later_manual_edit_or_delete_is_preserved(self):
        book = record_capture_changes({'entries': [entry()]}, {'entries': [entry('自动修订')]}, turn(1, 'first'))
        for values in ([entry('人工修订')], []):
            edited = {**book, 'entries': values}
            restored, report = reconcile_capture_history(edited, [])
            self.assertEqual(restored['entries'], values)
            self.assertEqual(len(report['detached']), 1)

    def test_manual_edit_between_auto_changes_is_not_overwritten(self):
        book = record_capture_changes({'entries': [entry()]}, {'entries': [entry('自动1')]}, turn(1, 'one'))
        manual = {**book, 'entries': [entry('人工')]}
        updated = record_capture_changes(manual, {**manual, 'entries': [entry('自动2')]}, turn(2, 'two'))
        restored, report = reconcile_capture_history(updated, [])
        self.assertEqual(restored['entries'], [entry('人工')])
        self.assertEqual(len(report['reverted']), 1)
        self.assertEqual(len(report['detached']), 1)

    def test_legacy_without_source_is_unchanged(self):
        book = {'entries': [entry()]}
        original = copy.deepcopy(book)
        self.assertEqual(record_capture_changes({}, book, None), book)
        self.assertEqual(reconcile_capture_history(book, [])[0], book)
        self.assertEqual(book, original)


if __name__ == '__main__':
    unittest.main()
