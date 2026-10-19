import asyncio
import unittest
from unittest.mock import Mock

import httpx
from openai import APIConnectionError, APIStatusError
from core.provider_retry import request_with_retry, request_with_retry_async, retry_delay
from core.generation_control import generation_scope, cancel_generation, GenerationCancelled


def failure(status=503, code='', retry_after=None):
    response = httpx.Response(status, request=httpx.Request('POST', 'https://example.test/v1'),
                              headers={'retry-after': str(retry_after)} if retry_after is not None else {})
    return APIStatusError('temporary', response=response, body={'error': {'code': code}})


class RetryTests(unittest.TestCase):
    def test_limit_and_default_off(self):
        call = Mock(side_effect=failure())
        with self.assertRaises(APIStatusError):
            request_with_retry(call)
        self.assertEqual(1, call.call_count)
        call.reset_mock(); wait = Mock(); notify = Mock()
        with self.assertRaises(APIStatusError):
            request_with_retry(call, 3, wait=wait, notify=notify)
        self.assertEqual(4, call.call_count)
        self.assertEqual([1, 2, 4], [c.args[0] for c in wait.call_args_list])
        self.assertEqual((3, 3, 4), notify.call_args.args)

    def test_success_and_retry_after(self):
        call = Mock(side_effect=[failure(429, retry_after=7), 'ok']); wait = Mock()
        self.assertEqual('ok', request_with_retry(call, 2, wait=wait))
        wait.assert_called_once_with(7)
        self.assertIsNone(retry_delay(failure(429, retry_after=120), 1))

    def test_do_not_retry_permanent_or_unknown_outcomes(self):
        for error in [failure(401), failure(400), failure(429, 'insufficient_quota'),
                      failure(429, 'balance_not_enough'), ValueError('invalid JSON')]:
            self.assertIsNone(retry_delay(error, 1))
        error = APIConnectionError(request=httpx.Request('POST', 'https://example.test'))
        error.__cause__ = httpx.ReadTimeout('response lost')
        self.assertIsNone(retry_delay(error, 1))
        error.__cause__ = httpx.ConnectError('not connected')
        self.assertEqual(1, retry_delay(error, 1))

    def test_cancel_during_wait_prevents_next_call(self):
        call = Mock(side_effect=failure())
        with generation_scope(('story', 'test'), 'request'):
            with self.assertRaises(GenerationCancelled):
                request_with_retry(call, 3, wait=lambda _: cancel_generation(('story', 'test'), 'request'))
        self.assertEqual(1, call.call_count)


class AsyncRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_interrupts_backoff(self):
        started = asyncio.Event(); calls = []
        async def call():
            calls.append(1); raise failure(503, retry_after=30)
        async def wait(seconds):
            started.set(); await asyncio.sleep(seconds)
        task = asyncio.create_task(request_with_retry_async(call, 3, wait=wait))
        await started.wait(); task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(1, len(calls))
