import copy
import json
import tempfile
import unittest

from core.effect_progress import EffectProgressError, prepare_effect_preview, validate_effect_followup
from core.game_session import GameSession
from core.settlement_contract import validate_settlement, SettlementContractError
from tests.test_timed_effects import poisoned


def progress(amount=1, mode='rounds'):
    return {'mode': mode, 'amount': amount, 'reason': '测试世界每轮十秒', 'stop_at_zero': ['生命']}


def reaction(amount=1, mode='rounds'):
    return {'reactions': [{'id': 1, 'description': '按已有规则经过时间', 'weight': 1,
                           'effect_progress': progress(amount, mode)}]}


class SequenceAI:
    def __init__(self, values):
        self.values = list(values)
        self.requests = []

    def chat_json(self, system, user, **kwargs):
        self.requests.append((system, user))
        value = self.values.pop(0)
        if isinstance(value, str):
            return value, None
        return json.dumps(value, ensure_ascii=False), None


class EffectProgressTests(unittest.TestCase):
    def state(self, health=100):
        state = poisoned(health).state
        state['buffs']['毒']['tick_seconds'] = 10
        return state

    def test_seconds_fraction_survives_next_request(self):
        first = prepare_effect_preview(self.state(), progress(15, 'seconds'))
        self.assertEqual(first['state']['bars']['生命']['current'], 95)
        self.assertEqual(first['state']['buffs']['毒']['tick_elapsed'], 5)
        second = prepare_effect_preview(first['state'], progress(5, 'seconds'))
        self.assertEqual(second['state']['bars']['生命']['current'], 90)
        self.assertEqual(second['state']['buffs']['毒']['duration'], 3)
        self.assertEqual(second['state']['buffs']['毒']['tick_elapsed'], 0)

    def test_month_settles_only_remaining_damage(self):
        result = prepare_effect_preview(self.state(), progress(2592000, 'seconds'))
        self.assertEqual(result['state']['bars']['生命']['current'], 75)
        self.assertEqual(result['report']['expired'], ['毒'])
        self.assertEqual(result['report']['applied'], 2592000)
        self.assertFalse(result['report']['interrupted'])

    def test_critical_boundary_stops_before_month_finishes(self):
        result = prepare_effect_preview(self.state(8), progress(2592000, 'seconds'))
        self.assertEqual(result['report']['applied'], 20)
        self.assertEqual(result['report']['stopped_bar'], '生命')
        self.assertEqual(result['state']['bars']['生命']['current'], 0)
        self.assertEqual(result['state']['buffs']['毒']['duration'], 3)

    def test_distinct_clocks_in_time_order(self):
        state = self.state(10)
        state['buffs']['恢复'] = {'生命_per_turn': 2, 'duration': 8, 'tick_seconds': 3}
        result = prepare_effect_preview(state, progress(20, 'seconds'))
        self.assertEqual(result['state']['bars']['生命']['current'], 12)
        self.assertEqual(result['state']['buffs']['恢复']['tick_elapsed'], 2)

    def test_same_time_poison_is_not_cancelled_by_later_heal(self):
        state = self.state(4)
        state['buffs']['恢复'] = {'生命_per_turn': 10, 'duration': -1, 'tick_seconds': 10}
        result = prepare_effect_preview(state, progress(30, 'seconds'))
        self.assertEqual(result['report']['applied'], 10)
        self.assertEqual(result['state']['bars']['生命']['current'], 0)

    def test_invalid_plan_and_missing_clock_leave_input_unchanged(self):
        state = poisoned().state
        before = copy.deepcopy(state)
        for raw in (None, progress(True), progress(-1), progress(1, 'days'), progress(1, 'seconds')):
            with self.assertRaises(EffectProgressError):
                prepare_effect_preview(state, raw, required=True)
            self.assertEqual(state, before)

    def test_absolute_overwrite_rejected_but_extra_delta_allowed(self):
        preview = prepare_effect_preview(self.state(), progress())
        with self.assertRaises(EffectProgressError):
            validate_effect_followup({'dynamic_bars': {'生命': {'current': 100}}}, preview)
        validate_effect_followup({'dynamic_bars': {'生命': {'change': -2}}}, preview)

    def test_zero_duration_does_not_apply_again(self):
        state = self.state()
        state['buffs']['毒']['duration'] = 0
        result = prepare_effect_preview(state, progress(0))
        self.assertEqual(result['state']['bars']['生命']['current'], 100)
        self.assertEqual(result['state']['buffs'], {})

    def test_periodic_budget_reports_actual_not_requested_time(self):
        state = self.state()
        state['buffs']['毒'].update(duration=-1, tick_seconds=1)
        raw = {**progress(100000, 'seconds'), 'stop_at_zero': []}
        result = prepare_effect_preview(state, raw)
        self.assertTrue(result['report']['interrupted'])
        self.assertEqual(result['report']['applied'], 10000)

    def test_period_validated_and_server_owns_fraction(self):
        for period in (0, -1, True, 1.2):
            with self.assertRaises(SettlementContractError):
                validate_settlement({'story_text': '效果出现', 'new_buffs': {'毒': {'tick_seconds': period}}})
        result = validate_settlement({'story_text': '效果出现', 'new_buffs': {'毒': {'tick_seconds': 10, 'tick_elapsed': 9}}})
        self.assertEqual(result['new_buffs']['毒']['tick_elapsed'], 0)


class EffectStoryTests(unittest.TestCase):
    def session(self, directory, ai):
        session = GameSession(ai, '效果测试', directory, {
            'entitiesEnabled': False, 'worldbookCaptureEnabled': False,
            'learnUserPreferences': False, 'autoCompressMemory': False,
        })
        session.state_mgr.state = poisoned().state
        session.state['buffs']['毒']['tick_seconds'] = 10
        return session

    def test_normal_reroll_save_and_undo_use_same_start(self):
        ai = SequenceAI([reaction(25, 'seconds'), {'story_text': '只经过二十五秒。'}, {'story_text': '重新描述二十五秒。'}])
        with tempfile.TemporaryDirectory() as path:
            session = self.session(path, ai)
            result = session.process_turn('等待二十五秒')
            self.assertFalse(result.get('error'))
            self.assertEqual(session.state['bars']['生命']['current'], 90)
            self.assertIn('"current": 90', ai.requests[1][1])
            self.assertIn('runtime.effect_progress', ai.requests[1][1])
            session.reroll_turn()
            self.assertEqual(session.state['bars']['生命']['current'], 90)
            self.assertEqual(session.state['buffs']['毒']['tick_elapsed'], 5)
            self.assertIn('"current": 90', ai.requests[2][1])
            saved = session.export_save_data()
            self.assertEqual(saved['state']['buffs']['毒']['tick_elapsed'], 5)
            self.assertTrue(session.rollback())
            self.assertEqual(session.state['bars']['生命']['current'], 100)
            self.assertEqual(session.state['buffs']['毒']['duration'], 5)

    def test_bad_story_rolls_back_preview_and_retry_not_double_charged(self):
        ai = SequenceAI([reaction(2), '{bad json', reaction(2), {'story_text': '继续。'}])
        with tempfile.TemporaryDirectory() as path:
            session = self.session(path, ai)
            before = copy.deepcopy(session.state)
            self.assertTrue(session.process_turn('等待')['error'])
            self.assertEqual(session.state, before)
            self.assertFalse(session.process_turn('等待').get('error'))
            self.assertEqual(session.state['bars']['生命']['current'], 90)

    def test_missing_progress_stops_before_second_request(self):
        ai = SequenceAI([{'reactions': [{'description': '继续', 'weight': 1}]}])
        with tempfile.TemporaryDirectory() as path:
            session = self.session(path, ai)
            self.assertEqual(session.process_turn('等待')['stage'], 'effect_progress')
            self.assertEqual(len(ai.requests), 1)
            self.assertEqual(session.state['bars']['生命']['current'], 100)

    def test_stale_absolute_current_rejects_whole_turn(self):
        ai = SequenceAI([reaction(2), {'story_text': '继续。', 'dynamic_bars': {'生命': {'current': 100}}}])
        with tempfile.TemporaryDirectory() as path:
            session = self.session(path, ai)
            self.assertTrue(session.process_turn('等待')['error'])
            self.assertEqual(session.state['bars']['生命']['current'], 100)

    def test_failed_reroll_restores_previous_result(self):
        ai = SequenceAI([reaction(2), {'story_text': '继续。'}, '{bad json'])
        with tempfile.TemporaryDirectory() as path:
            session = self.session(path, ai)
            session.process_turn('等待')
            before = copy.deepcopy(session.state)
            self.assertTrue(session.reroll_turn()['error'])
            self.assertEqual(session.state, before)


if __name__ == '__main__':
    unittest.main()
