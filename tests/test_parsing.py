import pytest
from pathlib import Path
from typing import Callable, Any

from conftest import TestCfg
from ini_config import IniConfig, ConfigError

def test_normal_operation(dummy_cfg: TestCfg, tmp_path: Path) -> None:
   '''Тест нормального (без ошибок) преобразования'''

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
         if  param_type is bool:
            if param == True:
               assert v in dummy_cfg.true_cases
            else:
               assert v in dummy_cfg.false_cases
         else:
            assert param == param_type(v)
         assert type(param) is param_type

test_cases = [
   ('test', 'integer', 'string', int),
   ('test', 'bool', 'not_bool', bool),
   ('test', 'float', 'True', float)
]

@pytest.mark.parametrize('section, param, val, param_type', test_cases)
def test_wrong_type(
   dummy_cfg: TestCfg,
   tmp_path: Path,
   caplog,
   section: str,
   param: str,
   val: str,
   param_type: Callable[[str], Any]

) -> None:
   '''Тест неверного типа параметров'''

   dummy_cfg.add_section(section)
   dummy_cfg.add_param(param, section, val, param_type)
   cfg_file = dummy_cfg.make_file(tmp_path)
   cfg_parser=dummy_cfg.make_parser()
   with pytest.raises(ConfigError) as err:
      cfg_parser.parse_file(cfg_file)

   if param_type.__name__ == 'bool':
      param_type_str = '_str_to_bool'
   else:
      param_type_str = param_type.__name__

   assert (
         f'Ошибка преобразования параметра {section}.{param}={val} '
         f'к типу {param_type_str}'
      ) in caplog.text
   assert f'Отсутствует параметр {section}.{param}' == str(err.value)

def test_empty_section(dummy_cfg: TestCfg, tmp_path: Path) -> None:
   '''Тест обработки пустой секции'''

   dummy_cfg.add_section('Empty')
   cfg_file = dummy_cfg.make_file(tmp_path)
   cfg_parser = dummy_cfg.make_parser()

   cfg = cfg_parser.parse_file(cfg_file)

   assert hasattr(cfg, 'empty')

def test_main_section(dummy_cfg: TestCfg, tmp_path: Path) -> None:
   '''Тест параметров в секции MAIN'''

   dummy_cfg.add_section('maiN')
   dummy_cfg.add_param('param1', 'maiN', 345, str)
   dummy_cfg.add_section('section')
   dummy_cfg.add_param('param1', 'section', 'hooy', str)
   cfg_file = dummy_cfg.make_file(tmp_path)
   cfg_parser = dummy_cfg.make_parser()
   cfg = cfg_parser.parse_file(cfg_file)

   assert hasattr(cfg, 'param1')
   assert getattr(cfg, 'param1') == str(345)
   assert (param := getattr(cfg, 'section'))
   assert hasattr(param, 'param1') and getattr(param, 'param1') == 'hooy'

def test_repeating_sections(dummy_cfg: TestCfg, tmp_path: Path) -> None:
   '''Тест повторяющихся секций'''

   dummy_cfg.add_section('section_1')
   dummy_cfg.add_param('param_1', 'section_1', 345, int)
   dummy_cfg.add_section('SECTION_1')
   dummy_cfg.add_param('param_2', 'SECTION_1', 765, int)
   dummy_cfg.add_section('secTion_1')
   dummy_cfg.add_param('param_3', 'secTion_1', 323, int)

   cfg_file = dummy_cfg.make_file(tmp_path)

   dummy_cfg.clear()
   dummy_cfg.add_section('section_1')
   dummy_cfg.add_param('param_1', 'section_1', 345, int)
   dummy_cfg.add_param('param_2', 'section_1', 345, int)
   dummy_cfg.add_param('param_3', 'section_1', 345, int)

   cfg_parser = dummy_cfg.make_parser()

   with pytest.raises(ConfigError) as err:
      cfg_parser.parse_file(cfg_file)

   assert f'Ошибка разбора файла конфигурации {cfg_file}:' in str(err.value)

def test_params_without_values(dummy_cfg: TestCfg, tmp_path: Path) -> None:
   '''Тест параметров без значений'''

   cfg_file = tmp_path / 'tmp_cfg'
   with open(cfg_file, 'w') as f:
      f.write('[main]\nparam1')

   dummy_cfg.add_section('main')
   dummy_cfg.add_param('param1', 'main', 123, int)
   cfg_parser = dummy_cfg.make_parser()

   with pytest.raises(ConfigError) as err:
      cfg_parser.parse_file(str(cfg_file))

   assert f'Ошибка разбора файла конфигурации {cfg_file}:' in str(err.value)

def test_repeating_params_in_file(dummy_cfg: TestCfg, tmp_path: Path) -> None:
   '''Тест повторяющихся параметров'''

   cfg_file = tmp_path / 'tmp_cfg'
   with open(cfg_file, 'w') as f:
      f.write('[main]\nparam1=123\nPARAM1=456\nPaRaM1=789')

   dummy_cfg.add_section('main')
   dummy_cfg.add_param('param1', 'main', 789, int)
   cfg_parser = dummy_cfg.make_parser()
   
   with pytest.raises(ConfigError) as err:
      cfg_parser.parse_file(str(cfg_file))

   assert f'Ошибка разбора файла конфигурации {cfg_file}:' in str(err.value)

def test_repeating_params_in_parser(dummy_cfg: TestCfg) -> None:

   dummy_cfg.add_section('main')
   dummy_cfg.add_param('param1', 'main', 123, int)
   dummy_cfg.add_param('Param1', 'main', 123, int)

   with pytest.raises(ConfigError) as err:
      dummy_cfg.make_parser()

   assert str(err.value) == 'Дублированный параметр main.param1'

def test_wrong_default_value(dummy_cfg: TestCfg) -> None:

   dummy_cfg.add_section('main')
   dummy_cfg.add_param('param1', 'main', 123, int, default = 'string')

   with pytest.raises(ConfigError) as err:
      dummy_cfg.make_parser()

   assert 'Ошибка приведения значения по умолчанию' in str(err.value)

def test_no_value_with_default(dummy_cfg: TestCfg, tmp_path: Path) -> None:

   dummy_cfg.add_section('main')
   cfg_file = dummy_cfg.make_file(tmp_path)
   dummy_cfg.add_param('param1', 'main', '123', int, default = 123)
   cfg_parser = dummy_cfg.make_parser()

   cfg = cfg_parser.parse_file(Path(cfg_file))

   assert getattr(cfg, 'param1', None) == 123

def test_wrong_value_with_default(dummy_cfg: TestCfg, tmp_path: Path) -> None:

   dummy_cfg.add_section('main')
   dummy_cfg.add_param('param1', 'main', 'string', int, 345)
   cfg_file = dummy_cfg.make_file(tmp_path)
   cfg_parser = dummy_cfg.make_parser()

   cfg = cfg_parser.parse_file(cfg_file)

   assert getattr(cfg, 'param1') == 345

def test_empty_string_param( dummy_cfg: TestCfg, tmp_path: Path) -> None:

   dummy_cfg.add_section('main')
   dummy_cfg.add_param('param1', 'main', '', str, 123)
   cfg_file = dummy_cfg.make_file(tmp_path)
   cfg_parser = dummy_cfg.make_parser()
   cfg = cfg_parser.parse_file(cfg_file)

   assert getattr(cfg, 'param1') == ''
   
def test_unknown_params(
   dummy_cfg: TestCfg,
   tmp_path: Path,
   caplog,
) -> None:
   '''Проверка неизвестных параметров'''

   dummy_cfg.create_rnd_cfg()
   cfg_file = dummy_cfg.make_file(tmp_path)
   cfg_parser = dummy_cfg.make_parser()

   with open(cfg_file, 'a') as f:
      f.write('[main]\nunknown_param1=10\n[empty]')

   cfg_parser.parse_file(cfg_file)

   assert 'Неизвестная пустая секция в файле конфигурации: empty' in caplog.text
   assert 'Неизвестный параметр main.unknown_param1' in caplog.text
   assert 'DEFAULT' not in caplog.text