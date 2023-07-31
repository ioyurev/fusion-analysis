from pprint import pprint
import configparser
import os

_TRUE_STR = 'True'
DEFAULT_CONFIG_PATH = os.path.abspath("config.ini")
DEFAULT_CONFIG = {
    'Plotter' : {
        'autocolor' : 'False',
        'default_heat_color' : '[1,0,0]',
        'default_cool_color' : '[0,0,1]'
    }
}

def _parse_config(config: configparser.ConfigParser) -> dict:
    return {
            'Plotter' : {
                'autocolor' : config['Plotter']['autocolor'] == _TRUE_STR,
                'default_heat_color' : [float(n) for n in config['Plotter']['default_heat_color'][1:-2].split(',')],
                'default_cool_color' : [float(n) for n in config['Plotter']['default_cool_color'][1:-2].split(',')]
            }
        }

def read_config():
    config = configparser.ConfigParser()
    if config.read(DEFAULT_CONFIG_PATH):
        dct = _parse_config(config=config)
        print(f"* прочитан конфиг файл {DEFAULT_CONFIG_PATH}")
        pprint(dct)
        return dct
    else:
        print("* конфиг файл не прочитан")
        print("* применены параметры по умолчанию")
        write_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG

def write_config(dct: dict):
    config = configparser.ConfigParser()
    config.read_dict(dct)
    with open(DEFAULT_CONFIG_PATH, 'w') as f:
        config.write(f)
    print(f"* записан конфиг файл {DEFAULT_CONFIG_PATH}")
    pprint(dct)
