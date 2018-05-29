'''Move operation tests of the release test plan.'''


def test_move(crosscloud):
    """Test moving of files/folders."""

    crosscloud.login_to_admin_console()
    crosscloud.startup()

    storage = crosscloud.add_storage_pair('gdrive_ci6')

    storage.local.add_folder('alpha/one')
    storage.local.add_folder('banana/two')

    not_synced = storage.wait_until_synced(['alpha/one', 'banana/two'], timeout=120)
    assert len(not_synced) == 0

    storage.local.touch('alpha/move_me.txt', 10, b'a')

    not_synced = storage.wait_until_synced(['alpha/move_me.txt'], timeout=120)
    assert len(not_synced) == 0
    assert storage.remote.exists('alpha/move_me.txt')

    storage.local.move('alpha/move_me.txt', 'alpha/one/move_me.txt')

    not_synced = storage.wait_until_synced(['alpha/one/move_me.txt'], timeout=120)
    assert len(not_synced) == 0
    assert storage.remote.exists('alpha/one/move_me.txt')

    storage.local.move('alpha/one', 'alpha/two')

    not_synced = storage.wait_until_synced(['alpha/two/move_me.txt'], timeout=120)
    assert len(not_synced) == 0
    assert storage.remote.exists('alpha/two/move_me.txt')

    storage.local.move('alpha/two', 'banana/two')

    not_synced = storage.wait_until_deleted(['banana/two/move_me.txt'], timeout=120)
    assert len(not_synced) == 0
    assert storage.remote.exists('banana/two/move_me.txt')
