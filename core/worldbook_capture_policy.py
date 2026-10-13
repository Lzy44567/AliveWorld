"""Small policy for evidence-backed automatic revisions, not semantic judging."""


def automatic_revision(candidate, events, *, review_all, has_source):
    if review_all or not has_source or not events:
        return False
    index = candidate.get('event_index')
    if type(index) is not int or not 0 <= index < len(events):
        return False
    event = events[index]
    allowed = {'update': {'update'}, 'retire': {'suspend', 'expire'}}
    return (event['change_kind'] in allowed.get(candidate.get('operation'), set())
            and event['time_hint'] == 'persistent'
            and event['scope_hint'] != 'individual_exception'
            and candidate.get('scope') in {'world_rule', 'social_system', 'natural_law', 'technology_magic_rule'}
            and candidate.get('confidence') == 'high' and candidate.get('risk') == 'low')
