import logging

from app.logging_config import CustomJsonFormatter, setup_logging


def test_custom_json_formatter_adds_timestamp_and_uppercases_level():
    formatter = CustomJsonFormatter("%(timestamp)s %(level)s %(name)s %(message)s")
    record = logging.LogRecord("test.logger", logging.INFO, __file__, 1, "hello", (), None)
    payload = {"level": "info"}

    formatter.add_fields(payload, record, {})

    assert "timestamp" in payload
    assert payload["level"] == "INFO"


def test_custom_json_formatter_uses_record_level_when_missing():
    formatter = CustomJsonFormatter("%(timestamp)s %(level)s %(name)s %(message)s")
    record = logging.LogRecord("test.logger", logging.WARNING, __file__, 1, "warn", (), None)
    payload = {}

    formatter.add_fields(payload, record, {})

    assert payload["level"] == "WARNING"


def test_setup_logging_json_mode_configures_root_and_noise_loggers():
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    try:
        setup_logging(level=logging.DEBUG, json_format=True)
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, CustomJsonFormatter)
        assert root.level == logging.DEBUG
        assert logging.getLogger("nats").level == logging.WARNING
        assert logging.getLogger("livekit").level == logging.WARNING
        assert logging.getLogger("httpx").level == logging.WARNING
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)


def test_setup_logging_text_mode_uses_standard_formatter():
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    try:
        setup_logging(level=logging.ERROR, json_format=False)
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, logging.Formatter)
        assert not isinstance(root.handlers[0].formatter, CustomJsonFormatter)
        assert root.level == logging.ERROR
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)
