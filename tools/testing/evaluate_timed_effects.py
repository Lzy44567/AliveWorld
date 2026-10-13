"""Opt-in paid evaluation using synthetic stories and the production turn path.

Run without --live to list cases. Credentials are read, never copied to reports.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from datetime import datetime
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]

CASES = (
    ('short', 100, '我留在安全房间，等待十五秒。', 95, False),
    ('critical', 8, '我打算在安全房间休息一个月。', 0, True),
    ('no_time', 100, '【场外说明：不推进故事时间】我询问当前中毒状态。', 100, False),
)


def check_state(name, state, report):
    health, elapsed, remaining, remainder, interrupted = {
        'short': (95, 15, 4, 5, False),
        'critical': (0, 20, 3, 0, True),
        'no_time': (100, 0, 5, 0, False),
    }[name]
    poison = state.get('buffs', {}).get('毒', {})
    return {
        'health': state.get('bars', {}).get('生命', {}).get('current') == health,
        'elapsed': report.get('mode') == 'seconds' and report.get('applied') == elapsed,
        'remaining': poison.get('duration') == remaining,
        'remainder': poison.get('tick_elapsed') == remainder,
        'interrupted': report.get('interrupted') == interrupted,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Authorize up to six paid requests')
    parser.add_argument('--config', type=Path, default=ROOT / 'config.yml')
    parser.add_argument('--cases', nargs='+', choices=[c[0] for c in CASES], default=[c[0] for c in CASES])
    parser.add_argument('--max-requests', type=int, choices=range(1, 7), default=6)
    parser.add_argument('--disable-thinking', action='store_true', help='Test-only DeepSeek override; never changes saved configuration')
    args = parser.parse_args()
    if not args.live:
        print(json.dumps({'cases': args.cases, 'max_requests': args.max_requests,
                          'live': False}, ensure_ascii=False))
        return 0

    runtime = ROOT / 'build' / ('effect-eval-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    runtime.mkdir(parents=True)
    # Set before importing any production singleton; no player assets or prompts.
    os.environ['ALIVEWORLD_USER_DIR'] = str(runtime)
    os.environ['ALIVEWORLD_RESOURCE_DIR'] = str(ROOT)
    sys.path.insert(0, str(ROOT))
    from core.model_connections.repository import ConnectionRepository
    from core.ai_engine import AIEngine
    from core.game_session import GameSession

    repository = ConnectionRepository(args.config.resolve())
    connection = repository.resolve(repository.load(persist_migration=False), 'story')
    if not connection or not connection.profile.api_key:
        print('No configured story API key; no requests sent.')
        return 2
    config = connection.ai_config()
    # This evaluator's approved provider; do not silently send to another host.
    if urlsplit(config['base_url']).hostname != 'api.deepseek.com':
        print('This evaluation requires the official DeepSeek endpoint; no requests sent.')
        return 2
    engine = AIEngine(config)
    engine.client = engine.client.with_options(timeout=90, max_retries=0)
    create = engine.client.chat.completions.create
    requests = []

    def bounded_create(**kwargs):
        if len(requests) >= args.max_requests:
            raise RuntimeError('Evaluation request limit reached')
        if args.disable_thinking:
            kwargs['extra_body'] = {'thinking': {'type': 'disabled'}}
        requests.append({'status': 'started'})
        response = create(**kwargs)
        usage = response.usage
        requests[-1] = {'status': 'received', 'usage': usage.model_dump() if usage else {},
                        'finish_reason': response.choices[0].finish_reason,
                        'content': response.choices[0].message.content or ''}
        return response

    engine.client.chat.completions.create = bounded_create
    results = []
    for name, health, action, expected_health, interrupted in CASES:
        if name not in args.cases:
            continue
        session = GameSession(engine, name, str(runtime / name), {
            'entitiesEnabled': False, 'worldbookCaptureEnabled': False,
            'learnUserPreferences': False, 'useUserPreferences': False,
            'autoCompressMemory': False, 'targetStoryLength': 300,
        })
        session.world_premise = (
            '合成验收世界：成年旅行者在无其他事件的安全房间。'
            '生命为0时昏迷，不能完成休息。没有治疗、自然恢复或其他伤害。'
            '毒每十秒扣5点生命，剩余五次，当前刚开始计时。'
            '一月按30天。不要擅自添加事件、药物或生命变化。'
        )
        session._refresh_local_context()
        session.state_mgr.state.update({
            'bars': {'生命': {'current': health, 'max': 100, 'change': 0}},
            'buffs': {'毒': {'生命_per_turn': -5, 'duration': 5,
                           'tick_seconds': 10, 'tick_elapsed': 0,
                           'description': '每十秒损失5点生命，剩余五次'}},
            'properties': {'当前时间': '第一日 12:00:00'},
        })
        result = session.process_turn(action)
        preview = result.get('effect_preview') or {}
        report = preview.get('report') or {}
        error = bool(result.get('error'))
        checks = check_state(name, session.state, report)
        passed = not error and all(checks.values())
        row = {'case': name, 'state_passed': passed, 'narrative_review': 'pending', 'error': error,
               'checks': checks,
               'stage': result.get('stage'), 'message': result.get('message'),
               'report': report, 'state': session.state,
               'story': (result.get('settlement') or {}).get('story_text', '')}
        results.append(row)
        print(json.dumps({'case': name, 'state_passed': passed, 'narrative_review': 'pending', 'error': error,
                          'stage': result.get('stage')}, ensure_ascii=False), flush=True)
        # Connection failure is not a reason to spend the remaining requests.
        if error and not report and result.get('stage') == 'reaction':
            break
    output = {'model': config['model'], 'disable_thinking': args.disable_thinking,
              'max_requests': args.max_requests, 'requests': requests, 'results': results,
              'note': 'Exit code 0 means state checks only, NOT narrative acceptance. Review rule consequences, time and agency separately.'}
    (runtime / 'report.json').write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Report: {runtime / "report.json"}', flush=True)
    return 0 if len(results) == len(set(args.cases)) and all(r['state_passed'] for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
