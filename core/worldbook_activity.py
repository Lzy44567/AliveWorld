"""Read-only, spoiler-safe projection of existing local revision history."""
from core.worldbook_revisions import reconcile_capture_history


def activity_page(books, turns, *, offset=0, limit=30, details=False):
    rows = []
    pending = 0
    for book_id, original in books.items():
        book, _ = reconcile_capture_history(original, turns)
        entries = {e['id']: e for e in book.get('entries', [])}
        pending += sum('待确认' in e.get('tags', []) for e in entries.values())
        reviews = {r['proposal_id']: r['decision'] for r in book.get('capture_reviews', [])}
        for index, change in enumerate(book.get('capture_history', [])):
            before, after = change.get('before'), change.get('after')
            status = change['status']
            if status == 'applied':
                if after and '待确认' in after.get('tags', []):
                    status = reviews.get(change['entry_id'], 'pending' if change['entry_id'] in entries else 'changed')
                else:
                    status = 'recorded'
            operation = (after or before or {}).get('pending_operation') or (
                'add' if before is None else 'remove' if after is None else
                'retire' if before.get('is_active', True) and not after.get('is_active', True) else 'update')
            item = {'id': f"{book_id}:{change['id']}", 'book_id': book_id,
                    'book_name': book.get('name', book_id), 'turn': change.get('source_turn'),
                    'status': status, 'operation': operation, '_index': index}
            if details:
                item.update(name=(after or before or {}).get('name', ''),
                            before=before, after=after)
            rows.append(item)
    rows.sort(key=lambda r: (r['turn'] or 0, r['book_id'], r['_index']), reverse=True)
    ids = [r['id'] for r in rows]
    selected = rows[offset:offset + limit]
    for row in selected:
        row.pop('_index')
    return {'total': len(rows), 'pending': pending, 'ids': ids, 'items': selected,
            'next_offset': offset + limit if offset + limit < len(rows) else None}
