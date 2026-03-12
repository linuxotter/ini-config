from typing import Any, Callable
from dataclasses import dataclass
from pathlib import Path
import configparser
import logging
import keyword
import gettext

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Language settings
t = gettext.NullTranslations()
_ = t.gettext


class ConfigError(Exception):
    """
    Класс ошибки конфигурации

    Наследуется от класса Exception, не имеет дополнительных свойств
    """

    pass


@dataclass
class Parameter:
    """
    Объект параметра конфигурации

    Содержит информацию об отдельном параметре конфигурации.
    """

    param_name: str
    attr_name: str
    param_type: Callable[[Any], Any] = str
    default: Any = None
    converted_default: Any = None


class ConfigNamespace:
    """
    Объект конфигурации

    Для каждой секции конфигурации создается объект, имеющий атрибуты
    параметр = значение. Объект итоговой конфигурации имеет объединяет
    в себе объекты секций, имея атрибуты имя_секции = объект_секции.
    """

    def __init__(self, **kwargs) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __repr__(self) -> str:
        items = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items())
        return f"Config({items})"

    def __bool__(self) -> bool:
        """Если у объекта есть ключи, возвращает True, иначе False"""
        return bool(self.__dict__)

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(f"'{type(self).__name__}' у объекта нет атрибута '{name}'")


class ConfigSection:
    """
    Класс создания секции конфигурации

    Описывает отдельную секцию конфигурацию с ожидаемыми в ней параметрами
    """

    @staticmethod
    def _str_to_bool(param: Any) -> bool:
        """
        Конвертация строки в булево значение

        Заменяет класс bool при добавлении параметра для корректного
        преобразования строки в булево значение
        """

        true_cases = ("true", "yes", "1", "on", "enable")
        false_cases = ("false", "no", "0", "off", "disable")

        if isinstance(param, bool):
            return param
        elif str(param).lower() in true_cases:
            return True
        elif str(param).lower() in false_cases:
            return False
        else:
            raise ValueError

    @staticmethod
    def _chk_attr_name(attr_name: str) -> str:
        """
        Проверка имени атрибута

        Проверяет соответствие строки правилам именования атрибутов в python.
        """

        if not isinstance(attr_name, str):
            raise ValueError(
                _("{attr_name} is not a string").format(attr_name=attr_name)
            )
        elif not (attr_name):
            raise ValueError(_("empty string"))
        elif not attr_name.isidentifier():
            raise ValueError(
                _("{attr_name} is not a valid identifier").format(attr_name)
            )
        elif keyword.iskeyword(attr_name):
            raise ValueError(_("{attr_name} is a Python keyword").format(attr_name))
        elif attr_name.startswith("__") and attr_name.endswith("__"):
            raise ValueError(_("{attr_name} is a Python magic word").format(attr_name))
        elif attr_name in dir(object):
            raise ValueError(
                _("{attr_name} is a built-in Python attribute").format(attr_name)
            )
        else:
            return attr_name.lower()

    def __init__(self, section_name: str, attr_name: str | None) -> None:

        self._section_name = section_name

        try:
            if attr_name is not None:
                self._attr_name = self._chk_attr_name(attr_name)
            else:
                self._attr_name = self._chk_attr_name(section_name)
        except ValueError as err:
            raise ConfigError(
                _("Incorrect attribute name for section{section} : {err}").format(
                    section=self._section_name, err=err
                )
            )

        self._params: dict[str, Parameter] = {}

    def add_param(
        self,
        param_name: str,
        attr_name: str | None = None,
        param_type: Callable[[Any], Any] = str,
        default: Any = None,
    ):
        """Добавляет параметр в секцию"""

        if not isinstance(param_name, str):
            raise ConfigError(
                _("Parameter name {section}.{param} is not a string").format(
                    section=self._section_name,
                    param=param_name,
                )
            )

        param_name = param_name.lower()

        try:
            if attr_name is None:
                attr_name = self._chk_attr_name(param_name)
            else:
                attr_name = self._chk_attr_name(attr_name)
        except ValueError as err:
            raise ConfigError(
                _(
                    "Incorrect attribute name for parameter {section}.{param} : {err}"
                ).format(section=self._section_name, param=param_name, err=err)
            )

        if self._params.get(param_name):
            raise ConfigError(
                _("Duplicate parameter {section}.{param}").format(
                    section=self._section_name, param=param_name
                )
            )

        # Тип bool заменяется на метод _str_to_bool
        if param_type is bool:
            param_type = self._str_to_bool

        # Check if param_type is callable
        if not callable(param_type):
            raise ConfigError(
                _("Parameter {section}.{param} {type} is not callable").format(
                    section=self._section_name, param=param_name, type=param_type
                )
            )

        # Проверка типа значения по умолчанию
        if default is not None:
            try:
                converted_default = param_type(default)
            except Exception:
                raise ConfigError(
                    _(
                        "Error converting default value for parameter "
                        "{section}.{param} to type {type}"
                    ).format(
                        section=self._section_name,
                        param=param_name,
                        type=param_type.__name__,
                    )
                )
        else:
            converted_default = None

        self._params[param_name] = Parameter(
            param_name=param_name,
            attr_name=attr_name,
            param_type=param_type,
            default=default,
            converted_default=converted_default,
        )

        return self

    def __repr__(self) -> str:
        return (
            f"ConfigSection({self._section_name}, params={list(self._params.keys())})"
        )


class IniConfig:
    """Класс обработчика конфигурации"""

    @staticmethod
    def _normalize_ini(content: str) -> str:
        """Преобразование имен секций файла INI в нижний регистр"""

        normalized_ini: list[str] = []

        for line in content.splitlines():
            stripped_line = line.strip()
            # Преобразование названия секции в нижний регистр
            if stripped_line.startswith("[") and stripped_line.endswith("]"):
                normalized_ini.append(stripped_line.lower())
            # Пропуск пустых строк
            elif not stripped_line:
                continue
            # Остальные строки остаются неизменными
            else:
                normalized_ini.append(stripped_line)

        return "\n".join(normalized_ini)

    @staticmethod
    def set_language(lang: str | None = None) -> None:

        global _

        if lang in ("en", "default", None):
            t = gettext.NullTranslations()
            _ = t.gettext
            logger.debug("English language is set")

        else:
            if lang == "locale":
                lang = None

            locales_dir = Path(__file__).parent / "locales"
            domain = (__name__).split(".")[1]

            try:
                t = gettext.translation(domain, locales_dir, [lang] if lang else None)
                _ = t.gettext
                logger.debug(_("Locale is set, lang=%s"), lang)

            except FileNotFoundError:
                t = gettext.NullTranslations()
                _ = t.gettext
                logger.warning(
                    _("Files for lang=%s not found in %s directory"), lang, locales_dir
                )

    def __init__(self) -> None:
        self._sections: dict[
            str, ConfigSection
        ] = {}  # Словарь, содержащий объекты секций

    def add_section(
        self, section_name: str, attr_name: str | None = None
    ) -> ConfigSection:
        """
        Добавляет секцию конфигурации

        Добавляет секцию конфигурации, поиск которой будет выполняться в
        файле
        """

        if not isinstance(section_name, str):
            raise ConfigError(
                _("Section name {section} is not a string").format(section=section_name)
            )

        section_name = section_name.lower()

        if section_name in self._sections:
            raise ConfigError(_("Duplicate section {name}").format(name=section_name))

        section = ConfigSection(section_name, attr_name)
        self._sections[section_name] = section

        logger.debug(_("Config section %s added to parser"), section_name)

        return section

    def parse_file(self, cfg_file: str | Path) -> ConfigNamespace:
        """
        Чтение файла конфигурации и проверка значений

        Читает файл конфигурации, разбирает его на секции и параметры,
        производит проверку полученных параметров на основании данных,
        добавленных в обработчик
        """

        # Преобразование пути в объект Path, если в аргументах передана строка
        cfg_file = Path(cfg_file)

        logger.info(_("Reading configuration file %s"), cfg_file)
        try:
            with open(cfg_file, "r") as f:
                ini_content = f.read()
        except Exception as err:
            cfg_file_read_err = True
            logger.warning(_("Error reading file %s : %s"), cfg_file, err)
            ini_content = ""
        else:
            cfg_file_read_err = False

        config = configparser.ConfigParser()
        try:
            config.read_string(self._normalize_ini(ini_content))
        except Exception as err:
            raise ConfigError(
                _("Error parsing configuration file {file} : {err}").format(
                    file=cfg_file, err=err
                )
            )

        if not cfg_file_read_err:
            logger.info(_("Configuration file read successfully"))

        # Создание пустого объекта конфигурации
        namespace = ConfigNamespace()

        for section_name, section_obj in self._sections.items():
            logger.debug(_("Checking configuration section %s"), section_name)
            section_namespace = ConfigNamespace()
            section_in_file = section_name in config
            if section_in_file:
                logger.debug(_("Section %s found in file %s"), section_name, cfg_file)
            else:
                logger.debug(
                    _("Section %s not found in file %s"), section_name, cfg_file
                )

            for param in section_obj._params.values():
                logger.debug(
                    _("Checking parameter %s.%s"), section_name, param.param_name
                )
                val = None
                is_missing = True

                # Проверка наличия параметра и получение его значения
                # из файла
                if section_in_file and param.param_name in config[section_name]:
                    raw_val = config[section_name][param.param_name]
                    logger.debug(_("Parameter found, value from file: %s"), raw_val)
                    try:
                        val = param.param_type(raw_val)
                        is_missing = False
                        logger.debug(
                            _("Parameter value converted to type %s : %s"),
                            param.param_type.__name__,
                            val,
                        )
                    except Exception as err:
                        logger.error(
                            _("Error converting parameter %s.%s=%s to type %s. %s"),
                            section_name,
                            param.param_name,
                            raw_val,
                            param.param_type.__name__,
                            err,
                        )
                    finally:
                        # Удаление обработанного параметра из объекта configparser
                        del config[section_name][param.param_name]

                if is_missing:
                    log_msg = (
                        "Parameter {section}.{param} is missing "
                        "or it's value is incorrect"
                    )

                    if param.converted_default is not None:
                        val = param.converted_default
                        is_missing = False
                        logger.warning(
                            _(log_msg + ", using default value {default}").format(
                                section=section_name,
                                param=param.param_name,
                                default=param.default,
                            )
                        )
                    else:
                        raise ConfigError(
                            _(log_msg + ", default value is not set").format(
                                section=section_name, param=param.param_name
                            )
                        )

                # Добавление параметра в объект секции
                setattr(section_namespace, param.attr_name, val)

            # Добавление объекта секции в объект конфигурации
            # Если секция MAIN, то параметры добавляются как ключи
            # корневого объекта: объект.параметр
            if section_name == "main":
                for k, v in section_namespace.__dict__.items():
                    setattr(namespace, k, v)
            # Для других секций создается структура объект.секция.параметр
            else:
                setattr(namespace, section_obj._attr_name, section_namespace)

            # Если в секции не осталось необработанных параметров,
            # удаляем ее из объекта configparser
            if config.has_section(section_name) and not config[section_name]:
                del config[section_name]

        # Проверяем, остались ли после разбора конфигурации
        # необработанные параметры и секции. Если такие есть,
        # игнорируем их как неизвестные, но вносим информацию
        # в журнал
        if config:
            for section in config:
                if not config[section]:
                    # Пропускаем секцию DEFAULT, по умолчанию создается
                    # при разборе файла INI
                    if section == "DEFAULT":
                        continue
                    else:
                        logger.warning(
                            _(
                                "Empty section %s is not defined in expected "
                                "configuration file structure. Ignoring"
                            ),
                            section,
                        )
                else:
                    for param in config[section]:
                        logger.warning(
                            _("Unknown parameter %s.%s=%s. Ignoring"),
                            section,
                            param,
                            config[section][param],
                        )

        return namespace

    def __repr__(self):

        sections = []
        for name in self._sections:
            params = self._sections[name]._params.keys()
            sections.append(f"section={name}, parameters={', '.join(params)}")
        return f"IniConfig({'; '.join(sections)})"
