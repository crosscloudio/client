"""SyncEngine Unit Tests
"""
import contextlib
import datetime
from copy import deepcopy
from unittest.mock import ANY, MagicMock, Mock
import mock

import pytest
from bushn import DELETE, Node
from fysom import Fysom

import cc.synchronization.syncfsm as syncfsm
from cc.synchronization.syncengine import (STORAGE, normalize_path,
                                           update_storage_delete,
                                           update_storage_props,
                                           SyncEngineState)
# fixture import
# pylint: disable=unused-import
from cc.synctask import CancelSyncTask
from .conftest import CSP_1, MBYTE, storage_metrics, storage_model_with_files, sync_engine, \
    sync_engine_tester

# pylint: disable=redefined-outer-name,protected-access

__author__ = "crosscloud GmbH"

TEST_PROPS = {"abc": "def", "asdf": "jklö"}


def test_query(sync_engine):
    """Test if query works and if a copy of the properties are returned."""
    new_node = sync_engine.root_node.add_child("test", TEST_PROPS)

    assert sync_engine.query(new_node.path) == TEST_PROPS
    assert sync_engine.query(new_node.path) is not new_node.props


def test_query_storage_path(sync_engine):
    """Tests the syncengine's test_query_storage_path method"""
    node1 = sync_engine.root_node.add_child("test", TEST_PROPS)
    node1.props = {STORAGE: {'csp1': {syncfsm.DISPLAY_NAME: 'TeSt'}}}
    node1.props[STORAGE]['csp2'] = {syncfsm.DISPLAY_NAME: 'tEsT'}
    node_path = node1.path

    paths = sync_engine.query_storage_path(node_path)
    assert paths == {'csp1': ['TeSt'],
                     'csp2': ['tEsT']}

    node2 = node1.add_child("foo", TEST_PROPS)
    node2.props = {STORAGE: {'csp1': {syncfsm.DISPLAY_NAME: 'Foo'}}}
    node2.props[STORAGE]['csp2'] = {syncfsm.DISPLAY_NAME: 'fOo'}
    node_path = node2.path

    paths = sync_engine.query_storage_path(node_path)
    assert paths == {'csp1': ['TeSt', 'Foo'],
                     'csp2': ['tEsT', 'fOo']}


def test_get_default_fsm(sync_engine):
    """Chick if get_default_fsm works"""
    testpath = ['a', 'b', 'c']
    fsm = sync_engine.get_default_fsm(testpath)
    assert isinstance(fsm, Fysom)
    assert isinstance(sync_engine.root_node.get_node(testpath), Node)


def test_sync_state(sync_engine):
    """Check mainly if e_check is called for all nodes in the model"""

    sync_engine.root_node.add_child('hello node').add_child('other node')

    root_copy = deepcopy(sync_engine.root_node)

    sync_engine.get_default_fsm = Mock()
    sync_engine._sync_state()

    for node in root_copy:
        if node.parent is not None:
            # check if it was trying to get a default fsm
            sync_engine.get_default_fsm.assert_any_call(node.path)

            # check if it called e_check on that fsm
            hopefully_called_mock = sync_engine.get_default_fsm(node.path)
            assert hopefully_called_mock.e_check.called


@pytest.mark.parametrize('node_props', [{},
                                        {syncfsm.STORAGE: {
                                            syncfsm.FILESYSTEM_ID: {'deleted': True}
                                        }}])
def test_update_storage_props(node_props):
    """This handler will set the properties 'storage_id' and 'modified_date' from
    the event
    """
    node = MagicMock(spec=['props', 'path', 'name'])
    node.props = node_props
    event_props = {}
    storage_id = syncfsm.FILESYSTEM_ID
    event_props['version_id'] = 'blabal'
    event_props['modified_date'] = datetime.datetime.now()
    event_props['size'] = 17
    event_props['display_name'] = 'asdf'
    event_props['is_dir'] = False

    update_storage_props(storage_id, node, event_props)
    fs_storage = node.props[syncfsm.STORAGE][syncfsm.FILESYSTEM_ID]

    assert fs_storage['version_id'] == event_props['version_id']
    assert fs_storage['modified_date'] == event_props['modified_date']
    assert 'deleted' not in node.props[syncfsm.STORAGE][syncfsm.FILESYSTEM_ID]

    del event_props['version_id']
    storage_id = 'test1'
    with contextlib.suppress(KeyError):
        update_storage_props(storage_id=storage_id, node=node, props=event_props)
    assert storage_id not in node.props[syncfsm.STORAGE]


def test_update_storage_props_delete():
    """Check if the special DELETE constant works do delete properties."""
    props = {
        'version_id': 17,
        'modified_date': datetime.datetime.now(),
        'size': 23,
        'display_name': 'TestNode',
        'is_dir': False,
        'shared': True,
        'share_id': 12345,
        'public_share': True
    }

    node = Node(name="testnode", parent=None,
                props={syncfsm.STORAGE: {CSP_1.storage_id: props}})

    assert node.props[STORAGE][CSP_1.storage_id] == props

    event_props = {'version_id': 17,
                   'modified_date': datetime.datetime.now(),
                   'size': 23,
                   'display_name': 'TestNode',
                   'is_dir': False,
                   'shared': False,
                   'share_id': DELETE,
                   'public_share': DELETE}

    update_storage_props(CSP_1.storage_id, node, event_props)

    del event_props['share_id']
    del event_props['public_share']

    assert node.props[STORAGE][CSP_1.storage_id] == event_props

    # if a mandatory valie is set to DELETE the props do not change
    with contextlib.suppress(KeyError):
        update_storage_props(CSP_1.storage_id, node, {'version_id': DELETE})
    assert node.props[STORAGE][CSP_1.storage_id] == event_props


def test_update_storage_delete():
    """ Test for while delete callback handler."""
    storage_id = CSP_1.storage_id
    node = MagicMock(spec=['path'], props={
        syncfsm.STORAGE: {CSP_1.storage_id: {'version_id': 'something'}}})

    update_storage_delete(storage_id, node)

    assert node.props[syncfsm.STORAGE][CSP_1.storage_id].get('deleted')
    assert 'version_id' not in node.props[syncfsm.STORAGE][CSP_1.storage_id]


def test_path_normalize():
    """Check if normalize_path works"""
    path1 = ['a', 'b', 'c.txt']
    assert path1 == normalize_path(path1)

    path2 = ['A', 'b', 'C.txt']
    assert ['a', 'b', 'c.txt'] == normalize_path(path2)


# @pytest.mark.parametrize('flat', [False, True])
# def test_mergemodel_performance(flat):
#     """
#     Tests the performance of the model merge functionality
#     """
#     sync_model = Node(name=None)
#     test_size = 500
#
#     # create a deep storage model
#     storage_model = Node(name=None)
#     parent = storage_model
#     for cnt in range(test_size):
#         name = 'child_{}'.format(cnt)
#         node = parent.add_child(name=name)
#         node.props['version_id'] = 0
#         node.props['is_dir'] = False
#         if not flat:
#             parent = node
#
#     start = time.time()
#     merge_storage_to_sync_model(sync_model, storage_model, CSP_1.storage_id)
#     dur = time.time() - start
#     print(dur)


def populate_sync_engine_with_shared_paths(model):
    """Pupulate sync engine model to contain the following model.

    + 'public shared folder'
    +- 'child'
    + 'folder share_id'
    +- 'child'
    + 'public and share_id shared folder'
    +- 'child'
    + 'private folder'
    +- 'child'
    """
    model.add_child(
        'public shared folder',
        {STORAGE: {CSP_1.storage_id: {syncfsm.PUBLIC_SHARE: True}}})
    model.add_child(
        'folder share_id',
        {STORAGE: {CSP_1.storage_id: {syncfsm.SHARE_ID: 1337}}})
    model.add_child(
        'public and share_id shared folder',
        {STORAGE: {CSP_1.storage_id: {syncfsm.SHARE_ID: 1337, syncfsm.PUBLIC_SHARE: True}}})
    model.add_child(
        'private folder', {})

    for child in model.children:
        child.add_child('child')


@pytest.mark.parametrize('path', [['public Shared folder', 'child'],
                                  ['public Shared folder'],
                                  ['public Shared folder', 'lala']])
def test_query_shared_state_public_shared(path, sync_engine):
    """Test if the shared folder returns true if it is relevant."""
    populate_sync_engine_with_shared_paths(sync_engine.root_node)
    state = sync_engine.query_shared_state(path)
    assert state.public_shared


@pytest.mark.parametrize('path', [['folder share_id', 'child'],
                                  ['folder share_id'],
                                  ['folder share_id', 'lala']])
def test_query_shared_state_share_id(sync_engine, path):
    """Test if the shared folder returns true if it is relevant."""
    populate_sync_engine_with_shared_paths(sync_engine.root_node)
    state = sync_engine.query_shared_state(path)
    assert not state.public_shared
    assert state.share_id == 1337


@pytest.mark.parametrize('path', [['public and share_id shared folder', 'child'],
                                  ['public and share_id shared folder'],
                                  ['public and share_id shared folder', 'lala']])
def test_query_shared_state_share_id_public_shared(sync_engine, path):
    """Test if the shared folder returns true if it is relevant."""
    populate_sync_engine_with_shared_paths(sync_engine.root_node)
    state = sync_engine.query_shared_state(path)
    assert state.public_shared
    assert state.share_id == 1337


@pytest.mark.parametrize('path', [['private folder', 'child'],
                                  ['private folder'],
                                  ['private folder', 'lala']])
def test_query_shared_state_private(sync_engine, path):
    """Test if the shared folder returns true if it is relevant."""
    populate_sync_engine_with_shared_paths(sync_engine.root_node)
    state = sync_engine.query_shared_state(path)
    assert not state.public_shared
    assert not state.share_id


# TODO: Modify event?
def test_on_node_changed(sync_engine):
    """Test the syncengine's on node changed signal."""

    receiver = Mock()
    signal = sync_engine.on_node_props_change
    signal.connect(receiver, weak=False)

    sync_engine.storage_create(
        CSP_1.storage_id, [CSP_1.storage_id, 'test.txt'],
        {'version_id': 'asdfasdf', 'is_dir': False})

    receiver.assert_called_with(
        sync_engine,
        old_props={syncfsm.SE_FSM: ANY},
        storage_id=CSP_1.storage_id,
        node=ANY)

    assert receiver.call_args[1]['node'].props == {  # pylint: disable=unsubscriptable-object
        syncfsm.SE_FSM: ANY,
        'storage': {'csp1': {
            'display_name': 'test.txt',
            'is_dir': False,
            'modified_date': datetime.datetime(1, 1, 1, 0, 0),
            'shared': False,
            'public_share': False,
            'size': 0,
            'version_id': 'asdfasdf'}}}


def test_storage_create(sync_engine_tester):
    """Test if a create event writes diplay names to the node and it's parents.

    :param sync_engine_without_files:
    :return:
    """
    sync_engine_tester.init_with_files([])

    test_path = ['AaA', 'BbB', 'CCc.tXt']
    sync_engine_tester.sync_engine.storage_create(CSP_1.storage_id, test_path,
                                                  {'is_dir': False,
                                                   'size': MBYTE,
                                                   'version_id': 66})

    node = sync_engine_tester.sync_engine.root_node.get_node(normalize_path(test_path))
    result_path = syncfsm.get_storage_path(node, CSP_1.storage_id)
    assert test_path == result_path


def test_cancel_all_tasks(sync_engine_tester):
    """Test that canceling all taks works as expected."""
    test_path = ['hello.txt']
    sync_engine_tester.init_with_files([test_path], equivalent=False)
    sync_engine_tester.task_list.clear()

    sync_engine_tester.sync_engine.cancel_all_tasks()

    expected_tasks = [CancelSyncTask(test_path)]
    sync_engine_tester.assert_expected_tasks(expected_tasks)


@pytest.mark.parametrize('old_state', [SyncEngineState.STATE_SYNC,
                                       SyncEngineState.RUNNING,
                                       SyncEngineState.OFFLINE,
                                       SyncEngineState.STOPPED])
def test_storage_offline(sync_engine_tester, old_state):
    """Ensure syncengine state is switched to offline."""
    sync_engine_tester.sync_engine.state = old_state
    sync_engine_tester.sync_engine.storage_offline()
    assert sync_engine_tester.sync_engine.state is SyncEngineState.OFFLINE


@pytest.mark.parametrize('old_state', [SyncEngineState.STATE_SYNC,
                                       SyncEngineState.RUNNING,
                                       SyncEngineState.OFFLINE,
                                       SyncEngineState.STOPPED])
def test_storage_online(sync_engine_tester, old_state):
    """Ensure syncengine state is switched to online."""
    sync_engine_tester.sync_engine.state = old_state
    with mock.patch('cc.synchronization.syncengine.SyncEngine.init') as mock_init:
        sync_engine_tester.sync_engine.storage_online()
        if old_state is SyncEngineState.OFFLINE:
            mock_init.assert_called()
        else:
            assert not mock_init.called
