"""Incremental v3 JSON lexer: expose only messages[N].text, never private data.

Events are uncommitted previews. The complete contract and source validator is
still required before a transaction can persist any of these messages.
"""
import json

from .message_groups import MAX_BUBBLES, MAX_GROUP_CHARACTERS
from .models import CharacterSessionError
from .protocol import V3, result_keys


class GroupPreview:
    def __init__(self, emit):
        self.emit = emit
        self.stack = []
        self.started = self.complete = False
        self.in_string = self.escape = False
        self.unicode = self.high = None
        self.string = ''
        self.string_key = False
        self.visible = None
        self.primitive = None
        self.raw_size = self.visible_size = 0
        self.output = []

    def fail(self):
        raise CharacterSessionError('CONTRACT_INVALID')

    def flush(self):
        if self.output:
            body = ''.join(self.output)
            self.output = []
            for start in range(0, len(body), 2048):
                self.emit({'kind': 'preview_delta', 'ordinal': self.visible,
                           'text': body[start:start + 2048]})

    def path(self):
        top = self.stack[-1]
        return top['path'] + ((top['key'],) if top['object'] else (top['index'],))

    def expecting_value(self):
        return self.stack[-1]['state'] in {'value', 'value_or_end'}

    def value_done(self):
        top = self.stack[-1]
        if not self.expecting_value():
            self.fail()
        top['state'] = 'after'
        if not top['object']:
            top['index'] += 1

    def value_type(self, kind):
        path = self.path()
        if path == ('messages',) and kind != 'array':
            self.fail()
        if len(path) == 2 and path[0] == 'messages':
            if kind != 'object' or path[1] >= MAX_BUBBLES:
                self.fail()
        if len(path) == 3 and path[0] == 'messages' and kind != 'string':
            self.fail()
        return path

    def decoded(self, char):
        point = ord(char)
        if 0xD800 <= point <= 0xDBFF:
            if self.high is not None:
                self.fail()
            self.high = point
            return
        if 0xDC00 <= point <= 0xDFFF:
            if self.high is None:
                self.fail()
            char = chr(0x10000 + ((self.high - 0xD800) << 10) + point - 0xDC00)
            self.high = None
        elif self.high is not None:
            self.fail()
        if self.visible is not None:
            self.visible_size += 1
            if self.visible_size > MAX_GROUP_CHARACTERS:
                self.fail()
            self.output.append(char)
        else:
            self.string += char

    def end_string(self):
        if self.high is not None:
            self.fail()
        top = self.stack[-1]
        self.in_string = False
        if self.string_key:
            key = self.string
            if key in top['seen']:
                self.fail()
            if top['path'] == ():
                if key not in result_keys(V3) or (not top['seen'] and key != 'messages'):
                    self.fail()
            if len(top['path']) == 2 and top['path'][0] == 'messages':
                if key not in {'local_id', 'text'}:
                    self.fail()
            top['seen'].add(key)
            top['key'] = key
            top['state'] = 'colon'
        else:
            if self.visible is not None:
                self.flush()
                self.emit({'kind': 'preview_end', 'ordinal': self.visible})
                self.visible = None
            self.value_done()

    def finish_primitive(self):
        try:
            json.loads(self.primitive, parse_constant=lambda _: self.fail())
        except (ValueError, TypeError):
            self.fail()
        self.primitive = None
        self.value_done()

    def character(self, char):
        if self.in_string:
            if self.unicode is not None:
                if char not in '0123456789abcdefABCDEF':
                    self.fail()
                self.unicode += char
                if len(self.unicode) == 4:
                    self.decoded(chr(int(self.unicode, 16)))
                    self.unicode = None
            elif self.escape:
                self.escape = False
                escapes = {'"': '"', '\\': '\\', '/': '/', 'b': '\b', 'f': '\f', 'n': '\n', 'r': '\r', 't': '\t'}
                if char == 'u':
                    self.unicode = ''
                elif char in escapes:
                    self.decoded(escapes[char])
                else:
                    self.fail()
            elif char == '\\':
                self.escape = True
            elif char == '"':
                self.end_string()
            else:
                if ord(char) < 32:
                    self.fail()
                self.decoded(char)
            return
        if self.primitive is not None:
            if char not in ' \t\r\n,]}':
                self.primitive += char
                return
            self.finish_primitive()
            # Delimiter belongs to the surrounding object, not the primitive.
        if char in ' \t\r\n':
            return
        if self.complete:
            self.fail()
        if not self.started:
            if char != '{':
                self.fail()
            self.started = True
            self.stack.append({'object': True, 'path': (), 'state': 'key_or_end', 'seen': set(), 'key': None})
            return
        top = self.stack[-1]
        if char == '"':
            self.string_key = top['object'] and top['state'] in {'key', 'key_or_end'}
            if not self.string_key and not self.expecting_value():
                self.fail()
            self.string = ''
            self.in_string = True
            if not self.string_key:
                path = self.value_type('string')
                if len(path) == 3 and path[0] == 'messages' and path[2] == 'text':
                    self.visible = path[1]
                    self.emit({'kind': 'preview_start', 'ordinal': self.visible})
        elif char == ':':
            if top['state'] != 'colon':
                self.fail()
            top['state'] = 'value'
        elif char in '{[':
            if not self.expecting_value():
                self.fail()
            path = self.value_type('object' if char == '{' else 'array')
            self.stack.append({'object': char == '{', 'path': path,
                               'state': 'key_or_end' if char == '{' else 'value_or_end',
                               'seen': set(), 'key': None, 'index': 0})
            if len(self.stack) > 12:
                self.fail()
        elif char in '}]':
            if (char == '}') != top['object'] or top['state'] not in {'after', 'key_or_end', 'value_or_end'}:
                self.fail()
            if len(top['path']) == 2 and top['path'][0] == 'messages' and top['seen'] != {'local_id', 'text'}:
                self.fail()
            self.stack.pop()
            if self.stack:
                self.value_done()
            else:
                self.complete = True
        elif char == ',':
            if top['state'] != 'after':
                self.fail()
            top['state'] = 'key' if top['object'] else 'value'
        else:
            if not self.expecting_value():
                self.fail()
            self.value_type('primitive')
            self.primitive = char

    def feed(self, chunk):
        try:
            self.raw_size += len(chunk.encode('utf-8'))
            if self.raw_size > 65536:
                self.fail()
            for char in chunk:
                self.character(char)
            self.flush()
        except UnicodeError:
            self.fail()
