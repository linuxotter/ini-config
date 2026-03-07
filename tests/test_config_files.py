import pytest
from ini_config import IniConfig, ConfigError
from pathlib import Path
import os


def test_no_cfg_file() -> None:
    """Тест отстутствия файла конфигурации"""

    config = IniConfig()
    with pytest.raises(ConfigError) as err:
        config.parse_file("not_exists")

    assert err.value.__str__() == "Файл не найден: not_exists"


def test_unreadable_cfg_file(tmp_path: Path) -> None:
    """Тест отстутствия прав на чтение файла"""

    unreadable_cfg = tmp_path / "unreadable_cfg"
    with open(unreadable_cfg, "w"):
        pass
    os.chmod(unreadable_cfg, 0x000)

    config = IniConfig()
    with pytest.raises(ConfigError) as err:
        config.parse_file(str(unreadable_cfg))
    os.chmod(unreadable_cfg, 0x777)
    assert f"Ошибка чтения файла {unreadable_cfg}" in str(err.value)


def test_unreadable_cfg_dir(tmp_path: Path) -> None:
    """Каталог с файлом конфигурации недоступен для чтения"""

    unreadable_cfg_dir = tmp_path
    os.chmod(tmp_path, 0x000)

    config = IniConfig()
    with pytest.raises(ConfigError) as err:
        config.parse_file(str(unreadable_cfg_dir / "cfg_file"))
    os.chmod(tmp_path, 0x777)
    assert f"Ошибка чтения файла {unreadable_cfg_dir}/cfg_file" in str(err.value)


def test_corrupted_cfg_file(tmp_path: Path) -> None:
    """Тест файла конфигурации с неверными данными"""

    corrupted_cfg = tmp_path / "corrupted_cfg_file"
    with open(corrupted_cfg, "w") as f:
        f.write("corrupted_data")

    config = IniConfig()
    with pytest.raises(ConfigError) as err:
        config.parse_file(str(corrupted_cfg))

    assert f"Ошибка разбора файла конфигурации {corrupted_cfg}" in str(err.value)
