# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import json
import os


def get_config(env_var, *args):
    # First file
    value = None
    try:
        with open('config.json') as fd:
            file_config = json.load(fd)
        for k, v in file_config.items():
            if k.upper() == env_var:
                value = v
    except:
        pass
    # Second environment
    env_config = os.environ.get(env_var)
    if env_config is not None:
        try:
            value = json.loads(env_config)
        except:
            value = env_config
    if args:
        return value if value else args[0]
    raise EnvironmentError(f'Configuration {env_var} variable is not set by file or environment')


DATABASE_URL = get_config('DATABASE_URL', 'postgresql://localhost/test')

DUBTRACK_USERNAME = get_config('DUBTRACK_USERNAME', None)
DUBTRACK_PASSWORD = get_config('DUBTRACK_PASSWORD', None)
