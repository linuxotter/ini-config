import pytest
from pathlib import Path
from typing import Callable, Any

from conftest import TestCfg
from config_parser import ConfigParser, ConfigError

def test_normal_operation(dummy_cfg: TestCfg, tmp_path: Path) -> None:
   '''Тест нормального (без ошибок) преобразования'''

   dummy_cfg.create_rnd_cfg()
   cfg_file = dummy_cfg.make_file(tmp_path)
   cfg_parser = dummy_cfg.make_parser()
   cfg = cfg_parser.parse_file(cfg_file)
   src_params, src_types = dummy_cfg.get_config()

   for section in src_params:
      assert (attr_section := getattr(cfg, section, None)) is not None
      for k, v in src_params[section].items():
         param = getattr(attr_section, f'{k.lower()}', None)
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