"""Explicit one-turn control input; never inferred from dialogue or author data."""

class OocInputError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def normalize_ooc(value=None):
    if value is None:
        return ''
    if not isinstance(value, str):
        raise OocInputError('INVALID_REQUEST')
    value = value.strip()
    try:
        value.encode('utf-8', errors='strict')
    except UnicodeError:
        raise OocInputError('INVALID_REQUEST') from None
    if len(value) > 1000:
        raise OocInputError('INPUT_LIMIT')
    return value


def validate_stored_ooc(record):
    """Persisted fields are optional, but when present must be canonical/nonempty."""
    if 'ooc_note' in record:
        value = record['ooc_note']
        if not isinstance(value, str) or not value or normalize_ooc(value) != value:
            raise ValueError('Invalid stored OOC')
