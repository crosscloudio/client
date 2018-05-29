"""Various components required for logging."""

import logging.handlers
import logging.config
import os
import sys

from raven.handlers.logging import SentryHandler
import yaml
import cc


def setup_logging(log_dir):
    """Set up the logging for the client."""
    # The location of the logfile stays the same, we only want to define what is written to it.
    file_handler = logging.handlers.RotatingFileHandler(os.path.join(log_dir, 'client.log'),
                                                        backupCount=5,
                                                        maxBytes=(1024 * 1024 * 50),
                                                        mode='w',
                                                        encoding="UTF-8")
    # rotates the file once to have a clean output
    file_handler.doRollover()

    # redirect all stderr to the logger
    # sys.stderr = StreamToLogger(logging.getLogger('stderr'))

    if hasattr(sys, 'frozen'):
        # If we are in production use a simple log format and set the overall log level to
        # "WARNING". If CC_DEBUG is set we enable DEBUG for certain CC internal modules.
        root = logging.getLogger()
        simple_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(simple_format)
        root.addHandler(file_handler)

        # Set default logging level
        root.setLevel(logging.WARNING)

        # If CC_DEBUG is set enable DEBUG mode for CC internal modules only.
        if os.environ.get('CC_DEBUG', False):
            logging.getLogger("cc").setLevel(logging.DEBUG)
            logging.getLogger('jars').setLevel(logging.DEBUG)
            logging.getLogger('bushn').setLevel(logging.DEBUG)
            logging.getLogger("cc.ipc_server").setLevel(logging.WARNING)
            logging.getLogger('cc.connection_state').setLevel(logging.WARNING)

        # Setup and enable logging to sentry.
        sentry_handler = SentryHandler('https://5c5af4f036d541a5bc440ce9469bff69:'
                                       '807a50ea8c5d483fab655d8695904100@sentry.io/209330',
                                       release=cc.__version__)
        sentry_handler.setLevel(logging.ERROR)
        root.addHandler(sentry_handler)
    else:
        # We are in development. If CC_LOGGING_CFG is set and points to an existing file you
        # can specify the entire logging configuration here. run wild.
        dev_logging_setup = os.environ.get('CC_LOGGING_CFG', None)
        if dev_logging_setup:
            with open(dev_logging_setup) as log_config:
                logging.config.dictConfig(yaml.load(log_config))

        root = logging.getLogger()
        detailed_format = '%(asctime)s %(name)-25s %(levelname)-6s[ %(funcName)-10s] %(message)s'
        file_handler.setFormatter(logging.Formatter(detailed_format))
        root.addHandler(file_handler)

        # Set default logging level if not using custom logging configuration.
        if dev_logging_setup is None:
            root.setLevel(logging.DEBUG)
