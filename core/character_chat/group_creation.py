"""New schema2 construction only; no stored legacy record is converted here."""
from .models import create_session
from .group_schema import validate_schema2


def create_group_session(*args, **kwargs):
    value = create_session(*args, **kwargs)
    del value['turns']
    value.update(schema_version=2, context_epoch=0, next_seq=1, read_ai_seq=0, inputs=[], groups=[])
    validate_schema2(value)
    return value
