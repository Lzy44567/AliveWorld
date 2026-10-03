"""Atomic YAML replacement: serialization/write failure leaves the old file intact."""
import os
import tempfile
from pathlib import Path
import yaml


def save_yaml_atomic(path, value):
    target = Path(path)
    encoded = yaml.safe_dump(value, allow_unicode=True, sort_keys=False)
    temporary = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent,
                                         prefix='.asset-', suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
