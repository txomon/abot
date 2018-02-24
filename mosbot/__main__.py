# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

from abot import cli
from mosbot.command import botcli, botcmd

main = cli.CommandCollection(sources=[botcli, botcmd])

if __name__ == '__main__':
    main()
