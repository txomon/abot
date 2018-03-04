# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import logging.config
import os
import pprint
import sys
import traceback

from alembic.config import Config
from alembic.runtime.environment import EnvironmentContext
from alembic.script import ScriptDirectory

logger = logging.getLogger(__name__)


def setup_logging(debug=False):
    filename = 'logging.conf' if not debug else 'logging-debug.conf'
    logging.config.fileConfig(os.path.join(os.path.dirname(__file__), filename), disable_existing_loggers=False)
    if debug:
        logger.debug('Level is debug now')

        # logging.getLogger('abot.dubtrack.layer3').setLevel(logging.DEBUG)
        def excepthook(type, value, tb):
            traceback.print_exception(type, value, tb)

            while tb.tb_next:
                tb = tb.tb_next

            logger.error(f'Locals: {pprint.pformat(tb.tb_frame.f_locals)}')

        sys.excepthook = excepthook
    else:
        logger.info('Level is info now')


def check_alembic_in_latest_version():
    config = Config('alembic.ini')
    script = ScriptDirectory.from_config(config)
    heads = script.get_revisions(script.get_heads())
    head = heads[0].revision
    current_head = None

    def _f(rev, context):
        nonlocal current_head
        current_head = rev[0] if rev else 'base'
        return []

    with EnvironmentContext(config, script, fn=_f):
        script.run_env()

    if head != current_head:
        raise RuntimeError(f'Database is not upgraded to latest head {head} from {current_head}')
