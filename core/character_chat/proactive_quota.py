"""Single-process, conservative daily call/group reservations without chat text."""
import copy
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from .models import CharacterSessionError


class ProactiveQuota:
    def __init__(self, path, clock=None):
        self.path = Path(path)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.error = None
        self.data = {'version': 1, 'day': self.clock().date().isoformat(), 'call_limit': 5, 'contact_limit': 10, 'reservations': {}}
        try:
            if self.path.exists():
                value = json.loads(self.path.read_text(encoding='utf-8'))
                self._validate(value)
                self.data = value
        except (OSError, ValueError, KeyError, TypeError):
            self.error = 'CONTACT_QUOTA_UNAVAILABLE'

    @staticmethod
    def _validate(value):
        if not isinstance(value, dict) or set(value) != {'version', 'day', 'call_limit', 'contact_limit', 'reservations'} or value['version'] != 1:
            raise ValueError()
        datetime.strptime(value['day'], '%Y-%m-%d')
        if any(type(value[k]) is not int or not 1 <= value[k] <= 100 for k in ('call_limit', 'contact_limit')):
            raise ValueError()
        if not isinstance(value['reservations'], dict):
            raise ValueError()
        for item in value['reservations'].values():
            if set(item) != {'contacts', 'released'} or type(item['contacts']) is not int or type(item['released']) is not int or not 0 <= item['released'] <= item['contacts'] <= 5:
                raise ValueError()

    def _current(self):
        data = copy.deepcopy(self.data)
        day = self.clock().date().isoformat()
        if day > data['day']:
            data.update(day=day, reservations={})
        return data

    def _save(self, data):
        if self.error:
            raise CharacterSessionError(self.error)
        temporary = self.path.with_name(self.path.name + '.' + str(uuid4()) + '.tmp')
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open('w', encoding='utf-8') as handle:
                json.dump(data, handle, ensure_ascii=False, separators=(',', ':'))
                handle.flush(); os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            self.data = data
        except OSError:
            self.error = 'CONTACT_QUOTA_UNAVAILABLE'
            raise CharacterSessionError(self.error) from None
        finally:
            temporary.unlink(missing_ok=True)

    def snapshot(self):
        data = self._current()
        calls = len(data['reservations'])
        groups = sum(r['contacts'] - r['released'] for r in data['reservations'].values())
        reset = datetime.fromisoformat(data['day']).replace(tzinfo=timezone.utc) + timedelta(days=1)
        return {k: data[k] for k in ('day', 'call_limit', 'contact_limit')} | {
            'calls_used': calls, 'contacts_used': groups,
            'calls_remaining': max(0, data['call_limit'] - calls),
            'contacts_remaining': max(0, data['contact_limit'] - groups),
            'resets_at': reset.isoformat(), 'available': self.error is None, 'error': self.error}

    def configure(self, payload):
        if not isinstance(payload, dict) or set(payload) != {'call_limit', 'contact_limit'} or any(
                type(payload[k]) is not int or not 1 <= payload[k] <= 100 for k in payload):
            raise CharacterSessionError('INVALID_REQUEST')
        data = self._current(); data.update(payload)
        self._save(data)
        return self.snapshot()

    def reserve(self, plan_id, maximum):
        if self.error:
            raise CharacterSessionError(self.error)
        data = self._current()
        if plan_id in data['reservations']:
            return data['day'], data['reservations'][plan_id]['contacts']
        used = sum(r['contacts'] - r['released'] for r in data['reservations'].values())
        count = min(maximum, data['contact_limit'] - used)
        if len(data['reservations']) >= data['call_limit'] or count < 1:
            return data['day'], 0
        data['reservations'][plan_id] = {'contacts': count, 'released': 0}
        self._save(data)
        return data['day'], count

    def release(self, plan_id, undelivered, day=None):
        data = self._current()
        if day is not None and day != data['day']:
            return
        item = data['reservations'].get(plan_id)
        if not item or item['released'] >= undelivered:
            return
        item['released'] = min(item['contacts'], undelivered)
        self._save(data)

    def reserved_contacts(self, plan_id, day):
        data = self._current()
        item = data['reservations'].get(plan_id) if data['day'] == day else None
        return item['contacts'] if item else 0
