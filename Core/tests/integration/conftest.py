"""Fixtures for integration tests.

These integration tests are configured using a yaml file.
`py.test tests/integration/ -s --integration-config test_integration_config.yaml`

Here is a sample:

```yaml
admin_console:
  user: user@domain.tld
  password: secretpassword

storages:
  gdrive_0:
    type: gdrive
    token: ~/.cc_test_config/gdrive_ci6_token

  gdrive_1:
    type: dropbox
    token: {"refresh_token": "...", ...}
```

"""
import logging
import os
import random
import string
import tempfile
import time
import uuid
import queue
import json
import shutil
from functools import partial
from abc import ABCMeta, abstractmethod
from io import StringIO, BytesIO
from unittest import mock

import requests
import pytest
import yaml
from oauthlib.oauth2.rfc6749.errors import TokenExpiredError

import cc
from cc.client import Client

from cc.synchronization.models import instantiate_storage

from cc.synctask import UploadSyncTask, DownloadSyncTask, CreateDirSyncTask, DeleteSyncTask


PATH_SEPARATOR = '/'

M_DECLINE_DEVICE_APPROVAL = '''
mutation DeclineDevice($device_id: String!, $public_device_key: String!)
{
    declineDevice(device_id: $device_id, public_device_key: $public_device_key)
}
'''

M_REMOVE_USER_SHARE = '''mutation DeleteShare($storage_type: String!, $unique_id: String!)
{
    deleteShare(storage_type: $storage_type, unique_id: $unique_id)
}'''

M_RESET_USER_KEYS = '''mutation ResetUserKeys($id: String!)
{
    resetUserKeys(id: $id){id public_key}
}'''

Q_USER_INFORMATION = '''{
  currentUser
  {
    id
    email
    approval_requests { device_id public_device_key }
    csps { shares { unique_id storage_type } } } }'''


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logging.getLogger('jars').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)
logging.getLogger('requests_oauthlib').setLevel(logging.WARNING)
logging.getLogger('watchdog').setLevel(logging.WARNING)
logging.getLogger('cc.synchronization_directory').setLevel(logging.WARNING)
logging.getLogger('cc.ipc_gui').setLevel(logging.WARNING)
logging.getLogger('cc.ipc_core').setLevel(logging.WARNING)
logging.getLogger('cc.client').setLevel(logging.WARNING)
logging.getLogger('cc.settings_sync').setLevel(logging.WARNING)
logging.getLogger('cc.configuration').setLevel(logging.WARNING)


def _get_basic_config_mock():
    """Setup all the fields required on a base config."""
    from cc.configuration import base_entries, helpers

    config = base_entries.LocalConfig()

    config = helpers.set_constants(config)
    config = helpers.set_methods(config)

    # Hack for non-constant dirs
    config.config_dir = tempfile.mkdtemp()
    config.cache_dir = tempfile.mkdtemp()
    config.log_dir = tempfile.mkdtemp()
    config.config_file = os.path.join(config.config_dir, "config.json")
    config.sync_root = tempfile.mkdtemp()
    config.lock_file = os.path.join(config.config_dir, config.LOCK_FILE)

    return config


def _ac_request(session, query, variables=dict):
    response = session.post(cc.settings_sync.GRAPHQL_URL, json={'query': query,
                                                                'variables': variables})
    response.raise_for_status()
    return response


def _purify_user(username, password):
    session = requests.session()
    session.headers['X-Api-Version-Expected'] = cc.settings_sync.EXEPECETD_API_VERSION
    res = session.post(cc.settings_sync.TOKEN_URL, json={'email': username, 'password': password})
    assert res.status_code == 200
    token = res.json()
    session.headers = {'Authorization': 'Bearer {}'.format(token['token'])}

    # Fetch current user information
    resp = session.post(cc.settings_sync.GRAPHQL_URL, json={'query': Q_USER_INFORMATION})
    resp.raise_for_status()
    current_user = resp.json()['data']['currentUser']

    # Decline approval requests
    for device_approval in current_user['approval_requests']:
        _ac_request(session, M_DECLINE_DEVICE_APPROVAL, device_approval)

    # Reset keys
    _ac_request(session, M_RESET_USER_KEYS, {'id': current_user['id']})

    # Reset shares
    for storage_provider in current_user['csps']:
        for share in storage_provider['shares']:
            _ac_request(session, M_REMOVE_USER_SHARE, share)


def add_to_rpc_queue_factory(rpc_queue):
    """Create a function which acts like the rpc but simply saves the requests to a queue."""
    def func(method, *args, **kwargs):
        """The function used to catch calls to the rpc."""
        # logger.debug('[RPC_Queue] %s(%s %s) ', method, args, kwargs)
        rpc_queue.put((method, args, kwargs))
    return func


class Crosscloud:
    """A testwrapper around the client."""

    def __init__(self, test_config):
        self.client = Client(config=_get_basic_config_mock())

        self.added_storage_ids = []
        self.link_helper = []

        self.rpc_queue = queue.Queue()

        self.test_config = test_config

        # This is a ugly hack because we use a global for the rpc rpc_object.
        # Because of this we will not be able to track notifications of multiple cc fixtures.
        cc.ipc_gui.rpc_object = add_to_rpc_queue_factory(self.rpc_queue)

        # Remove shares, decline all open approval requests and reset keys of this user
        _purify_user(username=self.test_config['admin_console']['user'],
                     password=self.test_config['admin_console']['password'])

    def login_to_admin_console(self):
        """Use the configuration passed in the yaml fixture to log into the admin console."""
        cc.settings_sync.authenticate_user(username=self.test_config['admin_console']['user'],
                                           password=self.test_config['admin_console']['password'],
                                           config=self.client.config)

        try:
            cc.settings_sync.fetch_and_apply_configuration(config=self.client.config)
        except cc.DeviceApprovalRequiredError:
            pytest.fail("DeviceApprovalRequiredError: Login with the user '%s' requires approval "
                        "by other devices. Did you purify the user before running this test?"
                        % self.test_config['admin_console']['user'])

    def startup(self):
        """Start crosscloud."""
        self.client.startup()
        logger.info('Crosscloud fixture started')

    def shutdown(self):
        """Shutdown crosscloud client and all link helpers."""
        self.client.shutdown()
        logger.info('Crosscloud fixture stopped')

        for link_helper in self.link_helper:
            link_helper.shutdown()

        logger.info('Crosscloud fixture stopped')

    def add_storage_pair(self, storage_id: str):
        """Add a storage pair to the crosscloud instance."""

        if storage_id not in self.test_config['storages']:
            pytest.fail("No storage with id '%s' configured. Check your configuration!"
                        % storage_id)

        storage_config = self.test_config['storages'][storage_id]

        try:
            self.client.add_storage(storage_name=storage_config['type'], storage_id=storage_id)
        except json.decoder.JSONDecodeError:
            pytest.fail("Unable to parse token for storage '%s'!" % storage_id)
        except TokenExpiredError:
            pytest.fail("Token for storage '%s' has expired, please renew!" % storage_id)

        self.added_storage_ids.append(storage_id)

        return self._create_link_helper(storage_id)

    def _create_link_helper(self, storage_id):
        """Return a local, remote and link associated with a storage_id"""

        storage_id = "local::" + storage_id
        if storage_id not in self.client.synchronization_graph.links:
            return None, None

        link = LinkHelper(
            self.client.synchronization_graph.links[storage_id],
            self.client.synchronization_graph, self.client.config
            )

        self.link_helper.append(link)

        return link

    def pause(self):
        """Pause all synchronization."""
        self.client.pause()

    def resume(self):
        """Resume all synchronization."""
        self.client.resume()


class LinkHelper:
    """Wraps a SynchronizationLink, allows access to local and remote storage."""

    def __init__(self, link, graph, config):
        self.graph = graph
        self.link = link

        self.task_queue = self.link.queue

        self.local_storage = LocalStorage(link.local)
        self.remote_storage = RemoteStorage(link.remote, config)

        self.total_synced_files = set()

        self.unsynced_files = []

    @property
    def storage_type(self):
        """Return the storage type contained in this Link Helper

        This can be used to skip tests for certain sotrage types.
        """
        return self.remote_storage.storage.storage_name

    @property
    def local(self):
        """Return reference to the local storage."""
        return self.local_storage

    @property
    def remote(self):
        """Return reference to the remote storage."""
        return self.remote_storage

    def shutdown(self):
        """Shutdown both storages."""
        self.local.shutdown()
        self.remote.shutdown()

    def task_acked(self, accepted_tasks, task):
        """Callback for finished synchronization tasks."""

        if isinstance(task, tuple(accepted_tasks)):
            try:
                if self.unsynced_files:
                    self.unsynced_files.remove(PATH_SEPARATOR.join(task.path))
            except ValueError:
                pass

    def task_putted(self, task):
        """Callback for newly created synchronization tasks."""
        pass

    def _wait_until_no_sync_tasks(self, timeout=None):
        tasks_started = False
        while True:
            sync_tasks = self.task_queue.statistics['sync_task_count']

            if not tasks_started and sync_tasks > 0:
                tasks_started = True
            elif tasks_started and sync_tasks == 0:
                break

            if timeout is not None:
                if timeout <= 0:
                    break

                timeout -= 1

            time.sleep(1)

    def _wait_until(self, files=None, timeout=None, tasks=None):
        if files is None:
            return self._wait_until_no_sync_tasks(timeout=timeout)

        if tasks is None:
            tasks = [UploadSyncTask, DownloadSyncTask, CreateDirSyncTask, DeleteSyncTask]

        # Non-weak ref because the partial falls out of scope after this line
        # and this would disconnect the signal again
        self.task_queue.task_acked.connect(partial(self.task_acked, tasks), weak=False)
        self.task_queue.task_putted.connect(self.task_putted)

        self.unsynced_files = list(files)
        while True:
            if len(self.unsynced_files) == 0:
                break

            if timeout is not None:
                if timeout <= 0:
                    break

                timeout -= 1

            time.sleep(1)

        self.task_queue.task_acked.disconnect(self.task_acked)
        self.task_queue.task_putted.disconnect(self.task_putted)

        # Copy the list of remaining files before deleting it for the next run
        unsynced_files = list(self.unsynced_files)
        self.unsynced_files = None
        return unsynced_files

    def wait_until_synced(self, files=None, timeout=None):
        """Wait until either all files are in sync or until no sync tasks are running any more."""
        return self._wait_until(files, timeout)

    def wait_until_directory_created(self, files=None, timeout=None):
        """Wait until all directories are created."""
        return self._wait_until(files, timeout, [CreateDirSyncTask])

    def wait_until_deleted(self, files=None, timeout=None):
        """Wait until all files are deleted."""
        return self._wait_until(files, timeout, [DeleteSyncTask])

    def wait_until_uploaded(self, files=None, timeout=None):
        """Wait until all files are uploaded/directories are created."""
        return self._wait_until(files, timeout, [UploadSyncTask, CreateDirSyncTask])

    def wait_until_downloaded(self, files=None, timeout=None):
        """Wait until all files are downloaded."""
        return self._wait_until(files, timeout, [DownloadSyncTask])


class StorageHelper(metaclass=ABCMeta):
    """Test wrapper for a jars storage."""

    def __init__(self, storage):
        self.storage = storage

    def shutdown(self):
        """Shutdown a storage helper."""
        pass

    @abstractmethod
    def add_files_flat(self, number, size=1024, path=None):
        """Add files to the root of the storage."""
        raise NotImplementedError

    @abstractmethod
    def touch(self, path: str, size: int=0, fill: bytes=b'0') -> None:
        """Write size times a '0'"""
        raise NotImplementedError

    @abstractmethod
    def add_folder(self, path: str):
        """Create a folder and all of its parents."""
        raise NotImplementedError

    @abstractmethod
    def remove_folder(self, path: str):
        """Remove a folder."""
        raise NotImplementedError

    @abstractmethod
    def exists(self, path: str):
        """Returns if a path exists."""
        raise NotImplementedError

    @abstractmethod
    def open(self, path: str):
        """Opens a path for reading and returns a file-like object."""
        raise NotImplementedError

    def is_available(self) -> bool:
        """Returns if the storage is up and running."""
        try:
            self.storage.check_available()
            return True
        except BaseException:
            # Catch all exceptions and assume they mean that the storage is offline
            return False

    @abstractmethod
    def move(self, source, target):
        """Move or rename a file or directory."""
        raise NotImplementedError

    @staticmethod
    def _get_file_name():
        return "%s.txt" % (str(uuid.uuid4()))

    @staticmethod
    def _write_random_data(file_obj, size=1024):
        block_size = 64 if size >= 64 else size
        blocks = size // block_size

        for block in range(0, blocks):
            if block == blocks - 1:
                block_size += size % block_size
            data_block = ''.join(random.choice(string.ascii_uppercase + string.digits)
                                 for _ in range(block_size))
            file_obj.write(data_block)


class LocalStorage(StorageHelper):
    """Test wrapper around a local storage object."""

    def _abs_path(self, path):
        return os.path.join(self.storage.root, path)

    def get_path(self):
        """Returns the path to the local sync root."""
        return self.storage.root

    def add_folder(self, path: str):
        """Create a folder in the local sync_root."""
        os.makedirs(self._abs_path(path), exist_ok=True)

    def remove_folder(self, path: str):
        """Remove a folder and all of its children."""
        shutil.rmtree(self._abs_path(path))

    def touch(self, path: str, size: int=0, fill: bytes=b'0') -> None:
        """Write size times a '0'"""
        with open(self._abs_path(path), 'wb') as stream:
            stream.write(fill * size)

    def exists(self, path: str):
        """Returns if a path exists."""
        return os.path.exists(self._abs_path(path))

    def open(self, path: str):
        """Opens a path for reading and returns a file-like object."""
        return open(self._abs_path(path), "r")

    def move(self, source, target):
        """Move or rename a file or directory."""
        os.rename(self._abs_path(source), self._abs_path(target))

    def append_to_file(self, path: str, new_string: str) -> str:
        """Append new_string to a file."""
        with open(self._abs_path(path), 'a') as file_obj:
            file_obj.writelines(new_string + '\n')
        return path

    def add_files_flat(self, number, size=1024, path=None):
        """Add a certain number of files of a certain size to the root of the storage."""
        files = []
        for _ in range(0, number):
            name = self._get_file_name()

            if path:
                name = os.path.join(path, name)

            files.append(name)
            with open(self._abs_path(name), 'w') as stream:
                self._write_random_data(stream, size=size)

        return files


class RemoteStorage(StorageHelper):
    """Test wrapper for remote storage object."""

    def __init__(self, storage, config):
        super().__init__(storage)

        self.secondary_storage = instantiate_storage(
            type(storage), storage.storage_id, config=config, sync_engine=mock.Mock())
        self.secondary_storage.update()
        self.secondary_storage.start_events()

    def shutdown(self):
        """Stop events in the secondary storage."""
        self.secondary_storage.stop_events(join=True)

    def add_folder(self, path: str):
        """Create a folder on the remote storage."""
        self.secondary_storage.make_dir(path)

    def try_clean(self, path: str):
        """Attempt to remove elements from the storage if they are avaliable.

        This is to be used to ensure previous test runs do not interefere with current test.
        """
        try:
            self.secondary_storage.delete(path.split(PATH_SEPARATOR), None)
        except FileNotFoundError:
            logger.info('failed to delete %s.' +
                        'It does not exits on %s', path, self.storage.storage_name)

    def touch(self, path: str, size: int=0, fill: bytes=b'0') -> None:
        """Write size times a '0'"""
        f_out = BytesIO(fill * size)
        self.secondary_storage.write(path.split(PATH_SEPARATOR), f_out)

    def exists(self, path: str):
        """Returns if a path exists."""
        path_list = path.split(PATH_SEPARATOR)

        target = path_list.pop()

        try:
            children = self.secondary_storage.get_tree_children(path_list)
        except FileNotFoundError:
            return False

        for (name, _) in children:
            if name == target:
                return True

        return False

    def open(self, path: str):
        """Opens a path for reading and returns a file-like object."""
        return self.secondary_storage.open_read(path.split(PATH_SEPARATOR))

    def move(self, source, target):
        """Move or rename a file or directory."""
        self.secondary_storage.move(source.split(PATH_SEPARATOR), target.split(PATH_SEPARATOR))

    def remove_folder(self, path: str):
        """Remove a folder and all of its children."""
        path_list = path.split(PATH_SEPARATOR)
        self.secondary_storage.delete(path_list, None)

    def append_to_file(self, path: str, new_string: str):
        """ Append new content to the file on the remote storage"""
        path_list = path.split(PATH_SEPARATOR)
        old_content = self.storage.open_read(path_list)
        new_content_str = '\n' + old_content.read().decode() + new_string
        content1 = BytesIO(new_content_str.encode())
        self.secondary_storage.write(path_list, content1, size=len(content1.getvalue()))

    def add_files_flat(self, number, size=1024, path=None):
        """Add a certain number of files of a certain size to the root of the storage."""
        files = []
        for _ in range(0, number):
            content = StringIO()
            self._write_random_data(content, size=size)
            name = self._get_file_name()

            full_path = []
            if path:
                full_path = path.split(PATH_SEPARATOR)

            full_path.append(name)

            files.append(PATH_SEPARATOR.join(full_path))
            self.secondary_storage.write(full_path, content)

        return files


class MockAuthenticator(cc.client.StorageAuthenticator):
    """Mock the StorageAuthenticator to return valid tokens without invoking an oauth flow."""
    test_config = []

    def load_token(self):
        """Load an oauth token for the chosen CSP from the configuration.

        If this token starts with '{', it is expected to be the token
        in JSON and returned directly.
        Otherwhise, it's expected to be a path to a file containing the token
        and the file's contents will be returned.
        """
        assert 'token' in MockAuthenticator.test_config['storages'][self.storage_id]

        token = MockAuthenticator.test_config['storages'][self.storage_id]['token']

        if token.startswith('{'):
            logger.info("Reading token for '%s' from integration test configuration.",
                        self.storage_name)
            return token
        else:
            logger.info("Loading token for '%s' from file %s.", self.storage_id, token)
            try:
                path = os.path.abspath(os.path.expanduser(token))
                with open(path, 'r') as stream:
                    return stream.read()
            except FileNotFoundError:
                pytest.fail("Could not find token file for storage '%s' at %s!"
                            % (self.storage_id, path))

    def authenticate(self):
        token = self.load_token()

        auth_data = {'display_name': self.display_name,
                     'sp_dir': self.sp_dir,
                     'new_storage_id': self.new_storage_id,
                     'storage': self.storage,
                     'identifier': 'something',
                     'credentials': token
                     }

        return auth_data


@pytest.fixture(autouse=True)
def mock_authenticator(monkeypatch):
    """Always use the mock authenticator for tests in this module."""
    monkeypatch.setattr('cc.client.StorageAuthenticator', MockAuthenticator)


@pytest.fixture
def crosscloud(mocker, integration_config):
    """Fixture to test various scenarios with crosscloud."""
    if not integration_config:
        pytest.skip('No integration_config. Call pytest with --integration-config set')

    def platform_start():
        """We patch the `platform start` so no platform specific extensions are launched."""
        pass

    with mocker.patch('cc.client.platform_start', return_value=platform_start):
        assert os.path.exists(integration_config)

        with open(integration_config, 'r') as stream:
            config = yaml.load(stream)

        assert 'admin_console' in config
        assert 'user' in config['admin_console']
        assert 'password' in config['admin_console']

        MockAuthenticator.test_config = config
        cc_fixture = Crosscloud(test_config=config)

    yield cc_fixture
    cc_fixture.shutdown()
