"""SyncEngine integration tests to test if deletion works correct4 """
import logging

from jars import VERSION_ID

from cc.synctask import DeleteSyncTask
# pylint: disable=unused-import
# pylint: disable=redefined-outer-name
# noinspection PyUnresolvedReferences
from .conftest import MBYTE, sync_engine_with_files, sync_engine_without_files, \
    EVENT_TYPE_CREATED, FILESYSTEM_ID, CSP_1, ack_all_tasks, storage_metrics, \
    sync_engine_tester

__author__ = 'crosscloud GmbH'


def test_delete_non_existing(sync_engine_tester):
    """Test if an empty SyncEngine does not emit tasks in case delete event"""

    sync_engine_tester.init_with_files([])

    sync_engine_tester.sync_engine.storage_delete(
        storage_id=FILESYSTEM_ID,
        path=['blabla'])

    sync_engine_tester.assert_expected_tasks([])


def test_delete_file(sync_engine_tester):
    """Test if a single file is deleted correctly"""
    tree = sync_engine_tester.init_with_files([['hello.txt']])
    node_to_test = next(iter(tree.children))

    # simulate it has been deleted locally
    sync_engine_tester.sync_engine.storage_delete(
        storage_id=FILESYSTEM_ID,
        path=node_to_test.path)

    expected_tasks = [DeleteSyncTask(original_version_id=node_to_test.props[VERSION_ID],
                                     path=node_to_test.path, target_storage_id=CSP_1.storage_id)]

    sync_engine_tester.assert_expected_tasks(expected_tasks)

    sync_engine_tester.ack_all_tasks()

    # lets simulate that the node has been deleted on the csp as well
    sync_engine_tester.sync_engine.storage_delete(
        storage_id=CSP_1.storage_id,
        path=node_to_test.path)

    assert len(sync_engine_tester.sync_engine.root_node) == 1


def test_delete_directory(sync_engine_tester):
    """Test if a directory containing files is deleted correctly"""
    files = [['a', 'hello.txt'], ['a', 'hella.txt'], ['a', 'hellc.txt']]

    tree = sync_engine_tester.init_with_files(files)
    node_to_test = next(iter(tree.children))

    sync_engine_tester.sync_engine.storage_delete(
        storage_id=CSP_1.storage_id,
        path=node_to_test.path)

    expected_tasks = []
    for child_node in tree:
        if child_node.parent is not None:
            expected_tasks.append(DeleteSyncTask(original_version_id=child_node.props[VERSION_ID],
                                                 path=child_node.path,
                                                 target_storage_id=FILESYSTEM_ID))

    sync_engine_tester.assert_expected_tasks(expected_tasks)

    sync_engine_tester.ack_all_tasks()

    # a delete on the top dir should be sufficent
    sync_engine_tester.sync_engine.storage_delete(
        storage_id=FILESYSTEM_ID,
        path=node_to_test.path)

    sync_engine_tester.assert_expected_tasks([])

    # All nodes should be gone after we deleted them
    assert len(sync_engine_tester.sync_engine.root_node) == 1


def test_delete_child_before_parent(sync_engine_tester):
    """Test if storage_delete handles deleting a child before its parent correctly.
    This happens if we rename a folder using storage_move."""
    files = [['a', 'hello.txt'], ['a', 'hella.txt'], ['a', 'hellc.txt']]

    logging.basicConfig(level=logging.DEBUG)

    tree = sync_engine_tester.init_with_files(files)

    # Get the parent and a child node
    node_top = next(iter(tree.children))
    node_child = next(iter(node_top))

    expected_tasks = []
    for child_node in tree:
        if child_node.parent is not None:
            expected_tasks.append(DeleteSyncTask(original_version_id=child_node.props[VERSION_ID],
                                                 path=child_node.path,
                                                 target_storage_id=CSP_1.storage_id))

    # ... and delete the child
    sync_engine_tester.sync_engine.storage_delete(
        storage_id=FILESYSTEM_ID,
        path=node_child.path)

    sync_engine_tester.sync_engine.storage_delete(
        storage_id=FILESYSTEM_ID,
        path=node_top.path)

    sync_engine_tester.assert_expected_tasks(expected_tasks)
