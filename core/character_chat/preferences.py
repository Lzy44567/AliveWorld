"""Opt-in, confirmed-only preference projection; no learning or stored snapshots."""
from copy import deepcopy

CATEGORY_SETTINGS = {
    'story': 'preferenceStoryEnabled', 'narrative': 'preferenceStoryEnabled',
    'content': 'preferenceStoryEnabled', 'boundary': 'preferenceStoryEnabled',
    'other': 'preferenceStoryEnabled', 'adult': 'preferenceAdultEnabled',
    'action': 'preferenceActionEnabled', 'character': 'preferenceCharacterEnabled',
    'relationship': 'preferenceRelationshipEnabled', 'visual': 'preferenceVisualEnabled',
}
DEFAULT_SETTINGS = {'enabled': False, 'include_sensitive': False}


def validate_settings(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULT_SETTINGS) or any(type(v) is not bool for v in value.values()):
        raise ValueError('Invalid character preference settings')
    if not value['enabled'] and value['include_sensitive']:
        raise ValueError('Sensitive preferences require enabled preferences')
    return deepcopy(value)


def session_settings(session):
    return deepcopy(session.get('extensions', {}).get('character_preferences', DEFAULT_SETTINGS))


def project_preferences(profile, settings, global_settings):
    """Whole statements only; never return evidence, identifiers or inferred reasons."""
    validate_settings(settings)
    if not settings['enabled']:
        return []
    items = profile.get('preferences', []) if isinstance(profile, dict) else []
    if not isinstance(items, list) or not isinstance(global_settings, dict):
        return []
    eligible = []
    for item in items:
        if not isinstance(item, dict) or item.get('status') != 'active':
            continue
        if item.get('manual_override') is not True and item.get('source_type') != 'declared':
            continue
        category, statement, polarity = item.get('category'), item.get('statement'), item.get('polarity')
        if not isinstance(category, str) or category not in CATEGORY_SETTINGS or global_settings.get(CATEGORY_SETTINGS[category], True) is not True:
            continue
        sensitive = item.get('sensitive', False)
        if type(sensitive) is not bool or (sensitive or category == 'adult') and not settings['include_sensitive']:
            continue
        if not isinstance(statement, str) or not statement.strip() or len(statement) > 400 or polarity not in ('prefer', 'avoid'):
            continue
        eligible.append({'category': category, 'polarity': polarity, 'statement': statement})
    eligible.sort(key=lambda item: item['category'])
    selected, used, seen = [], 0, set()
    for item in eligible:
        identity = (item['category'], item['polarity'], item['statement'])
        if identity in seen or used + len(item['statement']) > 2400:
            continue
        seen.add(identity)
        selected.append(item)
        used += len(item['statement'])
        if len(selected) == 20:
            break
    return selected


def load_preferences(settings):
    # Keep both disk reads and repository construction behind explicit opt-in.
    if not settings['enabled']:
        return []
    from core.user_preferences import UserPreferenceRepository
    from utils.runtime_paths import PATHS
    import yaml
    try:
        raw = yaml.safe_load(PATHS.config_file.read_text(encoding='utf-8')) or {}
    except (OSError, yaml.YAMLError):
        return []
    if not isinstance(raw, dict):
        return []
    return project_preferences(UserPreferenceRepository().load(), settings, raw.get('settings', {}))
