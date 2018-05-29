"""Tests for all state sync operations in the syncengine.

This are kind of integration tests, since
"""
import logging
from copy import deepcopy

import pytest
from bushn import Node
from jars import VERSION_ID

from cc.synchronization.syncengine import (FILESYSTEM_ID, IS_DIR, SyncEngineState)
from cc.synchronization.syncfsm import STORAGE
from cc.synctask import CreateDirSyncTask, DeleteSyncTask, DownloadSyncTask, FetchFileTreeTask, \
    UploadSyncTask

# fixture import
# pylint: disable=unused-import
from .conftest import CSP_1, csp_dir_model, storage_model_with_files, \
    sync_engine_tester

# pylint: disable=redefined-outer-name, redefined-variable-type

__author__ = 'crossscloud GmbH'
LOGGER = logging.getLogger(__name__)


def test_state_empty_storage_provider_empty_local(sync_engine_tester):
    """Scenario: empty storage provider some file local. That should result in no action

    Tests as well the internal state of the syncengine, (remote_tree_fetched, local_tree_fetched)
    """
    sync_engine_tester.sync_engine.init()

    # first, only the remote tree gets fetched, otherwise the encryptionwrapper
    # don't know share ids
    sync_engine_tester.assert_expected_tasks([FetchFileTreeTask(CSP_1.storage_id)])

    sync_engine_tester.ack_fetch_tree_task(CSP_1.storage_id, Node(name=None))
    assert sync_engine_tester.sync_engine.remote_tree_fetched
    assert not sync_engine_tester.sync_engine.local_tree_fetched

    sync_engine_tester.assert_expected_tasks([FetchFileTreeTask(FILESYSTEM_ID)])
    sync_engine_tester.ack_fetch_tree_task(FILESYSTEM_ID, Node(name=None))

    assert not sync_engine_tester.sync_engine.local_tree_fetched
    assert not sync_engine_tester.sync_engine.remote_tree_fetched

    sync_engine_tester.assert_expected_tasks([])

    assert sync_engine_tester.sync_engine.state == SyncEngineState.RUNNING


def test_state_empty_storage_provider(sync_engine_tester, storage_model_with_files):
    """Scenario: empty storage provider some file local. That should result in uploads"""
    sync_engine_tester.sync_engine.init()

    # first, only the remote tree gets fetched, otherwise the encryptionwrapper
    # don't know share ids
    sync_engine_tester.assert_expected_tasks([FetchFileTreeTask(CSP_1.storage_id)])
    sync_engine_tester.ack_fetch_tree_task(CSP_1.storage_id, Node(name=None))

    sync_engine_tester.assert_expected_tasks([FetchFileTreeTask(FILESYSTEM_ID)])
    sync_engine_tester.ack_fetch_tree_task(FILESYSTEM_ID, storage_model_with_files)

    expected_tasks = []
    for node in storage_model_with_files:
        if node.parent is not None:
            if not node.props[IS_DIR]:
                sync_task = UploadSyncTask(path=node.path, target_storage_id=CSP_1.storage_id,
                                           source_version_id=1)
            else:
                sync_task = CreateDirSyncTask(path=node.path, target_storage_id=CSP_1.storage_id,
                                              source_storage_id=FILESYSTEM_ID)
            expected_tasks.append(sync_task)

    assert sync_engine_tester.sync_engine.state == SyncEngineState.RUNNING
    sync_engine_tester.assert_expected_tasks(expected_tasks)


def test_state_empty_local(sync_engine_tester, storage_model_with_files):
    """Scenario: empty storage provider some file local. That should result in downloads"""
    sync_engine_tester.sync_engine.init()

    # first, only the remote tree gets fetched, otherwise the encryptionwrapper
    # don't know share ids
    sync_engine_tester.assert_expected_tasks([FetchFileTreeTask(CSP_1.storage_id)])
    sync_engine_tester.ack_fetch_tree_task(CSP_1.storage_id, storage_model_with_files)

    sync_engine_tester.assert_expected_tasks([FetchFileTreeTask(FILESYSTEM_ID)])
    sync_engine_tester.ack_fetch_tree_task(FILESYSTEM_ID, Node(name=None))

    expected_tasks = []
    for node in storage_model_with_files:
        if node.parent is not None:
            if not node.props[IS_DIR]:
                sync_task = DownloadSyncTask(path=node.path, source_storage_id=CSP_1.storage_id,
                                             source_version_id=1)
            else:
                sync_task = CreateDirSyncTask(path=node.path, target_storage_id=FILESYSTEM_ID,
                                              source_storage_id=CSP_1.storage_id)
            expected_tasks.append(sync_task)

    assert sync_engine_tester.sync_engine.state == SyncEngineState.RUNNING
    sync_engine_tester.assert_expected_tasks(expected_tasks)


@pytest.mark.simple_integration
@pytest.mark.parametrize("empty_storage_id, not_empty_storage_id",
                         [(FILESYSTEM_ID, CSP_1.storage_id),
                          (CSP_1.storage_id, FILESYSTEM_ID)])
def test_state_sync_deletes(sync_engine_tester, csp_dir_model, empty_storage_id,
                            not_empty_storage_id):
    """State Sync after files have been removed from local or remote -> trigger delete """

    # we put two times the same model into the syncengine
    sync_engine_tester.sync_engine.merge_storage_to_sync_model(storage_model=csp_dir_model,
                                                               storage_id=FILESYSTEM_ID)
    sync_engine_tester.sync_engine.merge_storage_to_sync_model(storage_model=csp_dir_model,
                                                               storage_id=CSP_1.storage_id)

    # we simulate that everything was in sync before
    for node in sync_engine_tester.sync_engine.root_node:
        if node.parent is not None:
            node.props['equivalents'] = \
                {'new': {FILESYSTEM_ID: node.props[STORAGE][FILESYSTEM_ID][VERSION_ID],
                         CSP_1.storage_id: node.props[STORAGE][CSP_1.storage_id][VERSION_ID]}}

    sync_engine_tester.sync_engine.init()

    # now we initalize the sync engine and ack either one with an empty tree
    # the local one need to be acked last
    if empty_storage_id == FILESYSTEM_ID:
        sync_engine_tester.ack_fetch_tree_task(not_empty_storage_id, csp_dir_model)
        sync_engine_tester.ack_fetch_tree_task(empty_storage_id, Node(name=None))
    else:
        sync_engine_tester.ack_fetch_tree_task(empty_storage_id, Node(name=None))
        sync_engine_tester.ack_fetch_tree_task(not_empty_storage_id, csp_dir_model)

    expected_tasks = []

    for node in csp_dir_model:
        if node.parent is None:
            continue
        sync_task = DeleteSyncTask(node.path, not_empty_storage_id, node.props[VERSION_ID])
        expected_tasks.append(sync_task)

    sync_engine_tester.assert_expected_tasks(expected_tasks)


@pytest.mark.parametrize("modified_storage_id, not_modified_storage_id",
                         [(FILESYSTEM_ID, CSP_1.storage_id),
                          (CSP_1.storage_id, FILESYSTEM_ID)])
def test_state_sync_modifies(sync_engine_tester, csp_dir_model, modified_storage_id,
                             not_modified_storage_id):
    """State Sync with either local or remote file(all) modified --> triggers upload or download"""
    # we put two times the same model into the syncengine
    sync_engine_tester.sync_engine.merge_storage_to_sync_model(storage_model=csp_dir_model,
                                                               storage_id=FILESYSTEM_ID)
    sync_engine_tester.sync_engine.merge_storage_to_sync_model(storage_model=csp_dir_model,
                                                               storage_id=CSP_1.storage_id)

    # we simulate that everything was in sync before
    for node in sync_engine_tester.sync_engine.root_node:
        if node.parent is not None:
            node.props['equivalents'] = \
                {'new': {FILESYSTEM_ID: node.props[STORAGE][FILESYSTEM_ID][VERSION_ID],
                         CSP_1.storage_id: node.props[STORAGE][CSP_1.storage_id][VERSION_ID]}}

    modified_model = deepcopy(csp_dir_model)

    # modify all the not dirs on one side
    for node in modified_model:
        if node.parent is not None and not node.props[IS_DIR]:
            node.props[VERSION_ID] = 2

    sync_engine_tester.sync_engine.init()

    # the local one need to be acked last
    if modified_storage_id == FILESYSTEM_ID:
        sync_engine_tester.ack_fetch_tree_task(not_modified_storage_id, csp_dir_model)
        sync_engine_tester.ack_fetch_tree_task(modified_storage_id, modified_model)
    else:
        sync_engine_tester.ack_fetch_tree_task(modified_storage_id, modified_model)
        sync_engine_tester.ack_fetch_tree_task(not_modified_storage_id, csp_dir_model)

    expected_tasks = []

    # expected tasks are all except directories
    for node in csp_dir_model:
        if node.parent is None:
            continue
        if modified_storage_id == FILESYSTEM_ID and not node.props[IS_DIR]:
            sync_task = UploadSyncTask(path=node.path, target_storage_id=not_modified_storage_id,
                                       source_version_id=2, original_version_id=1)
            expected_tasks.append(sync_task)
        elif not node.props[IS_DIR]:
            sync_task = DownloadSyncTask(path=node.path, source_storage_id=modified_storage_id,
                                         source_version_id=2, original_version_id=1)
            expected_tasks.append(sync_task)

    sync_engine_tester.assert_expected_tasks(expected_tasks)


def test_state_no_modifies(sync_engine_tester):
    """State Sync with either local or remote file(all) modified --> triggers upload or download"""
    # we put two times the same model into the syncengine
    sync_engine_tester.init_with_files([['hello.txt']])

    # assert that now tasks have been issued
    assert not sync_engine_tester.task_list
