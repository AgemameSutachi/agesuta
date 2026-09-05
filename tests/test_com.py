from unittest.mock import MagicMock

import pytest

from agesuta.com import log_decorator


def test_log_decorator_normal_call():
    mock_logger = MagicMock()

    @log_decorator(mock_logger)
    def add(a, b):
        return a + b

    result = add(2, 3)

    assert result == 5
    assert mock_logger.debug.call_count == 2
    start_msg = mock_logger.debug.call_args_list[0][0][0]
    end_msg = mock_logger.debug.call_args_list[1][0][0]
    assert start_msg == "start: add  args: {'a': 2, 'b': 3}"
    assert end_msg == "  end: add  ret: 5"
    mock_logger.error.assert_not_called()


def test_log_decorator_exception_reraises_and_logs_error():
    mock_logger = MagicMock()

    @log_decorator(mock_logger)
    def fail():
        raise ValueError("boom")

    with pytest.raises(ValueError):
        fail()

    assert mock_logger.debug.call_count == 1
    mock_logger.error.assert_called_once()
    error_msg = mock_logger.error.call_args[0][0]
    assert error_msg == "error: fail - ValueError: boom"


def test_log_decorator_excludes_self_from_logged_args():
    mock_logger = MagicMock()

    class Foo:
        @log_decorator(mock_logger)
        def method(self, x):
            return x * 2

    foo = Foo()
    result = foo.method(10)

    assert result == 20
    start_msg = mock_logger.debug.call_args_list[0][0][0]
    assert start_msg == "start: method  args: {'x': 10}"
