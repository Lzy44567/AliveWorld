import unittest
import tempfile
from pathlib import Path
import yaml

from core.worldbook import WorldbookRetriever, normalize_entry, normalize_worldbook, save_worldbook_atomic


class WorldbookDomainTests(unittest.TestCase):
    def test_normalization_assigns_stable_entry_id_and_system_tags(self):
        book = normalize_worldbook({
            "name": "测试世界",
            "entries": [{"name": "法律", "content": "必须遵守", "tags": "绝对规则，玩家设定"}],
        })
        entry = book["entries"][0]
        self.assertTrue(entry["id"].startswith("entry_"))
        self.assertEqual(entry["tags"], ["绝对规则", "玩家设定"])
        self.assertEqual(entry["id"], normalize_entry(entry)["id"])

    def test_keyword_and_resident_entries_are_retrieved(self):
        retriever = WorldbookRetriever(budget_chars=1000)
        selected, omitted = retriever.retrieve([
            {"name": "学校", "keys": "学校,课堂", "content": "学校规则"},
            {"name": "常识", "content": "世界常识", "tags": ["常驻"]},
            {"name": "远方", "keys": "沙漠", "content": "沙漠规则"},
        ], "玩家进入学校")
        self.assertEqual({hit.entry["name"] for hit in selected}, {"学校", "常识"})
        self.assertEqual(omitted, [])

    def test_pending_and_inactive_entries_never_enter_context(self):
        retriever = WorldbookRetriever()
        selected, _ = retriever.retrieve([
            {"name": "待确认", "keys": "命中", "content": "不可见", "tags": ["待确认"]},
            {"name": "待删除", "keys": "命中", "content": "不可见", "tags": ["待删除"]},
            {"name": "关闭", "keys": "命中", "content": "不可见", "is_active": False},
        ], "命中")
        self.assertEqual(selected, [])

    def test_budget_omits_lower_priority_entries(self):
        retriever = WorldbookRetriever(budget_chars=6)
        selected, omitted = retriever.retrieve([
            {"name": "甲", "keys": "命中", "content": "一二三四"},
            {"name": "乙", "keys": "命中", "content": "五六七八"},
        ], "命中")
        self.assertEqual(len(selected), 1)
        self.assertEqual(len(omitted), 1)

    def test_semantic_provider_can_be_added_without_changing_context_contract(self):
        class FakeSemantic:
            def scores(self, _query, entries):
                return {normalize_entry(entries[0])["id"]: 0.82}

        selected, _ = WorldbookRetriever(semantic=FakeSemantic()).retrieve([
            {"name": "学校制度", "content": "课程与校服规则"},
        ], "玩家进入校园")
        self.assertEqual(selected[0].entry["name"], "学校制度")
        self.assertIn("语义:0.820", selected[0].reasons)

    def test_atomic_save_writes_normalized_worldbook_without_temp_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "book.yml"
            save_worldbook_atomic(path, {"name": "世界", "entries": [{"name": "规则", "content": "内容"}]})
            saved = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertTrue(saved["entries"][0]["id"].startswith("entry_"))
            self.assertEqual(list(Path(temp_dir).glob(".book.yml.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
