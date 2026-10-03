"""SSE delivery around existing synchronous, aggregate-owned transactions.

Disconnecting abandons previews, not a transaction already executing. No retry,
cancel registry or reconnect replay is implied by this small transport adapter.
"""

import asyncio
import copy
import json
import queue
import threading
import time

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from core.session_manager import MutationBusyError, mutation_guard


def workshop_stream_response(workshop_id, operation):
    def guarded(emit):
        try:
            with mutation_guard("workshop", workshop_id):
                return operation(emit)
        except MutationBusyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    return stream_response(guarded, identity=workshop_id)


def workshop_chat_transaction(workshop, directory, operation):
    """Apply on an isolated copy; expose it only after the atomic session save."""
    candidate = copy.deepcopy(workshop)
    result = operation(candidate)
    candidate.save_session(directory)
    workshop.__dict__.clear()
    workshop.__dict__.update(candidate.__dict__)
    return result


def stream_response(operation, *, identity="", queue_size=64):
    events = queue.Queue(maxsize=queue_size)
    abandoned = threading.Event()
    finished = threading.Event()

    def emit(event, data):
        if abandoned.is_set():
            return
        # Slow/dead consumers must not keep a paid generation's transaction locked.
        try:
            events.put((event, copy.deepcopy(data)), timeout=0.5)
        except queue.Full:
            abandoned.set()

    def run():
        try:
            emit("start", {"id": identity})
            result = operation(lambda text: emit("delta", {"text": text}))
            emit("complete", result)
        except HTTPException as exc:
            message = str(exc.detail) if exc.status_code in {404, 409, 500} else "请求或模型结果无法安全完成，请重新载入核对。"
            emit("error", {"message": message, "code": exc.status_code})
        except Exception:
            # Provider details/raw responses/credentials are never SSE error bodies.
            emit("error", {"message": "生成、传输或保存异常，请重新载入核对。", "code": "generation_failed"})
        finally:
            finished.set()

    async def body():
        worker = threading.Thread(target=run, name="aliveworld-stream", daemon=True)
        worker.start()
        heartbeat = time.monotonic()
        try:
            while not (finished.is_set() and events.empty()):
                if abandoned.is_set():
                    break
                try:
                    event, data = events.get_nowait()
                except queue.Empty:
                    if time.monotonic() - heartbeat >= 10:
                        yield ": keepalive\n\n"
                        heartbeat = time.monotonic()
                    await asyncio.sleep(0.02)
                    continue
                try:
                    encoded = json.dumps(data, ensure_ascii=False)
                except Exception:
                    yield 'event: error\ndata: {"message":"传输异常，请重新载入核对。","code":"transport_failed"}\n\n'
                    break
                yield f"event: {event}\ndata: {encoded}\n\n"
                heartbeat = time.monotonic()
        finally:
            abandoned.set()

    return StreamingResponse(body(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })
