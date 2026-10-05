"""Versioned input evidence permissions, independent from reply protocols."""
LEGACY = 'character.context.v1'
M3 = 'character.context.m3.v1'


class ContextContractError(ValueError):
    code = 'CONTEXT_CONTRACT_UNSUPPORTED'


def validate_context_contract(value):
    if not isinstance(value, str) or value not in {LEGACY, M3}:
        raise ContextContractError('Unsupported context contract')
    return value


def context_contract(attempt):
    return validate_context_contract(attempt.get('context_contract_id', LEGACY))
