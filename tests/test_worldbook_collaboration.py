import unittest
from copy import deepcopy

from core.worldbook_collaboration import (
    collect_conflicts, decide_conflict, default_collaboration, disabled_references,
    primary_book, public_collaboration, rule_catalog,
)


class WorldbookCollaborationTests(unittest.TestCase):
    def setUp(self):
        self.books = {key: {"name": key, "entries": [{"id": "same", "name": "规则", "content": text}]}
                      for key, text in (("主书", "此地禁止飞行"), ("知识书", "此地允许飞行"))}
        self.state = {**default_collaboration(), "primary_book": "主书"}
        self.turn = {"turn_id": 1, "player": "试飞", "story": "此地不能飞行", "source_message_ids": ["m1"]}
        self.rules = rule_catalog(self.books)
        self.keep, self.disable = list(self.rules)
        self.proposal = {"keep": self.keep, "disable": self.disable, "keep_quote": "禁止飞行",
                         "disable_quote": "允许飞行", "scope": "同一地点", "reason": "飞行许可互斥"}

    def collect(self, state=None, proposals=None, supplied=None):
        return collect_conflicts(proposals if proposals is not None else [self.proposal],
                                 state=state or self.state, books=self.books,
                                 supplied_rules=self.rules if supplied is None else supplied,
                                 source_turn=self.turn)

    def test_qualified_ids_and_no_implicit_multibook_primary(self):
        self.assertNotEqual(self.keep, self.disable)
        self.assertEqual(primary_book(default_collaboration(), self.books), "")
        self.assertEqual(primary_book(default_collaboration(), {"主书": self.books["主书"]}), "主书")
        self.assertEqual(primary_book({"primary_book": "不存在"}, {"主书": self.books["主书"]}), "")

    def test_overlay_does_not_edit_assets_and_undo_invalidates(self):
        original = deepcopy(self.books)
        state, count = self.collect()
        self.assertEqual(count, 1)
        self.assertEqual(disabled_references(state, self.books, [self.turn]), {self.disable})
        self.assertEqual(disabled_references(state, self.books, []), set())
        replacement = {**self.turn, "story": "另一个未来"}
        self.assertEqual(disabled_references(state, self.books, [replacement]), set())
        self.assertEqual(self.books, original)

    def test_bad_or_unsupplied_signals_are_ignored(self):
        for change in ({"keep": []}, {"disable": self.keep}, {"keep_quote": "不存在"}, {"scope": ""}):
            self.assertEqual(self.collect(proposals=[{**self.proposal, **change}])[1], 0)
        self.assertEqual(self.collect(supplied={self.keep: self.rules[self.keep]})[1], 0)
        self.assertEqual(self.collect(proposals={})[1], 0)

    def test_manual_review_and_restore_do_not_repeat(self):
        state, _ = self.collect(state={**self.state, "review": True})
        self.assertEqual(disabled_references(state, self.books, [self.turn]), set())
        identity = state["conflicts"][0]["id"]
        state = decide_conflict(state, identity, "disable", books=self.books, turns=[self.turn])
        self.assertEqual(disabled_references(state, self.books, [self.turn]), {self.disable})
        state = decide_conflict(state, identity, "restore", books=self.books, turns=[self.turn])
        self.assertEqual(disabled_references(state, self.books, [self.turn]), set())
        self.assertEqual(self.collect(state=state)[1], 0)

    def test_content_or_primary_changes_invalidate_overlay(self):
        state, _ = self.collect()
        self.assertEqual(disabled_references({**state, "primary_book": "知识书"}, self.books, [self.turn]), set())
        self.books["主书"]["entries"][0]["content"] = "允许低空飞行"
        self.assertEqual(disabled_references(state, self.books, [self.turn]), set())
        with self.assertRaises(ValueError):
            decide_conflict(state, state["conflicts"][0]["id"], "disable", books=self.books, turns=[self.turn])
        self.assertFalse(public_collaboration(state, self.books, [self.turn])["conflicts"][0]["current"])

    def test_replayed_turn_can_report_same_conflict_again(self):
        state, _ = self.collect()
        self.turn = {**self.turn, 'story': '新的未来'}
        state, count = self.collect(state=state)
        self.assertEqual(count, 1)
        self.assertNotEqual(state['conflicts'][0]['id'], state['conflicts'][1]['id'])
        self.assertEqual(disabled_references(state, self.books, [self.turn]), {self.disable})

    def test_non_entry_targets_and_pending_entries_not_eligible(self):
        self.books["知识书"]["overview"] = "此地允许飞行"
        rules = rule_catalog(self.books)
        overview = next(ref for ref, rule in rules.items() if rule["kind"] == "overview")
        _, count = collect_conflicts([{**self.proposal, "disable": overview}], state=self.state,
                                    books=self.books, supplied_rules=rules, source_turn=self.turn)
        self.assertEqual(count, 0)
        self.books["知识书"]["entries"][0]["tags"] = ["待确认"]
        self.assertNotIn(self.disable, rule_catalog(self.books))


if __name__ == "__main__":
    unittest.main()
