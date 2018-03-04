# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import logging.config
import os
import sys
import traceback

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


