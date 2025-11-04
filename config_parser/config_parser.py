from typing import Any, Callable, Self
from dataclasses import dataclass
from pathlib import Path
import configparser
import logging

class ConfigError(Exception):
    pass

@dataclass
class Parameter:
    name: str
    type: Callable[[str], Any] = str
    required: bool = False
    default: Any = None

class ConfigNamespace:
    '''Объект конфигурации'''

    def __init__(self, **kwargs) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __repr__(self) -> str:
        items = ', '.join(f'{k}={v!r}' for k, v in self.__dict__.items())
        return f'Config({items})'

class SectionBuilder:
    '''Класс добавляет секцию конфигурации'''

    @staticmethod
    def _str_to_bool(param: str) -> bool:
        '''Конвертация строки в булево значение'''
        true_cases = ('true', 'yes', '1', 'on')
        false_cases = ('false', 'no', '0', 'off')

        if param.lower() in true_cases: return True
        elif param.lower() in false_cases: return False
        else: raise ValueError 

    def __init__(self, name: str) -> None:
        self._name: str = name
        self._params: dict[str, Parameter] = {}

    def add_param(
        self,
        name: str,
        type: Callable[[str], Any] = str,
        required: bool = False,
        default: Any = None
    ) -> Self:
        '''Метод добавляет параметр в секцию'''

        name = name.lower()
        if type is bool:
            type = self._str_to_bool
        self._params[name] = Parameter(
            name = name,
            type = type,
            required = required,
            default = default
        )

        return self

    def __repr__(self) -> str:
        repr_str = f'SectionBuilder({self._name}, '
        repr_str += f'params={list(self._params.keys())})'
        return  repr_str

class ConfigParser:
    '''Класс обработчика конфигурации'''

    @staticmethod
    def _normalize_ini(content: str) -> str:
        '''Преобразование имен секций файла INI в нижний регистр'''

        normalized_ini: list[str] = []

        for line in content.splitlines():
            stripped_line = line.strip()
            # Преобразование названия секции в нижний регистр
            if stripped_line.startswith('[') and stripped_line.endswith(']'):
                normalized_ini.append(stripped_line.lower())
            # Пропуск пустых строк
            elif not stripped_line:
                continue
            # Остальные строки остаются неизменными
            else:
                normalized_ini.append(stripped_line)

        return '\n'.join(normalized_ini)

    def __init__(self) -> None:
        self._sections: dict[str, SectionBuilder] = {}
        self._logger = logging.getLogger()
        self._logger.setLevel(logging.DEBUG)

    def add_section(self, name: str) -> SectionBuilder:
        '''Метод добавляет секцию конфигурации'''

        name = name.lower()
        self._logger.debug(f'Добавление секции конфигурации {name}')
        if name in self._sections:
            raise ConfigError(f'Секция {name} уже добавлена')

        section = SectionBuilder(name)
        self._sections[name] = section

        return section

    def parse_file(self, cfg_file: str) -> ConfigNamespace:
        '''Чтение файла конфигурации и проверка значений'''

        self._logger.info(f'Чтение файла конфигурации {cfg_file}')
        try:
            with open(Path(cfg_file), 'r') as f:
                ini_content = f.read()
        except FileNotFoundError:
            raise ConfigError(f'Файл не найден: {cfg_file}')
        except Exception as err:
            raise ConfigError(f'Ошибка чтения файла {cfg_file}: {err}')

        config = configparser.ConfigParser()
        try:
            config.read_string(self._normalize_ini(ini_content))
        except Exception as err:
            raise ConfigError(f'Ошибка разбора файла конфигурации {cfg_file}: {err}')

        self._logger.info('Файл конфигурации успешно прочитан')

        # Создание пустого объекта конфигурации 
        namespace = ConfigNamespace()

        for section_name, section_builder in self._sections.items():
            self._logger.debug(f'Проверяется секция конфигурации {section_name}')
            section_ns = ConfigNamespace()
            section_in_file = section_name in config
            if section_in_file:
                self._logger.debug(f'Секция {section_name} найдена в файле {cfg_file}')
            else:
                self._logger.debug(f'Секция {section_name} не найдена в файле {cfg_file}')

            for param in section_builder._params.values():
                self._logger.debug(f'Проверяется параметр {section_name}.{param.name}')
                val = None
                is_missing = True

                # Проверка наличие параметра и получение его значения из файла
                if section_in_file and param.name in config[section_name]:
                    raw_val = config[section_name][param.name]
                    self._logger.debug(f'параметр найден, значение из файла: {raw_val}')
                    try:
                        val = param.type(raw_val)
                        is_missing = False
                        self._logger.debug(
                            f'Значение параметра приведено к типу {param.type}: {val}'
                        )
                    except Exception as err:
                        self._logger.error(
                            f'Ошибка преобразования параметра '
                            f'{section_name}.{param.name}={raw_val} к типу '
                            f'{param.type.__name__}. {err}'
                        )
                    finally:
                        # Удаление обработанного параметра из объекта configparser
                        del config[section_name][param.name]

                if is_missing:
                    self._logger.info(
                        f'Значение параметра {param.name} отсутствует либо '
                        f'задано неверно, попытка использовать значение '
                        f'по умолчанию'
                    )
                    if param.default is not None:
                        val = param.default
                        is_missing = False
                        self._logger.info(
                            'Используется значение по умолчанию '
                            f'{section_name}.{param.name} = {val}'
                        )
                    else:
                        self._logger.warning(
                            f'Отсутствует значение по умолчанию для '
                            f'параметра {section_name}.{param.name}'
                        )
                        raise ConfigError(
                            'Отсутствует параметр '
                            f'{section_name}.{param.name}'
                        )

                # Добавление параметра в объект секции
                setattr(section_ns, param.name, val)

            # Добавление объекта секции в объект конфигурации
            setattr(namespace, section_name, section_ns)

            # Если в секции не осталось необработанных параметров,
            # удаляем ее из объекта configparser
            if not config[section_name]: del config[section_name]

        # Проверяем, остались ли после разбора конфигурации
        # необработанные параметры и секции. Если такие есть,
        # игнорируем их как неизвестные, но вносим информацию
        # в журнал
        if config:
            for section in config:
                if not config[section]:
                    self._logger.warning(
                        f'Неизвестная пустая секция в файле конфигурации: '
                        f'{section}. Игнорируется'
                    )
                else:
                    for param in config[section]:
                        self._logger.warning(
                            f'Неизвестный параметр {section}.{param}='
                            f'{config[section][param]}. Игнорируется'
                        )

        return namespace

    def __repr__(self):

        sections = []
        for name in self._sections:
            params = self._sections[name]._params.keys()
            section_str = f'section={name}, '
            section_str += f'parameters={", ".join(params)}'
            sections.append(section_str)

        return f'ConfigParser({"; ".join(sections)})'