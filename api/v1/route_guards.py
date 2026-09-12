"""HTTP adapters for aggregate mutation guards."""

from functools import wraps

from fastapi import HTTPException

from core.session_manager import MutationBusyError, mutation_guard


def guarded_workshop(function):
    @wraps(function)
    def wrapped(workshop_id: str, *args, **kwargs):
        try:
            with mutation_guard("workshop", workshop_id):
                return function(workshop_id, *args, **kwargs)
        except MutationBusyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    return wrapped
