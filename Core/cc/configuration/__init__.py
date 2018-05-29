"""The packages of the configuration.

* models contains the building blocks.
* constants contains a collection of constants to be set on the base config object.
* helpers contain functions for working with config objects.
"""
import os
import uuid
from . import models
from . import constants
from . import helpers

from . import base_entries


def get_basic_config():
    """Setup all the fields required on a base config."""
    # config = helpers.build_config(base_entries)
    config = base_entries.LocalConfig()

    config = helpers.set_constants(config)
    config = helpers.set_methods(config)

    # Hack for non-constant dirs
    config.config_dir = config.CONFIG_DIR
    config.cache_dir = config.CACHE_DIR
    config.config_dir = config.CONFIG_DIR
    config.log_dir = config.LOG_DIR
    config.config_file = config.CONFIG_FILE_PATH
    config.lock_file = config.LOCK_FILE
    config.sync_root = os.path.join(os.path.expanduser('~'), config.APP_NAME)

    config.lock_file = os.path.join(config.config_dir, config.LOCK_FILE)

    return config
