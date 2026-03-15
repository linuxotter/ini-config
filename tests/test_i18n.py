import pytest
import logging
import os
from pathlib import Path
import re
import polib
import glob

from ini_config import IniConfig

LOCALES_DIR = Path(__name__).parent.parent / "src/ini_config/locales"
DOMAIN = "ini_config"


def test_locales_dir_structure() -> None:

    print(LOCALES_DIR.resolve())
    dir_structure = os.scandir(LOCALES_DIR.resolve())

    mo_file_mtime: float | None = None
    po_file_mtime: float | None = None
    pot_file_mtime: float | None = None

    for item in dir_structure:
        print(item.name)
        if item.is_dir():
            po_file = Path(item.path) / f"LC_MESSAGES/{DOMAIN}.po"
            mo_file = Path(str(po_file).replace(".po", ".mo"))

            # Locale dir name check
            assert re.fullmatch(r"[a-z]{2}(_[A-Z]{2})?", item.name)
            # .mo and .po files check
            assert po_file.exists()
            assert mo_file.exists()
            po_file_mtime = po_file.stat().st_mtime
            mo_file_mtime = mo_file.stat().st_mtime

        pot_file = Path(LOCALES_DIR / "ini_config.pot")
        assert pot_file.exists()
        pot_file_mtime = pot_file.stat().st_mtime

        assert po_file_mtime is not None and mo_file_mtime is not None
        assert mo_file_mtime >= po_file_mtime
        assert po_file_mtime >= pot_file_mtime


po_files = glob.glob("**/*.po", recursive=True)


@pytest.mark.parametrize("po_file", po_files)
def test_all_lines_translated(po_file: str) -> None:

    untranslated = polib.pofile(po_file).untranslated_entries()
    assert len(untranslated) == 0


@pytest.mark.parametrize("po_file", po_files)
def test_placeholders_match(po_file: str) -> None:

    pattern_1 = re.compile(r"`?{[a-z_]+}`?")
    pattern_2 = re.compile(r"`?%s`?")
    po = polib.pofile(po_file)

    for entry in po:
        src_1 = set(pattern_1.findall(entry.msgid))
        src_2 = set(pattern_2.findall(entry.msgid))
        dst_1 = set(pattern_1.findall(entry.msgstr))
        dst_2 = set(pattern_2.findall(entry.msgstr))
        assert src_1 == dst_1, f"{entry.msgid} : {entry.msgstr}"
        assert src_2 == dst_2


test_cases: list[tuple[str | None, str]] = [
    (None, "English language is set"),
    ("en", "English language is set"),
    ("default", "English language is set"),
    ("ru", "Локаль установлена, lang=`ru`"),
    ("ru_RU", "Локаль установлена, lang=`ru_RU`"),
    ("invalid", "Files for lang=`invalid` not found in"),
]


@pytest.mark.parametrize("lang, log_msg", test_cases)
def test_set_locale(caplog, lang: str | None, log_msg: str) -> None:

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    IniConfig.set_language(lang)
    assert log_msg in caplog.text
