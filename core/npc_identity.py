"""Local scene identities; not an entity simulator or a second memory store."""
from copy import deepcopy
from uuid import uuid4


class NpcIdentityError(ValueError):
    pass


NPC_IDENTITY_INSTRUCTION = '''【场景人物身份】
npc_states仍用显示名对应状态。NPC获得名字/明确离场/重返时，另附npc_identity_updates数组：
{"name":"当前显示名","id":"给出的已有ID（可省略）","previous_name":"明确旧称（可省略）","present":true,"reason":"本回合依据"}。
新人物省略id和previous_name，由程序分配。改名必须引用已有id或previous_name；不得猜测不同称呼必为同人。只说起、回忆某人不等于他在场。离场present=false；真正重返present=true且在npc_states写新状态。生命/死亡等词出现在描述里不代表离场，明确用present表达。
已知身份只含玩家可知称呼；同名不同人用清楚的区分称呼，不能挪用他人ID。改名后只提交新显示名的状态，不同时提交矛盾的新旧状态。身份操作涉及的人物不要同时放status_deletions，退出用present=false。'''


def validate_identity_updates(value):
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 100:
        raise NpcIdentityError('人物身份更新必须为不超过100项的列表')
    clean = []
    for item in value:
        if not isinstance(item, dict) or set(item) - {'name', 'id', 'previous_name', 'present', 'reason'}:
            raise NpcIdentityError('人物身份更新含未知字段')
        result = {}
        for key in ('name', 'id', 'previous_name', 'reason'):
            if key not in item and key not in ('name', 'reason'):
                continue
            text = item.get(key)
            if not isinstance(text, str) or not text.strip() or len(text) > (1000 if key == 'reason' else 120):
                raise NpcIdentityError(f'人物身份的{key}需要有效文本')
            result[key] = text.strip()
        if 'present' in item:
            if type(item['present']) is not bool:
                raise NpcIdentityError('人物在场标记必须是true或false')
            result['present'] = item['present']
        clean.append(result)
    return clean


class NpcIdentityBook:
    def __init__(self, records=None):
        self.records = deepcopy(records or {})

    def by_name(self, name):
        matches = [r for r in self.records.values() if name == r['name'] or name in r['aliases']]
        if len(matches) > 1:
            raise NpcIdentityError(f'“{name}”对应多个人物，请使用已有身份ID或明确区分称呼')
        return matches[0] if matches else None

    def ensure(self, name, status=''):
        record = self.by_name(name)
        if record is None:
            ident = 'npc_' + uuid4().hex
            record = {'id': ident, 'name': name, 'aliases': [], 'last_status': status,
                      'present': True, 'explicit_absent': False}
            self.records[ident] = record
        return record

    def canonicalize(self, values):
        result = {}
        for name, value in values.items():
            record = self.ensure(name, value)
            target = record['name']
            if target in result and result[target] != value:
                raise NpcIdentityError(f'“{target}”的新旧称呼提交了不同状态，请只保留一份')
            result[target] = value
        return result

    def prepare(self, current, updates, operations, absent_turns, deletions=()):
        for name, status in current.items():
            self.ensure(name, status)
        forced = {}
        seen = set()
        for item in operations:
            record = self.records.get(item['id']) if 'id' in item else None
            if 'id' in item and record is None:
                raise NpcIdentityError('人物身份ID不存在于当前故事')
            previous = self.by_name(item['previous_name']) if 'previous_name' in item else None
            if 'previous_name' in item and previous is None:
                raise NpcIdentityError(f'找不到旧称“{item["previous_name"]}”，不能自动合并人物')
            if record and previous and record['id'] != previous['id']:
                raise NpcIdentityError('人物ID与旧称指向不同人物')
            record = record or previous or self.ensure(item['name'])
            if record['id'] in seen:
                raise NpcIdentityError('同一人物本回合只能提交一次身份更新')
            seen.add(record['id'])
            occupant = self.by_name(item['name'])
            if occupant and occupant['id'] != record['id']:
                raise NpcIdentityError(f'“{item["name"]}”已被另一人物使用，请使用区分称呼')
            old = record['name']
            if old != item['name']:
                if 'id' not in item and 'previous_name' not in item:
                    raise NpcIdentityError('改名需要明确引用原身份ID或旧称')
                if old not in record['aliases']:
                    record['aliases'].append(old)
                record['name'] = item['name']
                if old in absent_turns:
                    absent_turns[item['name']] = absent_turns.pop(old)
            record['reason'] = item['reason']
            if 'present' in item:
                forced[record['name']] = item['present']
                record['explicit_absent'] = not item['present']
                record['presence_explicit'] = True
        for name in deletions:
            record = self.by_name(name)
            if record and record['id'] in seen:
                raise NpcIdentityError('同一人物不要同时更新身份和删除，请用present=false')
        current, updates = self.canonicalize(current), self.canonicalize(updates)
        for record in self.records.values():
            name = record['name']
            if record['explicit_absent']:
                current.pop(name, None)
                updates.pop(name, None)
                absent_turns.pop(name, None)
            elif forced.get(name) is True:
                if name not in updates:
                    raise NpcIdentityError(f'“{name}”在场或重返时需要同时提交npc_states状态')
                current[name] = updates[name]
        return current, updates, forced

    def finish(self, current):
        for record in self.records.values():
            record['present'] = record['name'] in current
            if record['present']:
                record['last_status'] = current[record['name']]

    def hide(self, name):
        record = self.by_name(name)
        if record:
            record['present'] = False
            record['explicit_absent'] = True

    def explicitly_present(self, name):
        record = self.by_name(name)
        return bool(record and record.get('presence_explicit') and not record['explicit_absent'])

    def context(self, current, action):
        selected = []
        for record in sorted(self.records.values(), key=lambda r: r['name'] not in current):
            names = [record['name'], *record['aliases']]
            if record['name'] in current or any(name in action for name in names):
                selected.append({k: deepcopy(record[k]) for k in ('id', 'name', 'aliases', 'present')})
        return selected[:30]
