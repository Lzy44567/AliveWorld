import threading
import unittest
from core.generation_control import (
    GenerationBusy, GenerationCancelled, generation_scope,
    generation_commit, cancel_generation, check_generation, generation_status, report_retry,
)


class GenerationControlTests(unittest.TestCase):
    def test_retry_status_is_request_scoped_and_cleared_on_exit(self):
        scope = ('story', 'retry-status')
        with generation_scope(scope, 'current'):
            report_retry(1, 3, 5)
            status = generation_status(scope, 'current')
            self.assertEqual(1, status['retry']['attempt'])
            self.assertGreater(status['retry']['remaining_seconds'], 0)
            self.assertIsNone(generation_status(scope, 'old')['retry'])
        self.assertEqual('not_running', generation_status(scope, 'current')['status'])

    def test_cancel_before_commit_and_cleanup(self):
        with generation_scope(('story', 'a'), 'one'):
            self.assertEqual(cancel_generation(('story', 'a'), 'one')['status'], 'cancelling')
            with self.assertRaises(GenerationCancelled), generation_commit():
                self.fail('must not commit')
        self.assertEqual(cancel_generation(('story', 'a'), 'one')['status'], 'not_running')

    def test_commit_wins_cancel_does_not_claim_success(self):
        with generation_scope(('workshop', 'a'), 'one'), generation_commit():
            self.assertEqual(cancel_generation(('workshop', 'a'), 'one')['status'], 'committing')
            check_generation()

    def test_scope_and_request_identity_isolation(self):
        with generation_scope(('story', 'a'), 'new'):
            self.assertEqual(cancel_generation(('story', 'a'), 'old')['status'], 'not_running')
            with generation_scope(('workshop', 'a'), 'other'):
                cancel_generation(('story', 'a'), 'new')
                check_generation()
            with self.assertRaises(GenerationCancelled):
                check_generation()
            with self.assertRaises(GenerationBusy), generation_scope(('story', 'a'), 'next'):
                pass

    def test_cross_thread_cancel_and_error_cleanup(self):
        with self.assertRaises(GenerationCancelled):
            with generation_scope(('story', 'thread'), 'one'):
                worker = threading.Thread(target=cancel_generation, args=(('story', 'thread'), 'one'))
                worker.start()
                worker.join()
                check_generation()
        with generation_scope(('story', 'thread'), 'two'):
            check_generation()

    def test_no_generation_context_does_not_change_existing_mutations(self):
        check_generation()
        with generation_commit():
            pass

    def test_sdk_stream_cancel_closes_provider_and_never_retries(self):
        from tests.test_streaming import chunk, stream_engine
        def chunks():
            yield chunk('{"story_text":"partial')
            cancel_generation(('workshop', 'sdk'), 'request')
            yield chunk('"}', 'stop')
        engine, stream, create, _ = stream_engine(chunks())
        with generation_scope(('workshop', 'sdk'), 'request'), self.assertRaises(GenerationCancelled):
            engine.chat_json('JSON', 'test', on_text_delta=lambda _: None)
        self.assertTrue(stream.closed)
        self.assertEqual(create.call_count, 1)
