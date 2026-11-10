"""Bounded retry for transient Windows destination-file contention."""
import os
import time


def replace_file(source, destination):
    # Windows can briefly deny rename while another process inspects the file.
    # Never delete the destination or fall back to a non-atomic overwrite.
    for attempt in range(3):
        try:
            os.replace(source, destination)
            return
        except OSError as exc:
            if getattr(exc, 'winerror', None) not in (5, 32, 33) or attempt == 2:
                raise
            time.sleep(0.05 * (attempt + 1))
