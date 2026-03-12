import pytest
import logging

from ini_config import IniConfig


test_cases = [
    (None, "English language is set"),
    ("en", "English language is set"),
    ("default", "English language is set"),
    ("ru", "Локаль установлена, lang=ru"),
    ("ru_RU", "Локаль установлена, lang=ru_RU"),
    ("locale", "Локаль установлена, lang=None"),
    ("invalid", "Files for lang=invalid not found in"),
]


@pytest.mark.parametrize("lang, log_msg", test_cases)
def test_set_locale(caplog, lang: str | None, log_msg: str) -> None:

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    IniConfig.set_language(lang)
    assert log_msg in caplog.text
