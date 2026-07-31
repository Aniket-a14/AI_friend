import logging
import sys

try:
    from pythonjsonlogger.json import JsonFormatter as _JsonFormatter
except ImportError:
    from pythonjsonlogger.jsonlogger import JsonFormatter as _JsonFormatter
from datetime import UTC, datetime


class CustomJsonFormatter(_JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        if not log_record.get("timestamp"):
            # this doesn't use record.created, so it is slightly off
            now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            log_record["timestamp"] = now
        if log_record.get("level"):
            log_record["level"] = log_record["level"].upper()
        else:
            log_record["level"] = record.levelname


def setup_logging(level=logging.INFO, json_format=True):
    """
    Setup logging configuration.
    If json_format is True, logs will be in JSON format for production observability.
    """
    handler = logging.StreamHandler(sys.stdout)

    if json_format:
        formatter = CustomJsonFormatter("%(timestamp)s %(level)s %(name)s %(message)s")
        handler.setFormatter(formatter)
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(level)

    # Silence noisy loggers
    logging.getLogger("nats").setLevel(logging.WARNING)
    logging.getLogger("livekit").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
