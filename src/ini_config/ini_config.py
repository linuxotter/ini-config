from typing import Any, Callable
from dataclasses import dataclass
from pathlib import Path
import configparser
import logging
import keyword

class ConfigError(Exception):
    '''
    Класс ошибки конфигурации

    Наследуется от класса Exception, не имеет дополнительных свойств
    '''

    pass

@dataclass
class Parameter:
    '''
    Объект параметра конфигурации
    
    Содержит информацию об отдельном параметре конфигурации. 
    '''

    param_name: str
    attr_name: str
    param_type: Callable[[Any], Any] = str
    default: Any = None

class ConfigNamespace:
    '''
    Объект конфигурации
    
    Для каждой секции конфигурации создается объект, имеющий атрибуты
    параметр = значение. Объект итоговой конфигурации имеет объединяет
    в себе объекты секций, имея атрибуты имя_секции = объект_секции.
    '''

    def __init__(self, **kwargs) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __repr__(self) -> str:
        items = ', '.join(f'{k}={v!r}' for k, v in self.__dict__.items())
        return f'Config({items})'

    def __bool__(self) -> bool:
        '''Если у объекта есть ключи, возвращает True, иначе False'''
        return bool(self.__dict__)

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(
            f"'{type(self).__name__}' у объекта нет атрибута '{name}'"
        )

class ConfigSection:
    '''
    Класс создания секции конфигурации
    
    Описывает отдельную секцию конфигурацию с ожидаемыми в ней параметрами
    '''

    @staticmethod
    def _str_to_bool(param: Any) -> bool:
        '''
        Конвертация строки в булево значение
        
        Заменяет класс bool при добавлении параметра для корректного
        преобразования строки в булево значение
        '''

        true_cases = ('true', 'yes', '1', 'on', 'enable')
        false_cases = ('false', 'no', '0', 'off', 'disable')

        if isinstance(param, bool): return param
        elif str(param).lower() in true_cases: return True
        elif str(param).lower() in false_cases: return False
        else: raise ValueError     

    @staticmethod
    def _chk_attr_name(attr_name: str) -> str:
        '''
        Проверка имени атрибута
        
        Проверяет соответствие строки правилам именования атрибутов в python.
        '''

        if  not isinstance(attr_name, str):
            raise ValueError(f'{attr_name} не является строкой')
        elif not (attr_name):
            raise ValueError('пустая строка')
        elif not attr_name.isidentifier():
            raise ValueError(f'{attr_name} не является корректным идентификатором')
        elif keyword.iskeyword(attr_name):
            raise ValueError(f'{attr_name} является ключевым словом python')
        elif attr_name.startswith('__') and attr_name.endswith('__'):
            raise ValueError(
                f'{attr_name} является магическим методом Python'
            )
        elif attr_name in dir(object):
            raise ValueError(
                f'{attr_name} является встроенным атрибутом Python'
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
                f'Ошибка именования свойства секции {self._section_name} : '
                f'{err}'
            )

        self._params: dict[str, Parameter] = {}

    def add_param(
        self,
        param_name: str,
        attr_name: str | None = None,
        param_type: Callable[[Any], Any] = str,
        default: Any = None
    ):
        '''Добавляет параметр в секцию'''

        if not isinstance(param_name, str):
            raise ConfigError(
                f'Название параметра {self._section_name}.{param_name} '
                'не является строкой'
            )

        param_name = param_name.lower()

        try:
            if attr_name is None:
                attr_name = self._chk_attr_name(param_name)
            else:
                attr_name = self._chk_attr_name(attr_name)
        except ValueError as err:
            raise ConfigError(
                'Ошибка именования свойства параметра '
                f'{self._section_name}.{param_name} : {err}'
            )

        if self._params.get(param_name):
            raise ConfigError(
                f'Дублированный параметр {self._section_name}.{param_name}'
            )

        # Тип bool заменяется на метод _str_to_bool
        if param_type is bool:
            param_type = self._str_to_bool

        # Проверка типа значения по умолчанию
        if default is not None:
            try:
                default = param_type(default)
            except:
                raise ConfigError(
                    f'Ошибка приведения значения по умолчанию для параметра '
                    f'{self._section_name}.{param_name} к типу '
                    f'{param_type.__name__}'
                )

        if not callable(param_type):
            raise ConfigError(
                f'Тип параметра {self._section_name}.{param_name} '
                f'{param_type} не является функцией'
            )

        self._params[param_name] = Parameter(
            param_name = param_name,
            attr_name = attr_name,
            param_type = param_type,
            default = default
        )

        return self

    def __repr__(self) -> str:
        return (
            f'ConfigSection({self._section_name}, '
            f'params={list(self._params.keys())})'
        )

class IniConfig:
    ''' Класс обработчика конфигурации '''

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
        self._sections: dict[str, ConfigSection] = {}   # Словарь, содержащий объекты секций
        self._logger = logging.getLogger(__file__.removesuffix('.py'))
        self._logger.addHandler(logging.NullHandler())

    def add_section(
        self,
        section_name: str,
        attr_name: str | None = None
    ) -> ConfigSection:
        '''
        Добавляет секцию конфигурации
        
        Добавляет секцию конфигурации, поиск которой будет выполняться в
        файле
        '''

        if not isinstance(section_name, str):
            raise ConfigError(
                f'Название секции {section_name} не является строкой'
            )
        section_name = section_name.lower()

        if section_name in self._sections:
            raise ConfigError(f'Секция {section_name} уже существует')


        section = ConfigSection(section_name, attr_name)
        self._sections[section_name] = section

        self._logger.debug(
            f'Секция конфигурации {section_name} добавлена в обработчик'
        )

        return section

    def parse_file(self, cfg_file: str | Path) -> ConfigNamespace:
        '''
        Чтение файла конфигурации и проверка значений
        
        Читает файл конфигурации, разбирает его на секции и параметры,
        производит проверку полученных параметров на основании данных,
        добавленных в обработчик 
        '''

        # Преобразование пути в объект Path, если в аргументах передана строка
        cfg_file = Path(cfg_file)

        self._logger.info(f'Чтение файла конфигурации {cfg_file}')
        try:
            with open(cfg_file, 'r') as f:
                ini_content = f.read()
        except FileNotFoundError:
            raise ConfigError(f'Файл не найден: {cfg_file}')
        except Exception as err:
            raise ConfigError(f'Ошибка чтения файла {cfg_file}: {err}')

        config = configparser.ConfigParser()
        try:
            config.read_string(self._normalize_ini(ini_content))
        except Exception as err:
            raise ConfigError(
                f'Ошибка разбора файла конфигурации {cfg_file}: {err}'
            )

        self._logger.info('Файл конфигурации успешно прочитан')

        # Создание пустого объекта конфигурации 
        namespace = ConfigNamespace()

        for section_name, section_obj in self._sections.items():
            self._logger.debug(
                f'Проверяется секция конфигурации {section_name}'
            )
            section_namespace = ConfigNamespace()
            section_in_file = section_name in config
            if section_in_file:
                self._logger.debug(
                    f'Секция {section_name} найдена в файле {cfg_file}'
                )
            else:
                self._logger.debug(
                    f'Секция {section_name} не найдена в файле {cfg_file}'
                )

            for param in section_obj._params.values():
                self._logger.debug(
                    f'Проверяется параметр {section_name}.{param.param_name}'
                )
                val = None
                is_missing = True

                # Проверка наличия параметра и получение его значения
                # из файла
                if (
                    section_in_file and
                    param.param_name in config[section_name]
                ):
                    raw_val = config[section_name][param.param_name]
                    self._logger.debug(
                        f'Параметр найден, значение из файла: {raw_val}'
                    )
                    try:
                        val = param.param_type(raw_val)
                        is_missing = False
                        self._logger.debug(
                            f'Значение параметра приведено к типу '
                            f'{param.param_type.__name__}: {val}'
                        )
                    except Exception as err:
                        self._logger.error(
                            'Ошибка преобразования параметра '
                            f'{section_name}.{param.param_name}={raw_val} '
                            f'к типу {param.param_type.__name__}. {err}'
                        )
                    finally:
                        # Удаление обработанного параметра из объекта configparser
                        del config[section_name][param.param_name]

                if is_missing:
                    log_msg = (
                        f'Параметр {section_name}.{param.param_name} '
                        'отсутствует или задан неверно'
                    )
                    if param.default is not None:
                        val = param.default
                        is_missing = False
                        self._logger.warning(
                            f'{log_msg}, используется значение '
                            f'по умолчанию : {val}'
                        )
                    else:
                        self._logger.error(
                            f'{log_msg}, значение по умолчанию не задано'
                        )
                        raise ConfigError(
                            'Отсутствует параметр '
                            f'{section_name}.{param.param_name}'
                        )

                # Добавление параметра в объект секции
                setattr(section_namespace, param.attr_name, val)

            # Добавление объекта секции в объект конфигурации
            # Если секция MAIN, то параметры добавляются как ключи
            # корневого объекта: объект.параметр
            if section_name == 'main':
                for k, v in section_namespace.__dict__.items():
                    setattr(namespace, k, v)
            # Для других секций создается структура объект.секция.параметр
            else:
                setattr(namespace, section_obj._attr_name, section_namespace)

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
                    # Пропускаем секцию DEFAULT, по умолчанию создается
                    # при разборе файла INI
                    if section == 'DEFAULT':
                        continue
                    else:
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
            sections.append(
                f'section={name}, parameters={", ".join(params)}'
            )
        return f'IniConfig({"; ".join(sections)})'
