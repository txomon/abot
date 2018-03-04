# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import click

from mosbot.command import botcli, botcmd

main = click.CommandCollection(sources=[botcli, botcmd])

if __name__ == '__main__':
    main()
