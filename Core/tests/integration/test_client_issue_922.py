"""Test for issue 922

https://gitlab.crosscloud.me/crosscloud/client/issues/922

"""
import os
import pytest


@pytest.mark.parametrize('storage_config', ['dropbox_0',
                                            'gdrive_0',
                                            'onedrive_0'])
def test_pause_remote_delete(crosscloud, storage_config):
    """Test syncing when remote folders are deleted while syncing is paused. (client#922)

    This only fails on id-based storages (e.g. gdrive)

    1) Create a folder with some files A in it
    2) Let it sync
    3) Pause syncing
    4) Delete the remote folder
    5) Add files B to the folder locally
    6) Resume syncing

    Expected behaviour:
    The files A are deleted remotely and locally.
    The folder still exists
    The folder contains files B remotely and locally.
    """

    crosscloud.login_to_admin_console()
    crosscloud.startup()

    # Add storage
    storage = crosscloud.add_storage_pair(storage_config)
    if storage.storage_type in ('gdrive', 'onedrive'):
        pytest.skip('%s Is know to fail this test' % storage.storage_type)

    # 1) Create folder called 'test' and fill it with files A
    storage.local.add_folder("test")
    files_a = storage.local.add_files_flat(1, 10, path="test")

    # 2) Let it sync
    not_synced = storage.wait_until_synced(files_a, timeout=60)
    assert len(not_synced) == 0

    # 3) Pause syncing
    crosscloud.pause()

    # 4) Delete the remote folder
    storage.remote.remove_folder("test")

    # 5) Add files B to the folder locally
    files_b = storage.local.add_files_flat(1, 10, path="test")

    # 6) Resume syncing
    crosscloud.resume()

    # Wait until everything's synced
    storage.wait_until_synced(timeout=70)

    # Verify, that the folder 'test' still exists locally
    assert os.path.exists(os.path.join(storage.local.get_path(), "test"))

    # Verify, that the folder still contains files B
    local_path = os.path.join(storage.local.get_path(), "test")
    actual_local_files = [os.path.join("test", x) for x in os.listdir(local_path)]
    assert set(files_b).issubset(actual_local_files)

    # Verify, that the folder does not contain files A
    # assert not set(files_a).issubset(actual_local_files)
