"""Small model-output boundary for classified undercurrent records."""

KINDS = {'plan', 'action', 'fact'}


def classify_event(event):
    # Older providers produce executed actions without a kind.
    kind = event.get('kind', 'action')
    if kind not in KINDS:
        raise ValueError('暗流记录类型必须为 plan、action 或 fact')
    basis = event.get('basis', '')
    known_to = event.get('known_to', [])
    if not isinstance(basis, str) or not isinstance(known_to, list) or any(not isinstance(value, str) for value in known_to):
        raise ValueError('暗流依据必须为文字，知情者必须为名称或ID列表')
    return kind, basis, list(dict.fromkeys(known_to))
