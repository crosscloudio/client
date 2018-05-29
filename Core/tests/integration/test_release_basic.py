"""Basic tests of the release test plan."""

import pytest


@pytest.mark.parametrize('storage_config', ['dropbox_0',
                                            'gdrive_0',
                                            'onedrive_0'])
def test_storage_add(crosscloud, storage_config):
    """Test adding a storage and check that it is online."""
    crosscloud.login_to_admin_console()
    crosscloud.startup()

    storage = crosscloud.add_storage_pair(storage_config)

    assert storage.local.is_available()
    import time
    time.sleep(5)
    assert storage.remote.is_available()


@pytest.mark.parametrize('storage_config', ['dropbox_0',
                                            'gdrive_0',
                                            'onedrive_0'])
def test_add_files(crosscloud, storage_config):
    """Test simple syncing of files to a folder."""
    crosscloud.login_to_admin_console()
    crosscloud.startup()

    storage = crosscloud.add_storage_pair(storage_config)

    # Create folder called 'test' and fill it with files
    storage.local.add_folder('add_files')
    files = storage.local.add_files_flat(10, 10, path='add_files')

    # Let it sync
    not_synced = storage.wait_until_uploaded(files, timeout=120)
    assert len(not_synced) == 0


@pytest.mark.parametrize('storage_config', ['dropbox_0',
                                            'gdrive_0',
                                            'onedrive_0'])
def test_modify_file_locally(crosscloud, storage_config):
    """Test modifying a file and check that it is being synced correctly."""
    crosscloud.login_to_admin_console()
    crosscloud.startup()

    storage = crosscloud.add_storage_pair(storage_config)

    storage.local.touch('modify.txt', 10, b'a')
    not_synced = storage.wait_until_uploaded(['modify.txt'], timeout=120)
    assert len(not_synced) == 0

    storage.local.touch('modify.txt', 10, b'b')
    not_synced = storage.wait_until_uploaded(['modify.txt'], timeout=120)
    assert len(not_synced) == 0

    remote_content = storage.remote.open('modify.txt').read()

    assert remote_content == b'b' * 10


@pytest.mark.parametrize('storage_config', ['dropbox_0',
                                            'gdrive_0',
                                            'onedrive_0'])
def test_rename_file_locally(crosscloud, storage_config):
    """Test renaming a file locally to see if the change is reflected remotely."""
    crosscloud.login_to_admin_console()
    crosscloud.startup()

    storage = crosscloud.add_storage_pair(storage_config)
    storage.local.touch('rename_locally.txt', 10, b'a')

    not_synced = storage.wait_until_uploaded(['rename_locally.txt'], timeout=120)
    assert len(not_synced) == 0

    storage.local.move('rename_locally.txt', 'rename_locally2.txt')

    not_synced = storage.wait_until_uploaded(['rename_locally2.txt'], timeout=120)
    assert len(not_synced) == 0

    assert storage.remote.exists('rename_locally2.txt')


@pytest.mark.parametrize('storage_config', ['dropbox_0',
                                            'gdrive_0',
                                            'onedrive_0'])
def test_rename_file_remotely(crosscloud, storage_config):
    """Test renaming a file remotely to see if the change is reflected locally."""
    crosscloud.login_to_admin_console()
    crosscloud.startup()

    storage = crosscloud.add_storage_pair(storage_config)
    storage.remote.touch('rename_remotely.txt', 10, b'a')

    not_synced = storage.wait_until_uploaded(['rename_remotely.txt'], timeout=120)
    assert len(not_synced) == 0

    storage.remote.move('rename_remotely.txt', 'rename_remotely2.txt')

    not_synced = storage.wait_until_uploaded(['rename_remotely2.txt'], timeout=120)
    assert len(not_synced) == 0

    assert storage.local.exists('rename_remotely2.txt')


@pytest.mark.parametrize('storage_config', ['dropbox_0',
                                            'gdrive_0',
                                            'onedrive_0'])
def test_delete_directory_locally(crosscloud, storage_config):
    """Test deleting a file locally to see if the change is reflected remotely."""
    crosscloud.login_to_admin_console()
    crosscloud.startup()

    storage = crosscloud.add_storage_pair(storage_config)

    storage.local.add_folder('delete_directory_locally')
    files = storage.local.add_files_flat(1, 10, path='delete_directory_locally')

    not_synced = storage.wait_until_uploaded(files, timeout=120)
    assert len(not_synced) == 0

    storage.local.remove_folder('delete_directory_locally')
    not_synced = storage.wait_until_deleted(files, timeout=120)
    assert len(not_synced) == 0

    assert not storage.remote.exists(files[0])
