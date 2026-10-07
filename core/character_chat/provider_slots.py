"""One provider budget shared by synchronous legacy admission and async workers."""
import asyncio
from collections import deque
from threading import Lock


class ProviderSlots:
    def __init__(self, limit=4):
        if type(limit) is not int or limit < 1:
            raise ValueError('positive slot limit required')
        self.limit = limit
        self._used = 0
        self._waiters = deque()
        self._lock = Lock()
        self._loop = None

    def acquire(self, blocking=False):
        """Legacy admission never blocks the application event loop."""
        if blocking:
            raise ValueError('use acquire_async instead of blocking')
        with self._lock:
            if self._used >= self.limit or self._waiters:
                return False
            self._used += 1
            return True

    async def acquire_async(self):
        loop = asyncio.get_running_loop()
        with self._lock:
            if self._loop is not None and self._loop is not loop:
                raise RuntimeError('provider slots belong to one application loop')
            self._loop = loop
            if self._used < self.limit and not self._waiters:
                self._used += 1
                return
            future = loop.create_future()
            self._waiters.append(future)
        try:
            await future
        except asyncio.CancelledError:
            # A reserved slot already handed to us must not disappear when
            # cancellation wins before the caller enters its context body.
            if future.done() and not future.cancelled():
                self.release()
            else:
                with self._lock:
                    try:
                        self._waiters.remove(future)
                    except ValueError:
                        pass  # Scheduled grant returns the reserved slot.
            raise

    def release(self):
        with self._lock:
            if not self._used:
                raise ValueError('provider slot released twice')
            while self._waiters:
                future = self._waiters.popleft()
                if not future.done():
                    future.get_loop().call_soon_threadsafe(self._grant, future)
                    return  # Transfer ownership; used count stays unchanged.
            self._used -= 1

    def _grant(self, future):
        if future.done():
            self.release()
        else:
            future.set_result(None)

    async def __aenter__(self):
        await self.acquire_async()
        return self

    async def __aexit__(self, *_):
        self.release()

