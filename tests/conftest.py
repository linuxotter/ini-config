import pytest
import random
import string
from typing import Any, Callable
from pathlib import Path

from ini_config import IniConfig


class TestCfg:
    """Эмуляция загрузки конфигурации из файла"""

    true_cases = ("true", "yes", "1", "on", "enable")
    false_cases = ("false", "no", "0", "off", "disable")

    def __init__(self) -> None:

        self._types: tuple[Callable[[str], Any], ...] = (int, str, bool)
        self._config: dict[str, dict[str, Any]] = {}
        self._param_types: dict[str, dict[str, Callable[[str], Any]]] = {}
        self._default: dict[str, dict[str, Any]] = {}
        self._sect_attr_name: dict[str, str | None] = {}
        self._param_attr_name: dict[str, dict[str, str | None]] = {}

    def create_rnd_cfg(self) -> None:
        """Создание случайной корректной конфигурации"""

        for section_num in range(1, random.randint(2, 5)):
            section_name = f"Section_{section_num}"

            for param_num in range(1, random.randint(2, 10)):
                param_name = f"Param_{param_num}"
                if not self._param_types.get(section_name):
                    self._param_types[section_name] = {}
                    self._config[section_name] = {}
                    self._default[section_name] = {}
                    self._param_attr_name[section_name] = {}

                param_type = random.choice(self._types)
                if param_type is int:
                    value = random.randint(1, 99)
                elif param_type is bool:
                    value = random.choice(self.true_cases + self.false_cases)
                else:
                    len = random.randint(3, 10)
                    value = "".join(random.choices(string.ascii_letters, k=len))

                self._param_types[section_name][param_name] = param_type
                self._config[section_name][param_name] = value
                self._default[section_name][param_name] = None
                self._sect_attr_name[section_name] = None
                self._param_attr_name[section_name][param_name] = None

    def add_section(self, name: str, attr_name: str | None = None) -> None:
        """Добавление секции конфигурации"""
        self._config[name] = {}
        self._param_types[name] = {}
        self._default[name] = {}
        self._sect_attr_name[name] = attr_name
        self._param_attr_name[name] = {}

    def add_param(
        self,
        name: str,
        section: str,
        val: Any,
        type: Callable[[str], Any],
        default: Any = None,
        attr_name: str | None = None,
    ) -> None:
        """Добавление параметра"""
        self._config[section][name] = val
        self._param_types[section][name] = type
        if default is not None:
            self._default[section][name] = default
        else:
            self._default[section][name] = None
        self._param_attr_name[section][name] = attr_name

    def make_file(self, tmp_path: Path) -> str:
        """Создание тестового файла конфигурации"""

        cfg_file = tmp_path / "tmp_cfg"
        with open(cfg_file, "w") as f:
            for section in self._config:
                f.write(f"[{section}]\n")
                for k, v in self._config[section].items():
                    f.write(f"{k} = {v}\n")
                f.write("\n")

        return str(cfg_file)

    def make_parser(self):

        cfg_parser = IniConfig()

        for section in self._config:
            cfg_section = cfg_parser.add_section(section, self._sect_attr_name[section])
            for param in self._config[section]:
                cfg_section.add_param(
                    param_name=param,
                    attr_name=self._param_attr_name[section][param],
                    param_type=self._param_types[section][param],
                    default=self._default[section][param],
                )

        return cfg_parser

    def get_config(
        self,
    ) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Callable[[str], Any]]]]:
        return self._config, self._param_types

    def clear(self) -> None:
        self._config = {}
        self._param_types = {}


@pytest.fixture
def dummy_cfg() -> TestCfg:
    return TestCfg()


@pytest.fixture
def positive_int() -> Callable[[Any], Any]:
    def _positive_int(param: Any) -> int:
        try:
            param = int(param)
        except:
            raise

        if param > 0:
            return param
        else:
            raise ValueError

    return _positive_int
