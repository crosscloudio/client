"""Test for the synchronization directory module."""
import os
import tempfile
from unittest.mock import Mock
import shutil

import mock
import pytest
from send2trash import send2trash

from cc.synchronization_directory import SynchronizationDirectoryWatcher
from cc.configuration.constants import HIDDEN_FILE_PREFIX

TEST_DISPLAY_NAME = 'The funny directory'
TEST_POLLING_INTERVAL = 0.1


# pylint: disable=invalid-name,redefined-outer-name

@pytest.fixture
def synchronization_directory_watcher(tmpdir):
    """Fixture with a SynchronizationDirectoryWatcher setup and a simple config."""
    config = Mock()
    config.sync_root = str(tmpdir)
    storage_provider_dir = tmpdir.join(TEST_DISPLAY_NAME)
    storage_provider_dir.mkdir()
    print(storage_provider_dir)
    inode = storage_provider_dir.stat().ino

    config.csps = [{'display_name': TEST_DISPLAY_NAME, 'local_unique_id': inode}]

    return SynchronizationDirectoryWatcher(config), tmpdir


def test_get_fs_entries(synchronization_directory_watcher):
    """Test if the get_fs_entries function return everything correctly."""
    watcher, sync_dir = synchronization_directory_watcher
    assert watcher.get_fs_entries() == \
        {sync_dir.join(TEST_DISPLAY_NAME).stat().ino: TEST_DISPLAY_NAME}


def test_get_config_entries(synchronization_directory_watcher):
    """Test if the get_config_entries function return everything correctly."""
    watcher, sync_dir = synchronization_directory_watcher
    assert watcher.get_config_entries() == \
        {sync_dir.join(TEST_DISPLAY_NAME).stat().ino: TEST_DISPLAY_NAME}


def test_nothing_changed(synchronization_directory_watcher):
    """If nothing changed, nothing should be changed :)."""
    watcher, _ = synchronization_directory_watcher
    delete_callback = mock.Mock()
    rename_callback = mock.Mock()
    watcher.storage_directory_deleted.connect(delete_callback, weak=False)
    watcher.storage_directory_renamed.connect(rename_callback, weak=False)
    watcher.check()

    assert not delete_callback.called
    assert not rename_callback.called


def test_nothing_not_involved_dir(synchronization_directory_watcher):
    """If nothing changed, nothing should be changed :)."""
    watcher, tmpdir = synchronization_directory_watcher
    tmpdir.mkdir('hello dir')
    delete_callback = mock.Mock()
    rename_callback = mock.Mock()
    watcher.storage_directory_deleted.connect(delete_callback, weak=False)
    watcher.storage_directory_renamed.connect(rename_callback, weak=False)
    watcher.check()

    assert not delete_callback.called
    assert not rename_callback.called


def test_rename(synchronization_directory_watcher):
    """Check if the display_name gets properly update in case the directory got renamed."""
    watcher, tmpdir = synchronization_directory_watcher
    delete_callback = mock.Mock()
    rename_callback = mock.Mock()
    watcher.storage_directory_deleted.connect(delete_callback, weak=False)
    watcher.storage_directory_renamed.connect(rename_callback, weak=False)
    tmpdir.join(TEST_DISPLAY_NAME).rename(tmpdir.join('Hello the other one'))
    watcher.check()

    assert rename_callback.called
    assert not delete_callback.called


def test_delete(synchronization_directory_watcher):
    """Test if the deletion of a storage dir will cause deleting the config"""
    watcher, tmpdir = synchronization_directory_watcher
    delete_callback = mock.Mock()
    watcher.storage_directory_deleted.connect(delete_callback, weak=False)
    shutil.rmtree(str(tmpdir.join(TEST_DISPLAY_NAME)))
    watcher.check()
    assert delete_callback.called


def test_move2trash(synchronization_directory_watcher):
    """Test if the move2trash of a storage_dir will cause deleting the config"""
    watcher, tmpdir = synchronization_directory_watcher
    delete_callback = mock.Mock()
    watcher.storage_directory_deleted.connect(delete_callback, weak=False)
    send2trash(str(tmpdir.join(TEST_DISPLAY_NAME)))
    watcher.check()
    assert delete_callback.called


def test_move_outside(synchronization_directory_watcher):
    """Test if moving storage dir to another place will trigger storage_directory_deleted signal.

    This test assumes that the path of pytests tmpdir and tempfile.TemporaryDirectory are in the
    same filesystem"""
    watcher, sync_root = synchronization_directory_watcher
    delete_callback = mock.Mock()
    watcher.storage_directory_deleted.connect(delete_callback, weak=False)

    with tempfile.TemporaryDirectory() as tmpdir:
        os.rename(str(sync_root.join(TEST_DISPLAY_NAME)), os.path.join(tmpdir, 'blabla'))
        watcher.check()

    assert delete_callback.called


def test_migrate_old(synchronization_directory_watcher, mocker):
    """Test if an oldstyle with hidden file config can be migrated."""
    config_writer = mocker.patch('cc.synchronization_directory.write_config')

    watcher, sync_root = synchronization_directory_watcher
    holla_id = 'bla123'
    sync_root.join(TEST_DISPLAY_NAME).join('{}{}'.format(HIDDEN_FILE_PREFIX, holla_id)).write(b'')
    watcher.config.csps[0]['id'] = holla_id
    old_unique_id = watcher.config.csps[0].pop('local_unique_id')

    watcher.migrate_old_config()

    assert watcher.config.csps[0]['local_unique_id'] == old_unique_id

    # ensure the files are delted as well
    assert not sync_root.join(TEST_DISPLAY_NAME).listdir()
    assert config_writer.called


def test_migrate_old_files_in_syncdir(synchronization_directory_watcher, mocker):
    """Test if an oldstyle with hidden file config can be migrated."""
    config_writer = mocker.patch('cc.synchronization_directory.write_config')

    watcher, sync_root = synchronization_directory_watcher
    sync_root.join('hello').write('blabla')

    watcher.migrate_old_config()

    assert not config_writer.called
