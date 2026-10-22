"""Validate model-selected destinations without guessing from display names."""
from copy import deepcopy


ROUTING_PROMPT = """
本次提供多本局内世界书。每项候选必须额外填写 target_book_id 与 routing_reason。
修改/废止必须使用原书的 book_id 和该书准确的 target_entry_id，不因标题或主题改变而迁移。
新增基础规则优先主书；明确的专门知识进入收录主题匹配的知识书。
多书同等匹配、交叉知识或无法确定时 target_book_id 留空，交给本局自动设定。
不要按目录顺序选书，不要把同名条目当成同一条目；不要修改未提供的书。
"""


def route_candidates(payload, books):
    """Return grouped candidates and rejected revisions; empty key means fallback."""
    groups, skipped = {}, []
    candidates = payload.get('candidates') if isinstance(payload, dict) else None
    for item in candidates if isinstance(candidates, list) else []:
        if not isinstance(item, dict):
            continue
        candidate = deepcopy(item)
        target = str(candidate.get('target_book_id') or '').strip()
        operation = candidate.get('operation', 'add')
        book = books.get(target)
        if operation in {'update', 'retire'}:
            entry_id = candidate.get('target_entry_id')
            if not book or not any(entry.get('id') == entry_id for entry in book.get('entries', [])):
                skipped.append(f"无法定位原书条目：{candidate.get('name') or entry_id or target}")
                continue
        elif operation == 'add':
            if not book:
                if target:
                    candidate['risk'] = 'high'
                target = ''
        else:
            skipped.append(f"未知捕获操作：{operation}")
            continue
        groups.setdefault(target, []).append(candidate)
    return groups, skipped
