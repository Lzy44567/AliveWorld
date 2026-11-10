import unittest
from unittest.mock import patch

from core.atomic_replace import replace_file


class AtomicReplaceTests(unittest.TestCase):
    def test_windows_contention_retries_same_atomic_operation(self):
        for code in (5, 32, 33):
            with self.subTest(code=code):
                error = PermissionError(13, 'synthetic')
                error.winerror = code
                with patch('core.atomic_replace.os.replace', side_effect=[error, None]) as replace, \
                        patch('core.atomic_replace.time.sleep') as sleep:
                    replace_file('source', 'destination')
                self.assertEqual(2, replace.call_count)
                self.assertEqual(replace.call_args_list[0], replace.call_args_list[1])
                sleep.assert_called_once_with(0.05)

    def test_persistent_windows_denial_has_bounded_wait(self):
        error = PermissionError(13, 'synthetic')
        error.winerror = 5
        with patch('core.atomic_replace.os.replace', side_effect=error) as replace, \
                patch('core.atomic_replace.time.sleep') as sleep:
            with self.assertRaises(PermissionError):
                replace_file('source', 'destination')
        self.assertEqual(3, replace.call_count)
        self.assertEqual([0.05, 0.1], [call.args[0] for call in sleep.call_args_list])

    def test_other_errors_are_not_retried(self):
        with patch('core.atomic_replace.os.replace', side_effect=OSError(28, 'full')) as replace, \
                patch('core.atomic_replace.time.sleep') as sleep:
            with self.assertRaises(OSError):
                replace_file('source', 'destination')
        replace.assert_called_once()
        sleep.assert_not_called()
