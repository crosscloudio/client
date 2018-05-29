"""Test for issue CC-633 Gdrive two users edit file, conflict file not generated

https://gitlab.crosscloud.me/crosscloud/client/issues/495

* File opened by user A and B
* File modified by user A
* Client A uploads file
* User B modifies file
* Client B downloads file
* Both clients are in sync

"""
import logging
import os

import pytest

from tests.integration.conftest import Crosscloud

logger = logging.getLogger(__name__)


@pytest.mark.parametrize('storage_config', [
    # 'dropbox_0',
    'gdrive_0'
    # 'onedrive_0'
])
def test_conflict_resolution(crosscloud: Crosscloud, storage_config):
    """Ensure that conflict resolution is triggered when files are changed on local and remote."""

    crosscloud.login_to_admin_console()
    crosscloud.startup()

    # Add storage
    storage = crosscloud.add_storage_pair(storage_config)

    # make a clean start
    file_name = 'issue_495.txt'
    conflict_name = file_name + ' (Conflicting copy).txt'
    storage.remote.try_clean(file_name)
    storage.remote.try_clean(conflict_name)

    # write a file
    logger.warning('Creating local file')
    storage.local.touch(path=file_name, size=1, fill=b'l')

    # Let it sync
    not_synced = storage.wait_until_synced([file_name], timeout=90)
    assert len(not_synced) == 0

    logger.warning('Pausing')
    crosscloud.client.pause()

    # Change on both remote and local at the about the same time.
    logger.warning('Touching local and remote')
    storage.local.touch(path=file_name, size=2, fill=b'l')
    storage.remote.touch(path=file_name, size=2, fill=b'r')

    logger.warning('Resuming')
    crosscloud.client.resume()

    storage.wait_until_synced([file_name, conflict_name], timeout=20)

    local_path = os.path.join(storage.local.get_path())
    local_files = os.listdir(local_path)

    assert file_name in local_files
    assert conflict_name in local_files
