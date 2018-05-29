"""Test the JSONRPC implementation to communicate with the core process."""
# pylint: disable=redefined-outer-name
import json
import pytest
import mock

from jars.googledrive import GoogleDrive

import cc.ipc_core


@pytest.fixture
def google_drive():
    """Create a registered storages list."""
    return GoogleDrive(event_sink=mock.Mock(), storage_id='gdrive1',
                       storage_cred_reader=mock.Mock(return_value=json.dumps({})),
                       storage_cred_writer=mock.Mock())


@pytest.mark.parametrize('enabled_storage', [[], ['gdrive'], ['dropbox', 'owncloud']])
def test_getAccountTypes_with_filter(enabled_storage, config):
    """Ensure the storage types are filtered properly."""
    config.enabled_storage_types = enabled_storage
    cc_core = mock.Mock(cc.ipc_core.CrossCloudCore)
    cc_core.client = mock.Mock(cc.client.Client)
    cc_core.client.config = config

    account_types = cc.ipc_core.CrossCloudCore.getAccountTypes(cc_core)

    for account in account_types:
        if account['name'] in enabled_storage:
            assert account['enabled']
        else:
            assert not account['enabled']
