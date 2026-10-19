"""In-flight generation cancellation, independent of browser subscriptions."""
from contextlib import contextmanager
from contextvars import ContextVar
from threading import RLock
import time


class GenerationCancelled(RuntimeError):
    pass


class GenerationBusy(RuntimeError):
    pass


_lock = RLock()
_active = {}
_current = ContextVar('aliveworld_generation', default=None)


class Generation:
    def __init__(self, scope, request_id):
        self.scope = scope
        self.request_id = request_id
        self.state = 'running'
        self.retry = None


@contextmanager
def generation_scope(scope, request_id):
    task = Generation(scope, request_id)
    with _lock:
        if scope in _active:
            raise GenerationBusy('该会话仍有生成任务，请等待结束')
        _active[scope] = task
    token = _current.set(task)
    try:
        yield task
    finally:
        _current.reset(token)
        with _lock:
            if _active.get(scope) is task:
                del _active[scope]


def cancel_generation(scope, request_id):
    with _lock:
        task = _active.get(scope)
        if task is None or task.request_id != request_id:
            return {'status': 'not_running', 'request_id': request_id}
        if task.state == 'running':
            task.state = 'cancelling'
        return {'status': task.state, 'request_id': request_id}


def check_generation():
    task = _current.get()
    if task is not None:
        with _lock:
            if task.state == 'cancelling':
                raise GenerationCancelled('已停止生成，本次未完成内容未保存')


def report_retry(attempt, limit, delay):
    task = _current.get()
    if task is not None:
        with _lock:
            task.retry = {'attempt': attempt, 'limit': limit, 'deadline': time.monotonic() + delay}


def clear_retry():
    task = _current.get()
    if task is not None:
        with _lock:
            task.retry = None


def generation_status(scope, request_id):
    with _lock:
        task = _active.get(scope)
        if task is None or task.request_id != request_id:
            return {'status': 'not_running', 'request_id': request_id, 'retry': None}
        retry = task.retry
        return {'status': task.state, 'request_id': request_id,
                'retry': None if retry is None else {'attempt': retry['attempt'], 'limit': retry['limit'],
                    'remaining_seconds': max(0, retry['deadline'] - time.monotonic())}}


@contextmanager
def generation_commit():
    """Linearization point: cancellation wins only before commit begins."""
    task = _current.get()
    with _lock:
        check_generation()
        if task is not None:
            task.state = 'committing'
    yield
