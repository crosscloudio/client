"""
This tests here check the ability of the sync engine to detect and resolve conflicts
"""

# pylint: disable=redefined-outer-name,unused-import
import logging

import pytest

from cc.synctask import CompareSyncTask, MoveSyncTask, \
    PathWithStorageAndVersion, SyncTask
from .conftest import CSP_1, FILESYSTEM_ID, sync_engine_tester

__author__ = 'crosscloud GmbH'

logger = logging.getLogger(__name__)


# @pytest.mark.simple_integration
@pytest.mark.parametrize('equal', [True, False])
def test_conflict_simple(sync_engine_tester, equal):
    """ The sync engine is initialized with a tree with just one node.
    This node has 2 entries. One on local and one on csp1.
    This should rename the latter and download it afterwards
    """

    # we initalize the sync engine with an inequivalent tree, this will cause an conflict
    test_file = ['evil_conflict.png']
    sync_engine_tester.init_with_files([test_file], equivalent=False)

    expected_tasks = [
        CompareSyncTask(path=test_file,
                        storage_id_paths=[
                            PathWithStorageAndVersion(
                                storage_id=CSP_1.storage_id,
                                path=test_file,
                                expected_version_id=None,
                                is_dir=False),
                            PathWithStorageAndVersion(
                                storage_id=FILESYSTEM_ID,
                                path=test_file,
                                expected_version_id=None,
                                is_dir=False)])]

    sync_engine_tester.assert_expected_tasks(expected_tasks)

    task = sync_engine_tester.task_list[0]
    if equal:
        task.equivalents = [[CSP_1.storage_id, FILESYSTEM_ID]]
        expected_tasks = []
    else:
        task.equivalents = [[CSP_1.storage_id], [FILESYSTEM_ID]]
        expected_tasks = [MoveSyncTask(
            source_version_id=1, source_storage_id=CSP_1.storage_id,
            path=test_file,
            source_path=test_file,
            target_path=['evil_conflict.png (Conflicting copy).png'])]
    task.state = SyncTask.SUCCESSFUL
    sync_engine_tester.ack_task(task)

    sync_engine_tester.assert_expected_tasks(expected_tasks)
