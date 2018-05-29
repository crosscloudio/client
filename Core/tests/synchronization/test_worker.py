"""Tests that cover the functionality of the cc.synchronization.worker module."""
import collections
import io
import logging
import time

import mock
import pytest
import jars

import cc
from cc.synchronization import syncengine
from cc.synchronization.worker import (SyncTaskCancelledException, Worker,
                                       calculate_waiting_time)

__author__ = 'crosscloud GmbH'

logger = logging.getLogger(__name__)

ONE_MB = 1024 * 1024


def test_worker_run_with_stop_token_in_queue():
    """Ensures that a worker thread will break out of the run loop if it encounters the stop token
    in the queue."""
    task_queue, ack_sink = [cc.synctask.STOP_TOKEN], []
    worker = Worker(task_source=task_queue.pop,
                    task_sink=None,
                    ack_sink=ack_sink.append)
    assert worker.daemon
    worker.run()

    return


@pytest.mark.parametrize('exec_func_side_effect, exec_task_state', [
    # INVALID_OPERATION
    (BaseException('Boom!'), cc.synctask.SyncTask.INVALID_OPERATION),
    (jars.UnavailableError('Boom!', None), cc.synctask.SyncTask.INVALID_OPERATION),
    (jars.InvalidOperationError('Boom!'), cc.synctask.SyncTask.INVALID_OPERATION),
    (FileNotFoundError('Boom!'), cc.synctask.SyncTask.INVALID_OPERATION),
    # INVALID_AUTHENTICATION
    (jars.AuthenticationError('Boom!'), cc.synctask.SyncTask.INVALID_AUTHENTICATION),
    # VERSION_ID_MISMATCH
    (jars.VersionIdNotMatchingError('Boom!'), cc.synctask.SyncTask.VERSION_ID_MISMATCH),
    # CANCELLED
    (SyncTaskCancelledException('Boom!'), cc.synctask.SyncTask.CANCELLED),
    (jars.CancelledException('Boom!'), cc.synctask.SyncTask.CANCELLED),

])
@pytest.mark.parametrize('task', [
    (cc.synctask.CreateDirSyncTask(None, None, None)),
    (cc.synctask.DownloadSyncTask(None, None, None)),
    (cc.synctask.UploadSyncTask(None, None, None)),
    (cc.synctask.DeleteSyncTask(None, None, None)),
    (cc.synctask.FetchFileTreeTask(None, None)),
    (cc.synctask.MoveSyncTask(None, None, None, None, None)),
    (cc.synctask.CompareSyncTask(None, None))
])
def test_worker_run_and_ensure_proper_dispatch(task, exec_func_side_effect, exec_task_state):
    """Ensures that given a certain task object the worker can dispatch the correct
    execution task."""

    # We populate the task queue with a stop token and the task we want to execute.
    task_queue, ack_sink = [cc.synctask.STOP_TOKEN, task], []

    worker = Worker(task_source=task_queue.pop,
                    task_sink=None,
                    ack_sink=ack_sink.append)

    # We replace the expected "execute" function with a mock to ensure it got called later.
    task.execute = mock.Mock()

    # If a side_effect is given we add it to the mock and will check below for the matching
    # 'exec_task_state'.
    if exec_func_side_effect:
        task.execute.side_effect = exec_func_side_effect

    worker.run()

    # Once the worker is running, the task's execute must be called once.
    task.execute.assert_called_once()

    # Ensure our task is marked SUCCESSFUL unless we have given side_effects. In that case
    # we ensure that the task is in 'exec_task_state'.
    if exec_func_side_effect:
        assert task.state == exec_task_state
    else:
        # Finally our task should be marked as SUCCESSFULLY
        assert task.state == cc.synctask.SyncTask.SUCCESSFUL

    # The task must be ack'ed.
    assert task in ack_sink


@pytest.mark.parametrize('task', [
    (cc.synctask.CreateDirSyncTask(None, None, None)),
    (cc.synctask.DownloadSyncTask(None, None, None)),
    (cc.synctask.UploadSyncTask(None, None, None)),
    (cc.synctask.DeleteSyncTask(None, None, None)),
    (cc.synctask.FetchFileTreeTask(None, None)),
    (cc.synctask.MoveSyncTask(None, None, None, None, None)),
    (cc.synctask.CompareSyncTask(None, None))
])
def test_dispatch_with_policy_error(task):
    """Ensure that a policy error triggers a call to the IPC GUI."""
    task_queue, ack_sink = [cc.synctask.STOP_TOKEN, task], []

    worker = Worker(task_source=task_queue.pop,
                    task_sink=None,
                    ack_sink=ack_sink.append)

    # Setup the PolicyError side_effect
    task.execute = mock.Mock()
    task.execute.side_effect = cc.synchronization.exceptions.PolicyError("Boom!")

    ipc_mock = mock.Mock()
    with mock.patch('cc.ipc_gui.displayNotification', new=ipc_mock):
        worker.dispatch(task)

    ipc_mock.assert_called_once()

    # INVALID_OPERATION prevents the task of being executed in a loop
    assert task.state == cc.synctask.SyncTask.INVALID_OPERATION
    assert task in ack_sink


def test_dispatch_marks_unknown_or_invalid_tasks_as_invalid():
    """Ensure that if the dispatch of a worker is called with an invalid or unknown sync tasks
    as invalid. In this case if we pass a base class (CopySyncTask) directly and create a dummy
    class that is not handled in the dispatch function."""

    ack_sink = []
    worker = Worker(ack_sink=ack_sink.append, task_source=None, task_sink=None)

    # We shouldn't be able to dispatch a class that is used as a base class.
    base_class_task = cc.synctask.CopySyncTask(None, None, None, None, None, None, None)
    logger.info("Dispatching 'CopySyncTask'...")
    worker.dispatch(base_class_task)
    logger.info("Not dead now, good sign!")
    assert ack_sink[0].state == cc.synctask.SyncTask.INVALID_OPERATION

    # Unknown/Unhandled Task
    class UnknownTask(cc.synctask.CopySyncTask):
        """Dummy tasks that represents an unhandled task type."""
        pass

    unknown_task = UnknownTask(None, None, None, None, None, None, None)
    logger.info("Dispatching 'Unknown Task'...")
    worker.dispatch(unknown_task)
    logger.info("Not dead now, good sign!")
    assert ack_sink[0].state == cc.synctask.SyncTask.INVALID_OPERATION


def test_dispatch_cancel_sync_task():
    """Ensure that dispatching a task with 'cancel' set gets ack'ed with the CANCELLED state."""
    ack_sink = []
    worker = Worker(ack_sink=ack_sink.append, task_source=None, task_sink=None)

    task = cc.synctask.UploadSyncTask(None, None, None, None)
    task.cancel()

    worker.dispatch(task)

    assert ack_sink[0].state == cc.synctask.SyncTask.CANCELLED


def test_dispatch_retry_count():
    """Ensure that the retry count increases at the start of the dispatch."""
    ack_sink = []
    worker = Worker(ack_sink=ack_sink.append, task_source=None, task_sink=None)
    worker.exec_upload = mock.MagicMock()

    task = cc.synctask.UploadSyncTask(None, None, None, None)
    worker.dispatch(task)

    assert task.tries == 1


def test_calculate_waiting_time():
    """Ensure that the waiting time is calculated properly if we have to back-off."""
    max_val = 30
    delta = 10
    old_value = 0
    for num in range(100):
        value = calculate_waiting_time(num, max_delay=max_val, delta=delta)
        assert old_value < value + delta
        assert value < delta + max_val
        old_value = value


def test_worker_run_timed_execution():
    """Tests if a task is only executed if the time is right. """
    ack_queue = []
    tasks_queue = collections.deque()
    worker = Worker(task_source=tasks_queue.popleft,
                    ack_sink=ack_queue.append,
                    task_sink=tasks_queue.append,
                    wait_delay=0.1)

    task = cc.synctask.MoveSyncTask(None, None, None, None, None)
    task.execute_after = 100
    task.execute = mock.Mock()

    tasks_queue.clear()
    tasks_queue.extend([task, cc.synctask.STOP_TOKEN])

    start_time = time.time()

    # its 50 o clock, but the task should be executed after 100 o clock
    with mock.patch("time.time", new=mock.MagicMock(return_value=50)):
        worker.run()

    assert not task.execute.called
    assert [task] == list(tasks_queue)
    # we use 0.09 instead of 0.1 since kvm virtual machines are not that accurate
    # when it comes to timing
    assert (time.time() - start_time) >= 0.09

    tasks_queue.append(cc.synctask.STOP_TOKEN)
    # its 101 o clock, and the task should be executed
    with mock.patch("time.time", new=mock.MagicMock(return_value=101)):
        worker.run()
    assert task.execute.called
    assert [task] == ack_queue


def test_worker_dispatch_currently_not_possible():
    """Tests if, e.g. upload raises a :class:`jars.CurrentlyNotPossibleError` """
    ack_queue = []
    tasks_queue = collections.deque()
    worker = Worker(task_source=tasks_queue.popleft,
                    ack_sink=ack_queue.append,
                    task_sink=tasks_queue.append,
                    max_retries=10)

    task = cc.synctask.MoveSyncTask(None, None, None, None, None)
    task.execute = mock.MagicMock(side_effect=jars.CurrentlyNotPossibleError(storage_id='st_id'))

    with mock.patch("time.time", new=mock.MagicMock(return_value=0)):
        with mock.patch("cc.synchronization.worker.calculate_waiting_time",
                        new=mock.MagicMock(return_value=10)):
            worker.dispatch(task)
            assert task.execute_after == 10
            assert task not in ack_queue
            assert task in tasks_queue
            tasks_queue.clear()

    # Test if it is ack'ed as 'Currently Not Possible' after the retry count is reached.
    task.tries = 10
    worker.dispatch(task)
    assert task.state == cc.synctask.SyncTask.CURRENTLY_NOT_POSSIBLE
    assert task in ack_queue
    assert task not in tasks_queue


def test_worker_dispatch_upload(link_with_storages, monkeypatch, config):
    """Ensure that an UploadSyncTask is properly dispatched and called by the worker."""

    # Create an UploadSyncTask
    path = ['a', 'b.xyz']
    task = cc.synctask.UploadSyncTask(path=path,
                                      target_storage_id='remote',
                                      source_version_id=123,
                                      original_version_id=321)

    # This is currently done inside the SynchronizationLink.task_sink during runtime.
    task.link = link_with_storages
    task.link.client_config = config

    task_queue, ack_sink = [cc.synctask.STOP_TOKEN, task], []

    worker = Worker(task_source=task_queue.pop,
                    ack_sink=ack_sink.append,
                    task_sink=None,
                    max_retries=1)

    local = task.link.storages[syncengine.FILESYSTEM_ID]
    local.get_props = mock.Mock(return_value={'size': 123})

    remote = task.link.storages['remote']

    monkeypatch.setattr('cc.synchronization.models.ControlFileWrapper.tell', lambda x: 123)
    worker.dispatch(task)

    local.open_read.assert_called_with(path=path, expected_version_id=123)
    remote.write.assert_called_with(path=path,
                                    file_obj=mock.ANY,
                                    original_version_id=321,
                                    size=123)
    assert task.target_version_id == remote.write()

    # This also fails in Sprint-M.
    assert task.bytes_transferred == 123


def test_worker_dispatch_download(link_with_storages):
    """Ensure that an DownloadSyncTask is properly dispatched and called by the worker."""
    task = cc.synctask.DownloadSyncTask(path=[],
                                        source_storage_id='remote',
                                        source_version_id=123,
                                        original_version_id=321)
    # This is currently done inside the SynchronizationLink.task_sink during runtime.
    task.link = link_with_storages

    task_queue, ack_sink = [cc.synctask.STOP_TOKEN, task], []
    worker = Worker(task_source=task_queue.pop,
                    ack_sink=ack_sink.append,
                    task_sink=None,
                    max_retries=1)

    worker.dispatch(task)

    remote = task.link.storages['remote']
    remote.open_read.assert_called_with(path=[], expected_version_id=123)

    local = task.link.storages[syncengine.FILESYSTEM_ID]
    local.write.assert_called_with(path=[], file_obj=mock.ANY,
                                   original_version_id=321)

    assert task.target_version_id == local.write()


def test_worker_dispatch_delete(link_with_storages):
    """Ensure that an DeleteSyncTask is properly dispatched and called by the worker."""
    task = cc.synctask.DeleteSyncTask(path=[],
                                      target_storage_id='remote',
                                      original_version_id=123)
    # This is currently done inside the SynchronizationLink.task_sink during runtime.
    task.link = link_with_storages

    task_queue, ack_sink = [cc.synctask.STOP_TOKEN, task], []
    worker = Worker(task_source=task_queue.pop,
                    ack_sink=ack_sink.append,
                    task_sink=None,
                    max_retries=1)

    worker.dispatch(task)

    remote = task.link.storages['remote']
    remote.delete.assert_called_with(path=[],
                                     original_version_id=123)


def test_worker_dispatch_move(link_with_storages):
    """Ensure that an MoveSyncTask is properly dispatched and called by the worker."""
    task = cc.synctask.MoveSyncTask(path=[],
                                    source_path=[],
                                    target_path=['asd'],
                                    source_storage_id="remote",
                                    source_version_id=321)
    # This is currently done inside the SynchronizationLink.task_sink during runtime.
    task.link = link_with_storages

    task_queue, ack_sink = [cc.synctask.STOP_TOKEN, task], []
    worker = Worker(task_source=task_queue.pop,
                    ack_sink=ack_sink.append,
                    task_sink=None,
                    max_retries=1)

    worker.dispatch(task)

    remote = task.link.storages['remote']
    remote.move.assert_called_with(source=[], target=['asd'], expected_source_vid=321)


def test_worker_dispatch_create_dir(link_with_storages):
    """Ensure that an CreateDirSyncTask is properly dispatched and called by the worker."""
    task = cc.synctask.CreateDirSyncTask(
        path=['asd'],
        target_storage_id="remote",
        source_storage_id=cc.synchronization.syncengine.FILESYSTEM_ID)
    # This is currently done inside the SynchronizationLink.task_sink during runtime.
    task.link = link_with_storages

    task_queue, ack_sink = [cc.synctask.STOP_TOKEN, task], []
    worker = Worker(task_source=task_queue.pop,
                    ack_sink=ack_sink.append,
                    task_sink=None,
                    max_retries=1)

    worker.dispatch(task)

    remote = task.link.storages['remote']
    remote.make_dir.assert_called_with(path=['asd'])


def test_worker_dispatch_fetch_file_tree(link_with_storages):
    """Ensure that an FetchFileTreeTask is properly dispatched and called by the worker."""

    task = cc.synctask.FetchFileTreeTask(storage_id='remote')
    # This is currently done inside the SynchronizationLink.task_sink during runtime.
    task.link = link_with_storages

    task_queue, ack_sink = [cc.synctask.STOP_TOKEN, task], []
    worker = Worker(task_source=task_queue.pop,
                    ack_sink=ack_sink.append,
                    task_sink=None,
                    max_retries=1)

    worker.dispatch(task)

    remote = task.link.storages['remote']
    remote.get_tree.assert_called_with(cached=True)


def test_control_file_cancel():
    """ tests exec_upload """

    sync_task = cc.synctask.SyncTask(path=[])

    f_test = io.StringIO("0" * 200)
    wrapped_f = cc.synchronization.models.ControlFileWrapper(f_test, sync_task)
    assert "0" * 100 == wrapped_f.read(100)

    sync_task.cancel()

    with pytest.raises(cc.synchronization.models.SyncTaskCancelledException):
        wrapped_f.read(100)


def test_control_file_speed():
    """ tests exec_upload """

    def callback(speed):
        """ test callback """
        callback.super_speed = speed

    callback.super_speed = None

    sync_task = cc.synctask.SyncTask(path=[])

    f_test = io.StringIO("0" * 200)
    wrapped_f = cc.synchronization.models.ControlFileWrapper(f_test, sync_task, callback)
    with mock.patch("time.time", new=mock.MagicMock(side_effect=[0, 1])):
        wrapped_f.read(100)

    assert callback.super_speed == 100


@pytest.mark.parametrize("test_inputs,expected", [
    ([io.BytesIO(b'test' * 100), io.BytesIO(b'test' * 100), io.BytesIO(b'test' * 100)],
     [set(range(3))]),
    ([io.BytesIO(b'test' * ONE_MB), io.BytesIO(b'test' * ONE_MB),
      io.BytesIO(b'test' * ONE_MB)], [set(range(3))]),
    ([io.BytesIO(b'test' * ONE_MB), io.BytesIO(b'test1' * ONE_MB)], [{0}, {1}]),
    ([io.BytesIO(b'test' * ONE_MB), io.BytesIO(b'test1' * ONE_MB)], [{0}, {1}]),
    ([io.BytesIO(b'test' * ONE_MB), io.BytesIO(b'test' * ONE_MB),
      io.BytesIO(b'test1' * ONE_MB)], [{0, 1}, {2}]),
    ([io.BytesIO(b'test' * ONE_MB), io.BytesIO(b'test' * ONE_MB), io.BytesIO(b'test1' * ONE_MB),
      io.BytesIO(b'test1' * ONE_MB)], [{0, 1}, {2, 3}])
])
def test_worker_dispatch_compare(test_inputs, expected):
    """Ensure that an CompareSyncTask is properly dispatched and called by the worker."""
    storages = {}
    to_compare = []

    for test_input, num in zip(test_inputs, range(len(test_inputs))):
        to_compare.append(cc.synctask.PathWithStorageAndVersion(storage_id=num,
                                                                path=['A'],
                                                                expected_version_id=None,
                                                                is_dir=False))
        storages[num] = mock.MagicMock()
        storages[num].open_read = mock.MagicMock(return_value=test_input)

    link_mock = mock.MagicMock()
    link_mock.storages = storages

    task = cc.synctask.CompareSyncTask(['a'], to_compare)
    # This is currently done inside the SynchronizationLink.task_sink during runtime.
    task.link = link_mock

    task_queue, ack_sink = [cc.synctask.STOP_TOKEN, task], []
    worker = Worker(task_source=task_queue.pop,
                    ack_sink=ack_sink.append,
                    task_sink=None,
                    max_retries=1)

    worker.dispatch(task)

    print(task.equivalents)
    assert {tuple(l) for l in iter(task.equivalents)} == \
           {tuple(l) for l in expected}
    assert len(task.equivalents) == len(expected)


def test_worker_dispatch_compare_dir():
    """Ensure that an CompareSyncTask is properly dispatched and called by the worker."""
    storages = {}
    to_compare = []

    for num in range(4):
        to_compare.append(cc.synctask.PathWithStorageAndVersion(storage_id=num,
                                                                path=['A'],
                                                                expected_version_id=None,
                                                                is_dir=True))
        storages[num] = mock.MagicMock()

    link_mock = mock.MagicMock()
    link_mock.storages = storages

    task = cc.synctask.CompareSyncTask(['a'], to_compare)
    task.link = link_mock

    task_queue, ack_sink = [cc.synctask.STOP_TOKEN, task], []
    worker = Worker(task_source=task_queue.pop,
                    ack_sink=ack_sink.append,
                    task_sink=None,
                    max_retries=1)

    worker.dispatch(task)

    print(task.equivalents)
    assert len(task.equivalents) == 1
    assert {tuple(l) for l in iter(task.equivalents)} == \
           {tuple(l) for l in [range(4)]}
