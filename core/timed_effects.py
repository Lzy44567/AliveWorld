"""Deterministic effect arithmetic; callers own time interpretation and commit."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EffectProgress:
    completed_rounds: int
    stopped_bar: str | None = None


def tick_effects(state, *, stop_at_zero=()):
    """Apply one legacy effect step, optionally stopping at a critical resource.

    Effect insertion order is preserved. A threshold is checked before later
    effects can heal it away. With no threshold this retains legacy arithmetic.
    """
    expired = []
    stopped = None
    for name, effect in state['buffs'].items():
        for field, amount in effect.items():
            if field.endswith('_per_turn'):
                target = field.replace('_per_turn', '')
                if target in state['bars']:
                    bar = state['bars'][target]
                    bar['current'] += amount
                    bar['change'] += amount
                    if target in stop_at_zero and bar['current'] <= 0:
                        stopped = target
        if effect.get('duration', -1) != -1:
            effect['duration'] -= 1
            if effect['duration'] <= 0:
                expired.append(name)
        if stopped is not None:
            break
    for name in expired:
        del state['buffs'][name]
    return stopped


def advance_effects(state, rounds, *, stop_at_zero=()):
    """Advance a staged state. This does not infer seconds from dialogue.

    stop_at_zero names are explicit rules, never guessed from a bar's label.
    On interruption, the caller must resolve the event, not resume this step.
    """
    if type(rounds) is not int or rounds < 0:
        raise ValueError('rounds must be a non-negative integer')
    for bar in state['bars'].values():
        bar['change'] = 0
    for name in stop_at_zero:
        if name in state['bars'] and state['bars'][name]['current'] <= 0:
            return EffectProgress(0, name)
    for step in range(rounds):
        if not state['buffs']:
            return EffectProgress(rounds)
        stopped = tick_effects(state, stop_at_zero=stop_at_zero)
        for bar in state['bars'].values():
            bar['current'] = max(0, min(bar['current'], bar.get('max', 100)))
        if stopped is not None:
            return EffectProgress(step + 1, stopped)
    return EffectProgress(rounds)
