"""Small shared rules for workshop author guidance, not published asset facts."""


def set_brief(workshop, text):
    workshop.assert_editable()
    workshop.creative_brief = text.strip()
    workshop.brief_edited = True
    workshop.touch()


def capture_initial_brief(workshop, payload, error_type):
    brief = payload.get('creative_brief')
    if not workshop.creative_brief and not workshop.brief_edited and brief is not None:
        if not isinstance(brief, str) or len(brief) > 2000:
            raise error_type('创作目标必须为不超过2000字的文本')
        workshop.creative_brief = brief.strip()
