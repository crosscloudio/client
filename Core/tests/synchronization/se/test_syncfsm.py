"""This are the tests for all syncfsm functions. That means fsm handlers and helpers"""
# pylint: disable=unused-import

import csv
import json
import os
from unittest.mock import MagicMock
import yaml

import pytest
import requests
from bushn import Node
from jars import StorageMetrics

from cc.synchronization import syncfsm
from cc.synchronization.syncengine import SyncEngine
from cc.synchronization.syncfsm import DISPLAY_NAME, FILESYSTEM_ID, SIZE, STORAGE, \
    NoStorageForFileException, get_storage_path

from cc.synctask import SyncTask, UploadSyncTask
from .conftest import CSP_1, KBYTE, MBYTE, storage_metrics

# set all tests with mark unittest and sync_engine
pytestmark = [pytest.mark.unittest, pytest.mark.sync_engine]  # pylint: disable=invalid-name

GDOC_URL = ('https://docs.google.com/spreadsheets/d/'
            '18qbGtO2XxC7KnxnFrX1SKmlEfQZ1buxnO_KWprYiSVY/'
            'export?format=csv&gid={gid}')

CSP_2_ID = 'csp2'


def test_while_csp_uldl_success():
    """the ul success handler should set the property in the node
    """
    # pylint: disable=protected-access
    node = MagicMock(
        props={syncfsm.STORAGE: {FILESYSTEM_ID: {SIZE: MBYTE},
                                 CSP_1.storage_id: {syncfsm.SYNC_TASK_RUNNING: True},
                                 CSP_2_ID: {syncfsm.SYNC_TASK_RUNNING: True}}})
    task = UploadSyncTask(path=['abc'],
                          target_storage_id=CSP_1.storage_id,
                          source_version_id=123)
    task.state = SyncTask.SUCCESSFUL

    sync_engine = SyncEngine([], None)

    task.target_version_id = 321
    fsm = MagicMock()
    sync_engine._ack_updownload_task(fsm, node, task)

    assert not node.props[syncfsm.STORAGE][CSP_1.storage_id][syncfsm.SYNC_TASK_RUNNING]
    assert node.props[syncfsm.STORAGE][CSP_2_ID][syncfsm.SYNC_TASK_RUNNING]
    assert (syncfsm.FILESYSTEM_ID, 123) in node.props['equivalents']['new'].items()
    assert (CSP_1.storage_id, 321) in node.props['equivalents']['new'].items()
    assert len(node.props['equivalents']['old']) == 0

    task2 = UploadSyncTask(path=['abc'],
                           target_storage_id=CSP_2_ID,
                           source_version_id=123)
    task2.state = SyncTask.SUCCESSFUL
    task2.target_version_id = 456

    sync_engine._ack_updownload_task(fsm, node, task2)

    assert not node.props[syncfsm.STORAGE][CSP_1.storage_id][syncfsm.SYNC_TASK_RUNNING]
    assert not node.props[syncfsm.STORAGE][CSP_2_ID][syncfsm.SYNC_TASK_RUNNING]
    assert (syncfsm.FILESYSTEM_ID, 123) in node.props['equivalents']['new'].items()
    assert (CSP_1.storage_id, 321) in node.props['equivalents']['new'].items()
    assert (CSP_2_ID, 456) in node.props['equivalents']['new'].items()
    assert len(node.props['equivalents']['old']) == 0

    task3 = UploadSyncTask(path=['abc'],
                           target_storage_id=CSP_1.storage_id,
                           source_version_id=234)
    task3.state = SyncTask.SUCCESSFUL
    task3.target_version_id = 345

    sync_engine._ack_updownload_task(fsm, node, task3)

    assert (syncfsm.FILESYSTEM_ID, 123) in node.props['equivalents']['old'].items()
    assert (CSP_1.storage_id, 321) in node.props['equivalents']['old'].items()
    assert (CSP_2_ID, 456) in node.props['equivalents']['old'].items()
    assert (syncfsm.FILESYSTEM_ID, 234) in node.props['equivalents']['new'].items()
    assert (CSP_1.storage_id, 345) in node.props['equivalents']['new'].items()
    assert len(node.props['equivalents']['new'].items()) == 2
    assert len(node.props['equivalents']['old'].items()) == 3


def test_while_issue_upload():
    """ Check if issue upload issues an upload task
    """
    task_queue = []
    event = MagicMock(spec=['task_queue', 'node', 'target_storage_ids'])
    event.node = MagicMock(spec=['props', 'path', 'iter_up', 'parent', 'name'])
    event.node.path = ['hello.txt']
    event.node.name = 'hello.txt'
    parent = MagicMock(spec=['parent'])
    parent.parent = None
    event.node.iter_up = [event.node, parent]
    event.node.parent = parent
    event.node.props = {'storage': {'local': {'version_id': 123, 'size': 10,
                                              'is_dir': False}}}

    event.target_storage_ids = [CSP_2_ID]
    event.task_sink = task_queue.append

    syncfsm.while_issue_upload(event)
    assert task_queue == [UploadSyncTask(path=['hello.txt'],
                                         target_storage_id=CSP_2_ID,
                                         source_version_id=123)]


def get_paramters_from_gdocs(url):
    """ Helper to read tests from a google doc spreadsheet. It produces nodes according
    to the columns
    """
    result = []
    req = requests.get(url)
    for row in csv.DictReader(req.text.split('\n')):
        node = MagicMock(sepc=['props', 'parent', 'path'])
        parent = MagicMock(sepc=['props', 'parent', 'path'])
        parent.parent = None
        node.parent = parent
        node.path = ['test.txt']
        node.props = {}
        for key, val in row.items():
            # convert everything possible from json
            try:
                def convert_list_to_set(obj):
                    """ Converts a list to a set in an object  """
                    if isinstance(obj, dict):
                        for key, val in obj.items():
                            if isinstance(val, list):
                                obj[key] = set(val)
                    return obj

                row[key] = json.loads(val, object_hook=convert_list_to_set)
            except ValueError:
                pass

        node.props['equivalents'] = {}
        if row['old_equivalents']:
            node.props['equivalents']['old'] = row['old_equivalents']
        if row['new_equivalents']:
            node.props['equivalents']['new'] = row['new_equivalents']
        node.props['desired_storages'] = set(row['desired_storages'])
        for storage_id, version_id in row['actual_storages'].items():
            if isinstance(version_id, dict):
                node.props.setdefault(syncfsm.STORAGE, {})[storage_id] = version_id
            else:
                node.props.setdefault(syncfsm.STORAGE, {})[storage_id] = {
                    'version_id': version_id}

            node.props.setdefault(syncfsm.STORAGE, {}).setdefault(storage_id, {})[
                'size'] = 111
        result.append((row['enabled'] == 'y', node, row['expected_event'], row['params'],
                       row['comment']))
    return result


def get_paramters_from_yaml(file_name):
    """Load config from yaml to be used by the test on synced fiunction"""
    tests = yaml.load(open(os.path.join(os.path.dirname(__file__), file_name)))
    for test in tests:
        node = MagicMock(sepc=['props', 'parent', 'path'])
        parent = MagicMock(sepc=['props', 'parent', 'path'])
        parent.parent = None
        node.parent = parent
        node.path = ['test.txt']
        node.props = test['node']
        yield node, test['expected_event'], test.get('params')


@pytest.mark.parametrize(['node', 'expected_result', 'params'],
                         get_paramters_from_yaml('on-synced-cases.yaml'))
def test_on_synced(node, expected_result, params):
    """ Checks the on_synced test with the table from google analytics
    """
    event = MagicMock(spec=['node', 'csps', 'fsm', 'task_sink'])
    possible_actions = {'e_issue_delete', 'e_issue_download', 'e_issue_upload', 'e_conflicted'}
    event.fsm = MagicMock(spec=list(possible_actions))
    event.node = node
    storarage_providers = [MagicMock(storage_id='remote', free_space=100 * MBYTE, offline=False)]

    event.csps = storarage_providers

    syncfsm.on_synced(event)

    # all others should not be called
    for possible_action in possible_actions - {expected_result}:
        assert not getattr(event.fsm, possible_action).called

    if expected_result:
        if params:
            getattr(event.fsm, expected_result).assert_called_with(
                node=event.node,
                task_sink=event.task_sink,
                **params)
        else:
            assert getattr(event.fsm, expected_result).called


@pytest.mark.parametrize(['enabled', 'node', 'expected_result', 'params', 'comment'],
                         get_paramters_from_gdocs(GDOC_URL.format(gid=200431302)))
def test_on_deleting_online(enabled, node, expected_result, params, comment):
    """ tests the :function:`syncfsm.on_deleting` according to the gdocs table.
    """
    _ = comment
    if not enabled:
        pytest.skip('Not enabled in testmatrix')
    event = MagicMock(spec=['node', 'csps', 'fsm', 'task_sink'])
    possible_actions = {'e_issue_delete', 'e_issue_download', 'e_issue_upload',
                        'e_all_done', 'e_cancel_all', 'e_node_deleted'}
    event.fsm = MagicMock(spec=list(possible_actions))
    event.node = node
    csps = [MagicMock(storage_id=CSP_1.storage_id, free_space=10 * MBYTE),
            MagicMock(storage_id=CSP_2_ID, free_space=100 * MBYTE)]

    event.csps = csps

    syncfsm.on_deleting(event)

    if expected_result:
        if params:
            getattr(event.fsm, expected_result).assert_called_with(
                node=event.node,
                task_sink=event.task_sink,
                **params)
        else:
            assert getattr(event.fsm, expected_result).called

    # all others should not be called
    for possible_action in possible_actions - {expected_result}:
        assert not getattr(event.fsm, possible_action).called


# pylint: disable=unused-argument
@pytest.mark.parametrize(['enabled', 'node', 'expected_result', 'params', 'comment'],
                         get_paramters_from_gdocs(GDOC_URL.format(gid=920127810)))
def test_on_uploading_online_test(enabled, node, expected_result, params, comment):
    """ tests the :function:`syncfsm.on_uploading` according to the gdocs table.
    """
    if not enabled:
        pytest.skip('Not enabled in testmatrix')
    event = MagicMock(spec=['node', 'csps', 'fsm', 'task_sink'])
    possible_actions = {'e_issue_delete', 'e_issue_download', 'e_issue_upload',
                        'e_all_done', 'e_cancel_all'}
    event.fsm = MagicMock(spec=list(possible_actions))
    event.node = node
    csps = [MagicMock(storage_id=CSP_1.storage_id, free_space=10 * MBYTE),
            MagicMock(storage_id=CSP_2_ID, free_space=100 * MBYTE)]

    event.csps = csps

    syncfsm.on_uploading(event)

    # all others should not be called
    for possible_action in possible_actions - {expected_result}:
        assert not getattr(event.fsm, possible_action).called

    if expected_result:
        if params:
            getattr(event.fsm, expected_result).assert_called_with(
                node=event.node,
                task_sink=event.task_sink,
                **params)
        else:
            assert getattr(event.fsm, expected_result).called


def test_on_resolving():
    """  Tests the resolving function for different cases
    """
    event = MagicMock(spec=['task_sink', 'node', 'fsm', 'csps'])
    event.node = MagicMock(spec=['props', 'path'])
    event.node.props = {syncfsm.STORAGE: {}}

    syncfsm.on_resolving(event)

    event.fsm.e_all_done.assert_called_with(node=event.node, csps=event.csps,
                                            task_sink=event.task_sink)
    event.fsm.e_all_done.reset_mock()

    event.node.props[syncfsm.STORAGE] = {CSP_1.storage_id: {'deleted': True}}

    syncfsm.on_resolving(event)
    event.fsm.e_all_done.assert_called_with(node=event.node, csps=event.csps,
                                            task_sink=event.task_sink)
    event.fsm.e_all_done.reset_mock()

    del event.node.props[syncfsm.STORAGE][CSP_1.storage_id]['deleted']
    event.node.props[syncfsm.STORAGE][CSP_1.storage_id][
        syncfsm.SYNC_TASK_STATE] = syncfsm.MOVING

    syncfsm.on_resolving(event)

    event.fsm.e_all_done.assert_not_called()

    event.node.props[syncfsm.STORAGE][CSP_1.storage_id]['deleted'] = True
    event.node.props[syncfsm.STORAGE][CSP_1.storage_id][
        syncfsm.SYNC_TASK_STATE] = syncfsm.MOVING

    syncfsm.on_resolving(event)

    event.fsm.e_all_done.assert_not_called()

    event.node.props[syncfsm.STORAGE][CSP_1.storage_id]['deleted'] = False
    event.node.props[syncfsm.STORAGE][CSP_1.storage_id][syncfsm.SYNC_TASK_STATE] = \
        syncfsm.MOVED

    syncfsm.on_resolving(event)

    event.fsm.e_all_done.assert_not_called()

    event.fsm.e_all_done.reset_mock()
    event.node.props[syncfsm.STORAGE][CSP_1.storage_id]['deleted'] = True
    event.node.props[syncfsm.STORAGE][CSP_1.storage_id][syncfsm.SYNC_TASK_STATE] = \
        syncfsm.MOVED

    syncfsm.on_resolving(event)

    event.fsm.e_all_done.assert_called_with(node=event.node, csps=event.csps,
                                            task_sink=event.task_sink)


def test_get_storage_path():
    """
    creates a small tree and sees if sync-rule inheritance works
    """
    root = Node(name=None)

    child1 = root.add_child('child1')
    metrics = child1.props.setdefault(STORAGE, {}).setdefault(FILESYSTEM_ID, {})
    metrics[DISPLAY_NAME] = "CHILD1"

    metrics = child1.props.setdefault(STORAGE, {}).setdefault(CSP_1.storage_id, {})
    metrics[DISPLAY_NAME] = "Child1"

    child2 = child1.add_child('child2')
    metrics = child2.props.setdefault(STORAGE, {}).setdefault(CSP_1.storage_id, {})
    metrics[DISPLAY_NAME] = "Child2"

    path = get_storage_path(child2, FILESYSTEM_ID, CSP_1.storage_id)
    assert ["CHILD1", "Child2"] == path


#
# # pylint: disable=redefined-outer-name
# @pytest.fixture()
# def impl_sr_csps():
#     """
#     Fixture with available csps for implicit syncrule tests
#     :return:
#     """
#     return [StorageMetrics(free_space=50, storage_id='csp_1'),
#             StorageMetrics(free_space=200, storage_id='csp_2')]
#
#
# def test_implicit_syncrules_1():
#     """
#      ---
#     | a | storages = local + csp1
#      ---
#       |
#      ---
#     | b |
#      ---
#       |
#      -------
#     | c.txt |
#      -------
#
#     expected result for b and c.txt is csp1
#
#     """
#     root = tree.Node(name=None)
#     node_1 = root.add_child('a', props={STORAGE: {'csp_1': {}, FILESYSTEM_ID: {}}})
#     child_1 = node_1.add_child('b')
#     child_2 = child_1.add_child('c.txt')
#     assert syncfsm.select_csp(child_2) == 'csp_1'
#     assert syncfsm.select_csp(child_1) == 'csp_1'
#
#
# def test_implicit_syncrules_2():
#     """
#      ---
#     | a | storages = local + csp1
#      ---
#       |
#      ---
#     | b | storages = local + csp2
#      ---
#       |
#      -------
#     | c.txt |
#      -------
#
#     expected result for c.txt is csp2
#
#     """
#     root = tree.Node(name=None)
#     node_1 = root.add_child('a', props={STORAGE: {'csp_1': {}, FILESYSTEM_ID: {}}})
#     child_1 = node_1.add_child('b', props={STORAGE: {'csp_2': {}, FILESYSTEM_ID: {}}})
#     child_2 = child_1.add_child('c.txt')
#     assert syncfsm.select_csp(child_2) == 'csp_1'
#
#
# def test_implicit_syncrules_3():
#     """
#      ---         preselected to csp_1 --> csp1
#     | a |           ^         |
#      ---            |         |
#       |             |         |
#      ---            |         v
#     | b |           |       csp_1
#      ---            |
#       |             |
#      -------        |
#     | c.txt | --> csp_1
#      -------
#
#     expected result for c.txt is csp1 and afterwards the result for a is also csp1
#
#     """
#     root = tree.Node(name=None)
#     node_a = root.add_child('a')
#     node_b = node_a.add_child('b')
#     node_c = node_b.add_child('c.txt')
#     with mock.patch('cc.syncfsm.select_csp_by_usage', return_value='csp_1'):
#         assert syncfsm.select_csp(node_c) == 'csp_1'
#         assert node_a.props[STORAGE_PRESELECT] == 'csp_1'
#     with mock.patch('cc.syncfsm.select_csp_by_usage', return_value='csp_2'):
#         # select by free space would decide to sync to csp_2 but since
#         # we have implicit syncrules the result has to be csp_1
#         assert syncfsm.select_csp(node_a) == 'csp_1'
#         assert syncfsm.select_csp(node_b) == 'csp_1'
#
#
# def test_implicit_syncrules_4():
#     """
#     Test which represents a possible situation of an existing old CC
#     installation (before implicit sr)
#      ---
#     | a |
#      ---
#       |
#      ---
#     | b | storages = local + csp1 + csp2
#      ---
#       |
#       |---------------------
#       |           |         |
#      -------   -------   -------
#     | c.txt | | d.txt | | e.txt |
#      -------   -------   -------
#
#     expected result for c.txt, d.txt and e.txt should be either csp1 or csp2
#     but all three have to be the same
#
#     """
#     root = tree.Node(name=None)
#     node_a = root.add_child('a')
#     node_b = node_a.add_child('b', props={STORAGE: {'csp_1': {},
#                                                     'csp_2': {},
#                                                     FILESYSTEM_ID: {}}})
#     node_c = node_b.add_child('c.txt')
#     node_d = node_b.add_child('d.txt')
#     node_e = node_b.add_child('e.txt')
#
#     csp = syncfsm.select_csp(node_c)
#     assert csp in ['csp_1', 'csp_2']
#     assert syncfsm.select_csp(node_d) == csp
#     assert syncfsm.select_csp(node_e) == csp
#
#
# def test_implicit_syncrules_5():
#     """
#      ---
#     | a | storages = local + csp1
#      ---
#       |
#      ---
#     | b |
#      ---
#       |
#      -------
#     | c.txt |
#      -------
#
#     expected result for b and c.txt is csp1 but there is not enough space
#     left on csp1 so the result should be csp2
#
#     """
#
#     root = tree.Node(name=None)
#     node_1 = root.add_child('a', props={STORAGE: {'csp_1': {}, FILESYSTEM_ID: {}}})
#     child_1 = node_1.add_child('b')
#     child_2 = child_1.add_child('c.txt')
#     assert syncfsm.select_csp(child_2) == 'csp_2'


@pytest.fixture(params=[
    # free space, offline, id1, free space,
    (10 * MBYTE, False, CSP_1.storage_id, 100 * MBYTE,
     # offline, id2 , file size , exp. result
     False, CSP_2_ID, 10 * KBYTE, CSP_2_ID),

    (100 * MBYTE, False, CSP_1.storage_id, 10 * MBYTE,
     False, CSP_2_ID, 10 * KBYTE, CSP_1.storage_id),

    (10 * KBYTE, False, CSP_1.storage_id, 10 * KBYTE,
     False, CSP_2_ID, 100 * KBYTE, None),

    (100 * MBYTE, True, CSP_1.storage_id, 10 * MBYTE,
     False, CSP_2_ID, 10 * KBYTE, CSP_2_ID),

    (100 * MBYTE, True, CSP_1.storage_id, 10 * MBYTE,
     True, CSP_2_ID, 10 * KBYTE, None)])
def csp_config(request):
    """
    Fixture for CSP list
    :return:
    """
    csp1 = StorageMetrics(free_space=request.param[0], storage_id=request.param[2])
    csp1.offline = request.param[1]
    csp2 = StorageMetrics(free_space=request.param[3], storage_id=request.param[5])
    csp2.offline = request.param[4]

    return ([csp1, csp2], request.param[6], request.param[7])
