"""
Test for adding files and directories

"""
# pylint: disable=unused-import
import logging
from datetime import datetime

import pytest
from jars import VERSION_ID

from cc.synchronization.syncengine import IS_DIR, SE_FSM, SIZE, STORAGE, normalize_path
from cc.synchronization.syncfsm import (MODIFIED_DATE, S_CANCELLING, S_DOWNLOADING, S_SYNCED,
                                        S_UPLOADING, get_storage_path)
from cc.synctask import (CancelSyncTask, CreateDirSyncTask, DownloadSyncTask,
                         SyncTask, UploadSyncTask)
from .conftest import CSP_1, FILESYSTEM_ID, MBYTE, ack_all_tasks, sync_engine_with_files, \
    storage_metrics, sync_engine_without_files, sync_engine_tester

# pylint: disable=redefined-outer-name
# noinspection PyUnresolvedReferences

logger = logging.getLogger(__name__)

__author__ = 'crosscloud GmbH'


@pytest.mark.parametrize("target_storage_id,source_storage_id",
                         [(CSP_1.storage_id, FILESYSTEM_ID),
                          (FILESYSTEM_ID, CSP_1.storage_id)])
def test_add_file(sync_engine_tester, target_storage_id, source_storage_id):
    """test if adding a file locally works -> Download upload..."""

    test_path = ['a.txt']
    logging.basicConfig(level=logging.DEBUG)
    sync_engine_tester.init_with_files([])

    sync_engine_tester.sync_engine.storage_create(path=test_path, storage_id=source_storage_id,
                                                  event_props={VERSION_ID: 2, IS_DIR: False})

    if source_storage_id == FILESYSTEM_ID:
        expected_tasks = [UploadSyncTask(path=test_path, target_storage_id=target_storage_id,
                                         source_version_id=2)]
    else:
        expected_tasks = [DownloadSyncTask(path=test_path, source_storage_id=source_storage_id,
                                           source_version_id=2)]

    sync_engine_tester.assert_expected_tasks(expected_tasks)

    sync_engine_tester.ack_all_tasks()

    # the ack function just multiplies the version id by 2
    sync_engine_tester.sync_engine.storage_create(path=test_path, storage_id=target_storage_id,
                                                  event_props={VERSION_ID: 4, IS_DIR: False})

    assert sync_engine_tester.sync_engine.root_node.get_node(['a.txt']).props[SE_FSM].current == \
        S_SYNCED

    assert len(sync_engine_tester.sync_engine.root_node) == 2


@pytest.mark.parametrize("target_storage_id,source_storage_id",
                         [(CSP_1.storage_id, FILESYSTEM_ID),
                          (FILESYSTEM_ID, CSP_1.storage_id)])
def test_add_directory(sync_engine_tester, target_storage_id, source_storage_id):
    """test if adding a file locally works -> Download upload..."""

    test_path = ['hi dir']
    logging.basicConfig(level=logging.DEBUG)
    sync_engine_tester.init_with_files([])

    sync_engine_tester.sync_engine.storage_create(path=test_path,
                                                  storage_id=source_storage_id,
                                                  event_props={VERSION_ID: IS_DIR, IS_DIR: True})

    expected_tasks = [CreateDirSyncTask(path=test_path, source_storage_id=source_storage_id,
                                        target_storage_id=target_storage_id)]

    sync_engine_tester.assert_expected_tasks(expected_tasks)

    sync_engine_tester.ack_all_tasks()

    # the ack function just multiplies the version id by 2
    sync_engine_tester.sync_engine.storage_create(path=test_path, storage_id=target_storage_id,
                                                  event_props={VERSION_ID: IS_DIR, IS_DIR: True})

    assert sync_engine_tester.sync_engine.root_node.get_node(test_path).props[SE_FSM].current == \
        S_SYNCED

    assert len(sync_engine_tester.sync_engine.root_node) == 2


@pytest.mark.parametrize("target_storage_id,source_storage_id",
                         [(CSP_1.storage_id, FILESYSTEM_ID),
                          (FILESYSTEM_ID, CSP_1.storage_id)])
def test_modify_file(sync_engine_tester, target_storage_id, source_storage_id):
    """test if adding a file locally works -> Download upload..."""

    test_path = ['a.txt']
    logging.basicConfig(level=logging.DEBUG)
    sync_engine_tester.init_with_files([test_path])

    sync_engine_tester.sync_engine.storage_modify(path=test_path, storage_id=source_storage_id,
                                                  event_props={VERSION_ID: 2, IS_DIR: False})

    if source_storage_id == FILESYSTEM_ID:
        expected_tasks = [UploadSyncTask(path=test_path, target_storage_id=target_storage_id,
                                         source_version_id=2, original_version_id=1)]
    else:
        expected_tasks = [DownloadSyncTask(path=test_path, source_storage_id=source_storage_id,
                                           source_version_id=2, original_version_id=1)]

    sync_engine_tester.assert_expected_tasks(expected_tasks)

    sync_engine_tester.ack_all_tasks()

    # the ack function just multiplies the version id by 2
    sync_engine_tester.sync_engine.storage_modify(path=test_path, storage_id=target_storage_id,
                                                  event_props={VERSION_ID: 4, IS_DIR: False})

    assert sync_engine_tester.sync_engine.root_node.get_node(['a.txt']).props[SE_FSM].current == \
        S_SYNCED

    assert len(sync_engine_tester.sync_engine.root_node) == 2


@pytest.mark.parametrize("target_storage_id,source_storage_id",
                         [(CSP_1.storage_id, FILESYSTEM_ID),
                          (FILESYSTEM_ID, CSP_1.storage_id)])
def test_modify_while_uploading_downloading(sync_engine_tester, target_storage_id,
                                            source_storage_id):
    """test if adding a file locally works -> Download upload..."""

    test_path = ['a.txt']
    logging.basicConfig(level=logging.DEBUG)
    sync_engine_tester.init_with_files([])

    sync_engine_tester.sync_engine.storage_create(path=test_path, storage_id=source_storage_id,
                                                  event_props={VERSION_ID: 2, IS_DIR: False})

    if source_storage_id == FILESYSTEM_ID:
        expected_tasks = [UploadSyncTask(path=test_path, target_storage_id=target_storage_id,
                                         source_version_id=2)]
    else:
        expected_tasks = [DownloadSyncTask(path=test_path, source_storage_id=source_storage_id,
                                           source_version_id=2)]

    sync_engine_tester.assert_expected_tasks(expected_tasks)

    original_copy_task = sync_engine_tester.task_list[0]

    # now while the task is uploading it gets modified again
    sync_engine_tester.sync_engine.storage_modify(path=test_path, storage_id=source_storage_id,
                                                  event_props={VERSION_ID: 4, IS_DIR: False})

    assert sync_engine_tester.sync_engine.root_node.get_node(test_path).props[SE_FSM].current == \
        S_CANCELLING

    sync_engine_tester.assert_expected_tasks([CancelSyncTask(path=test_path), original_copy_task])

    logger.debug('acking up/download task %s', id(original_copy_task))
    original_copy_task.status = SyncTask.CANCELLED
    original_copy_task.cancel = True
    sync_engine_tester.ack_task(original_copy_task)
    logger.debug('acking up/download task')

    # when we ack the cancel task we expecting an upload or download again
    sync_engine_tester.ack_all_tasks()

    if source_storage_id == FILESYSTEM_ID:
        expected_tasks = [UploadSyncTask(path=test_path, target_storage_id=target_storage_id,
                                         source_version_id=4)]
        # TODO: should not be part of here: original_version_id=1
        expected_state = S_UPLOADING

    else:
        expected_tasks = [DownloadSyncTask(path=test_path, source_storage_id=source_storage_id,
                                           source_version_id=4)]
        expected_state = S_DOWNLOADING

    assert sync_engine_tester.sync_engine.root_node.get_node(test_path).props[SE_FSM].current == \
        expected_state

    sync_engine_tester.assert_expected_tasks(expected_tasks)

    assert len(sync_engine_tester.sync_engine.root_node) == 2
