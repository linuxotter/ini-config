import pytest
from pathlib import Path
from typing import Callable, Any
import logging

from conftest import TestCfg
from ini_config import ConfigError, IniConfig


def test_normal_operation(dummy_cfg: TestCfg, tmp_path: Path) -> None:
    """Test normal parsing without errors"""

    dummy_cfg.create_rnd_cfg()
    cfg_file = dummy_cfg.make_file(tmp_path)
    cfg_parser = dummy_cfg.make_parser()
    cfg = cfg_parser.parse_file(cfg_file)
    src_params, src_types = dummy_cfg.get_config()

    for section in src_params:
        assert (attr_section := getattr(cfg, section.lower(), None)) is not None
        for k, v in src_params[section].items():
            param = getattr(attr_section, k.lower(), None)
            param_type = src_types[section][k]
            if param_type is bool:
                if param:
                    assert v in dummy_cfg.true_cases
                else:
                    assert v in dummy_cfg.false_cases
            else:
                assert param == param_type(v)
            assert type(param) is param_type


test_cases = [
    ("test", "integer", "string", int),
    ("test", "bool", "not_bool", bool),
    ("test", "float", "True", float),
]


@pytest.mark.parametrize("section, param, val, param_type", test_cases)
def test_wrong_type(
    dummy_cfg: TestCfg,
    tmp_path: Path,
    caplog,
    section: str,
    param: str,
    val: str,
    param_type: Callable[[str], Any],
) -> None:
    """Test wrong parameter type"""

    dummy_cfg.add_section(section)
    dummy_cfg.add_param(param, section, val, param_type)
    cfg_file = dummy_cfg.make_file(tmp_path)
    cfg_parser = dummy_cfg.make_parser()
    with pytest.raises(ConfigError) as err:
        cfg_parser.parse_file(cfg_file)

    if param_type.__name__ == "bool":
        param_type_str = "_str_to_bool"
    else:
        param_type_str = param_type.__name__

    assert (
        f"Error converting parameter `{section}.{param}`=`{val}` "
        f"to type `{param_type_str}`"
    ) in caplog.text
    assert str(err.value) == (
        f"Parameter `{section}.{param}` is missing or it's value is incorrect, "
        "default value is not set"
    )


def test_empty_section(dummy_cfg: TestCfg, tmp_path: Path) -> None:
    """Test parsing empty section in file"""

    dummy_cfg.add_section("Empty")
    cfg_file = dummy_cfg.make_file(tmp_path)
    cfg_parser = dummy_cfg.make_parser()

    cfg = cfg_parser.parse_file(cfg_file)

    assert hasattr(cfg, "empty")


def test_main_section(dummy_cfg: TestCfg, tmp_path: Path) -> None:
    """Test MAIN section parameters"""

    dummy_cfg.add_section("maiN")
    dummy_cfg.add_param("param1", "maiN", 345, str)
    dummy_cfg.add_section("section")
    dummy_cfg.add_param("param1", "section", "hooy", str)
    cfg_file = dummy_cfg.make_file(tmp_path)
    cfg_parser = dummy_cfg.make_parser()
    cfg = cfg_parser.parse_file(cfg_file)

    assert hasattr(cfg, "param1")
    assert getattr(cfg, "param1") == str(345)
    assert (param := getattr(cfg, "section"))
    assert hasattr(param, "param1") and getattr(param, "param1") == "hooy"


def test_repeating_sections(dummy_cfg: TestCfg, tmp_path: Path) -> None:
    """Test duplicate sections"""

    dummy_cfg.add_section("section_1")
    dummy_cfg.add_param("param_1", "section_1", 345, int)
    dummy_cfg.add_section("SECTION_1")
    dummy_cfg.add_param("param_2", "SECTION_1", 765, int)
    dummy_cfg.add_section("secTion_1")
    dummy_cfg.add_param("param_3", "secTion_1", 323, int)

    cfg_file = dummy_cfg.make_file(tmp_path)

    dummy_cfg.clear()
    dummy_cfg.add_section("section_1")
    dummy_cfg.add_param("param_1", "section_1", 345, int)
    dummy_cfg.add_param("param_2", "section_1", 345, int)
    dummy_cfg.add_param("param_3", "section_1", 345, int)

    cfg_parser = dummy_cfg.make_parser()

    with pytest.raises(ConfigError) as err:
        cfg_parser.parse_file(cfg_file)

    assert f"Error parsing configuration file `{cfg_file}` :" in str(err.value)


def test_params_without_values(dummy_cfg: TestCfg, tmp_path: Path) -> None:
    """Test parameters without defined values"""

    cfg_file = tmp_path / "tmp_cfg"
    with open(cfg_file, "w") as f:
        f.write("[main]\nparam1")

    dummy_cfg.add_section("main")
    dummy_cfg.add_param("param1", "main", 123, int)
    cfg_parser = dummy_cfg.make_parser()

    with pytest.raises(ConfigError) as err:
        cfg_parser.parse_file(str(cfg_file))

    assert f"Error parsing configuration file `{cfg_file}` :" in str(err.value)


def test_repeating_params_in_file(dummy_cfg: TestCfg, tmp_path: Path) -> None:
    """Test duplicate parameters in same file section"""

    cfg_file = tmp_path / "tmp_cfg"
    with open(cfg_file, "w") as f:
        f.write("[main]\nparam1=123\nPARAM1=456\nPaRaM1=789")

    dummy_cfg.add_section("main")
    dummy_cfg.add_param("param1", "main", 789, int)
    cfg_parser = dummy_cfg.make_parser()

    with pytest.raises(ConfigError) as err:
        cfg_parser.parse_file(str(cfg_file))

    assert f"Error parsing configuration file `{cfg_file}` :" in str(err.value)


def test_repeating_params_in_parser(dummy_cfg: TestCfg) -> None:
    """Test repeating parameters in parser tree"""

    dummy_cfg.add_section("main")
    dummy_cfg.add_param("param1", "main", 123, int)
    dummy_cfg.add_param("Param1", "main", 123, int)

    with pytest.raises(ConfigError) as err:
        dummy_cfg.make_parser()

    assert str(err.value) == (
        "Duplicate parameter `main.param1` in expected configuration file structure"
    )


def test_wrong_default_value(dummy_cfg: TestCfg) -> None:
    """Test default value with wrong type"""

    dummy_cfg.add_section("main")
    dummy_cfg.add_param("param1", "main", 123, int, default="string")

    with pytest.raises(ConfigError) as err:
        dummy_cfg.make_parser()

    assert str(err.value) == (
        "Error converting default value for parameter `main.param1` to type `int`"
    )


def test_no_value_with_default(dummy_cfg: TestCfg, tmp_path: Path) -> None:
    """Test parameter missing from cfg file with default value set"""

    dummy_cfg.add_section("main")
    cfg_file = dummy_cfg.make_file(tmp_path)
    dummy_cfg.add_param("param1", "main", "123", int, default=123)
    cfg_parser = dummy_cfg.make_parser()

    cfg = cfg_parser.parse_file(Path(cfg_file))

    assert getattr(cfg, "param1", None) == 123


def test_wrong_value_with_default(dummy_cfg: TestCfg, tmp_path: Path) -> None:
    """Test parameter with wrong value in cfg file and defined default"""

    dummy_cfg.add_section("main")
    dummy_cfg.add_param("param1", "main", "string", int, 345)
    cfg_file = dummy_cfg.make_file(tmp_path)
    cfg_parser = dummy_cfg.make_parser()

    cfg = cfg_parser.parse_file(cfg_file)

    assert getattr(cfg, "param1") == 345


def test_empty_string_param(dummy_cfg: TestCfg, tmp_path: Path) -> None:
    """Test param with empty string value"""

    dummy_cfg.add_section("main")
    dummy_cfg.add_param("param1", "main", "", str, 123)
    cfg_file = dummy_cfg.make_file(tmp_path)
    cfg_parser = dummy_cfg.make_parser()
    cfg = cfg_parser.parse_file(cfg_file)

    assert getattr(cfg, "param1") == ""


def test_unknown_params(
    dummy_cfg: TestCfg,
    tmp_path: Path,
    caplog,
) -> None:
    """Test params not defined in parser tree"""

    dummy_cfg.create_rnd_cfg()
    cfg_file = dummy_cfg.make_file(tmp_path)
    cfg_parser = dummy_cfg.make_parser()

    with open(cfg_file, "a") as f:
        f.write("[main]\nunknown_param1=10\n[empty]")

    cfg_parser.parse_file(cfg_file)

    assert (
        "Empty section `empty` is not defined in expected "
        "configuration file structure. Ignoring"
    ) in caplog.text
    assert "Unknown parameter `main.unknown_param1`" in caplog.text
    assert "DEFAULT" not in caplog.text


test_cases = [
    ("str with space", None, "is not a valid Python identifier"),
    ("", None, "empty string"),
    ("@wrong_name", None, "is not a valid Python identifier"),
    ("1wrong_name", None, "is not a valid Python identifier"),
    ("class", None, "is a Python keyword"),
    (123, None, "Section name `123` is not a string"),
    ("str with space", "str_with_space", None),
    ("@wrong_name", "correct_name", None),
    (123, "correct_name", "Section name `123` is not a string"),
    ("123", 123, "Incorrect attribute name for section `123` : `123` is not a string"),
]


@pytest.mark.parametrize("section_name, attr_name, err_msg", test_cases)
def test_section_names(
    dummy_cfg: TestCfg,
    tmp_path: Path,
    section_name: Any,
    attr_name: Any | None,
    err_msg: str | None,
) -> None:
    """Тест названий секций с пробелами"""

    dummy_cfg.add_section(section_name, attr_name)
    if err_msg:
        with pytest.raises(ConfigError) as err:
            dummy_cfg.make_parser()

        assert err_msg in str(err.value)

    else:
        cfg_file = dummy_cfg.make_file(tmp_path)
        cfg_parser = dummy_cfg.make_parser()
        cfg = cfg_parser.parse_file(cfg_file)

        assert (attr_name) is not None
        assert hasattr(cfg, attr_name)


test_cases = [
    ("str with space", None, "is not a valid Python identifier"),
    ("", None, "empty string"),
    ("@wrong_name", None, "is not a valid Python identifier"),
    ("1wrong_name", None, "is not a valid Python identifier"),
    ("class", None, "is a Python keyword"),
    (123, None, "Parameter name `main.123` is not a string"),
    ("str with space", "str_with_space", None),
    ("@wrong_name", "correct_name", None),
    (123, "correct_name", "Parameter name `main.123` is not a string"),
    (
        "123",
        123,
        ("Incorrect attribute name for parameter `main.123` : `123` is not a string"),
    ),
]


@pytest.mark.parametrize("param_name, attr_name, err_msg", test_cases)
def test_param_names(
    dummy_cfg: TestCfg,
    tmp_path: Path,
    param_name: Any,
    attr_name: Any | None,
    err_msg: str | None,
) -> None:

    dummy_cfg.add_section("main")
    dummy_cfg.add_param(param_name, "main", "value", str, attr_name=attr_name)

    if err_msg:
        with pytest.raises(ConfigError) as err:
            dummy_cfg.make_parser()

        assert err_msg in str(err.value)

    else:
        cfg_file = dummy_cfg.make_file(tmp_path)
        cfg_parser = dummy_cfg.make_parser()
        cfg = cfg_parser.parse_file(cfg_file)

        assert attr_name is not None
        assert getattr(cfg, attr_name) == "value"


test_cases = [
    ("yes", None, True),
    ("yes", "TRUE", True),
    ("", True, True),
    ("disable", "on", False),
    (1, False, True),
    ("off", "on", False),
    ("", 0, False),
]


@pytest.mark.parametrize("val, default, expected_val", test_cases)
def test_bool(
    dummy_cfg: TestCfg, tmp_path: Path, val: str, default: Any, expected_val: bool
) -> None:

    dummy_cfg.add_section("main")
    dummy_cfg.add_param("bool", "main", val, bool, default)
    cfg_parser = dummy_cfg.make_parser()
    cfg_file = dummy_cfg.make_file(tmp_path)
    cfg = cfg_parser.parse_file(cfg_file)

    assert getattr(cfg, "bool") == expected_val


test_cases = [(0, int), (0.0, float), ("", str), (False, bool)]


@pytest.mark.parametrize("default_val, param_type", test_cases)
def test_default_values(
    dummy_cfg: TestCfg,
    tmp_path: Path,
    default_val: Any,
    param_type: Callable[[Any], Any],
) -> None:

    dummy_cfg.add_section("main")
    dummy_cfg.add_param("param1", "main", "", param_type, default_val)
    cfg_file = dummy_cfg.make_file(tmp_path)
    cfg_parser = dummy_cfg.make_parser()
    cfg = cfg_parser.parse_file(cfg_file)

    assert getattr(cfg, "param1") == default_val


test_cases = [
    (0, 1, 1, None),
    (5, None, 5, None),
    (-23, 7, 7, None),
    ("", 2, 2, None),
    ("", None, None, "Parameter `main.param1` is missing or it's value is incorrect"),
    ("0", None, None, "Parameter `main.param1` is missing or it's value is incorrect"),
    (
        "-23",
        None,
        None,
        "Parameter `main.param1` is missing or it's value is incorrect",
    ),
    ("no", None, None, "Parameter `main.param1` is missing or it's value is incorrect"),
    (1, 0, None, "Error converting default value for parameter `main.param1`"),
]


@pytest.mark.parametrize("val, default_val, expected_val, err_msg", test_cases)
def test_user_conversion(
    dummy_cfg: TestCfg,
    tmp_path: Path,
    positive_int: Callable[[Any], Any],
    val: Any,
    default_val: Any,
    expected_val: Any,
    err_msg: str | None,
) -> None:

    dummy_cfg.add_section("main")
    dummy_cfg.add_param("param1", "main", val, positive_int, default_val)
    cfg_file = dummy_cfg.make_file(tmp_path)

    if err_msg is None:
        cfg_parser = dummy_cfg.make_parser()
        cfg = cfg_parser.parse_file(cfg_file)
        assert getattr(cfg, "param1") == expected_val

    else:
        with pytest.raises(ConfigError) as err:
            cfg_parser = dummy_cfg.make_parser()
            cfg = cfg_parser.parse_file(cfg_file)

        assert err_msg in str(err.value)


test_cases = ["__dict__", "__class__", "items", "__str__"]


@pytest.mark.parametrize("attr_name", test_cases)
def test_attr_name_overrides_attributes(dummy_cfg: TestCfg, attr_name: str) -> None:

    dummy_cfg.add_section("main")
    dummy_cfg.add_param("param1", "main", "value", str, attr_name="__dict__")

    with pytest.raises(ConfigError) as err:
        dummy_cfg.make_parser()

    assert "is a Python magic method" in str(err.value)


def test_param_type(dummy_cfg: TestCfg) -> None:

    dummy_cfg.add_section("main")
    dummy_cfg.add_param(
        name="param_1",
        section="main",
        val=123,
        type=None,  # pyright: ignore[reportArgumentType]
    )

    with pytest.raises(ConfigError) as err:
        dummy_cfg.make_parser()

    assert str(err.value) == (
        "Parameter type `main.param_1` is instance of `None`, expected callable"
    )


def test_repeating_attr_names(dummy_cfg: TestCfg, tmp_path: Path) -> None:

    dummy_cfg.add_section("main", "duplicate")
    dummy_cfg.add_section("log", "duplicate")
    cfg_file = dummy_cfg.make_file(tmp_path)
    cfg_parser = dummy_cfg.make_parser()
    cfg = cfg_parser.parse_file(cfg_file)

    assert hasattr(cfg, "duplicate")


def test_default_value_in_logs(dummy_cfg: TestCfg, tmp_path, caplog) -> None:

    def _test_type(val: Any) -> bool:
        if not val:
            raise ValueError

        return True

    test_logger = logging.getLogger()
    test_logger.setLevel(logging.DEBUG)

    dummy_cfg.add_section("main")
    dummy_cfg.add_param("test_param", "main", "", _test_type, default="test_val")
    cfg_file = dummy_cfg.make_file(tmp_path)
    cfg_parser = dummy_cfg.make_parser()
    cfg = cfg_parser.parse_file(cfg_file)

    assert hasattr(cfg, "test_param") and getattr(cfg, "test_param")
    assert "using default value : `test_val`" in caplog.text


def test_empty_cfg_file(dummy_cfg: TestCfg, tmp_path: Path) -> None:

    cfg_file = tmp_path / "cfg_file"
    with open(cfg_file, "w"):
        pass

    dummy_cfg.add_section("main")
    dummy_cfg.add_param("test_param", "main", "test", str, default="test")
    cfg_parser = dummy_cfg.make_parser()
    cfg = cfg_parser.parse_file(cfg_file)
    assert hasattr(cfg, "test_param") and getattr(cfg, "test_param") == "test"


def test_parameter_with_default_val_with_no_section_in_cfg(
    tmp_path: Path, dummy_cfg: TestCfg
) -> None:

    cfg_file = tmp_path / "cfg_file"
    with open(cfg_file, "w") as f:
        f.write("[main]\ntest_param_1 = test\n")

    dummy_cfg.add_section("main")
    dummy_cfg.add_param("test_param_1", "main", "test", str)
    dummy_cfg.add_section("ghost_section")
    dummy_cfg.add_param(
        "test_param_2", "ghost_section", "test_val", str, default="test_val"
    )
    cfg_parser = dummy_cfg.make_parser()
    cfg = cfg_parser.parse_file(cfg_file)

    assert getattr(cfg, "test_param_1") == "test"
    assert (section := getattr(cfg, "ghost_section")) and getattr(
        section, "test_param_2"
    ) == "test_val"


def test_no_cfg_files_with_all_defult_params(caplog) -> None:

    cfg_parser = IniConfig()
    cfg_parser.add_section("main").add_param(
        "default_param_1", param_type=int, default=1
    ).add_param("default_param_2", param_type=int, default=2)
    cfg_parser.add_section("test").add_param(
        "default_param_3", param_type=int, default=3
    ).add_param("default_param_4", param_type=int, default=4)

    cfg = cfg_parser.parse_file("not_exists")

    assert "Error reading file `not_exists` :" in caplog.text
    assert getattr(cfg, "default_param_1") == 1
    assert getattr(cfg, "default_param_2") == 2

    assert (test_section := getattr(cfg, "test"))
    assert getattr(test_section, "default_param_3") == 3
    assert getattr(test_section, "default_param_4") == 4


def test_no_section_for_default_params(
    dummy_cfg: TestCfg, tmp_path: Path, caplog
) -> None:

    test_logger = logging.getLogger()
    test_logger.setLevel(logging.DEBUG)

    dummy_cfg.add_section("main")
    dummy_cfg.add_param("required_param", "main", "required_val", str)
    cfg_file = dummy_cfg.make_file(tmp_path)
    cfg_parser = dummy_cfg.make_parser()

    cfg_parser.add_section("test").add_param("default_param", default="default_val")

    cfg = cfg_parser.parse_file(cfg_file)

    assert getattr(cfg, "required_param") == "required_val"
    assert (test_section := getattr(cfg, "test"))
    assert getattr(test_section, "default_param") == "default_val"
    assert f"Section `test` not found in file `{cfg_file}`" in caplog.text
