"""C4 JSON commands and bounded, detachable event subscriptions."""
import asyncio
import json
from uuid import uuid4

from fastapi.responses import StreamingResponse
from core.character_chat.models import CharacterSessionError


def display_mode(payload):
    mode = payload.get('display_mode')
    delivery = payload.get('delivery')
    if 'delivery' in payload and delivery not in ('stream', 'non_stream'):
        raise CharacterSessionError('INVALID_REQUEST')
    if 'display_mode' not in payload:
        return 'instant' if delivery == 'non_stream' else 'stream'
    if not isinstance(mode, str) or mode not in ('stream', 'gaps', 'instant'):
        raise CharacterSessionError('INVALID_REQUEST')
    if delivery is not None and delivery != ('stream' if mode == 'stream' else 'non_stream'):
        raise CharacterSessionError('INVALID_REQUEST')
    return mode


class GroupSubscription:
    """Owns delivery frames, never the generation worker or its provider call."""
    def __init__(self, service, sid):
        self.service = service
        self.sid = sid
        self.stream_id = str(uuid4())
        self.sequence = 0
        self.queue = asyncio.Queue(maxsize=64)
        self.bytes = 0
        self.closed = False
        self.detach = service.subscribe(sid, self.emit)
        try:
            state = service._event_state(sid)
            self.emit('ready', {'session_id': sid, 'revision': state['revision']})
        except Exception:
            self.close()
            raise

    def emit(self, name, data):
        if self.closed:
            return
        self.sequence += 1
        body = {**data, 'stream_id': self.stream_id, 'event_seq': self.sequence}
        frame = 'event: ' + name + '\ndata: ' + json.dumps(body, ensure_ascii=False) + '\n\n'
        size = len(frame.encode('utf-8'))
        if self.queue.full() or self.bytes + size > 256 * 1024:
            self.close()
            return
        self.queue.put_nowait((frame, size))
        self.bytes += size

    def close(self):
        if not self.closed:
            self.closed = True
            self.detach()
            while not self.queue.empty():
                self.queue.get_nowait()
            self.bytes = 0

    async def events(self, request):
        loop = asyncio.get_running_loop()
        heartbeat = loop.time()
        try:
            while not self.closed:
                if await request.is_disconnected():
                    break
                try:
                    frame, size = await asyncio.wait_for(self.queue.get(), .2)
                except TimeoutError:
                    if loop.time() - heartbeat >= 15:
                        yield ': keepalive\n\n'
                        heartbeat = loop.time()
                    continue
                if self.closed:
                    break
                self.bytes -= size
                yield frame
        finally:
            self.close()

    def response(self, request):
        return StreamingResponse(self.events(request), media_type='text/event-stream',
            headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})
