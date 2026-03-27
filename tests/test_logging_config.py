import logging

from ktc_webscraping.logging_config import configure_logging


def test_configure_logging_uses_environment_level(monkeypatch) -> None:
    monkeypatch.setenv("KTC_LOG_LEVEL", "DEBUG")

    configure_logging()

    assert logging.getLogger().getEffectiveLevel() == logging.DEBUG
