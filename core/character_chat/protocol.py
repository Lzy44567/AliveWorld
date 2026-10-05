"""Explicit reply protocol identities shared by construction and validation."""
V1 = 'character.reply.v1'
V2 = 'character.reply.v2'


class ReplyContractError(ValueError):
    pass


def validate_contract(value):
    if not isinstance(value, str) or value not in {V1, V2}:
        raise ReplyContractError('Unsupported reply contract')
    return value


def contract_for(session):
    return V2 if session.get('extensions', {}).get('character_memory', {}).get('version', 1) == 2 else V1


def attempt_contract(attempt):
    return validate_contract(attempt.get('reply_contract_id', V1))


def result_keys(contract_id):
    validate_contract(contract_id)
    return {'reply', 'ledger_ops', 'memory_annotations'} if contract_id == V2 else {'reply', 'ledger_ops'}
