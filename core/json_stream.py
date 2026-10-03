"""Project only explicitly public JSON strings before the full result is valid.

This is a preview lexer, never a settlement validator or a JSON repair tool.
The completed raw response still passes the existing domain validators.
"""

import json


STORY_FIELDS = {"story_text": ""}
WORKSHOP_FIELDS = {"understanding": "理解", "design_notes": "设计依据", "message": "结论"}
PREFERENCE_FIELDS = {
    "understanding": "理解", "alternative_explanations": "仍需保留的其他解释",
    "design_notes": "设计取舍", "message": "结论",
}


def _partial_string(source, start):
    """Decode a string prefix, retaining incomplete escapes and surrogate pairs."""
    result, high, index = [], None, start + 1
    escapes = {'"': '"', '\\': '\\', '/': '/', 'b': '\b', 'f': '\f', 'n': '\n', 'r': '\r', 't': '\t'}
    while index < len(source):
        char = source[index]
        if char == '"':
            if high is not None:
                raise ValueError("Unpaired JSON unicode surrogate")
            return "".join(result)
        if char == '\\':
            if index + 1 >= len(source):
                break
            escaped = source[index + 1]
            if escaped == 'u':
                if index + 6 > len(source):
                    break
                digits = source[index + 2:index + 6]
                if any(item not in '0123456789abcdefABCDEF' for item in digits):
                    raise ValueError("Invalid JSON unicode escape")
                char = chr(int(digits, 16))
                index += 6
            else:
                if escaped not in escapes:
                    raise ValueError("Invalid JSON string escape")
                char = escapes[escaped]
                index += 2
        else:
            if ord(char) < 32:
                raise ValueError("Invalid JSON string control character")
            index += 1
        point = ord(char)
        if 0xD800 <= point <= 0xDBFF:
            if high is not None:
                raise ValueError("Unpaired JSON unicode surrogate")
            high = point
        elif 0xDC00 <= point <= 0xDFFF:
            if high is None:
                raise ValueError("Unpaired JSON unicode surrogate")
            result.append(chr(0x10000 + ((high - 0xD800) << 10) + point - 0xDC00))
            high = None
        else:
            if high is not None:
                raise ValueError("Unpaired JSON unicode surrogate")
            result.append(char)
    return "".join(result)


class JSONTextPreview:
    """Bounded-response projection; raw JSON and nested lookalike keys never emit."""

    def __init__(self, fields, emit):
        self.fields = dict(fields)
        self.emit = emit
        self.raw = ""
        self.visible = ""
        self.decoder = json.JSONDecoder()

    def _skip_space(self, index):
        while index < len(self.raw) and self.raw[index].isspace():
            index += 1
        return index

    def _strings(self, index, *, allow_array=False):
        """Only a scalar string or the first four direct string array elements."""
        if self.raw[index] == '"':
            return [_partial_string(self.raw, index)]
        if not allow_array or self.raw[index] != '[':
            return []
        values, index = [], index + 1
        while len(values) < 4:
            index = self._skip_space(index)
            if index >= len(self.raw) or self.raw[index] == ']':
                break
            if self.raw[index] == '"':
                values.append(_partial_string(self.raw, index))
            try:
                _, index = self.decoder.raw_decode(self.raw, index)
            except ValueError:
                break
            index = self._skip_space(index)
            if index >= len(self.raw) or self.raw[index] != ',':
                break
            index += 1
        return values

    def feed(self, text):
        self.raw += text
        index = self._skip_space(0)
        if index >= len(self.raw):
            return
        if self.raw[index] != '{':
            raise ValueError("Streaming model must return a JSON object")
        index += 1
        sections, seen = [], set()
        while True:
            index = self._skip_space(index)
            if index >= len(self.raw) or self.raw[index] == '}':
                break
            if self.raw[index] != '"':
                raise ValueError("Invalid JSON object key")
            try:
                key, index = self.decoder.raw_decode(self.raw, index)
            except ValueError:
                break
            index = self._skip_space(index)
            if index >= len(self.raw):
                break
            if self.raw[index] != ':':
                raise ValueError("Invalid JSON object separator")
            index = self._skip_space(index + 1)
            if index >= len(self.raw):
                break
            if key in self.fields:
                if key in seen:
                    raise ValueError("Duplicate public JSON field")
                seen.add(key)
                values = self._strings(index, allow_array=key in {"design_notes", "alternative_explanations"})
                heading = self.fields[key]
                if any(values):
                    body = "\n".join(f"{i}. {item}" for i, item in enumerate(values, 1)) if self.raw[index] == '[' else values[0]
                    sections.append((heading + "\n" if heading else "") + body)
            try:
                _, index = self.decoder.raw_decode(self.raw, index)
            except ValueError:
                break
            index = self._skip_space(index)
            if index >= len(self.raw) or self.raw[index] == '}':
                break
            if self.raw[index] != ',':
                raise ValueError("Invalid JSON object separator")
            index += 1
        visible = "\n\n".join(sections)
        if not visible.startswith(self.visible):
            raise ValueError("Non-monotonic JSON preview")
        delta = visible[len(self.visible):]
        self.visible = visible
        if delta:
            self.emit(delta)
