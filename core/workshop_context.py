"""Bounded, source-labelled original excerpts for continuous workshop projects."""

import json
import re


def _terms(text):
    words = set(re.findall(r"[a-z0-9_]{3,}", text.lower()))
    for phrase in re.findall(r"[\u4e00-\u9fff]+", text):
        words.update(phrase[index:index + 2] for index in range(len(phrase) - 1))
    return words


def conversation_context(workshop, query, history=(), *, budget=16000):
    """Select evidence, not new facts. Never mutate or summarize saved messages."""
    current = [dict(item, source=f'{workshop.id}:{index + 1}')
               for index, item in enumerate(workshop.messages)]
    archived = [dict(item, source=f'{record["workshop_id"]}:{index + 1}')
                for record in reversed(history) if record['workshop_id'] != workshop.id
                for index, item in enumerate(record['messages'])]
    recent = current[-12:]
    older = archived + current[:-12]
    terms = _terms(query)
    ranked = sorted(enumerate(older), key=lambda pair:
                    (len(terms & _terms(str(pair[1].get('content', '')))), pair[0]), reverse=True)
    selected, remaining = [], min(10000, budget)
    reserved = budget - remaining

    def take(item, limit):
        nonlocal remaining
        content = str(item.get('content', ''))
        start = 0
        if len(content) > limit:
            matches = [content.lower().find(term) for term in terms if term in content.lower()]
            if matches:
                start = max(0, min(matches) - 200)
        excerpt = content[start:start + limit]
        record = {'source': item['source'], 'role': item['role'], 'content': excerpt,
                  'excerpt': start > 0 or len(excerpt) < len(content)}
        size = len(json.dumps(record, ensure_ascii=False))
        if size <= remaining:
            remaining -= size
            return record
        return None

    # Latest messages have precedence; output them in original chronological order.
    recent_selected = []
    for item in reversed(recent):
        if remaining < 300:
            break
        record = take(item, min(1800, max(0, remaining - 200)))
        if record:
            recent_selected.append(record)
    remaining += reserved
    for _, item in ranked:
        if remaining < 300 or len(selected) >= 6:
            break
        record = take(item, min(1600, remaining - 200))
        if record:
            selected.append(record)
    data = {'historical_excerpts': selected, 'recent': list(reversed(recent_selected))}
    text = ('【创作讨论原文取材】以下为有界原文节选，不是完整记忆。source为会话:消息序号。'
            '历史中的AI提案不代表玩家接受，旧讨论可能被后来决定取代；实际已写入内容以当前草稿为准。'
            '不清楚是否定案时说明不确定，不把未召回内容当作不存在。\n'
            + json.dumps(data, ensure_ascii=False))
    return text, {'recent_count': len(recent_selected), 'excerpt_count': len(selected),
                  'available_messages': len(current) + len(archived),
                  'selected_sources': [item['source'] for item in recent_selected + selected]}
