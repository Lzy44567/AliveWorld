"""Shared selection rule; each workshop retains its own mutation rules."""


def select_operations(operations, operation_ids, error_type):
    selected = set(operation_ids)
    if not selected or not selected.issubset({item['operation_id'] for item in operations}):
        raise error_type('所选修改已不存在，请刷新后重试')
    return [item for item in operations if item['operation_id'] in selected]
