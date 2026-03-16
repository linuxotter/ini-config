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
    Configuration error class

    This class is inherited from Exception class
    Does not have any special properties
    """

    pass


@dataclass
class Parameter:
    """
    Configuration parameter object

    Holds data for a single configuration parameter
    """

    param_name: str
    attr_name: str
    param_type: Callable[[Any], Any] = str
    default: Any = None
    converted_default: Any = None


class ConfigNamespace:
    """
    Config Namespace object

    Namespace object is created for each configuration section. It has attributes
    ConfigNamespace.parameter = value. The whole configuration is stored in similar
    Namespace object containing all section objects.
    """

    def __init__(self, **kwargs) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __repr__(self) -> str:
        items = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items())
        return f"Config({items})"

    def __bool__(self) -> bool:
        """Retuns True, if object has any keys, otherwise False"""
        return bool(self.__dict__)

    # TODO: Translate and add test
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(f"'{type(self).__name__}' у объекта нет атрибута '{name}'")


class ConfigSection:
    """
    Config section class

    The class describes one config section with expected parameters
    """

    @staticmethod
    def _str_to_bool(param: Any) -> bool:
        """
        Converts str to bool

        This function used with bool parameters to correctly convert string value
        to bool
        """

        # Supported aliases for True
        true_cases = ("true", "yes", "1", "on", "enable")
        # Supported aliases for False
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
        Attribute name check

        Checks if attribute name meet all Python requirements
        """

        if not isinstance(attr_name, str):
            raise ValueError(
                _("`{attr_name}` is not a string").format(attr_name=attr_name)
            )
        elif not (attr_name):
            raise ValueError(_("empty string"))
        elif not attr_name.isidentifier():
            raise ValueError(
                _("`{attr_name}` is not a valid Python identifier").format(
                    attr_name=attr_name
                )
            )
        elif keyword.iskeyword(attr_name):
            raise ValueError(
                _("`{attr_name}` is a Python keyword").format(attr_name=attr_name)
            )
        elif attr_name.startswith("__") and attr_name.endswith("__"):
            raise ValueError(
                _("`{attr_name}` is a Python magic method").format(attr_name=attr_name)
            )
        elif attr_name in dir(object):
            raise ValueError(
                _("`{attr_name}` is a built-in Python attribute").format(
                    attr_name=attr_name
                )
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
                _("Incorrect attribute name for section `{section}` : {err}").format(
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
        """Adds parameter to config section"""

        if not isinstance(param_name, str):
            raise ConfigError(
                _("Parameter name `{section}.{param}` is not a string").format(
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
                    "Incorrect attribute name for parameter `{section}.{param}` : {err}"
                ).format(section=self._section_name, param=param_name, err=err)
            )

        if self._params.get(param_name):
            raise ConfigError(
                _(
                    "Duplicate parameter `{section}.{param}` in expected "
                    "configuration file structure"
                ).format(section=self._section_name, param=param_name)
            )

        # Bool type is changed to _str_to_bool
        if param_type is bool:
            param_type = self._str_to_bool

        # Check if param_type is callable
        if not callable(param_type):
            raise ConfigError(
                _(
                    "Parameter type `{section}.{param}` is instance of "
                    "`{type}`, expected callable"
                ).format(section=self._section_name, param=param_name, type=param_type)
            )

        # Default value check
        if default is not None:
            try:
                converted_default = param_type(default)
            except Exception:
                raise ConfigError(
                    _(
                        "Error converting default value for parameter "
                        "`{section}.{param}` to type `{type}`"
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
    """
    Config parser class

    Creates an instance of config parser object. It is used to describe expected
    config file structure, define required and optional parameters, parse
    config file, extract parameters and store them in ConfigNamespace object for
    further access
    """

    @staticmethod
    def _normalize_ini(content: str) -> str:
        """Converts section names from config file to lower case"""

        normalized_ini: list[str] = []

        for line in content.splitlines():
            stripped_line = line.strip()
            # Convert section name to lower case
            if stripped_line.startswith("[") and stripped_line.endswith("]"):
                normalized_ini.append(stripped_line.lower())
            # Exclude empty lines
            elif not stripped_line:
                continue
            # All other lines are not changed
            else:
                normalized_ini.append(stripped_line)

        return "\n".join(normalized_ini)

    @staticmethod
    def set_language(lang: str | None = None) -> None:
        """
        Set the modules language

        All log and Exception messages will be in selected language, if supported.
        If not, English will be used by default.
        """

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
                logger.debug(_("Locale is set, lang=`%s`"), lang)

            except FileNotFoundError:
                t = gettext.NullTranslations()
                _ = t.gettext
                logger.warning(
                    _("Files for lang=`%s` not found in `%s` directory"),
                    lang,
                    locales_dir,
                )

    def __init__(self) -> None:
        # Dictionary with ConfigSection objects. The key is section name
        self._sections: dict[str, ConfigSection] = {}

    def add_section(
        self, section_name: str, attr_name: str | None = None
    ) -> ConfigSection:
        """
        Add config section

        Adds section to the parser. Tells parser to search section with given
        name in configuration file
        """

        if not isinstance(section_name, str):
            raise ConfigError(
                _("Section name `{section}` is not a string").format(
                    section=section_name
                )
            )

        section_name = section_name.lower()

        if section_name in self._sections:
            raise ConfigError(
                _(
                    "Duplicate section `{section}` in expected configuration file "
                    "structure"
                ).format(section=section_name)
            )

        section = ConfigSection(section_name, attr_name)
        self._sections[section_name] = section

        logger.debug(_("Config section `%s` added to parser"), section_name)

        return section

    def parse_file(self, cfg_file: str | Path) -> ConfigNamespace:
        """
        Reads configuration file and parses extracted parameters

        Tries to extract parameters and their values from configuration
        file, compares extracted parameters to the expected config
        structure, returns ConfigNamespace object with config parameters.
        """

        # Cionvert cfg_file argument to Path object in case str was passed
        cfg_file = Path(cfg_file)

        logger.info(_("Reading configuration file `%s`"), cfg_file)
        try:
            with open(cfg_file, "r") as f:
                ini_content = f.read()
        except Exception as err:
            cfg_file_read_err = True
            logger.warning(_("Error reading file `%s` : %s"), cfg_file, err)
            ini_content = ""
        else:
            cfg_file_read_err = False

        config = configparser.ConfigParser()
        try:
            config.read_string(self._normalize_ini(ini_content))
        except Exception as err:
            raise ConfigError(
                _("Error parsing configuration file `{file}` : {err}").format(
                    file=cfg_file, err=err
                )
            )

        if not cfg_file_read_err:
            logger.info(_("Configuration file read successfully"))

        # Create empty Confignamespace object to store parsed config parameters
        namespace = ConfigNamespace()

        for section_name, section_obj in self._sections.items():
            logger.debug(_("Checking configuration section `%s`"), section_name)
            section_namespace = ConfigNamespace()
            section_in_file = section_name in config
            if section_in_file:
                logger.debug(
                    _("Section `%s` found in file `%s`"), section_name, cfg_file
                )
            else:
                logger.debug(
                    _("Section `%s` not found in file `%s`"), section_name, cfg_file
                )

            for param in section_obj._params.values():
                logger.debug(
                    _("Checking parameter `%s.%s`"), section_name, param.param_name
                )
                val = None
                is_missing = True

                # Check if parameter is in file and extract it's value
                if section_in_file and param.param_name in config[section_name]:
                    raw_val = config[section_name][param.param_name]
                    logger.debug(_("Parameter found, value from file : `%s`"), raw_val)
                    try:
                        val = param.param_type(raw_val)
                        is_missing = False
                        logger.debug(
                            _("Parameter value converted to type `%s` : `%s`"),
                            param.param_type.__name__,
                            val,
                        )
                    except Exception as err:
                        logger.error(
                            _(
                                "Error converting parameter `%s.%s`=`%s` to type `%s` : %s"
                            ),
                            section_name,
                            param.param_name,
                            raw_val,
                            param.param_type.__name__,
                            err,
                        )
                    finally:
                        # Delete processed parameter from IniConfig list
                        del config[section_name][param.param_name]

                if is_missing:
                    log_msg = (
                        "Parameter `{section}.{param}` is missing "
                        "or it's value is incorrect"
                    )

                    if param.converted_default is not None:
                        val = param.converted_default
                        is_missing = False
                        logger.warning(
                            _(log_msg + ", using default value : `{default}`").format(
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

                # Add parameter to section ConfigNamespace object
                setattr(section_namespace, param.attr_name, val)

            # Add section objects to root config object
            # If section name is MAIN, add parameters directly to root
            # config object : root_config.parameter
            if section_name == "main":
                for k, v in section_namespace.__dict__.items():
                    setattr(namespace, k, v)
            # For other section create structure root_config.section.parameter
            else:
                setattr(namespace, section_obj._attr_name, section_namespace)

            # If all section's parameters are processed, delete section
            # from IniConfig object
            if config.has_section(section_name) and not config[section_name]:
                del config[section_name]

        # All parameters and sections left in IniConfig list
        # are considered unknown, logged and ignored.
        if config:
            for section in config:
                if not config[section]:
                    # Section DEFAULT is ignored, it is created by configparser
                    # by default.
                    if section == "DEFAULT":
                        continue
                    else:
                        logger.warning(
                            _(
                                "Empty section `%s` is not defined in expected "
                                "configuration file structure. Ignoring"
                            ),
                            section,
                        )
                else:
                    for param in config[section]:
                        logger.warning(
                            _("Unknown parameter `%s.%s`=`%s`. Ignoring"),
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
