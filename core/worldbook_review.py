"""Deterministic review of save-local capture proposals."""
from copy import deepcopy
import hashlib
import json

from core.worldbook import normalize_entry
from core.capture_source import turn_identity
from core.worldbook_revisions import reconcile_capture_history, record_revision_changes


class WorldbookReviewError(ValueError):
    pass


def entry_revision(entry):
    return hashlib.sha256(json.dumps(normalize_entry(entry), sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def review_proposals(book, decisions, active_turns):
    """Apply a batch atomically on a copy; rejected proposals retain audit history."""
    result, _ = reconcile_capture_history(book, active_turns)
    active_sources = {turn_identity(turn) for turn in active_turns}
    seen = set()
    for decision in decisions:
        ident, accept = decision['id'], decision['accept']
        if ident in seen:
            raise WorldbookReviewError('同一提案不能重复处理')
        seen.add(ident)
        proposal = next((e for e in result['entries'] if e['id'] == ident), None)
        if proposal is None or '待确认' not in proposal.get('tags', []):
            raise WorldbookReviewError('提案已处理或源回合已撤回，请刷新后重试')
        source = next((r for r in reversed(result.get('capture_history', []))
                       if r['entry_id'] == ident), None)
        if accept and source and source['source'] not in active_sources:
            raise WorldbookReviewError('候选的源回合已撤回；保留的人工编辑不能作为原捕获结果接受')
        previous = deepcopy(result)
        operation = proposal.get('pending_operation', 'add')
        target_id = proposal.get('replaces_entry_id')
        target = next((e for e in result['entries'] if e['id'] == target_id), None)
        if accept and operation != 'add':
            if target is None:
                raise WorldbookReviewError('原条目已不存在，不能应用此提案')
            expected = proposal.get('proposal_target_revision')
            if expected and expected != entry_revision(target):
                raise WorldbookReviewError('原条目在提案产生后已修改，请检查后重新整理')
        result['entries'] = [e for e in result['entries'] if e['id'] != ident]
        if accept:
            if operation == 'retire':
                target['is_active'] = False
            else:
                accepted = {k: v for k, v in proposal.items() if k not in {
                    'pending_operation', 'replaces_entry_id', 'proposal_reason', 'proposal_target_revision'}}
                accepted['id'] = target_id if operation == 'update' else ident
                accepted['tags'] = [t for t in proposal['tags'] if t != '待确认']
                accepted['is_active'] = True
                if operation == 'update':
                    index = result['entries'].index(target)
                    result['entries'][index] = accepted
                else:
                    result['entries'].append(accepted)
        if source:
            result = record_revision_changes(previous, result, source['source'], source['source_turn'])
        result.setdefault('capture_reviews', []).append({
            'proposal_id': ident, 'decision': 'accepted' if accept else 'rejected',
            'source': source['source'] if source else None,
        })
    return result
