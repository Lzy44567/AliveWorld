import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import worldbook_workshop_registry as routes
from core.worldbook_workshop import WorldbookWorkshop


class WorkshopRetargetTests(unittest.TestCase):
    def setUp(self):
        routes.active_workshops.clear()

    def tearDown(self):
        routes.active_workshops.clear()

    def test_exact_worldbook_target_is_rewritten_and_persisted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sessions = root / "workshops"
            old = root / "old.yml"
            new = root / "new.yml"
            workshop = WorldbookWorkshop("one", old, {"name": "book"})
            workshop.save_session(sessions)
            with patch.object(routes, "WORKSHOP_DIR", sessions):
                self.assertEqual(1, routes.retarget_workshops(old, new))
            saved = json.loads((sessions / "one.json").read_text(encoding="utf-8"))
            self.assertEqual(str(new.resolve()), saved["target_path"])

    def test_save_directory_retarget_keeps_relative_worldbook_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sessions = root / "workshops"
            old = root / "Save_old"
            new = root / "Save_new"
            target = old / "worldbooks" / "book.yml"
            workshop = WorldbookWorkshop("two", target, {"name": "book"})
            routes.active_workshops[workshop.id] = workshop
            with patch.object(routes, "WORKSHOP_DIR", sessions):
                self.assertEqual(1, routes.retarget_workshops(old, new, recursive=True))
            self.assertEqual((new / "worldbooks" / "book.yml").resolve(), workshop.target_path)
