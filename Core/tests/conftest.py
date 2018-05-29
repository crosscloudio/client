"""Configuration for pytest."""
import os
import sys
import shutil
import tempfile
import uuid

import pytest

from cc.log_utils import setup_logging
from cc.configuration import models

TEMP_LOG_DIR = tempfile.mkdtemp(suffix='cc_test_run')
if sys.platform == 'win32':
    # because win32 does not find pytest_report_header correctly
    setup_logging(TEMP_LOG_DIR)


# pylint: disable=redefined-outer-name
# TODO: rename the config fixture below to client_config to solve the redefined-outer-name issue
def pytest_report_header(config):
    """Setup logging and inform the user where logs are going unless verbosity is increased

    To display logs directly use
    `py.test -vvvs`
    """
    if sys.platform == 'win32':
        # logging has been setup outside of this function.
        pass
    elif not config.getoption('verbose') > 2:
        setup_logging(TEMP_LOG_DIR)
    return 'Logging dir: %s' % TEMP_LOG_DIR


def pytest_addoption(parser):
    """Add an option to run manual tests"""
    parser.addoption("--manual", action="store_true",
                     help="run semi automatic tests, which require manual interaction.")

    parser.addoption("--integration-config", action="store",
                     help="Path to integration test config file (YAML)")


@pytest.fixture
def config(request):
    """Instantiate a config object."""
    dir_name = tempfile.mkdtemp()
    request.addfinalizer(lambda: shutil.rmtree(dir_name))

    test_config = models.Config()
    test_config.KEYCHAIN_CONFIGURATION_KEY_NAME = 'CrossCloud Configuration Key'
    test_config.APP_NAME = 'CrossCloud-DEV'
    test_config.KEYCHAIN_CONFIGURATION_KEY_SIZE = 32  # 256 bits
    test_config.KEYCHAIN_CONFIGURATION_TAG_NAME = 'CrossCloud Configuration Tag'
    test_config.KEYCHAIN_CONFIGURATION_TAG_SIZE = 16  # 128 bits
    test_config.VERSION = '1.0'
    test_config.CONFIG_FILE = 'config.json'
    test_config.CONFIGURATION_SCHEMA_VERSION = '1.0'
    test_config.KEYCHAIN_CONFIGURATION_KEY_IV_SIZE = 16  # 128 bits
    test_config.CONFIG_DIR = dir_name
    test_config.config_dir = dir_name
    test_config.CACHE_DIR = dir_name
    test_config.cache_dir = dir_name
    test_config.LOG_DIR = dir_name
    test_config.log_dir = dir_name
    test_config.HIDDEN_FILE_PREFIX = '.test_crosscloud_'
    test_config.encryption_csp_settings = []
    test_config.csps = []
    test_config.policies = []
    test_config.encryption_enabled = False
    test_config.encrypt_external_shares = True
    test_config.encrypt_public_shares = False
    test_config.last_login = ''
    test_config.auth_token = None
    test_config.admin_console_csps = []
    test_config.shares_with_external_users = []
    test_config.sync_root = tempfile.mkdtemp()
    test_config.device_id = str(uuid.uuid1())
    test_config.config_file = os.path.join(dir_name, test_config.CONFIG_FILE)
    test_config.device_public_key = b'tempdir:devicepublickey'
    test_config.device_private_key = b'tempdir:deviceprivatekey'
    test_config.user_public_key = b'tempdir:userpublickey'
    test_config.user_private_key = b'tempdir:userprivatekey'
    test_config.auth_token = ''
    test_config.enabled_storage_types = ['dropbox', 'gdrive', 'owncloud']
    test_config.share_key_pairs = {}
    test_config.blocked_extensions = set()
    test_config.blocked_mime_types = set()
    return test_config


@pytest.fixture
def integration_config(request):
    """Clean and return the path passed via --integration-config."""
    path = request.config.getoption("--integration-config")

    if path is not None:
        path = os.path.abspath(os.path.expanduser(path))

    return path
