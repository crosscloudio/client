"""
Tests for the metrics calculation during sync process
"""
# pylint: disable=protected-access, redefined-outer-name, unused-import

from unittest.mock import Mock

import pytest

from cc.synchronization.syncfsm import STORAGE, SIZE, FILESYSTEM_ID
from cc.synctask import DeleteSyncTask, SyncTask, UploadSyncTask, DownloadSyncTask, \
    CreateDirSyncTask
from .conftest import MBYTE, CSP_1, sync_engine_tester


@pytest.fixture()
def sync_engine_tester_fsm(sync_engine_tester):
    """Fake the get_default_fsm method, so the e_* can allways be called """

    sync_engine_tester.sync_engine.get_default_fsm = Mock(
        spec=['e_st_del_success', 'e_st_del_failed'])

    return sync_engine_tester


TASK_STATES = [SyncTask.SUCCESSFUL, SyncTask.INVALID_OPERATION,
               SyncTask.CURRENTLY_NOT_POSSIBLE, SyncTask.CANCELLED,
               SyncTask.NOT_AVAILABLE, SyncTask.UNEXECUTED]


@pytest.mark.parametrize('st_state', TASK_STATES)
def test_metrics_ack_delete(sync_engine_tester_fsm, st_state):
    """
    Test the SyncEngines behaviour on ACK of DeleteSyncTasks
    """
    sync_engine_tester_fsm.sync_engine.storage_metrics.free_space = 50 * MBYTE
    test_file = ['test.txt']

    task = DeleteSyncTask(test_file, CSP_1.storage_id, 123)

    sync_engine_tester_fsm.init_with_files([test_file], file_size=MBYTE)

    task.state = st_state
    # calculate expected free space
    expected_free_space = sync_engine_tester_fsm.sync_engine.storage_metrics.free_space

    if st_state == SyncTask.SUCCESSFUL:
        expected_free_space += MBYTE

    sync_engine_tester_fsm.sync_engine.ack_task(task)

    assert expected_free_space == sync_engine_tester_fsm.sync_engine.storage_metrics.free_space


@pytest.mark.parametrize('st_state', TASK_STATES)
def test_metrics_ack_upload(sync_engine_tester_fsm, st_state):
    """
    Test the SyncEngines behaviour on ACK of UploadSyncTasks
    """
    sync_engine_tester_fsm.init_with_files([['test.txt']])
    sync_engine_tester_fsm.sync_engine.storage_metrics.free_space = 50 * MBYTE

    task = UploadSyncTask(['test.txt'], CSP_1.storage_id, 123)

    task.state = st_state

    # calculate expected free space
    expected_free_space = sync_engine_tester_fsm.sync_engine.storage_metrics.free_space

    if st_state != SyncTask.SUCCESSFUL:
        expected_free_space += MBYTE

    sync_engine_tester_fsm.sync_engine.ack_task(task)

    assert expected_free_space == sync_engine_tester_fsm.sync_engine.storage_metrics.free_space


@pytest.mark.parametrize('task',
                         [UploadSyncTask(path=['test.txt'],
                                         target_storage_id=CSP_1.storage_id,
                                         source_version_id=123),

                          DownloadSyncTask(path=['test.txt'],
                                           source_storage_id=CSP_1.storage_id,
                                           source_version_id=123),

                          DeleteSyncTask(path=['test.txt'],
                                         target_storage_id=CSP_1.storage_id,
                                         original_version_id=123),

                          CreateDirSyncTask(['test.txt'],
                                            CSP_1.storage_id,
                                            FILESYSTEM_ID)])
def test_metrics_issue_synctask(sync_engine_tester, task):
    """Test the SyncEngines behaviour on ACK of UploadSyncTasks."""
    # calculate expected free space
    sync_engine_tester.init_with_files([['test.txt']])
    old_free_space = sync_engine_tester.sync_engine.storage_metrics.free_space
    if isinstance(task, UploadSyncTask):
        old_free_space -= next(iter(sync_engine_tester.sync_engine.root_node.children)).props[
            STORAGE][FILESYSTEM_ID][SIZE]

    sync_engine_tester.sync_engine.issue_sync_task(task)
    assert sync_engine_tester.sync_engine.storage_metrics.free_space == old_free_space
