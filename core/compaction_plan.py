"""Pure complete-unit prefix selection; callers own costs, data and I/O."""
import copy


def plan_compaction(units, *, high_water, low_water, min_hot_units,
                    bridge_tokens, force=False, minimum_force_tokens=300):
    total = sum(item['token_estimate'] for item in units)
    if not force and total < high_water:
        return None
    min_hot = min(min_hot_units, max(1, len(units) // 2))
    max_archive_count = len(units) - min_hot
    if max_archive_count <= 0:
        return None
    desired = max(1, total - low_water)
    if force:
        desired = max(desired, minimum_force_tokens)
    archive = []
    archived_tokens = 0
    for item in units[:max_archive_count]:
        archive.append(item)
        archived_tokens += item['token_estimate']
        if archived_tokens >= desired:
            break
    if not archive or (force and archived_tokens < minimum_force_tokens):
        return None
    bridge = []
    used = 0
    for item in units[len(archive):]:
        if bridge and used >= bridge_tokens:
            break
        bridge.append(item)
        used += item['token_estimate']
    return {'archive': copy.deepcopy(archive), 'bridge': copy.deepcopy(bridge),
            'total_tokens': total, 'archived_tokens': archived_tokens,
            'remaining_tokens': total - archived_tokens}
