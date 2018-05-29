"""
Base package for syncengine tests
"""
import datetime as dt
# pylint: skip-file
import logging
import sys
from collections import namedtuple
from copy import deepcopy
from unittest.mock import MagicMock
from mock import Mock
import pytest
from bushn import Node
from jars import StorageMetrics, VERSION_ID

from cc.path import normalize_path_element
from cc.synchronization.syncengine import IS_DIR, SE_FSM, SIZE, SyncEngine, normalize_path, \
    SyncEngineState
from cc.synchronization.syncfsm import MODIFIED_DATE, S_SYNCED, S_UPLOADING, STORAGE
from cc.synctask import CreateDirSyncTask, SyncTask, UploadSyncTask, FetchFileTreeTask

__author__ = "Julian Rath"

KBYTE = 1024
MBYTE = KBYTE * KBYTE

EVENT_TYPE_MOVED = 'moved'
EVENT_TYPE_DELETED = 'deleted'
EVENT_TYPE_CREATED = 'created'
EVENT_TYPE_MODIFIED = 'modified'

DIR_A = ['A']
FILE_A = DIR_A + ['test.txt']
DIR_B = ['B']


class TestStorageProvider:
    def __init__(self, id, display_name):
        self.storage_id = id
        self.display_name = display_name

    @property
    def name(self):
        return normalize_path_element(self.display_name)


CSP_1_ID = 'csp1'
CSP_1_DISPLAY_NAME = 'Csp_1_Display_Name'
CSP_1 = TestStorageProvider(id=CSP_1_ID, display_name=CSP_1_DISPLAY_NAME)
FILESYSTEM_ID = 'local'


@pytest.fixture
def storage_metrics():
    """Mock a basic storage provider.
    """
    storage_metrics = StorageMetrics(storage_id=CSP_1.storage_id,
                                     free_space=10000 * MBYTE,
                                     total_space=10000 * MBYTE,
                                     display_name=CSP_1_DISPLAY_NAME)
    return storage_metrics


@pytest.fixture
def sync_engine(storage_metrics):
    """Return sync engine instance"""
    tasks = []
    return SyncEngine(storage_metrics=storage_metrics, task_sink=tasks.append)


def ack_all_tasks(tasks, acker, state=SyncTask.SUCCESSFUL,
                  secure_hash_fun=lambda x: x * 2):
    """Pass all tasks to the acker

    - Set the state of each task to `state` A
    - Apply the `secure_hash_fun` to each version_id
    - Pass the task to the acker.

    """

    fut = None

    while tasks:
        task = tasks.pop()
        task.state = state
        if hasattr(task, 'source_version_id'):
            if task.source_version_id == IS_DIR:
                task.target_version_id = task.source_version_id
            else:
                task.target_version_id = secure_hash_fun(task.source_version_id)
        fut = acker(task)

    fut.get()


def get_sub_paths(path):
    """Generate a list of sub sub paths required to reach the path

    Example
    -------
    >>> get_sub_paths(['one', 'two', 'three'])
    [['one'], ['one', 'two'], ['one', 'two', 'three']]
    """
    sub_paths = []
    current_path = []
    for path_elm in path:
        current_path.append(path_elm)
        sub_paths.append(list(current_path))
    return sub_paths


TestFile = namedtuple('TestFile',
                      ['path', 'is_dir', 'csps', 'version_id'])


@pytest.fixture
def storage_model_with_files():
    """ Creates simple storage model for testing.
    Tree:
    child_1
        child_1_1
            child_1_1_1
        child_1_2
    child_2
        child_2_1
    """
    storage_model = Node(name=None)

    def create_props(size, is_dir):
        if is_dir:
            version_id = IS_DIR
        else:
            version_id = 1
        return {MODIFIED_DATE: dt.datetime.now(),
                SIZE: size,
                IS_DIR: is_dir,
                VERSION_ID: version_id}

    child_1 = storage_model.add_child(name='child_1', props=create_props(0, True))
    child_2 = storage_model.add_child(name='child_2', props=create_props(0, True))
    child_1_1 = child_1.add_child(name='child_1_1', props=create_props(MBYTE, False))
    child_1.add_child(name='child_1_2', props=create_props(MBYTE, False))
    child_2.add_child(name='child_2_1', props=create_props(MBYTE, False))
    child_1_1.add_child(name='child_1_1_1', props=create_props(MBYTE, False))

    return storage_model


@pytest.fixture
def csp_dir_model(storage_model_with_files):
    """
    """
    return deepcopy(storage_model_with_files)


@pytest.fixture(params=[
    [TestFile(path=[CSP_1.name, 'test.txt'], version_id=1123, is_dir=False, csps=[])],
    [TestFile(path=[CSP_1.name, 'A', 'rename.txt'],
              version_id=1123, is_dir=False, csps=[])],
    [TestFile(path=[CSP_1.name, 'A', 'B', 'rm.txt'],
              version_id=1123, is_dir=False, csps=[])],
    [TestFile(path=[CSP_1.name, 'A'], version_id='is_dir', is_dir=True, csps=[])],
    [TestFile(path=[CSP_1.name, 'A', 'B'], version_id='is_dir', is_dir=True, csps=[])],
    [TestFile(path=[CSP_1.name, 'A', 'rm.txt'], version_id=1123, is_dir=False, csps=[])],
    [TestFile(path=[CSP_1.name, 'B', 'rm.txt'], version_id=1123, is_dir=False, csps=[])]])
def sync_engine_with_files(request, storage_metrics):
    """
    creates a situation where file A/test_a.txt and B are in local
    file storage and on csp 1. Every future task should be executed on
    csp 1.
    """

    csps = storage_metrics
    tasklist = []

    actor = SyncEngine.start(csps=csps, task_sink=tasklist.append)
    actor._actor.initialized = True
    sync_engine = actor.proxy()

    sync_engine.storage_create(normalize_path_element(CSP_1_DISPLAY_NAME),
                               [CSP_1_DISPLAY_NAME],
                               dict(is_dir=True,
                                    modified_date=dt.datetime.now(),
                                    size=0,
                                    version_id='is_dir'
                                    )).get()

    tasklist.clear()

    test_files = deepcopy(request.param)

    expected_task_list = []
    future = None
    # creates folder structure an creates expected tasks
    for test_file in test_files:

        current_path = []
        for path_elm in test_file.path[0:-1]:

            # assemble path while iterating it
            current_path.append(path_elm)
            # Create parent directory Event
            if len(current_path) > 1:
                sync_engine.storage_create(FILESYSTEM_ID,
                                           current_path.copy(),
                                           dict(is_dir=True,
                                                modified_date=dt.datetime.now(),
                                                storage_id=FILESYSTEM_ID,
                                                size=0,
                                                version_id='is_dir'
                                                )).get()
                # Add Expected SyncTask
                expected_task_list.append(
                    CreateDirSyncTask(path=normalize_path(current_path.copy()),
                                      target_storage_id=csps[0].storage_id,
                                      source_storage_id=FILESYSTEM_ID))
        # create file
        future = sync_engine.storage_create(FILESYSTEM_ID, normalize_path(test_file.path),
                                            dict(modified_date=dt.datetime.now(),
                                                 is_dir=test_file.is_dir,
                                                 storage_id=FILESYSTEM_ID,
                                                 size=MBYTE,
                                                 version_id=test_file.version_id))

        # sync task depends on type of item
        if test_file.is_dir:
            expected_task_list.append(
                CreateDirSyncTask(path=normalize_path(test_file.path),
                                  target_storage_id=csps[0].storage_id,
                                  source_storage_id=FILESYSTEM_ID))
        else:
            expected_task_list.append(
                UploadSyncTask(path=normalize_path(test_file.path),
                               source_version_id=test_file.version_id,
                               target_storage_id=csps[0].storage_id))

    future.get()
    # check state of engine for each sub path
    # TODO:  assert sp folder does not have fsm
    for test_file in test_files:
        # sp folder does not have an fsm
        sub_paths = get_sub_paths(test_file.path)
        for sub_path in sub_paths[1:]:
            props = sync_engine.query(sub_path).get()
            assert props[SE_FSM].current == S_UPLOADING
    # assert if all expected tasks are in the tasklist

    assert set(expected_task_list) == set(tasklist)

    ack_all_tasks(tasklist, sync_engine.ack_task)
    # XXX: does the same thing as above. refactor?
    # # check state of engine for path
    # for test_file in test_files:
    #     sub_paths = get_sub_paths(test_file.path)
    #     for sub_path in sub_paths:
    #         props = sync_engine.query(sub_path).get()
    #         assert props[SE_FSM].current == S_UPLOADING

    csp_id = csps[0].storage_id
    for test_file in test_files:
        current_path = []
        for pathelm in test_file.path[:-1]:
            # assemble path while iterating it
            current_path.append(pathelm)
            # Create Directory Event
            sync_engine.storage_create(storage_id=csp_id,
                                       path=current_path,
                                       event_props=dict(
                                           modified_date=dt.datetime.now(),
                                           is_dir=True,
                                           storage_id=csp_id,
                                           version_id='is_dir',
                                           size=0)).get()
        if test_file.version_id == 'is_dir':
            vid = 'is_dir'
        else:
            vid = test_file.version_id * 2
        sync_engine.storage_create(storage_id=csp_id,
                                   path=test_file.path,
                                   event_props=dict(
                                       modified_date=dt.datetime.now(),
                                       is_dir=test_file.is_dir,
                                       storage_id=csp_id,
                                       version_id=vid,  # very secure hashing
                                       size=MBYTE)).get()

        # add the csp to the csp list
        test_file.csps.append(csps[0].storage_id)

    # check state of engine for each path
    for test_file in test_files:
        sub_paths = get_sub_paths(test_file.path)
        # sub_paths.reverse()
        for sub_path in sub_paths[1:]:
            props = sync_engine.query(sub_path).get()
            assert props[SE_FSM].current == S_SYNCED  # \
            # , \
            # 'path ' + str(sub_path) + ' not in sync state'
            assert MODIFIED_DATE in props[STORAGE][FILESYSTEM_ID]
            assert MODIFIED_DATE in props[STORAGE][csp_id]

    assert len(tasklist) == 0

    return_type = namedtuple('StorageEngineWithFiles',
                             ['test_files', 'sync_engine', 'csps', 'task_list'])

    yield return_type(test_files=test_files,
                      csps=csps,
                      task_list=tasklist,
                      sync_engine=sync_engine)

    sync_engine.stop()


@pytest.fixture(
    params=[[TestFile(path=[CSP_1.name, 'test.txt'], version_id=1123, is_dir=False,
                      csps=[])],

            [TestFile(path=[CSP_1.name, 'A', 'rm.txt'],
                      version_id=1123, is_dir=False, csps=[])],

            [TestFile(path=[CSP_1.name, 'A', 'B', 'rm.txt'],
                      version_id=1123, is_dir=False, csps=[])],

            [TestFile(path=[CSP_1.name, 'A'],
                      version_id='is_dir', is_dir=True, csps=[])],

            [TestFile(path=[CSP_1.name, 'A', 'B'],
                      version_id='is_dir', is_dir=True, csps=[])],

            [TestFile(path=[CSP_1.name, 'A', 'rm.txt'],
                      version_id=1123, is_dir=False, csps=[]),

             TestFile(path=[CSP_1.name, 'B', 'rm.txt'],
                      version_id=1123, is_dir=False, csps=[])]])
def sync_engine_without_files(mocker, request):
    mocker.patch('cc.config.write_hidden_file')
    csps = [StorageMetrics(storage_id=CSP_1.storage_id,
                           free_space=100 * MBYTE,
                           display_name=CSP_1.display_name)]

    tasklist = []

    actor = SyncEngine.start(csps=csps, task_sink=tasklist.append)
    sync_engine = actor.proxy()
    actor._actor.initialized = True

    test_files = request.param

    return_type = namedtuple('StorageEngineWithoutFiles',
                             ['test_files', 'sync_engine', 'csps', 'task_list'])
    # XXX: is this necessary?
    # sync_engine.root_node.get().add_child(name=CSP_1.name,
    #                                       props=dict(is_dir=True,
    #                                                  size=0,
    #                                                  version_id='is_dir'))

    yield return_type(test_files=test_files,
                      sync_engine=sync_engine,
                      csps=csps,
                      task_list=tasklist)

    sync_engine.stop()


@pytest.fixture
def mock_link():
    link = Mock()
    link.link_id = 'mock_link_id'
    return link


@pytest.fixture()
def sync_engine_without_params(request):
    '''
    Inits test without parametrisation
    '''
    # set free space, so everything is synced to csp 1
    csps = [MagicMock(spec=['free_space', 'storage_id'],
                      free_space=100 * MBYTE,
                      storage_id=CSP_1.storage_id),
            MagicMock(spec=['free_space', 'storage_id'],
                      free_space=10 * MBYTE,
                      storage_id=CSP_2_ID)]
    tasklist = []

    actor = SyncEngine.start(csps=csps, task_sink=tasklist)
    sync_engine = actor.proxy()

    # shutdown sync engine after test
    request.addfinalizer(sync_engine.stop)

    return_type = namedtuple('StorageEngineWithoutFiles',
                             ['sync_engine', 'csps', 'task_list'])

    return return_type(sync_engine=sync_engine,
                       csps=csps,
                       task_list=tasklist)


class SyncEngineTester:
    def __init__(self):
        self.task_list = []
        self.storage_metrics = StorageMetrics(CSP_1.storage_id, 100 * MBYTE)
        self.sync_engine = SyncEngine(self.storage_metrics, self.task_sink)
        self.link = Mock()
        self.link.link_id = 'mock_link_id'

    def task_sink(self, task):
        task.link = self.link
        self.task_list.append(task)

    def assert_expected_tasks(self, expected_tasks):
        """Assert that the tasks are in the task list regardless of the order."""
        for task in expected_tasks:
            task.link = self.link
        task_list_dict = {t: t for t in self.task_list}

        # use a set here on the left side to get better formatted diffs
        print(self.task_list)
        print(expected_tasks)
        assert set(task_list_dict.keys()) == set(expected_tasks)

        # asserting that is no enough!, now all the attributes will be asserted as well
        for expected_task in expected_tasks:
            task_from_list = task_list_dict.pop(expected_task)
            print(task_from_list.__dict__)
            print(expected_task.__dict__)
            assert task_from_list.__dict__ == expected_task.__dict__

    def ack_fetch_tree_task(self, storage_id, model, metrics=None):
        if metrics is None:
            metrics = StorageMetrics(storage_id=CSP_1.storage_id, free_space=10, total_space=100)
        for task in self.task_list:
            if isinstance(task, FetchFileTreeTask):
                if storage_id == task.storage_id:
                    task.file_tree = model
                    model.props['metrics'] = metrics
                    task.state = SyncTask.SUCCESSFUL
                    self.sync_engine.ack_task(task)
                    self.task_list.remove(task)
                    break
        else:
            raise AssertionError('No task to ack to')

    def init_with_files(self, files, equivalent=True, file_size=MBYTE):
        """Init sync engine with a set of files

        :param files: a list of paths(lists) to populate it with
        """
        tree = Node(name=None)
        for file in files:
            tree.get_node_safe(file).props.update({VERSION_ID: 1,
                                                   SIZE: file_size})

        for node in tree:
            if node.parent is not None and VERSION_ID not in node.props:
                # all nodes without a version id are auto generated by get_node_safe and are dirs
                # (implicitly created directories)
                node.props[IS_DIR] = True
                node.props[VERSION_ID] = IS_DIR
            else:
                node.props[IS_DIR] = False

        self.sync_engine.merge_storage_to_sync_model(tree, FILESYSTEM_ID)
        self.sync_engine.merge_storage_to_sync_model(tree, CSP_1.storage_id)

        if equivalent:
            for node in tree:
                if node.parent is None:
                    continue

                self.sync_engine.root_node.get_node(node.path).props['equivalents'] = \
                    {'new': {FILESYSTEM_ID: node.props[VERSION_ID],
                             CSP_1.storage_id: node.props[VERSION_ID]}}

        self.sync_engine._sync_state()
        self.sync_engine.state = SyncEngineState.RUNNING
        return tree

    def ack_task(self, task, state=SyncTask.SUCCESSFUL):
        """Acks a task back to the sync engine"""
        self.task_list.remove(task)
        logging.debug('acking task:%s', task)

        self.sync_engine.ack_task(task)

    def ack_all_tasks(self, state=SyncTask.SUCCESSFUL,
                      secure_hash_fun=lambda x: x * 2):
        """Pass all tasks to the acker

        - Set the state of each task to `state` A
        - Apply the `secure_hash_fun` to each version_id
        - Pass the task to the acker.
        """
        # work with a copy of the task list so tasks which are newly created are not touched
        for task in list(self.task_list):
            self.task_list.remove(task)
            logging.debug('acking task:%s', task)
            task.state = state
            if hasattr(task, 'source_version_id'):
                if task.source_version_id == IS_DIR:
                    task.target_version_id = task.source_version_id
                else:
                    task.target_version_id = secure_hash_fun(task.source_version_id)
            self.sync_engine.ack_task(task)


@pytest.fixture
def sync_engine_tester():
    return SyncEngineTester()


@pytest.fixture
def test_sync_task():
    """Dummy synctask."""
    return SyncTask(path=[])
