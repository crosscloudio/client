"""Fixtures for testing syncronization."""

from unittest import mock

import pytest

from cc import synctask
from cc.synchronization.models import SynchronizationLink
from cc.synchronization.models import TaskQueue
from tests.synchronization import dummy_link_with_id


@pytest.fixture()
def storage_configuration():
    """Temporary config dict for testing link.

    TODO: replace with config fixture.
    """
    return {"id": "dropbox1",
            "csp_id": "dropbox.1234",
            "display_name": "Dropbox 1",
            "unique_id": "dbid:AABHJTWSC00zK2URZEpz7CXWKy-aAFxgRjE",
            "selected_sync_directories": [["a", "b"], ["a"], ["b"]],
            'local_sync_state_file': './sync_state_file.dat',
            'local_sync_root_folder': '.',
            'encrypted': 'False',
            "authentication_data": "foobar",
            "shares": {
                "<unique_share_id>": {
                    "private_share_key": "<pem_key>"
                }
            },
            "type": "dropbox"}


@pytest.fixture
def abc_sync_tasks():
    """ :return: generates all possible sync tasks with path combinations of a, b, c  """
    tasks = [synctask.DownloadSyncTask(path=['a', 'b', 'c'],
                                       source_storage_id=None,
                                       source_version_id=None),
             synctask.UploadSyncTask(path=['a', 'b', 'c'],
                                     target_storage_id=None,
                                     source_version_id=None),
             synctask.MoveSyncTask(
        path=['a', 'b', 'c'],
        source_path=['a', 'b', 'c'],
        target_path=['a', 'b'],
        source_storage_id=None,
        source_version_id=None),
        synctask.CreateDirSyncTask(path=['a', 'b', 'c'],
                                   source_storage_id=None,
                                   target_storage_id=None)]

    for task in tasks:
        task.link = dummy_link_with_id("local::remote")

    return tasks


@pytest.fixture
def sample_create_dir_task():
    """Return a CreateDirSyncTask with a mocked '.cancel'."""
    task = synctask.CreateDirSyncTask(path=['a', 'b', 'c'],
                                      source_storage_id=None,
                                      target_storage_id=None)
    task.cancel = mock.Mock()
    task.link = dummy_link_with_id("local::remote")
    return task


@pytest.fixture
def link_with_storages():
    """Dummy link with storage attatched."""
    link = mock.Mock(spec=SynchronizationLink)
    link.storages = {
        'local': mock.Mock(),
        'remote': mock.Mock()
    }
    return link


@pytest.fixture(scope='function')
def task_queue():
    """task_queue fixture"""
    return TaskQueue()
