"""Tests for structured logging configuration."""

import json
import logging

from sonos_lastfm.logging_config import setup_logging


def test_setup_logging_json_format(capsys):
    setup_logging("INFO")
    logger = logging.getLogger("test_structured")
    logger.info("test message", extra={"artist": "Radiohead"})

    output = capsys.readouterr().out
    record = json.loads(output.strip())
    assert record["message"] == "test message"
    assert record["level"] == "INFO"
    assert record["artist"] == "Radiohead"
    assert "timestamp" in record


def test_setup_logging_sets_level():
    setup_logging("WARNING")
    assert logging.getLogger().level == logging.WARNING
    # Reset
    setup_logging("INFO")


def test_setup_logging_quiets_third_party():
    setup_logging("DEBUG")
    assert logging.getLogger("httpcore").level == logging.WARNING
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("pylast").level == logging.WARNING
    assert logging.getLogger("soco").level == logging.WARNING
    # Reset
    setup_logging("INFO")
