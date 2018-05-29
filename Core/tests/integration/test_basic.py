"""Write integration tests in basic python.

To run call: `py.test tests/integration/integration.py -s`

Example:
>>> def test_xyc(crosscloud):

>>>     # log in to the admin console
>>>     crosscloud.login_to_admin_console()

>>>     # starts crosscloud
>>>     crosscloud.startup()

>>>     # this adds the storage to the client and returns a helper object which holds
>>>     # a storage as well. The parameter name has to match one of the configurations in
>>>     # the YAML config
>>>     storage = crosscloud.add_storage_pair('dropbox')

>>>     # add 100 files, each 64 byte in size
>>>     files = storage.remote.add_files_flat(100, 64)

>>>     # waits 100 seconds until it has been synced
>>>     not_synced = storage.wait_until_synced(files, timeout=100)

>>>     # Everything should be synced now
>>>     asset len(not_synced) == 0
"""


def test_of_concept(crosscloud):
    """Run the test as described in issue 529."""

    crosscloud.login_to_admin_console()
    crosscloud.startup()

    storage = crosscloud.add_storage_pair('gdrive_0')
    files = storage.local.add_files_flat(10, 64)
    not_synced = storage.wait_until_synced(files, timeout=60)

    assert len(not_synced) == 0
