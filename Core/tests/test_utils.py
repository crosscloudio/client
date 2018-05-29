"""Test the functions from the utils module."""
import json

from jars import googledrive, owncloud
from cc import utils


def test_current_storage_props(mocker, config):
    """Assert an ordered with dicts is returned."""
    registered_storages = []

    registered_storages.append(owncloud.OwnCloud(mocker.Mock(), 'owncloud', None,
                                                 lambda: json.dumps({'server': 'ble',
                                                                     'username': 'blu',
                                                                     'password': 'bli'}),
                                                 None, polling_interval=30))

    registered_storages.append(googledrive.GoogleDrive(mocker.Mock(), 'gdrive',
                                                       storage_cache_dir=None,
                                                       storage_cred_reader=lambda: json.dumps({}),
                                                       storage_cred_writer=None,
                                                       polling_interval=5))

    current_props = utils.current_storage_props(config=config,
                                                registered_storages=registered_storages)

    # assert the items are ordered
    assert current_props[0]['display_name'] == 'Google Drive'
    assert current_props[-1]['display_name'] == 'OwnCloud'
