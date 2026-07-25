import logging
import unittest

from utils.sys_logger import CustomFormatter


class SysLoggerTests(unittest.TestCase):
    def test_formatter_keeps_exception_details(self):
        try:
            raise RuntimeError("diagnostic detail")
        except RuntimeError:
            record = logging.LogRecord(
                name="AliveWorld",
                level=logging.ERROR,
                pathname=__file__,
                lineno=1,
                msg="startup failed",
                args=(),
                exc_info=__import__("sys").exc_info(),
            )

        formatted = CustomFormatter().format(record)
        self.assertIn("startup failed", formatted)
        self.assertIn("RuntimeError: diagnostic detail", formatted)


if __name__ == "__main__":
    unittest.main()
