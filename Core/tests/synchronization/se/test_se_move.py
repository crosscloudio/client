"""
Test for moving files and directories

"""
import pytest
from jars import VERSION_ID, IS_DIR

from cc.synctask import (DeleteSyncTask, DownloadSyncTask, UploadSyncTask)
from .conftest import CSP_1, FILESYSTEM_ID

__author__ = 'crosscloud GmbH'


@pytest.fixture(params=[['rename.txt'], ['B', 'test.txt'], ['A', 'test2.txt']])
def other_path(request):
    """Append SP display name to path and return it."""
    path = [CSP_1.display_name]
    path.extend(request.param)
    return path


@pytest.mark.parametrize("source_storage_id, target_storage_id",
                         [[FILESYSTEM_ID, CSP_1.storage_id],
                          [CSP_1.storage_id, FILESYSTEM_ID]])
def test_move_file(sync_engine_tester, source_storage_id, target_storage_id):
    """Test move on a single file"""
    source_path = ['moimii.txt']
    target_path = ['blablablabla.txt']
    tree = sync_engine_tester.init_with_files([source_path])
    new_version_id = 2

    node_to_test = next(iter(tree.children))
    sync_engine_tester.sync_engine.storage_move(
        storage_id=source_storage_id,
        source_path=node_to_test.path,
        target_path=target_path,
        event_props={VERSION_ID: new_version_id, IS_DIR: False})

    if target_storage_id != FILESYSTEM_ID:
        expected_tasks = [
            DeleteSyncTask(original_version_id=node_to_test.props[VERSION_ID],
                           path=source_path, target_storage_id=target_storage_id),
            UploadSyncTask(path=target_path, target_storage_id=target_storage_id,
                           source_version_id=new_version_id)]
    else:
        expected_tasks = [
            DownloadSyncTask(path=target_path, source_storage_id=source_storage_id,
                             source_version_id=new_version_id),
            DeleteSyncTask(original_version_id=node_to_test.props[VERSION_ID],
                           path=source_path, target_storage_id=target_storage_id)]

    sync_engine_tester.assert_expected_tasks(expected_tasks)
