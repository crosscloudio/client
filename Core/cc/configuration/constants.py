"""Application Constants which need to be added to the base config during startup.

Use py:func:~`cc.configuration.helpers.set_constants, to add these to a config.
Note only uppercase constant names are added.
"""
import sys
import os
import appdirs
APP_NAME = 'CrossCloud'

# defining codes for determining between os
WINDOWS_PLATFORM_CODE = 'win32'
MACOS_PLATFORM_CODE = 'darwin'

if not getattr(sys, 'frozen', False):
    APP_NAME += '-DEV'

VERSION = '1.0'
CONFIG_FILE = 'config.json'
# Specifies the current schema version of configuration file.
CONFIGURATION_SCHEMA_VERSION = '1.0'
SYNC_ENGINE_STATE = 'sync_state.p'
LOCK_FILE = 'crosscloud.lock'

# define the name of the keyring item the key will be stored in.
KEYCHAIN_CONFIGURATION_KEY_NAME = 'CrossCloud Configuration Key'
KEYCHAIN_CONFIGURATION_KEY_IV_SIZE = 16  # 128 bits
KEYCHAIN_CONFIGURATION_KEY_SIZE = 32  # 256 bits

KEYCHAIN_CONFIGURATION_TAG_NAME = 'CrossCloud Configuration Tag'
KEYCHAIN_CONFIGURATION_TAG_SIZE = 16  # 128 bits

HIDDEN_FILE_PREFIX = '.crosscloud_'


CONFIG_DIR = appdirs.user_config_dir(appname=APP_NAME, version=VERSION)

CONFIG_FILE_PATH = os.path.join(CONFIG_DIR, CONFIG_FILE)
CACHE_DIR = appdirs.user_cache_dir(appname=APP_NAME, version=VERSION)
LOG_DIR = appdirs.user_log_dir(appname=APP_NAME, version=VERSION)

# path to the resources directory
if hasattr(sys, 'frozen'):
    RESOURCES_DIR = os.path.join(os.path.dirname(sys.executable), 'resources')
else:
    RESOURCES_DIR = os.path.join(os.path.dirname(__file__), "resources")
