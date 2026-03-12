import pytest
from ini_config import IniConfig, ConfigError
from pathlib import Path
import os


def test_no_cfg_file_with_required_params(caplog) -> None:
    """Missing cfg file with required params"""

    config_parser = IniConfig()
    config_parser.add_section("main").add_param("required_param")

    with pytest.raises(ConfigError) as err:
        config_parser.parse_file("not_exists")

    assert err.value.__str__() == (
        "Parameter main.required_param is missing or it's value is incorrect, "
        "default value is not set"
    )

    assert "Error reading file not_exists :" in caplog.text


def test_unreadable_cfg_file(tmp_path: Path, caplog) -> None:
    """Cfg file is not readable"""

    unreadable_cfg = tmp_path / "unreadable_cfg"
    with open(unreadable_cfg, "w"):
        pass
    os.chmod(unreadable_cfg, 0x000)

    config_parser = IniConfig()
    config_parser.add_section("main").add_param("required_param")

    with pytest.raises(ConfigError) as err:
        config_parser.parse_file(unreadable_cfg)

    assert err.value.__str__() == (
        "Parameter main.required_param is missing or it's value is incorrect, "
        "default value is not set"
    )
    assert f"Error reading file {unreadable_cfg} :" in caplog.text

    os.chmod(unreadable_cfg, 0x777)


def test_unreadable_cfg_dir(tmp_path: Path, caplog) -> None:
    """Config dir is not readable"""

    unreadable_cfg_dir = tmp_path
    os.chmod(tmp_path, 0x000)

    config_parser = IniConfig()
    config_parser.add_section("main").add_param("required_param")
    with pytest.raises(ConfigError) as err:
        config_parser.parse_file(unreadable_cfg_dir / "cfg_file")

    assert err.value.__str__() == (
        "Parameter main.required_param is missing or it's value is incorrect, "
        "default value is not set"
    )
    assert f"Error reading file {unreadable_cfg_dir}/cfg_file" in caplog.text
    os.chmod(tmp_path, 0x777)


def test_corrupted_cfg_file(tmp_path: Path) -> None:
    """Config file contains corrupted data"""

    corrupted_cfg = tmp_path / "corrupted_cfg_file"
    with open(corrupted_cfg, "w") as f:
        f.write("corrupted_data")

    config = IniConfig()
    with pytest.raises(ConfigError) as err:
        config.parse_file(str(corrupted_cfg))

    assert f"Error parsing configuration file {corrupted_cfg}" in str(err.value)
