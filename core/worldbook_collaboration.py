"""Story-local worldbook precedence and reversible conflict overlays.

No asset writes or model calls: the story transaction owns persistence.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import yaml

from core.capture_source import turn_identity
from core.worldbook import normalize_worldbook, read_worldbook_bytes
from core.worldbook_revisions import reconcile_capture_history


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def default_collaboration():
    return {"primary_book": "", "auto_disable": True, "review": False, "conflicts": []}


def load_books(save_dir, turns):
    books = {}
    for path in sorted((Path(save_dir) / "worldbooks").glob("*.yml")):
        book = normalize_worldbook(yaml.safe_load(read_worldbook_bytes(path).decode('utf-8')))
        if book.get("capture_history"):
            book, _ = reconcile_capture_history(book, turns)
        books[path.stem] = book
    return books


def primary_book(state, books):
    selected = state.get("primary_book", "")
    if selected:
        return selected if selected in books and books[selected].get("is_active", True) else ""
    active = [key for key, book in books.items() if book.get("is_active", True)]
    return active[0] if len(active) == 1 else ""


def rule_catalog(books):
    """Qualified references survive text edits, but not asset identity changes."""
    rules = {}
    for book_id, book in books.items():
        if not book.get("is_active", True):
            continue
        items = [("overview", "概述", book.get("overview", ""), "overview")]
        items.extend((f"axiom:{i}", f"公理 {i + 1}", text, "axiom")
                     for i, text in enumerate(book.get("axioms", [])))
        items.extend((entry["id"], entry["name"], entry["content"], "entry")
                     for entry in book.get("entries", [])
                     if entry.get("is_active", True) and not {"待确认", "待删除"}.intersection(entry.get("tags", [])))
        for item_id, name, content, kind in items:
            if not content:
                continue
            ref = "wb_" + fingerprint([book_id, kind, item_id])[:24]
            rules[ref] = {"ref": ref, "book_id": book_id, "book_name": book.get("name", book_id),
                          "item_id": item_id, "name": name, "content": content, "kind": kind,
                          "fingerprint": fingerprint([name, content])}
    return rules


def conflict_is_current(record, state, books, rules, turns):
    if record["primary_book"] != primary_book(state, books):
        return False
    if record["source"] not in {turn_identity(turn) for turn in turns}:
        return False
    return all(ref in rules and rules[ref]["fingerprint"] == record[field + "_fingerprint"]
               for field in ("keep", "disable") for ref in [record[field]])


def disabled_references(state, books, turns):
    rules = rule_catalog(books)
    return {item["disable"] for item in state.get("conflicts", [])
            if item["status"] == "disabled" and conflict_is_current(item, state, books, rules, turns)}


def collect_conflicts(payload, *, state, books, supplied_rules, source_turn, active_turns=None):
    """Validate optional model signals once; malformed auxiliary output is ignored."""
    result = deepcopy(state)
    primary = primary_book(state, books)
    if not primary or not isinstance(payload, list):
        return result, 0
    rules = rule_catalog(books)
    turns = active_turns if active_turns is not None else [source_turn]
    existing = {item["signature"] for item in result.get("conflicts", [])
                if item["status"] == "restored" or conflict_is_current(item, state, books, rules, turns)}
    added = 0
    for proposal in payload[:8]:
        if not isinstance(proposal, dict):
            continue
        keep, disable = (proposal.get(key) for key in ("keep", "disable"))
        if not isinstance(keep, str) or not isinstance(disable, str):
            continue
        if keep not in supplied_rules or disable not in supplied_rules or keep not in rules or disable not in rules:
            continue
        a, b = rules[keep], rules[disable]
        if a["book_id"] != primary or b["book_id"] == primary or b["kind"] != "entry":
            continue
        texts = {key: proposal.get(key) for key in ("keep_quote", "disable_quote", "scope", "reason")}
        if any(not isinstance(value, str) or not value.strip() or len(value) > 1000 for value in texts.values()):
            continue
        if texts["keep_quote"] not in a["content"] or texts["disable_quote"] not in b["content"]:
            continue
        # Both references must still describe exactly the request's input.
        if any(supplied_rules[ref]["fingerprint"] != rules[ref]["fingerprint"] for ref in (keep, disable)):
            continue
        signature = fingerprint([primary, keep, a["fingerprint"], disable, b["fingerprint"]])
        if signature in existing:
            continue
        existing.add(signature)
        result.setdefault("conflicts", []).append({
            "id": fingerprint([signature, turn_identity(source_turn)]), "signature": signature,
            "primary_book": primary, "keep": keep, "disable": disable,
            "keep_fingerprint": a["fingerprint"], "disable_fingerprint": b["fingerprint"],
            "source": turn_identity(source_turn), "turn_id": source_turn.get("turn_id"),
            "status": "disabled" if state.get("auto_disable", True) and not state.get("review", False) else "pending",
            **texts,
        })
        added += 1
    return result, added


def decide_conflict(state, conflict_id, decision, *, books, turns):
    return decide_conflicts(state, [{'conflict_id': conflict_id, 'decision': decision}], books=books, turns=turns)


def decide_conflicts(state, decisions, *, books, turns):
    """Validate the whole batch before returning a changed story-local copy."""
    result = deepcopy(state)
    records = {item['id']: item for item in result.get('conflicts', [])}
    rules = rule_catalog(books)
    seen = set()
    for item in decisions:
        conflict_id, decision = item['conflict_id'], item['decision']
        if decision not in {'disable', 'restore'}:
            raise ValueError('请选择停用或恢复')
        if conflict_id in seen:
            raise ValueError('同一冲突不能重复处理')
        seen.add(conflict_id)
        record = records.get(conflict_id)
        if record is None:
            raise ValueError('冲突记录不存在')
        if decision == 'disable' and not conflict_is_current(record, state, books, rules, turns):
            raise ValueError('来源或条目已变化，请刷新后重新选择；本批未保存')
        record['status'] = 'disabled' if decision == 'disable' else 'restored'
    return result


def public_collaboration(state, books, turns):
    rules = rule_catalog(books)
    primary = primary_book(state, books)
    records = []
    for record in state.get("conflicts", []):
        item = deepcopy(record)
        item["current"] = conflict_is_current(record, state, books, rules, turns)
        for field in ("keep", "disable"):
            rule = rules.get(record[field], {})
            item[field + "_label"] = " / ".join(filter(None, [rule.get("book_name"), rule.get("name")])) or "原条目已不可用"
        records.append(item)
    return {"revision": fingerprint(state), "primary_book": primary,
            "requested_primary_book": state.get("primary_book", ""),
            "auto_disable": state.get("auto_disable", True), "review": state.get("review", False),
            "books": [{"id": key, "name": value.get("name", key), "active": value.get("is_active", True)}
                      for key, value in books.items()], "conflicts": records}
