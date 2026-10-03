"""Single-pass bounded reply preview lexer; final JSON validation is independent."""
from .models import CharacterSessionError


class ReplyPreview:
    def __init__(self, emit):
        self.emit = emit
        self.stack = []
        self.in_string = False
        self.string = ''
        self.escape = False
        self.unicode = None
        self.high = None
        self.visible = False
        self.size = 0
        self.reply_size = 0
        self.root_started = False

    def fail(self):
        raise CharacterSessionError('CONTRACT_INVALID')

    def decoded(self, char, out):
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
        if self.visible:
            self.reply_size += 1
            if self.reply_size > 8000:
                self.fail()
            out.append(char)
        else:
            self.string += char

    def feed(self, chunk):
        self.size += len(chunk.encode('utf-8'))
        if self.size > 65536:
            self.fail()
        out = []
        escapes = {'"': '"', '\\': '\\', '/': '/', 'b': '\b', 'f': '\f', 'n': '\n', 'r': '\r', 't': '\t'}
        for c in chunk:
            if self.in_string:
                if self.unicode is not None:
                    if c not in '0123456789abcdefABCDEF':
                        self.fail()
                    self.unicode += c
                    if len(self.unicode) == 4:
                        self.decoded(chr(int(self.unicode, 16)), out)
                        self.unicode = None
                    continue
                if self.escape:
                    self.escape = False
                    if c == 'u':
                        self.unicode = ''
                    elif c in escapes:
                        self.decoded(escapes[c], out)
                    else:
                        self.fail()
                    continue
                if c == '\\':
                    self.escape = True
                elif c == '"':
                    if self.high is not None:
                        self.fail()
                    self.in_string = False
                    if self.stack and self.stack[-1]['state'] == 'key':
                        top = self.stack[-1]
                        if self.string in top['seen']:
                            self.fail()
                        if len(self.stack) == 1 and self.string not in {'reply', 'ledger_ops'}:
                            self.fail()
                        top['seen'].add(self.string)
                        top['key'] = self.string
                        top['state'] = 'colon'
                    elif self.stack:
                        self.stack[-1]['state'] = 'after'
                    self.visible = False
                else:
                    if ord(c) < 32:
                        self.fail()
                    self.decoded(c, out)
                continue
            if c.isspace():
                continue
            if not self.root_started:
                if c != '{':
                    self.fail()
                self.root_started = True
                self.stack.append({'state': 'key', 'key': '', 'seen': set(), 'object': True})
                continue
            if not self.stack:
                self.fail()
            top = self.stack[-1]
            if c == '"':
                self.in_string, self.string = True, ''
                self.visible = len(self.stack) == 1 and top['state'] == 'value' and top['key'] == 'reply'
            elif c == ':':
                if top['state'] != 'colon':
                    self.fail()
                top['state'] = 'value'
            elif c in '{[':
                self.stack.append({'state': 'key' if c == '{' else 'value', 'key': '', 'seen': set(), 'object': c == '{'})
                if len(self.stack) > 12:
                    self.fail()
            elif c in '}]':
                if (c == '}') != top['object']:
                    self.fail()
                self.stack.pop()
                if self.stack:
                    self.stack[-1]['state'] = 'after'
            elif c == ',':
                top['state'] = 'key' if top['object'] else 'value'
            elif top['state'] == 'value' and len(self.stack) == 1 and top['key'] == 'reply':
                self.fail()
        if out:
            body = ''.join(out)
            for start in range(0, len(body), 2048):
                self.emit(body[start:start + 2048])
