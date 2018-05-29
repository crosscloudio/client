"""Tests for the client module."""
# pylint: disable=redefined-outer-name
# pylint: disable=protected-access
import os
from mock import Mock, patch
import pytest
from requests import HTTPError, Response

from jars import BasicStorage
from jars.oauth_http_server import OAuthHTTPServer

from cc.client import Client, StorageAuthenticator


@pytest.fixture
def mocked_authenticate():
    """Create a mock authentication class."""
    mocked_authenticate = Mock(StorageAuthenticator)
    mocked_authenticate.storage = Mock()
    mocked_authenticate.url = Mock()
    mocked_authenticate.username = Mock()
    mocked_authenticate.password = Mock()
    mocked_authenticate.storage_name = 'storage_name'
    mocked_authenticate.ignore_warnings = Mock()
    mocked_authenticate.auth_data = dict()

    return mocked_authenticate


def test_remove_storage_with_folder(tmpdir):
    """Test if send2trash removes the storage when the folder is present."""
    storage_id = '123'
    display_name = 'Holla'

    mocked_client = Mock()
    mocked_client.config.sync_root = str(tmpdir)
    storage_dir = os.path.join(str(tmpdir), display_name)
    os.makedirs(storage_dir)

    fake_storage = {'storage_id': storage_id, 'display_name': display_name}

    # check the dir is there and working
    assert os.path.exists(storage_dir)
    with patch('cc.client.get_storage', return_value=fake_storage):
        Client.remove_storage(mocked_client, storage_id)

    # assert the directory is gone
    assert not os.path.exists(storage_dir)


def test_remove_storage_without_folder(tmpdir):
    """Test if send2trash deletes the storage from the config if the folder doesn't exist."""
    storage_id = '123'
    display_name = 'Holla'
    local_unique_id = 'id_123'

    mocked_client = Mock()
    fake_storage = {'storage_id': storage_id, 'display_name': display_name,
                    'local_unique_id': local_unique_id}

    mocked_client.config.sync_root = str(tmpdir)

    with patch('cc.client.get_storage', return_value=fake_storage):
        Client.remove_storage(mocked_client, storage_id)

    # assert on_storage_directory_deleted is called for the sp
    mocked_client.on_storage_directory_deleted.assert_called_with(None, local_unique_id)


@pytest.mark.parametrize('webserver', [None, Mock()])
def test_webserver_shutdown(mocked_authenticate, webserver):
    """Test webserver is shutdown if running."""
    mocked_authenticate.oauth_webserver = webserver
    StorageAuthenticator._webserver_shutdown(mocked_authenticate)
    assert mocked_authenticate.oauth_webserver is None


@pytest.mark.parametrize('auth_type', [[BasicStorage.AUTH_OAUTH], [BasicStorage.AUTH_CREDENTIALS],
                                       [BasicStorage.AUTH_CREDENTIALS_FIXED_URL],
                                       [BasicStorage.AUTH_NONE]])
def test_storage_authentication(mocked_authenticate, auth_type):
    """Test that the proper authenthication method is chosen."""
    storage = Mock(BasicStorage)
    storage.auth = auth_type
    mocked_authenticate.storage = 'storage'
    mocked_authenticate._storage_authentication(Mock())
    if BasicStorage.AUTH_OAUTH in auth_type:
        assert mocked_authenticate._oauth_authentication.called_once()
    elif (BasicStorage.AUTH_CREDENTIALS in auth_type) or \
            (BasicStorage.AUTH_CREDENTIALS_FIXED_URL in auth_type):
        assert mocked_authenticate._non_oauth_authentication.called_once()
    else:
        assert not mocked_authenticate._non_oauth_authentication.called
        assert not mocked_authenticate._oauth_authentication.called


@pytest.mark.parametrize('code', [401, 403, 404, 'assertion', 'basic'])
def test_non_oauth_authentication_fail(mocked_authenticate, code):
    """Assert  proper exceptions are raised."""
    storage = Mock(BasicStorage)
    if code == 401 or code == 403 or code == 404:
        response = Response()
        response.status_code = 401
        warning = HTTPError(response=response)
        storage.authenticate = Mock(side_effect=warning)
    elif code == 'assertion':
        storage.authenticate = Mock(side_effect=AssertionError)
    elif code == 'basic':
        storage.authenticate = Mock(side_effect=BaseException)
    mocked_authenticate.storage = storage
    with pytest.raises(ValueError):
        StorageAuthenticator._non_oauth_authentication(mocked_authenticate, Mock())


def test_non_oauth_authentication_success(mocked_authenticate):
    """Assert credentials and identifier are returned if authenthication is succesful."""
    storage = Mock(BasicStorage)
    storage.authenticate = Mock(return_value=(None, 'credentials', 'identifier'))
    mocked_authenticate.storage = storage
    StorageAuthenticator._non_oauth_authentication(mocked_authenticate, Mock())
    assert mocked_authenticate.auth_data['credentials'] == 'credentials'
    assert mocked_authenticate.auth_data['identifier'] == 'identifier'


@pytest.mark.parametrize('webserver', [True, False])
def test_oauth_authentication(mocked_authenticate, webserver):
    """Test oauth_authentication."""
    fake_url = Mock()
    storage = Mock(BasicStorage)
    storage.grant_url = Mock(return_value=fake_url)
    mocked_server = Mock(OAuthHTTPServer)
    mocked_server.shutdown = Mock(side_effect=OSError)
    mocked_server.socket = Mock(return_value='bla')
    mocked_server.done_event = Mock()

    if webserver:
        mocked_server.result = 'fake_result'
    else:
        mocked_server.result = None

    credentials = 'fake_credentials'
    identifier = 'fake_identifier'
    auth_return = (None, credentials, identifier)
    storage.authenticate = Mock(return_value=auth_return)
    mocked_authenticate.storage = storage
    with patch('cc.client.OAuthHTTPServer', return_value=mocked_server) as mock_oauth, \
            patch('cc.client.webbrowser') as mocked_webbrowser:
        StorageAuthenticator._oauth_authentication(mocked_authenticate, False)

    mock_oauth.assert_called_with(fake_url.check_function)
    mocked_webbrowser.open.assert_called_with(fake_url.grant_url)
    assert mocked_server.shutdown.called_once()
    assert mocked_server.socket.close.called_once()
    assert mocked_server.socket.shutdown.called_once()

    if webserver:
        assert mocked_authenticate.auth_data['credentials'] == credentials
        assert mocked_authenticate.auth_data['identifier'] == identifier
    else:
        assert mocked_authenticate.auth_data == {}
