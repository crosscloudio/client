"""
Unit tests for the settings sync module (acounts, rules, etc)
"""
# pylint: disable=redefined-outer-name, too-many-lines
import json
import logging
import time
import mock
import pytest
import requests_mock
import requests
from jars import SharedFolder

from cc import config
import cc.crypto
import cc.crypto2
import cc.settings_sync
from cc.client import SYNC_ADMIN_CONSOLE_PERIOD, Client
from cc.encryption.storage_wrapper import EncryptedVersionTag
from cc.periodic_scheduler import PeriodicScheduler

logger = logging.getLogger(__name__)

# pylint: disable=invalid-name, redefined-outer-name

DEVICE_KEY_PAIR = cc.crypto2.KeyPair(
    private_pem=b'''-----BEGIN PRIVATE KEY-----
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
Etsykg/rIj3o+dmQegI+RFhykYuUs2g=
-----END PRIVATE KEY-----''',
    public_pem=b'''-----BEGIN RSA PUBLIC KEY-----
MIICCgKCAgEA2PM2ALyuh/NcFzda8IgxYPt8CIh34OT9Ug0T5s+mZRNCF3rsb+wU
yGiz8fJ9XU+0nVS2ZfvSHLBFZl4E+5O3UqLJPckB00ROszdGTfM+43F5gSsAYC9k
CByHtFgJ4kKWzo6W0dNP6jQXuF0IDuilXqJp7mJs8rkqjKuvjpyEFQiktGSMBGZn
vpYu9S4FAJHN1G/ptBokbWSLRx7uDCzTnEDIXoQSUNY7vKVPwHIeJSK4vvduacFJ
+FLJtbtmMBRCMQ3iDFSaRVZwLS7XTxaAGeLsyfPCmsnm34cAENpQWgTaZLFh0rRD
FJMDW6uFu1rsuVa1/c81P0EvtCNSW8CtNBlHuYIDT/GFM4TKdbcT4FvlVzCmfiVp
QbZD0GQxnQe9OUDpgWNUdaa4vmfq1kC6nLq1BRekykDoeGuHwk1RgXiyZw5N3frx
yMiX9yMm+E+uLUVEvYukrFYn5WfMhSlboET1B8+YK0aS5ODXzeDhaPOUunHx02Hv
Rg0xiK107iHeU8cVojTlJP8J4pyluhKEBYrF4C7Dnd6iALhuloL4+omXrq0r96v7
ysT2BotqQzdjS7PNZfs9oqCii+jvkPenwh48s4CrCN8zE4mnii9gz4LvrWv3xZgQ
oIRHf+KAryYP/A76Wd9Ece9w6TQTDKWc6hr7U5kn/5klbgCCBEmrbtMCAwEAAQ==
-----END RSA PUBLIC KEY-----''')

FAKE_SERVER_CONFIG = {
    "id": "1",
    "email": "jakob@crosscloud.net",
    "roles": [
        "user",
        "administrator"
    ],
    "public_key": "test_key_public_user",
    "encrypted_user_keys": [],
    "approval_requests": [],
    "organization": {
        "id": "1",
        "display_name": "CrossCloud",
        "encryption": {
            "enabled": True
        },
        "policies": []
    },
    "csps": [
        {
            "id": "5",
            "csp_id": "gdrive_1489139368.067954",
            "display_name": "Gdrive",
            "type": "gdrive",
            "unique_id": "crosscloud.cloudtest@gmail.com",
            "shares": [
                {
                    "has_external_users": True,
                    "id": "2",
                    "name": "shary2",
                    "storage_type": "gdrive",
                    "unique_id": "0BxzVEypHi3fOeHEzV3JXMTVYdFk",
                    "public_share_key": "a public key",
                    "share_key_for_current_user": None,
                    "storage_unique_ids": ["crosscloud.cloudtest2@gmail.com",
                                           "crosscloud.cloudtest@gmail.com"],
                    "csps": [
                        {
                            "unique_id": "crosscloud.cloudtest2@gmail.com",
                            "user": {
                                "email": "crosscloud.cloudtest2@gmail.com",
                                "public_key": "-----BEGIN RSA PUBLIC KEY-----\n"
                                              "MIICCgKCAgEAtqgn6PR9DlGBmXHESfmWcgsVrCy+"
                                              "\n-----END RSA PUBLIC KEY-----\n"
                            }
                        },
                        {
                            "unique_id": "crosscloud.cloudtest@gmail.com",
                            "user": {
                                "email": "jakob@crosscloud.net",
                                "public_key": "-----BEGIN RSA PUBLIC KEY-----\n"
                                              "MIICCgKCAgEA0MturWSl5GoDF/YWEOjn7cXScjIC"
                                              "\n-----END RSA PUBLIC KEY-----\n"}
                        }
                    ]
                }
            ]
        }
    ]
}

EMPTY_FAKE_SERVER_CONFIG = {
    "id": "1",
    "email": "christoph@crosscloud.me",
    "roles": [
        "user",
        "administrator"
    ],
    "public_key": "test_key_public_user",
    "encrypted_user_keys": [],
    "approval_requests": [],
    "organization": {
        "id": "1",
        "display_name": "CrossCloud",
        "encryption": {
            "enabled": "false",
            "password": "",
            "master_key_pem": "null",
            "salt": "null"
        },
        "policies": [
            {
                "name": "Python Files",
                "type": "fileextension",
                "criteria": "py",
                "is_enabled": "true"
            },
            {
                "name": "Private Keys",
                "type": "fileextension",
                "criteria": "der",
                "is_enabled": "true"
            },
            {
                "name": "Private Keys (PEM) ",
                "type": "fileextension",
                "criteria": "pem",
                "is_enabled": "true"
            }
        ]
    },
    "csps": [

    ]
}

FAKE_SERVER_CONFIG_NO_SHARE_KEY = {
    "csps": [
        {
            "id": "5",
            "csp_id": "fake_gdrive_1",
            "display_name": "Gdrive",
            "type": "gdrive",
            "unique_id": "crosscloud.cloudtest@gmail.com",
            "shares": [
                {
                    "has_external_users": True,
                    "id": "2",
                    "name": "shary2",
                    "storage_type": "gdrive",
                    "unique_id": "0BxzVEypHi3fOeHEzV3JXMTVYdFk",
                    "public_share_key": "a public key",
                    "share_key_for_current_user": None,
                    "csps": [
                        {
                            "unique_id": "crosscloud.cloudtest2@gmail.com",
                            "user": {
                                "email": "crosscloud.cloudtest2@gmail.com",
                                "public_key": "-----BEGIN RSA PUBLIC KEY-----\n"
                                              "MIICCgKCAgEAtqgn6PR9DlGBmXHESfmWcgsVrCy+"
                                              "\n-----END RSA PUBLIC KEY-----\n"
                            }
                        },
                        {
                            "unique_id": "crosscloud.cloudtest@gmail.com",
                            "user": {
                                "email": "jakob@crosscloud.net",
                                "public_key": "-----BEGIN RSA PUBLIC KEY-----\n"
                                              "MIICCgKCAgEA0MturWSl5GoDF/YWEOjn7cXScjIC"
                                              "\n-----END RSA PUBLIC KEY-----\n"}
                        }
                    ]
                }
            ]
        }
    ]
}

FAKE_SERVER_CONFIG_SHARE_KEY = {
    "csps": [
        {
            "id": "5",
            "csp_id": "fake_gdrive_1",
            "display_name": "Gdrive",
            "type": "gdrive",
            "unique_id": "crosscloud.cloudtest@gmail.com",
            "shares": [
                {
                    "has_external_users": True,
                    "id": "2",
                    "name": "shary2",
                    "storage_type": "gdrive",
                    "unique_id": "0BxzVEypHi3fOeHEzV3JXMTVYdFk",
                    "public_share_key": "a public key",
                    "share_key_for_current_user": {
                        "encrypted_share_key": json.dumps("fake_encrypted_share_key")
                    },
                    "csps": [
                        {
                            "unique_id": "crosscloud.cloudtest2@gmail.com",
                            "user": {
                                "email": "crosscloud.cloudtest2@gmail.com",
                                "public_key": "-----BEGIN RSA PUBLIC KEY-----\n"
                                              "MIICCgKCAgEAtqgn6PR9DlGBmXHESfmWcgsVrCy+"
                                              "\n-----END RSA PUBLIC KEY-----\n"
                            }
                        },
                        {
                            "unique_id": "crosscloud.cloudtest@gmail.com",
                            "user": {
                                "email": "jakob@crosscloud.net",
                                "public_key": "-----BEGIN RSA PUBLIC KEY-----\n"
                                              "MIICCgKCAgEA0MturWSl5GoDF/YWEOjn7cXScjIC"
                                              "\n-----END RSA PUBLIC KEY-----\n"}
                        }
                    ]
                }
            ]
        }
    ]
}


def test_update_policies_success(config, mocker):
    """Test the successful policy fetching"""

    # mock the policies in the config
    policies = [
        {
            "name": "test",
            "type": "fileextension",
            "criteria": "123",
            "is_enabled": True
        },
        {
            "name": "texts",
            "type": "mimetype",
            "criteria": "text/html,text/plain",
            "is_enabled": True
        }
    ]
    server_config = {'organization': {'policies': policies}}

    # setting mock server config
    mocker.patch('cc.settings_sync.server_config', server_config)

    # running update policies
    cc.settings_sync.update_policies(config)

    # asserting result
    assert config.blocked_extensions == {'123'}
    assert config.blocked_mime_types == {'text/html', 'text/plain'}


def test_update_crypto_parameters_written(mocker, config):
    """ Tests the correct translation of crypto parameters into config settings"""
    # mocking the server encryption configuration
    encryption_types = [{"type": "dropbox", "enabled": False},
                        {"type": "onedrive", "enabled": True}]

    encryption = {
        "encrypt_external_shares": True,
        "encrypt_public_shares": True,
        "enabled": True,
        "csps_settings": encryption_types,
        "master_key": "yeah"
    }

    # setting mock public key
    mock_public_key = b'tempdir:userpublickey'.decode('ascii')

    # creating final mock server configuration
    mocker.patch('cc.settings_sync.server_config',
                 {'organization': {'encryption': encryption, 'id': 'loong uuid'},
                  'public_key': mock_public_key, 'encrypted_user_keys': [],
                  })

    # defining mocks to check side effect call
    mock_key_setup = mock.MagicMock()
    mock_request_device_approval = mock.MagicMock()

    config.encrypt_external_shares = False
    # with mocked config, updating crypto and checking if values are
    with mock.patch('cc.settings_sync.perform_initial_key_setup',
                    new=mock_key_setup), \
            mock.patch('cc.settings_sync.request_device_approval',
                       new=mock_request_device_approval), \
            mock.patch('cc.configuration.helpers.write_config'):
        cc.settings_sync.update_crypto(config=config)
        assert config.encryption_enabled is True
        assert config.encrypt_public_shares is True
        assert config.encrypt_external_shares is True
        assert config.encryption_csp_settings == {'dropbox': False, 'onedrive': True}

        # asserting that mocks were not called
        mock_key_setup.assert_not_called()
        mock_request_device_approval.assert_not_called()


def test_update_crypto_init_user_keys(mocker, config):
    """ tests the initial setup of keys in case not configured yet """
    encryption = {
        "encrypt_external_shares": False,
        "encrypt_public_shares": False,
        "enabled": False,
        "csps_settings": [],
        "master_key": "yeah"
    }

    # creating final mock server configuration
    mocker.patch('cc.settings_sync.server_config',
                 {'organization': {'encryption': encryption, 'id': '123123'},
                  'public_key': None,
                  'id': 'loong uuid'})

    # creating mock for AC call
    ac_mock = mock.MagicMock()
    mock_device_id = 'my_device_id'

    # with mocked config, updating crypto and checking if values are set
    config.device_private_key = None
    config.device_public_key = None
    config.user_private_key = None
    config.user_public_key = None
    config.device_id = mock_device_id
    with mock.patch('cc.settings_sync.init_admin_console_user_keys', new=ac_mock), \
            mock.patch('cc.configuration.helpers.write_config'):
        cc.settings_sync.update_crypto(config=config)
        print(config.user_public_key)
        assert config.user_public_key is not None
        assert config.user_private_key is not None
        assert config.device_public_key is not None
        assert config.device_private_key is not None

        ac_mock.assert_called_once()

        # getting key word arguments of call
        call = ac_mock.call_args[1]

        # extracting arguments of call
        device_id_call = call['device_id']
        public_user_key_call = call['public_user_key']
        encrypted_private_user_key_call = call['encrypted_private_user_key']
        public_device_key_call = call['public_device_key']

        assert device_id_call == mock_device_id
        assert public_user_key_call == config.user_public_key
        assert public_device_key_call == config.device_public_key

        assert cc.crypto2.unwrap_private_key(
            wrapped_object=encrypted_private_user_key_call,
            private_key_object=cc.crypto2.load_pem_private_key(
                config.device_private_key)) == config.user_private_key


def test_update_crypto_request_device_approval(mocker, config):
    """ test the mechanism for requesting approval from another device """
    encryption = {
        "encrypt_external_shares": False,
        "encrypt_public_shares": False,
        "enabled": False,
        "csps_settings": [],
        'master_key': 'pem file'
    }

    # setting differing public user keys on ac and locally
    public_key_local = b'public_key_local'
    public_key_ac = b'public_key_ac'

    # creating final mock server configuration
    mocker.patch('cc.settings_sync.server_config',
                 {'organization': {'encryption': encryption, 'id': 'loong uuid'},
                  'public_key': public_key_ac.decode('ascii'),
                  'encrypted_user_keys': []})

    # creating mock for AC call
    ac_mock = mock.MagicMock()
    mock_device_id = 'my_device_id'

    # with mocked config, updating crypto and checking if values are set
    config.device_private_key = None
    config.device_public_key = None
    config.user_public_key = public_key_local
    config.device_id = mock_device_id
    with mock.patch('cc.settings_sync.request_device_approval', new=ac_mock), \
            mock.patch('cc.configuration.helpers.write_config'):
        with pytest.raises(cc.DeviceApprovalRequiredError):
            cc.settings_sync.update_crypto(config)

        assert config.device_public_key is not None
        assert config.device_private_key is not None

        ac_mock.assert_called_once()

        # getting key word arguments of call
        call = ac_mock.call_args[1]

        # extracting arguments of call
        device_id_call = call['device_id']
        public_device_key_call = call['public_device_key']

        assert device_id_call == mock_device_id
        assert public_device_key_call == config.device_public_key


@mock.patch('cc.configuration.helpers.write_config')
def test_update_crypto_device_approved(config):
    """tests the handling if a approval request from another device was granted"""
    # mock: device_id
    encryption = {
        "encrypt_external_shares": False,
        "encrypt_public_shares": False,
        "enabled": False,
        "csps_settings": [],
        "master_key": "hello key"
    }

    # setting differing public user keys on ac and locally
    (mock_private_device_key, mock_public_device_key) = DEVICE_KEY_PAIR

    # key pair of
    (mock_private_user_key, mock_public_user_key) = cc.crypto2.generate_keypair()

    # mock device key
    mock_device_id = 'my_mock_device_key'

    # preparing approved request
    wrapped_user_key = \
        cc.crypto2.wrap_private_key(private_key_pem=mock_private_user_key,
                                    public_key_object=cc.crypto2.load_pem_public_key(
                                        mock_public_device_key))

    # creating final mock server configuration
    cc.settings_sync.server_config = {'organization': {'encryption': encryption, 'id': '123123'},
                                      'public_key': mock_public_user_key.decode('ascii'),
                                      'encrypted_user_keys': [{
                                          'public_device_key':
                                              mock_public_device_key.decode('ascii'),
                                          'device_id': mock_device_id,
                                          'encrypted_user_key':
                                              json.dumps(wrapped_user_key)
                                      }]
                                      }

    # creating mock for AC call
    ac_mock = mock.MagicMock()

    # with mocked config, updating crypto and checking if values are set
    config.device_private_key = mock_private_device_key
    config.device_public_key = mock_public_device_key
    config.user_public_key = None
    config.user_private_key = None
    config.device_id = mock_device_id
    with mock.patch('cc.settings_sync.request_device_approval', new=ac_mock):
        # calling update crypto
        cc.settings_sync.update_crypto(config)

        assert config.user_public_key == mock_public_user_key
        assert config.user_private_key == mock_private_user_key

        ac_mock.assert_not_called()


@pytest.fixture()
def add_remove_mocks(mocker):
    """
    Mocks all the add and remove functions and returns an example server response
    """

    add_local_mock = mock.MagicMock()
    remove_local_mock = mock.MagicMock()
    add_remote_mock = mock.MagicMock()
    remove_remote_mock = mock.MagicMock()
    mocker.patch('cc.settings_sync.add_csp_local', new=add_local_mock)
    mocker.patch('cc.settings_sync.add_csp_remote',
                 new=add_remote_mock)
    # mocker.patch('cc.settings_sync.remove_csp_local',
    #              new=remove_local_mock)
    mocker.patch('cc.settings_sync.remove_csp_remote',
                 new=remove_remote_mock)

    server_conf = {
        "id": "1",
        "email": "jakob@crosscloud.net",
        "roles": [],
        "organization": {
            "id": "1",
            "display_name": "CrossCloud",
            "encryption": {
                "enabled": "true",
                "password": "",
                "master_key_pem": None,
                "salt": None
            },
            "policies": [
                {
                    "name": "Zip files",
                    "type": "fileextension",
                    "criteria": "zip"
                }
            ]
        },
        "csps": [
            {
                "id": "16",
                "display_name": "Cifs 0",
                "csp_id": "cifs_1484126421.005579",
                "unique_id": '\\\\JAKOB-XPS13\\Shares\\Customers',
                "type": "cifs",
                "authentication_data": {'password': None,
                                        'unc_path': '\\\\JAKOB-XPS13\\Shares\\Customers',
                                        'username': None}
            }
        ]
    }

    return ((add_local_mock, remove_local_mock, add_remote_mock, remove_remote_mock),
            server_conf)


@pytest.mark.skip
def test_handle_changes_add_local(add_remove_mocks, config):
    """
    The local list is empty and the remote list has a configured storage so this
    storage has to be added
    """
    ((add_local_mock, remove_local_mock,
      add_remote_mock, remove_remote_mock), server_conf) = add_remove_mocks

    # added a csp remote so it has to be added locally
    with mock.patch('config.csps', new=[]):
        # setting mock server config
        cc.settings_sync.server_config = server_conf

        # calling update function
        cc.settings_sync.update_storages(config=config)

        add_local_mock.assert_called_once()
        add_remote_mock.assert_not_called()
        remove_local_mock.assert_not_called()
        remove_remote_mock.assert_not_called()

    add_local_mock.reset_mock()


def test_handle_changes_in_sync(add_remove_mocks, config):
    """
    The local and remote list is equal so nothing has to be done
    """
    ((add_local_mock, remove_local_mock,
      add_remote_mock, remove_remote_mock), server_conf) = add_remove_mocks
    config.csps = [{'display_name': 'Cifs 0',
                    'id': 'cifs_1484126421.005579',
                    'selected_sync_directories': [{'children': True, 'path': []}],
                    'type': 'cifs',
                    'unique_id': '\\\\JAKOB-XPS13\\Shares\\Customers'}]

    # setting mock server config
    cc.settings_sync.server_config = server_conf

    # calling update function
    cc.settings_sync.update_storages(config=config)

    # asserting calls
    add_local_mock.assert_not_called()
    add_remote_mock.assert_not_called()
    remove_local_mock.assert_not_called()
    remove_remote_mock.assert_not_called()


@pytest.mark.skip
def test_handle_changes_remove_local(add_remove_mocks, config):
    """removed a csp remotely so it has to be removed locally"""
    ((add_local_mock, remove_local_mock,
      add_remote_mock, remove_remote_mock), server_conf) = add_remove_mocks
    with mock.patch('config.csps', new=[
        {'display_name': 'Cifs 0',
         'id': 'cifs_1484126421.005579',
         'selected_sync_directories': [
             {'children': True, 'path': []}],
         'type': 'cifs',
         'unique_id': '\\\\JAKOB-XPS13\\Shares\\Customers'}]):
        with mock.patch('config.admin_console_csps', ['cifs_1484126421.005579']):
            # setting mock server config
            cc.settings_sync.server_config = server_conf

            # setting empty csps
            cc.settings_sync.server_config['csps'] = []

            # calling update function
            cc.settings_sync.update_storages(config=config)

            # asserting calls
            add_local_mock.assert_not_called()
            add_remote_mock.assert_not_called()
            remove_local_mock.assert_called_once()
            remove_remote_mock.assert_not_called()
        remove_local_mock.reset_mock()


def test_handle_changes_remove_remote(add_remove_mocks, config):
    """Remove a previously synced csp locally so it has to be removed remotely."""
    ((add_local_mock, remove_local_mock,
      add_remote_mock, remove_remote_mock), server_conf) = add_remove_mocks

    config.csps = []
    config.admin_console_csps = ['cifs_1484126421.005579']
    # setting mock server config
    cc.settings_sync.server_config = server_conf

    # calling update function
    cc.settings_sync.update_storages(config=config)

    # asserting calls
    add_local_mock.assert_not_called()
    add_remote_mock.assert_not_called()
    remove_local_mock.assert_not_called()
    remove_remote_mock.assert_called_once()


def test_handle_changes_add_remote(add_remove_mocks, config):
    """Remove a previously synced csp locally so it has to be removed remotely."""
    ((add_local_mock, remove_local_mock,
      add_remote_mock, remove_remote_mock), server_conf) = add_remove_mocks

    config.csps = [{'display_name': 'Cifs 0',
                    'id': 'cifs_1484126421.005579',
                    'selected_sync_directories': [{'children': True, 'path': []}],
                    'type': 'cifs',
                    'unique_id':'\\\\JAKOB-XPS13\\Shares\\Customers'},
                   {'display_name': 'Cifs 1',
                    'id': 'cifs_1234123412.12345',
                    'selected_sync_directories': [{'children': True, 'path': []}],
                    'type': 'cifs',
                    'unique_id': '\\\\JAKOB-XPS13\\Shares\\Public'}]
    config.admin_console_csps = ['cifs_1484126421.005579']
    # setting mock server config
    cc.settings_sync.server_config = server_conf

    # calling update function
    cc.settings_sync.update_storages(config=config)

    # asserting calls
    add_local_mock.assert_not_called()
    add_remote_mock.assert_called_once()
    remove_local_mock.assert_not_called()
    remove_remote_mock.assert_not_called()


def test_add_csp_local(config):
    """Test the local adding of accounts.

    :return:
    """
    auth_data = {'a': 'b'}
    csp = {
        "id": "1",
        "csp_id": "dropbox_1485254155.4567137",
        "unique_id": "crosscloud.cloudtest@gmail.com",
        "authentication_data": auth_data,
        "display_name": "Dropbox 0",
        "type": "dropbox"
    }

    config.csps = []
    config.write_config = mock.Mock()
    cc.settings_sync.add_csp_local(csp=csp, config=config)
    assert config.csps[0]['id'] == csp['csp_id']
    assert config.csps[0]['unique_id'] == csp['unique_id']
    assert config.csps[0]['display_name'] == csp['display_name']
    assert config.csps[0]['credentials'] == auth_data


# def test_remove_csp_local(config):
#     """Test the local removing of accounts.

#     :return:
#     """
#     config.remove_csp = mock.Mock()
#     csp = {"csp_id": "dropbox_1485254155.4567137"}
#     cc.settings_sync.remove_csp_local(csp, field='csp_id', config=config)
#     config.remove_csp.assert_called_once_with(mock.ANY, csp['csp_id'])
#     config.remove_csp.reset_mock()

#     csp = {"id": "dropbox_1485254155.4567137"}
#     cc.settings_sync.remove_csp_local(csp, config=config)
#     config.remove_csp.assert_called_once_with(mock.ANY, csp['id'])


@pytest.fixture
def fake_get_token(mocker):
    """ fakes the get_token """
    mocker.patch('cc.settings_sync.get_token', lambda config: {"token": 123})


@pytest.mark.usefixtures('fake_get_token')
def test_add_csp_remote_cifs(config):
    """Test remote function is called correctly, if a cifs share."""
    csp = {'display_name': 'Cifs 0',
           'id': 'cifs_1484126421.005579',
           'selected_sync_directories': [
               {'children': True, 'path': []}],
           'type': 'cifs',
           'unique_id': r'\\JAKOB-XPS13\Shares\Customers',
           'credentials': json.dumps({"random json": "1"})}

    with requests_mock.Mocker() as rmock:
        rmock.post(cc.settings_sync.GRAPHQL_URL)
        cc.settings_sync.add_csp_remote(csp, config=config)
        json_data = rmock.last_request.json()
        assert json_data['query'].startswith('mutation')
        assert json_data['variables']['input'] == {
            'csp_id': csp['id'],
            'type': csp['type'],
            'display_name': csp['display_name'],
            'unique_id': csp['unique_id'],
            'authentication_data': json.dumps({"random json": "1"})}


@pytest.mark.usefixtures('fake_get_token')
def test_add_csp_remote(config):
    """ test if the remote function was called correctly, if a cifs share """
    csp = {'display_name': 'Dropbox 0',
           'id': 'dropbox_1484126421.005579',
           'selected_sync_directories': [{'children': True, 'path': []}],
           'type': 'dropbox',
           'credentials': json.dumps({'username': 'a', 'password': 'b'}),
           'unique_id': r'xxxxxyxy'}

    with requests_mock.Mocker() as rmock:
        rmock.post(cc.settings_sync.GRAPHQL_URL)
        cc.settings_sync.add_csp_remote(csp, config)
        json_data = rmock.last_request.json()
        assert json_data['query'].startswith('mutation AddCspMutation')
        assert json_data['variables']['input'] == {
            'csp_id': csp['id'],
            'type': csp['type'],
            'display_name': csp['display_name'],
            'authentication_data': csp['credentials'],
            'unique_id': csp['unique_id']}


@pytest.mark.usefixtures('fake_get_token')
def test_remove_csp_remote(config):
    """Test if the remote function was called correctly, if a cifs share """
    csp = {'csp_id': 'dropbox_1484126421.005579'}

    with requests_mock.Mocker() as rmock:
        rmock.post(cc.settings_sync.GRAPHQL_URL)
        cc.settings_sync.remove_csp_remote(csp, config)
        json_data = rmock.last_request.json()
        assert json_data['query'].startswith('mutation DeleteCspMutation')
        assert json_data['variables'] == {'csp_id': csp['csp_id']}


def test_settings_sync_offline(config):
    """Test the proper exception handling when there is no internet connection"""
    session_mock = mock.MagicMock()
    session_mock.post = mock.MagicMock()
    session_mock.post.side_effect = requests.exceptions.ConnectionError()

    token_mock = mock.MagicMock()

    with mock.patch('cc.settings_sync.get_session',
                    mock.MagicMock(return_value=session_mock)), \
        mock.patch('cc.settings_sync.get_token',
                   mock.MagicMock(return_value=token_mock)), \
            pytest.raises(requests.exceptions.ConnectionError):
        cc.settings_sync.fetch_admin_console_configuration(config)


def test_settings_sync_unauthenticated(config):
    """Test the proper handling fo unauthenticated users."""

    # testing that unauthenticated error is thrown
    with pytest.raises(cc.UnauthenticatedUserError), \
            mock.patch('cc.settings_sync.get_token', mock.MagicMock(return_value=None)):
        cc.settings_sync.fetch_and_apply_configuration(config)


def test_update_share_information_remove(mocker, config):
    """ Tests that csp removed if only on server"""
    mock_storage = mock.MagicMock()
    mock_storage.storage_id = 'gdrive_1489139368.067954'
    config.auth_token = 'something'

    def mock_get_shared_folders():
        """ helper to mock local shares """
        return []

    mocker.patch('cc.configuration.helpers.write_config')

    # TODO: use mocker fixture here
    mock_storage.get_shared_folders.return_value = mock_get_shared_folders()
    mock_add_share_remote = mock.MagicMock()
    mock_remove_user_remote = mock.MagicMock()
    mock_adapt_users_remote = mock.MagicMock()
    config.csps = [{'id': 'gdrive_1489139368.067954',
                    'type': 'gdrive',
                    'unique_id': "crosscloud.cloudtest@gmail.com"}]

    with mock.patch('cc.settings_sync.add_share_remote', new=mock_add_share_remote), \
            mock.patch('cc.settings_sync.remove_user_from_share_remote',
                       new=mock_remove_user_remote), \
            mock.patch('cc.settings_sync.adapt_users_of_share_remote',
                       new=mock_adapt_users_remote), \
            mock.patch('cc.settings_sync.server_config', new=FAKE_SERVER_CONFIG):
        cc.settings_sync.update_share_information([mock_storage], config=config)
        mock_remove_user_remote.assert_called_once()
        mock_add_share_remote.assert_not_called()
        mock_adapt_users_remote.assert_not_called()


def test_add_share_remote(mocker, config):
    """Tests the working case."""
    mocker.patch('cc.settings_sync.get_token', return_value={'token': 'bla'})
    with requests_mock.Mocker() as rmock:
        add_share_req = rmock.register_uri('POST', cc.settings_sync.GRAPHQL_URL, [
            # second response for the share key
            {"json": {
                "data": {
                    "addShare": {
                        "id": "8",
                        "users": [
                            {
                                "id": "5",
                                "public_key": "<a sample public key>"
                            },
                            {
                                "id": "42",
                                "public_key": "<a public key>"
                            }
                        ]
                    }
                }
            }}
        ])

        config.user_public_key = ''
        with mock.patch(
                'cc.crypto2.generate_keypair',
                return_value=cc.crypto2.KeyPair(b'priv', b'pub')) as mock_generate_keypair, \
                mock.patch('cc.crypto2.wrap_private_key',
                           side_effect=lambda private_key_pem, public_key_object: 'wrapped key'), \
                mock.patch('cc.crypto2.load_pem_public_key') as wrap_load_pem_key_mock:
            cc.settings_sync.add_share_remote(
                share_name='The World', share_id='123', users=['james', 'inigo'],
                storage_type='gdrive',
                config=config)

    # keypair should have been created
    mock_generate_keypair.assert_called()

    for key in [b'<a public key>', b'<a sample public key>']:
        wrap_load_pem_key_mock.assert_any_call(key)
        # loaded_key_return = wrap_load_pem_key_mock(key)
        # assert wrap_private_key_mock.assert_any_call(mock_kp.public_pem)

    # now check if the structure of the second call made to graphQL api is correct
    assert add_share_req.request_history[1].json()['variables']['public_share_key'] == 'pub'
    assert add_share_req.request_history[1].json()['variables']['storage_type'] == 'gdrive'
    assert add_share_req.request_history[1].json()['variables']['share_unique_id'] == '123'
    assert add_share_req.request_history[1].json()['variables']['encrypted_share_keys'] == \
        [{'user_id': '5', 'encrypted_share_key': json.dumps('wrapped key')},
         {'user_id': '42', 'encrypted_share_key': json.dumps('wrapped key')}, ]


def test_add_share_remote_failes(mocker, config):
    """Tests behaviour when add_share fails."""
    mocker.patch('cc.settings_sync.get_token', return_value={'token': 'bla'})
    with requests_mock.Mocker() as rmock:
        rmock.post(cc.settings_sync.GRAPHQL_URL, json={
            "data": {
                "addShare": None
            },
            "errors": [
            ]
        })
        with mocker.patch('cc.crypto2.generate_keypair') as gen_key:
            cc.settings_sync.add_share_remote(
                share_name='The World', share_id='123', users=['james', 'inigo'],
                storage_type='gdrive',
                config=config)
            gen_key.assert_not_called()


def test_add_share_remote_user_with_no_public_key(config, mocker):
    """Ensure that given a backend response with one user having no public key doesn't
    stop the setup."""
    mocker.patch('cc.settings_sync.get_token', return_value={'token': 'bla'})

    with requests_mock.Mocker() as rmock:
        add_share_req = rmock.register_uri('POST', cc.settings_sync.GRAPHQL_URL, [
            # second response for the share key
            {"json": {
                "data": {
                    "addShare": {
                        "id": "8",
                        "users": [
                            {"id": "5", "public_key": "<a sample public key>"},
                            {"id": "0", "public_key": None},
                            {"id": "42", "public_key": "<a public key>"}
                        ]
                    }
                }
            }}
        ])

        config.user_public_key = ''
        with mock.patch(
                'cc.crypto2.generate_keypair',
                return_value=cc.crypto2.KeyPair(b'priv', b'pub')) as mock_generate_keypair, \
                mock.patch('cc.crypto2.wrap_private_key',
                           side_effect=lambda private_key_pem, public_key_object: 'wrapped key'), \
                mock.patch('cc.crypto2.load_pem_public_key') as wrap_load_pem_key_mock:

            cc.settings_sync.add_share_remote(
                share_name='The World', share_id='123', users=['james', 'inigo'],
                storage_type='gdrive',
                config=config)

    # keypair should have been created
    mock_generate_keypair.assert_called()

    for key in [b'<a public key>', b'<a sample public key>']:
        wrap_load_pem_key_mock.assert_any_call(key)
        # loaded_key_return = wrap_load_pem_key_mock(key)
        # assert wrap_private_key_mock.assert_any_call(mock_kp.public_pem)

    # now check if the structure of the second call made to graphQL api is correct.
    # User '0' should not be part of it as it has no public key attached.
    assert add_share_req.request_history[1].json()['variables']['public_share_key'] == 'pub'
    assert add_share_req.request_history[1].json()['variables']['storage_type'] == 'gdrive'
    assert add_share_req.request_history[1].json()['variables']['share_unique_id'] == '123'
    assert add_share_req.request_history[1].json()['variables']['encrypted_share_keys'] == \
        [{'user_id': '5', 'encrypted_share_key': json.dumps('wrapped key')},
         {'user_id': '42', 'encrypted_share_key': json.dumps('wrapped key')}, ]


def test_adapt_users_share_remote(mocker, config):
    """ tests the working case"""
    mocker.patch('cc.settings_sync.get_token', return_value={'token': 'bla'})
    with requests_mock.Mocker() as rmock:
        rmock.register_uri('POST', cc.settings_sync.GRAPHQL_URL, [
            # second response for the share key
            {"json": {
                "data": {
                    "updateShare": {
                        "id": "8",
                        "users_without_share_key": [
                            {
                                "id": "5",
                                "public_key": "<a public key>"
                            }
                        ]
                    }
                }
            }}
        ])

        config.user_public_keys = ''
        config.share_key_pairs = cc.crypto2.KeyPair(private_pem='private', public_pem='public')
        with mock.patch('cc.crypto2.generate_keypair',
                        return_value=cc.crypto2.KeyPair(b'priv', b'pub')), \
                mock.patch('cc.crypto2.wrap_private_key',
                           side_effect=lambda private_key_pem, public_key_object: 'wrapped key'), \
                mock.patch('cc.crypto2.load_pem_public_key'):
            cc.settings_sync.adapt_users_of_share_remote(
                share_name='The World', share_id='123', users=['james', 'inigo'],
                storage_type='gdrive',
                config=config)


def test_update_share_information_add(mocker, config):
    """ Tests that csps added if not on server

    The FAKE_SERVER_CONFIG already contains the share with the id `0BxzVEypHi3fOeHEzV3JXMTVYdFk`,
    so we are expecting `blabla` beeing added.
    """
    mock_storage = mock.MagicMock()
    mock_storage.storage_id = 'gdrive_1489139368.067954'

    mocker.patch('cc.configuration.helpers.write_config')

    def mock_get_shared_folders():
        """ helper to mock local shares """
        return [SharedFolder(path=['shary2'], share_id='0BxzVEypHi3fOeHEzV3JXMTVYdFk',
                             sp_user_ids={
                                 'crosscloud.cloudtest@gmail.com',
                                 'crosscloud.cloudtest2@gmail.com'}),
                SharedFolder(path=['testshare2'], share_id='blabla',
                             sp_user_ids={'christoph@crosscloud.me'})]

    mock_storage.get_shared_folders.return_value = mock_get_shared_folders()
    config.auth_token = 'fake  '
    config.share_key_pairs = {}
    config.csps = [{'id': 'gdrive_1489139368.067954', 'type': 'gdrive'}]
    with mock.patch('cc.settings_sync.add_share_remote') as mock_add_share_remote, \
            mock.patch(
                'cc.settings_sync.remove_user_from_share_remote') as mock_remove_user_remote, \
            mock.patch(
                'cc.settings_sync.adapt_users_of_share_remote', ) as mock_adapt_users_remote, \
            mock.patch('cc.settings_sync.server_config', FAKE_SERVER_CONFIG):
        cc.settings_sync.update_share_information([mock_storage], config=config)

    mock_add_share_remote.assert_called_once_with(
        share_id='blabla', users=['christoph@crosscloud.me'], storage_type='gdrive',
        share_name='testshare2',
        config=config
    )

    assert config.share_key_pairs['share:0:gdrive+blabla'] == mock_add_share_remote.return_value

    mock_remove_user_remote.assert_not_called()
    mock_adapt_users_remote.assert_not_called()


def test_update_share_information_adapt(mocker, config):
    """ Tests that adapt is called once if shares mismatch """
    mock_storage = mock.MagicMock()
    mock_storage.storage_id = 'gdrive_1489139368.067954'

    mocker.patch('cc.configuration.helpers.write_config')

    def mock_get_shared_folders():
        """ helper to mock local shares """
        return [
            SharedFolder(path=['testshareModified'], share_id='0BxzVEypHi3fOeHEzV3JXMTVYdFk',
                         sp_user_ids=['crosscloud.cloudtest@gmail.com'])]

    mock_storage.get_shared_folders.return_value = mock_get_shared_folders()
    mock_add_share_remote = mock.MagicMock()
    mock_remove_user_remote = mock.MagicMock()
    mock_adapt_users_remote = mock.MagicMock()
    config.auth_token = 'fake'
    config.csps = [{'id': 'gdrive_1489139368.067954', 'type': 'gdrive'}]
    with mock.patch('cc.settings_sync.adapt_users_of_share_remote',
                    new=mock_adapt_users_remote), \
            mock.patch('cc.settings_sync.server_config', new=FAKE_SERVER_CONFIG):
        cc.settings_sync.update_share_information([mock_storage], config=config)
        mock_adapt_users_remote.assert_called_once()
        mock_remove_user_remote.assert_not_called()
        mock_add_share_remote.assert_not_called()


def test_update_share_information_empty_server(mocker, config):
    """ tests that nothing happens if server has no csps """
    mock_storage = mock.MagicMock()
    mock_storage.storage_id = 'gdrive_1484421150.624657'

    mocker.patch('cc.configuration.helpers.write_config')

    def mock_get_shared_folders():
        """ helper to mock local shares """
        return [SharedFolder(path=['testshareModified'],
                             share_id='blabla',
                             sp_user_ids=['christoph@crosscloud.me'])]

    mock_storage.get_shared_folders.return_value = mock_get_shared_folders()
    mock_add_share_remote = mock.MagicMock()
    mock_remove_user_remote = mock.MagicMock()
    mock_adapt_users_remote = mock.MagicMock()
    config.csps = [{'id': 'gdrive_1484421150.624657', 'type': 'gdrive'}]
    with mock.patch('cc.settings_sync.add_share_remote', new=mock_add_share_remote), \
            mock.patch('cc.settings_sync.remove_user_from_share_remote',
                       new=mock_remove_user_remote), \
            mock.patch('cc.settings_sync.adapt_users_of_share_remote',
                       new=mock_adapt_users_remote), \
            mock.patch('cc.settings_sync.server_config', new=EMPTY_FAKE_SERVER_CONFIG):
        cc.settings_sync.update_share_information([mock_storage], config=config)
        mock_adapt_users_remote.assert_not_called()
        mock_remove_user_remote.assert_not_called()
        mock_add_share_remote.assert_not_called()


@pytest.mark.usefixtures('fake_get_token')
def test_get_public_key(config):
    """Mocks the response from the server and checks if this response is parsed correctly
    """
    key = 'asdf'
    with requests_mock.Mocker() as rmock:
        rmock.post(cc.settings_sync.GRAPHQL_URL, json={'data': {'publicKeyForUser': key}})
        assert cc.settings_sync.get_public_key('xyz', config=config) == key


@pytest.mark.usefixtures('fake_get_token')
def test_approve_device():
    """ Tests the call to approve another device """
    # defining the mock values
    mock_device_id = 'mock_device_id'
    mock_public_device_key = b'mock_public_device_key'
    mock_encrypted_user_key = {'bla': 'mock_encrypted_user_key'}

    # mocking request -> sending out request -> checking call in mock
    with requests_mock.Mocker() as m:
        m.post(cc.settings_sync.GRAPHQL_URL)
        cc.settings_sync.approve_device(device_id=mock_device_id,
                                        public_device_key=mock_public_device_key,
                                        encrypted_user_key=mock_encrypted_user_key,
                                        config=config)
        json_request = m.last_request.json()
        assert json_request['query'].startswith('mutation ApproveDevice')
        assert json_request['variables'] == {
            'device_id': mock_device_id,
            'public_device_key': mock_public_device_key.decode('ascii'),
            'encrypted_user_key': json.dumps(mock_encrypted_user_key)}


@pytest.mark.usefixtures('fake_get_token')
def test_decline_device():
    """ Tests the call to approve another device """
    # defining the mock values
    mock_device_id = 'mock_device_id'
    mock_public_device_key = b'mock_public_device_key'

    # mocking request -> sending out request -> checking call in mock
    with requests_mock.Mocker() as m:
        m.post(cc.settings_sync.GRAPHQL_URL)
        cc.settings_sync.decline_device(device_id=mock_device_id,
                                        public_device_key=mock_public_device_key,
                                        config=config)
        json_request = m.last_request.json()
        assert json_request['query'].startswith('mutation DeclineDevice')
        assert json_request['variables'] == {
            'device_id': mock_device_id,
            'public_device_key': mock_public_device_key.decode('ascii')}


@pytest.mark.usefixtures('fake_get_token')
def test_confirm_device_declination():
    """ Tests the confirm device approval call - this is called by the gui and
    performs the actual approval by wrapping the user"""
    # defining the mock values
    mock_device_id = 'mock_device_id'

    # generating device key pair
    _, mock_device_public_key = DEVICE_KEY_PAIR

    # adapting fake server config
    fake_config = FAKE_SERVER_CONFIG
    fake_config['approval_requests'] = [{
        'public_device_key': mock_device_public_key.decode('ascii'),
        'device_id': mock_device_id
    }]

    # calculating fingerprint of public key of device to approve
    fingerprint = cc.crypto.calculate_sha256(mock_device_public_key).decode('ascii')

    # mocking request -> sending out request -> checking call in mock
    with requests_mock.Mocker() as m, \
            mock.patch('cc.settings_sync.server_config', new=fake_config):
        m.post(cc.settings_sync.GRAPHQL_URL)
        cc.settings_sync.confirm_device_declination(device_id=mock_device_id,
                                                    public_key_fingerprint=fingerprint,
                                                    config=config)
        json_request = m.last_request.json()

        # checking variables
        assert json_request['query'].startswith('mutation DeclineDevice')
        assert json_request['variables']['device_id'] == mock_device_id
        assert json_request['variables']['public_device_key'] \
            == mock_device_public_key.decode('ascii')


@pytest.mark.usefixtures('fake_get_token')
def test_request_device_approval(config):
    """ Tests the basic call to request approval for this device"""
    # defining the mock values
    mock_device_id = 'mock_device_id'
    mock_public_device_key = b'mock_public_device_key'

    # mocking request -> sending out request -> checking call in mock
    with requests_mock.Mocker() as m:
        m.post(cc.settings_sync.GRAPHQL_URL)
        cc.settings_sync.request_device_approval(device_id=mock_device_id,
                                                 public_device_key=mock_public_device_key,
                                                 config=config)
        json_request = m.last_request.json()
        assert json_request['query'].startswith('mutation requestDeviceApproval')
        assert json_request['variables'] == {
            'device_id': mock_device_id,
            'public_device_key': mock_public_device_key.decode('ascii')}


@pytest.mark.usefixtures('fake_get_token')
def test_confirm_device_approval(config):
    """Test the confirm device approval call.

    this is called by the gui and performs the actual approval by wrapping the user
    """
    # defining the mock values
    mock_device_id = 'mock_device_id'

    # generating device and user key
    (mock_user_private_key, _) = cc.crypto2.generate_keypair()
    (mock_device_private_key, mock_device_public_key) = cc.crypto2.generate_keypair()

    # adapting fake server config
    fake_config = FAKE_SERVER_CONFIG
    fake_config['approval_requests'] = [{
        'public_device_key': mock_device_public_key.decode('ascii'),
        'device_id': mock_device_id
    }]

    # calculating fingerprint of public key of device to approve
    fingerprint = cc.crypto.calculate_sha256(mock_device_public_key).decode('ascii')

    # mocking request -> sending out request -> checking call in mock
    config.user_private_key = mock_user_private_key
    with requests_mock.Mocker() as m, \
            mock.patch('cc.settings_sync.server_config', new=fake_config):
        m.post(cc.settings_sync.GRAPHQL_URL)
        cc.settings_sync.confirm_device_approval(device_id=mock_device_id,
                                                 public_key_fingerprint=fingerprint,
                                                 config=config)
        json_request = m.last_request.json()

        # checking variables
        assert json_request['query'].startswith('mutation ApproveDevice')
        assert json_request['variables']['device_id'] == mock_device_id
        assert json_request['variables']['public_device_key'] \
            == mock_device_public_key.decode('ascii')

        # checking unwrapping
        wrapped_key = json_request['variables']['encrypted_user_key']
        private_key_unwrapped = cc.crypto2.unwrap_private_key(
            wrapped_object=json.loads(wrapped_key),
            private_key_object=cc.crypto2.load_pem_private_key(mock_device_private_key))

        assert private_key_unwrapped == mock_user_private_key


@pytest.mark.usefixtures('fake_get_token')
def test_confirm_device_approval_no_approval_request(config):
    """Test the confirm device approval call.

    this is called by the gui and performs the actual approval by wrapping the user
    """
    # defining the mock values
    mock_device_id = 'mock_device_id'

    # generating device and user key
    (mock_user_private_key, _) = cc.crypto2.generate_keypair()
    (_, mock_device_public_key) = cc.crypto2.generate_keypair()

    # calculating fingerprint of public key of device to approve
    fingerprint = cc.crypto.calculate_sha256(mock_device_public_key).decode('ascii')

    # mocking requests and key access
    config.user_private_key = mock_user_private_key
    with requests_mock.Mocker() as m, \
            mock.patch('cc.settings_sync.server_config', new=FAKE_SERVER_CONFIG):
        m.post(cc.settings_sync.GRAPHQL_URL)

        # calling confirm even though no request is in server_config -> nothing should
        # be called
        cc.settings_sync.confirm_device_approval(device_id=mock_device_id,
                                                 public_key_fingerprint=fingerprint,
                                                 config=config)
        assert m.last_request is None


@pytest.mark.usefixtures('fake_get_token')
def test_confirm_device_approval_no_matching_approval_request():
    """Test the confirm device approval call.

    this is called by the gui and performs the actual approval by wrapping the user
    """
    # creating two keys for devices
    (_, device_public_key1) = cc.crypto2.generate_keypair()
    (_, device_public_key2) = cc.crypto2.generate_keypair()

    # defining device ids
    device_id_1 = 'device_id_1'
    device_id_2 = 'device_id_2'

    # adapting fake server config
    fake_config = FAKE_SERVER_CONFIG
    fake_config['approval_requests'] = [{
        'public_device_key': device_public_key1.decode('ascii'),
        'device_id': device_id_1
    }, {
        'public_device_key': device_public_key2.decode('ascii'),
        'device_id': device_id_2
    }]

    # mocking requests and key access
    with requests_mock.Mocker() as m, \
            mock.patch('cc.settings_sync.server_config', new=fake_config):
        m.post(cc.settings_sync.GRAPHQL_URL)

        # calling confirm even though no request is in server_config -> nothing should
        # be called
        cc.settings_sync.confirm_device_approval(device_id='not there',
                                                 public_key_fingerprint='bla',
                                                 config=config)
        assert m.last_request is None

        cc.settings_sync.confirm_device_approval(device_id=device_id_2,
                                                 public_key_fingerprint='not_matching',
                                                 config=config)
        assert m.last_request is None


@pytest.mark.usefixtures('fake_get_token')
def test_update_device_approval_request():
    """Test the update device approval method."""
    # defining mock for gui communication
    mock_gui = mock.MagicMock()

    # creating two keys for devices
    (_, device_public_key1) = cc.crypto2.generate_keypair()
    (_, device_public_key2) = cc.crypto2.generate_keypair()

    # defining device ids
    device_id_1 = 'device_id_1'
    device_id_2 = 'device_id_2'

    # adapting fake server config
    fake_config = FAKE_SERVER_CONFIG
    fake_config['approval_requests'] = [{
        'public_device_key': device_public_key1.decode('ascii'),
        'device_id': device_id_1
    }, {
        'public_device_key': device_public_key2.decode('ascii'),
        'device_id': device_id_2
    }]

    # patching gui methods and server config
    with mock.patch('cc.settings_sync.server_config', new=fake_config), \
            mock.patch('cc.ipc_gui.showApproveDeviceDialog', new=mock_gui):
        cc.settings_sync.update_device_approval_request()

        # asserting that only callled once -> should be with first approval request
        mock_gui.assert_called_once()

        # getting key word arguments of call
        call = mock_gui.call_args[1]

        # extracting arguments of call
        device_id_call = call['device_id']
        fingerprint_call = call['fingerprint']

        # checking arguments
        assert device_id_call == device_id_1
        assert fingerprint_call == cc.crypto.calculate_sha256(
            device_public_key1).decode('ascii')


@pytest.mark.usefixtures('fake_get_token')
def test_init_user_keys(config):
    """Test the basic call to request approval for this device."""
    # defining the mock values
    mock_device_id = 'mock_device_id'

    # generating device key pair
    (_, mock_public_device_key) = cc.crypto2.generate_keypair()

    # generate wrap key pair
    (_, wrap_public_key) = cc.crypto2.generate_keypair()

    # generate user keypair
    (mock_user_private_key, mock_user_public_key) = cc.crypto2.generate_keypair()

    # wrapping user key
    wrapped_key = cc.crypto2.wrap_private_key(private_key_pem=mock_user_private_key,
                                              public_key_object=cc.crypto2.
                                              load_pem_public_key(wrap_public_key))

    # mocking request -> sending out request -> checking call in mock
    with requests_mock.Mocker() as m:
        m.post(cc.settings_sync.GRAPHQL_URL)
        cc.settings_sync. \
            init_admin_console_user_keys(device_id=mock_device_id,
                                         public_user_key=mock_user_public_key,
                                         encrypted_private_user_key=wrapped_key,
                                         public_device_key=mock_public_device_key,
                                         config=config)

        json_request = m.last_request.json()
        assert json_request['query'].startswith('mutation initUserKey')
        assert json_request['variables'] == {
            'device_id': mock_device_id,
            'public_device_key': mock_public_device_key.decode('ascii'),
            'public_user_key': mock_user_public_key.decode('ascii'),
            'encrypted_user_key': json.dumps(wrapped_key)}


def test_get_public_keys(config):
    """Test the extraction of public keys from a given server config."""
    with mock.patch('cc.settings_sync.server_config', new=FAKE_SERVER_CONFIG):
        public_keys, unique_id_mapping, share_key_pairs = \
            cc.settings_sync.get_share_info(config=config)

        assert public_keys == {
            "crosscloud.cloudtest2@gmail.com":
                "-----BEGIN RSA PUBLIC KEY-----\n"
                "MIICCgKCAgEAtqgn6PR9DlGBmXHESfmWcgsVrCy+"
                "\n-----END RSA PUBLIC KEY-----\n".encode(),
            "jakob@crosscloud.net":
                "-----BEGIN RSA PUBLIC KEY-----\n"
                "MIICCgKCAgEA0MturWSl5GoDF/YWEOjn7cXScjIC"
                "\n-----END RSA PUBLIC KEY-----\n".encode()}

        assert unique_id_mapping == {
            ('gdrive', 'crosscloud.cloudtest2@gmail.com'):
                'crosscloud.cloudtest2@gmail.com',
            ('gdrive', 'crosscloud.cloudtest@gmail.com'):
                'jakob@crosscloud.net'}
    assert share_key_pairs == {}


@pytest.mark.usefixtures('fake_get_token')
def test_check_login_fail(config):
    """Test that check_login returns False if the authentication with the AC is not possible."""
    # patching post to return 401 and calling check method
    with requests_mock.Mocker() as rmock:
        rmock.register_uri('POST', cc.settings_sync.GRAPHQL_URL, status_code=401)
        assert cc.settings_sync.check_login(config) is False


@pytest.mark.usefixtures('fake_get_token')
def test_check_login_succeed(config):
    """"Test that check_login returns True if the authentication with the AC is possible."""
    # defining fake data to be returned for the user
    fake_return_data = \
        {
            "data": {
                "currentUser":
                    {
                        "id": "5da189ac-93dd-4d5d-869c-dc966cfcc979"
                    }
            }
        }

    # patching post and calling check method -> this should succeed as all is there
    with requests_mock.Mocker() as rmock:
        rmock.register_uri('POST', cc.settings_sync.GRAPHQL_URL, json=fake_return_data)
        assert cc.settings_sync.check_login(config) is True


@pytest.mark.usefixtures('fake_get_token')
def test_check_login_error_ac_500(config):
    """Test that check_login returns True if the authentication with the AC returns 500."""
    # patching post to return 500 and calling check method
    with requests_mock.Mocker() as rmock:
        rmock.register_uri('POST', cc.settings_sync.GRAPHQL_URL, status_code=500)
        # We are allowing the users to continue if the AC is unavailable
        assert cc.settings_sync.check_login(config) is True


@pytest.mark.usefixtures('fake_get_token')
def test_check_login_error_ac_401(config):
    """Test that check_login returns False if the authentication with the AC returns 401."""
    # patching post to return 401 and calling check method
    with requests_mock.Mocker() as rmock:
        rmock.register_uri('POST', cc.settings_sync.GRAPHQL_URL, status_code=401)
        # needs to be false if AC not available
        assert cc.settings_sync.check_login(config) is False


@pytest.mark.skip('broke during refactoring to synchronization_graph and needs a rethink')
def test_periodic_admin_console_sync():
    """Test the dynamic adaption of the admin console poller.

    The tests checks if the polling time increases to the default value after the sync was
    successful the first time
    """
    self_mock = mock.MagicMock()
    self_mock.sync_engine.synchronization_graph.state = mock.MagicMock(return_value="RUNNING")
    periodic_ac_sync = PeriodicScheduler(1, Client.admin_console_sync)
    periodic_ac_sync.target_args = (self_mock, periodic_ac_sync)
    with mock.patch('cc.settings_sync'), \
            mock.patch('cc.configuration'),\
            mock.patch('cc.settings_sync.get_share_info', mock.MagicMock(return_value=(0, 0, 0))):
        assert periodic_ac_sync.interval == 1
        periodic_ac_sync.start()
        time.sleep(1)
        periodic_ac_sync.stop(join=True)
        assert periodic_ac_sync.interval == SYNC_ADMIN_CONSOLE_PERIOD


def test_is_encrypted_upload_or_download_task():
    """Ensure that the function detects tasks that handled encrypted data."""
    encrypted_version_tag = EncryptedVersionTag('version_id', True)
    invalid_encrypted_version_tag = EncryptedVersionTag('version_id', None)

    dummy_download = cc.synctask.DownloadSyncTask(path=None,
                                                  source_storage_id=None,
                                                  source_version_id=None)
    dummy_download.target_version_id = encrypted_version_tag
    assert cc.settings_sync.is_encrypted_upload_or_download_task(dummy_download)
    dummy_download.target_version_id = invalid_encrypted_version_tag
    assert not cc.settings_sync.is_encrypted_upload_or_download_task(dummy_download)

    dummy_upload = cc.synctask.UploadSyncTask(path=None,
                                              target_storage_id=None,
                                              source_version_id=encrypted_version_tag)
    assert cc.settings_sync.is_encrypted_upload_or_download_task(dummy_upload)
    dummy_upload.source_version_id = invalid_encrypted_version_tag
    assert not cc.settings_sync.is_encrypted_upload_or_download_task(dummy_upload)

    # Assert only Download/Upload Tasks with proper EncTag are marked.
    dummy = cc.synctask.MoveSyncTask(path=None,
                                     source_version_id=encrypted_version_tag,
                                     source_storage_id=None,
                                     source_path=None,
                                     target_path=None)
    dummy.target_version_id = encrypted_version_tag
    assert not cc.settings_sync.is_encrypted_upload_or_download_task(dummy)


def test_get_share_info_no_share_key(config):
    """Ensure proper get_share_info_return.

    Share_key_pairs in this keys should be an empty dict.
    """
    cc.settings_sync.server_config = FAKE_SERVER_CONFIG_NO_SHARE_KEY
    expected_public_keys = {'crosscloud.cloudtest2@gmail.com':
                            b'-----BEGIN RSA PUBLIC KEY-----\n' +
                            b'MIICCgKCAgEAtqgn6PR9DlGBmXHESfmWcgsVrCy+' +
                            b'\n-----END RSA PUBLIC KEY-----\n',
                            'jakob@crosscloud.net':
                            b'-----BEGIN RSA PUBLIC KEY-----\n' +
                            b'MIICCgKCAgEA0MturWSl5GoDF/YWEOjn7cXScjIC\n' +
                            b'-----END RSA PUBLIC KEY-----\n'}
    expected_unique_id_mapping = {('gdrive', 'crosscloud.cloudtest2@gmail.com'):
                                  'crosscloud.cloudtest2@gmail.com',
                                  ('gdrive', 'crosscloud.cloudtest@gmail.com'):
                                  'jakob@crosscloud.net'}
    expected_share_key_pairs = {}

    share_info = cc.settings_sync.get_share_info(config)
    public_keys, unique_id_mapping, share_key_pairs = share_info

    assert expected_public_keys == public_keys
    assert expected_unique_id_mapping == unique_id_mapping
    assert expected_share_key_pairs == share_key_pairs


def test_get_share_info_share_key(config):
    """Ensure proper get_share_info_return.
    """
    cc.settings_sync.server_config = FAKE_SERVER_CONFIG_SHARE_KEY
    expected_public_keys = {'crosscloud.cloudtest2@gmail.com':
                            b'-----BEGIN RSA PUBLIC KEY-----\n' +
                            b'MIICCgKCAgEAtqgn6PR9DlGBmXHESfmWcgsVrCy+' +
                            b'\n-----END RSA PUBLIC KEY-----\n',
                            'jakob@crosscloud.net':
                            b'-----BEGIN RSA PUBLIC KEY-----\n' +
                            b'MIICCgKCAgEA0MturWSl5GoDF/YWEOjn7cXScjIC\n' +
                            b'-----END RSA PUBLIC KEY-----\n'}
    expected_unique_id_mapping = {('gdrive', 'crosscloud.cloudtest2@gmail.com'):
                                  'crosscloud.cloudtest2@gmail.com',
                                  ('gdrive', 'crosscloud.cloudtest@gmail.com'):
                                  'jakob@crosscloud.net'}
    expected_share_key_pairs = {'share:0:gdrive+0BxzVEypHi3fOeHEzV3JXMTVYdFk':
                                cc.crypto2.KeyPair(private_pem='mocked_private_key',
                                                   public_pem=b'a public key')}

    mock_unwrap = mock.Mock(return_value="mocked_private_key")
    with mock.patch("cryptography.hazmat.primitives.serialization.load_pem_private_key"), \
            mock.patch("cc.crypto2.unwrap_private_key", new=mock_unwrap):
        share_info = cc.settings_sync.get_share_info(config=config)
        public_keys, unique_id_mapping, share_key_pairs = share_info

    assert expected_public_keys == public_keys
    assert expected_unique_id_mapping == unique_id_mapping
    assert expected_share_key_pairs == share_key_pairs


def test_get_share_info_share_key_not_unwrappable(config):
    """Ensure proper get_share_info_return.

    The user should be remove from the share in the case the key cannot be unwrapped
    """
    cc.settings_sync.server_config = FAKE_SERVER_CONFIG_SHARE_KEY

    mock_unwrap = mock.MagicMock(side_effect=cc.crypto2.KeyWrappingError)
    mock_remove_user_call = mock.Mock()
    with mock.patch("cryptography.hazmat.primitives.serialization.load_pem_private_key"), \
            mock.patch("cc.crypto2.unwrap_private_key", new=mock_unwrap), \
            mock.patch("cc.settings_sync.remove_user_from_share_remote") as mock_remove_user_call:
        cc.settings_sync.get_share_info(config)

    mock_remove_user_call.assert_called_once_with(share_id="2",
                                                  storage_type="gdrive",
                                                  storage_id="crosscloud.cloudtest@gmail.com",
                                                  config=config)


def response_with_error():
    """The response returned by the graphql endpoint when the following query was issued.

    ```json
    {
    currentUser {
        nom
    }
    ```
    Since nom is not a valid fieldname the error is included in a response which still reports its
    status as 200.
    """
    response = mock.Mock(spec=requests.Response)
    response.json.return_value = {
        "errors": [{"message": "Error during processing request",
                    "locations": [{"line": 4, "column": 2}
                                  ]}]}
    return response


def non_200_response():
    """A response which raises when raise_for_status is called on it."""
    response = mock.Mock(spec=requests.Response)
    http_error = requests.exceptions.HTTPError()
    response.raise_for_status.side_effect = http_error
    return response


@pytest.mark.parametrize('response',
                         [response_with_error, non_200_response],
                         ids=['response_with_error', 'non_200_response'])
def test_raise_for_graphql_status(response):
    """raise_for_graphql_error should raise for repsponses with errors, non 200 status_codes"""
    response = response()
    with pytest.raises((cc.settings_sync.GraphQLError, requests.exceptions.HTTPError)):
        cc.settings_sync.raise_for_graphql_error(response)


@pytest.fixture
def normal_response():
    """A response which neiter raises nor contains error in the json."""
    response = mock.Mock(spec=requests.Response)
    response.json.return_value = {"something": [1, 2, 3]}
    return response


def test_pass_raise_for_graphql_status(normal_response):
    """raise_for_graphql_error should pass repsponses without errors, and 200 status_codes."""
    response_json = normal_response.json()

    # This should not raise
    cc.settings_sync.raise_for_graphql_error(normal_response)

    # The call should not modify the response in any way
    assert response_json == normal_response.json()
