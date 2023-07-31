import configparser
import os

DEFAULT_CONFIG_PATH = os.path.abspath("config.ini")

DEFAULT_CONFIG = {
    'Plotter' : {
        'autocolor' : 0,
        'default_heat_color' : '100,0,0',
        'default_cool_color' : '0,0,100'
    }
}

def _parse_config(config: configparser.ConfigParser) -> dict:
    return {
            'Plotter' : {
                'autocolor' : bool(int(config['Plotter']['autocolor'])),
                'default_heat_color' : [float(n)/100 for n in config['Plotter']['default_heat_color'].split(',')],
                'default_cool_color' : [float(n)/100 for n in config['Plotter']['default_cool_color'].split(',')]
            }
        }

def read_config():
    config = configparser.ConfigParser()
    if config.read(DEFAULT_CONFIG_PATH):
        dct = _parse_config(config=config)
        print(f"* прочитан конфиг файл {DEFAULT_CONFIG_PATH}")
        return dct
    else:
        print("* конфиг файл не прочитан")
        print("* применены параметры по умолчанию")
        write_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG

def write_config(dct: dict):
    config = configparser.ConfigParser()
    config.read_dict(dct)
    with open('config.ini', 'w') as f:
        config.write(f)
