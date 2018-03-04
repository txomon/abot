# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

from typing import Union

import pytest

from abot.bot import extract_possible_argument_types


def func_union_dict_list(b: Union[dict, list]): pass


def func_dict(b: dict): pass


@pytest.mark.parametrize('func,outcome', [
    (func_union_dict_list, (dict, list)),
    (func_dict, (dict,)),
])
def test_extract_possible_argument_types(func, outcome):
    assert outcome == extract_possible_argument_types(func)
