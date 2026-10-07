import copy
import json
import unittest
from uuid import uuid4

from core.character_chat.capacity import group_capacity_report, capacity_report
from core.character_chat.models import CharacterSessionError, create_session
from core.character_chat.group_migration import convert_legacy_session
from core.character_chat.group_lifecycle import accept_input, claim_inputs, commit_generated, fail_generation
from tests.test_character_multibubble_protocol import result


class GroupCapacityTests(unittest.TestCase):
    def setUp(self):
        self.value = convert_legacy_session(create_session(str(uuid4()), {'name': '合成', 'description': '固定'},
                                                              {'kind': 'character', 'key': '合成'}))

    def start(self):
        accept_input(self.value, {'client_action_id': str(uuid4()), 'expected_revision': self.value['revision'], 'content': '输入'})
        return claim_inputs(self.value, explicit=True)

    def test_logical_group_reservation_not_bubble_count(self):
        attempt = self.start()
        before = copy.deepcopy(self.value)
        self.assertEqual(1, group_capacity_report(self.value)['public_counts']['formal_groups']['used'])
        self.assertEqual(before, self.value)
        commit_generated(self.value, attempt['request_id'], json.dumps(result('甲', '乙', '丙')), [], set())
        self.assertEqual(1, group_capacity_report(self.value)['public_counts']['formal_groups']['used'])

    def test_failed_archive_only_consumes_technical_limits(self):
        attempt = self.start(); fail_generation(self.value, attempt['request_id'])
        report = group_capacity_report(self.value)
        self.assertEqual(0, report['public_counts']['formal_groups']['used'])
        self.assertEqual(1, report['public_counts']['actions']['used'])
        self.assertEqual(1, report['public_counts']['attempts']['used'])
        self.assertEqual({'formal_groups', 'actions', 'attempts'}, set(report['public_counts']))
        self.assertNotIn('ledger', json.dumps(report))

    def test_unknown_or_legacy_does_not_use_group_reader(self):
        with self.assertRaises(CharacterSessionError): capacity_report(self.value)
        future = dict(self.value, schema_version=3)
        with self.assertRaises(CharacterSessionError): group_capacity_report(future)


if __name__ == '__main__': unittest.main()
