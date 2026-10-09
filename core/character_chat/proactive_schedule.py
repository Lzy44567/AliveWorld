"""One daily quiet window in the running computer's local time."""
from datetime import timedelta

DEFAULT_QUIET = {'enabled': False, 'start': '22:00', 'end': '08:00'}


def normalize_quiet(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULT_QUIET) or type(value['enabled']) is not bool:
        raise ValueError('invalid quiet window')
    for key in ('start', 'end'):
        text = value[key]
        if not isinstance(text, str) or len(text) != 5 or text[2] != ':' or not text[:2].isdigit() or not text[3:].isdigit():
            raise ValueError('invalid quiet time')
        if not 0 <= int(text[:2]) <= 23 or not 0 <= int(text[3:]) <= 59:
            raise ValueError('invalid quiet time')
    if value['start'] == value['end']:
        raise ValueError('quiet window must have an end')
    return dict(value)


def _at(day, value):
    return day.replace(hour=int(value[:2]), minute=int(value[3:]), second=0, microsecond=0)


def quiet_until(settings, now):
    window = settings.get('quiet_hours', DEFAULT_QUIET)
    if not window['enabled']:
        return None
    local = now.astimezone()
    start, end = _at(local, window['start']), _at(local, window['end'])
    if start < end:
        return end if start <= local < end else None
    if local >= start:
        return end + timedelta(days=1)
    return end if local < end else None


def next_quiet_start(settings, now):
    window = settings.get('quiet_hours', DEFAULT_QUIET)
    if not window['enabled']:
        return None
    local = now.astimezone()
    start = _at(local, window['start'])
    return start if start > local else start + timedelta(days=1)
