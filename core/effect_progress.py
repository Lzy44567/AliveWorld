"""Model-facing time plan and isolated effect preview for story requests."""

import copy
import heapq

from core.timed_effects import advance_effects


class EffectProgressError(ValueError):
    pass


def needs_effect_progress(state):
    return any(
        effect.get('duration', -1) >= 0 or any(k.endswith('_per_turn') for k in effect)
        for effect in state.get('buffs', {}).values()
    )


FUTURE_EFFECT_INSTRUCTION = '''【持续效果时间计划】
当前有持续效果。每个reactions候选附effect_progress：
{"mode":"rounds或seconds","amount":非负整数,"reason":"经过时间/结算轮数的依据","stop_at_zero":["归零会打断行动的已有进度条名称"]}。
amount不是消息条数。纯交谈未推进结算可为0；逃跑也计实际经过时间。优先依据已设规则，seconds仅用于所有当前计时效果都有tick_seconds时；否则给有依据的实际结算轮数，不能凭空规定每轮秒数。长休不得漏算此前持续伤害；如时间关系不明，在能确定的近期节点停下，不声称完成长休。stop_at_zero依据资源含义选择，不是所有数值归零都会死亡。不同候选可以经过不同时间。
你只提出计划，程序先计算再交正文；不要预写与临界中断矛盾的必然结局。'''


SETTLEMENT_EFFECT_INSTRUCTION = '''【程序已结算持续效果】
runtime.effect_progress报告及当前状态已包含本次持续效果结算。默认从dynamic_bars省略已结算的进度条：不要把报告changes再抄成change，也不要重新扣除/恢复。若同一进度条确有另一项独立行动变化，才写change，并在顶层direct_change_reasons中以该进度条名写明独立事件依据；持续效果本身不是独立事件。current只能原值回显，不能覆盖程序结果。
若报告interrupted=true，只叙述到实际中断点，不宣称完成原定长休或用药恢复，不推进时间越过该点。expired是已结束效果，不能无新原因重新添加。
新效果从本段时间之后开始：仍用new_buffs，duration为剩余结算次数；只有有世界依据时增加tick_seconds（正整数秒周期），程序维护tick_elapsed，模型不要填写。需要中途获得/解除效果时停在那个变化点，不把整月和多个事件一次结算。'''


def normalize_progress(raw, state):
    if not isinstance(raw, dict):
        raise EffectProgressError('持续效果缺少时间计划，请重新发送本次行动')
    mode, amount = raw.get('mode'), raw.get('amount')
    if mode not in ('rounds', 'seconds') or type(amount) is not int or not 0 <= amount <= 10**12:
        raise EffectProgressError('时间计划需要rounds/seconds及非负整数推进量')
    reason = raw.get('reason')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise EffectProgressError('时间计划缺少有效依据')
    stops = raw.get('stop_at_zero', [])
    if not isinstance(stops, list) or any(not isinstance(n, str) or n not in state.get('bars', {}) for n in stops):
        raise EffectProgressError('时间计划的中断进度条不存在')
    return {'mode': mode, 'amount': amount, 'reason': reason.strip(), 'stop_at_zero': list(dict.fromkeys(stops))}


def _advance_seconds(state, seconds, stops):
    """Process due instants, preserving one fractional clock per effect."""
    queue, clocks = [], {}
    for order, (name, effect) in enumerate(state['buffs'].items()):
        if effect.get('duration', -1) < 0 and not any(k.endswith('_per_turn') for k in effect):
            continue
        period = effect.get('tick_seconds')
        remainder = effect.get('tick_elapsed', 0)
        if type(period) is not int or period <= 0 or type(remainder) is not int or not 0 <= remainder < period:
            raise EffectProgressError(f'效果“{name}”缺少有效秒周期，不能自动换算故事时间')
        clocks[name] = (period, remainder)
        heapq.heappush(queue, (period - remainder, order, name))
    reached, stop, interrupted, count = seconds, None, False, 0
    while queue and queue[0][0] <= seconds:
        at, order, name = heapq.heappop(queue)
        if count >= 10000 and at > last_at:
            reached, interrupted = last_at, True
            break
        effect = state['buffs'][name]
        if effect.get('duration', -1) == 0:
            del state['buffs'][name]
            continue
        for key, amount in effect.items():
            if key.endswith('_per_turn') and key[:-9] in state['bars']:
                target = key[:-9]
                bar = state['bars'][target]
                before = bar['current']
                bar['current'] = max(0, min(before + amount, bar.get('max', 100)))
                bar['change'] += bar['current'] - before
                if target in stops and bar['current'] <= 0:
                    stop = target
        if effect.get('duration', -1) != -1:
            effect['duration'] -= 1
            if effect['duration'] <= 0:
                del state['buffs'][name]
        count += 1
        last_at = at
        if stop:
            reached, interrupted = at, True
            break
        if name in state['buffs']:
            heapq.heappush(queue, (at + clocks[name][0], order, name))
    for name, (period, remainder) in clocks.items():
        if name in state['buffs']:
            state['buffs'][name]['tick_elapsed'] = (remainder + reached) % period
    return reached, stop, interrupted


def prepare_effect_preview(state, raw, *, required=False):
    if raw is None and not required:
        return None
    plan = normalize_progress(raw, state)
    staged = copy.deepcopy(state)
    for name in list(staged.get('buffs', {})):
        if staged['buffs'][name].get('duration') == 0:
            del staged['buffs'][name]
    for bar in staged.get('bars', {}).values():
        bar['change'] = 0
    stops = plan['stop_at_zero']
    existing_stop = next((name for name in stops if staged['bars'][name]['current'] <= 0), None)
    if existing_stop:
        applied, stop, interrupted = 0, existing_stop, True
    elif plan['mode'] == 'seconds':
        applied, stop, interrupted = _advance_seconds(staged, plan['amount'], stops)
    else:
        # Bound a single calculation, never silently claim the unprocessed rest.
        rounds = min(plan['amount'], 10000)
        progress = advance_effects(staged, rounds, stop_at_zero=stops)
        applied, stop = progress.completed_rounds, progress.stopped_bar
        if not staged.get('buffs') and stop is None:
            applied = plan['amount']
        interrupted = stop is not None or applied < plan['amount']
    changes = {
        name: bar['current'] - state['bars'][name]['current']
        for name, bar in staged.get('bars', {}).items()
        if bar['current'] != state['bars'][name]['current']
    }
    # Net display changes match final clamped values, not arithmetic overflow.
    for name, bar in staged.get('bars', {}).items():
        bar['change'] = changes.get(name, 0)
    report = {**plan, 'applied': applied, 'interrupted': interrupted,
              'stopped_bar': stop, 'changes': changes,
              'expired': [name for name in state.get('buffs', {}) if name not in staged['buffs']]}
    return {'state': staged, 'report': report}


def validate_effect_followup(settlement, preview):
    if preview is None:
        return
    report = preview['report']
    bars = settlement.get('dynamic_bars', {})
    for name in report['changes']:
        update = bars.get(name, {})
        if 'current' in update and update['current'] != preview['state']['bars'][name]['current']:
            raise EffectProgressError(f'“{name}”已由程序结算，正文不得用绝对值覆盖')
        if update.get('change', 0) != 0:
            reasons = settlement.get('direct_change_reasons', {})
            reason = reasons.get(name) if isinstance(reasons, dict) else None
            if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
                raise EffectProgressError(f'“{name}”已由程序结算，额外变化必须说明独立事件依据，不能重复扣除持续效果')
    stopped = report['stopped_bar']
    if stopped and bars.get(stopped, {}).get('change', 0) != 0:
        raise EffectProgressError('当前行动已在临界点中断，不能在同一回合继续改变该关键数值')
