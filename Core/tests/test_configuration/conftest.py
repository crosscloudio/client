"""Fixtures for testing cc.configuration
"""
import collections

from unittest.mock import Mock

import keyring
import pytest

from cc.configuration import helpers


class SubscriberMock():
    """Subscriber which passes the calls to a mock, against which assertions can be made.
    """
    mock = Mock()

    def reset(self):
        """Reset the mock."""
        self.mock.reset_mock()

    def handler(self, *args, **kwargs):
        """Subscription handler which passes call to the mock.
        """
        # print(args)
        # print(kwargs)
        self.mock(*args, **kwargs)


@pytest.fixture(scope='function')
def subscriber():
    """Wraps a MockSubscriber."""
    return SubscriberMock()


class InMemoryKeyring(keyring.backend.KeyringBackend):
    """ Super-Secret Long-Time In-Memory Storage Backend. """
    priority = 1
    secrets = collections.defaultdict(lambda: collections.defaultdict(None))

    def set_password(self, servicename, username, password):
        """ Sets a password for a given service and username. """
        self.secrets[servicename][username] = password

    def get_password(self, servicename, username):
        """ Retrieves a password for a given service and username. """
        return self.secrets[servicename].get(username, None)

    def delete_password(self, servicename, username):
        """ Deletes a password for a given service and username. """
        try:
            del self.secrets[servicename][username]
        except KeyError:
            pass


@pytest.fixture
def in_memory_keyring():
    """ Fixture that creates and new in memory keyring. """
    keyring.set_keyring(InMemoryKeyring())


@pytest.fixture
def no_configuration_key(config):
    """ Ensures that there is no configuration key is stored in the keychain. """
    if keyring.get_password(config.APP_NAME,
                            config.KEYCHAIN_CONFIGURATION_KEY_NAME):

        keyring.delete_password(config.APP_NAME,
                                config.KEYCHAIN_CONFIGURATION_KEY_NAME)
    key = helpers.get_configuration_key(config, auto_create=False)
    assert not key
    return config, key


@pytest.fixture
def sample_csps():
    """Set currently mounted csps."""
    csps = []
    csp1 = dict()
    csp1['id'] = 'Dropbox'
    csp1['unique_id'] = '1'
    csp1['selected_sync_directories'] = None
    csp1['type'] = 'dropbox'
    csp2 = dict()
    csp2['id'] = 'gdrive'
    csp2['unique_id'] = '2'
    csp2['selected_sync_directories'] = 'root'
    csp2['type'] = 'gdrive'
    csps.append(csp1)
    csps.append(csp2)
    return csps
