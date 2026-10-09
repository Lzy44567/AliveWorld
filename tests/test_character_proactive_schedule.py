import unittest
from datetime import datetime, timedelta
from core.character_chat.proactive_schedule import normalize_quiet, quiet_until, next_quiet_start


class QuietScheduleTests(unittest.TestCase):
    def at(self, hour, minute=0):
        return datetime.now().astimezone().replace(hour=hour, minute=minute, second=0, microsecond=0)

    def test_daytime_and_midnight_window_boundaries(self):
        settings = {'quiet_hours': {'enabled': True, 'start': '22:00', 'end': '08:00'}}
        self.assertIsNone(quiet_until(settings, self.at(21,59)))
        self.assertEqual(self.at(8) + timedelta(days=1), quiet_until(settings, self.at(22)))
        self.assertEqual(self.at(8), quiet_until(settings, self.at(7,59)))
        self.assertIsNone(quiet_until(settings, self.at(8)))
        settings['quiet_hours'].update(start='09:00', end='17:00')
        self.assertEqual(self.at(17), quiet_until(settings, self.at(10)))
        self.assertIsNone(quiet_until(settings, self.at(17)))
        self.assertEqual(self.at(9)+timedelta(days=1), next_quiet_start(settings, self.at(17)))

    def test_default_off_and_boundary_validation(self):
        self.assertIsNone(quiet_until({}, self.at(23)))
        self.assertIsNone(next_quiet_start({}, self.at(23)))
        valid = {'enabled': True, 'start': '22:00', 'end': '08:00'}
        self.assertEqual(valid, normalize_quiet(valid))
        for patch in ({'start':'24:00'}, {'end':'08:60'}, {'start':'8:00'}, {'end':'22:00'}, {'enabled':1}):
            with self.assertRaises(ValueError):
                normalize_quiet({**valid, **patch})
