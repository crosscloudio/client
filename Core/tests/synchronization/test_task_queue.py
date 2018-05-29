"""Various tests for TaskQueue"""
from unittest import mock
import time

import pytest

import cc
from cc.synchronization.models import TaskQueue
from . import dummy_link_with_id


def test_put_and_get(task_queue, sample_create_dir_task):
    """Test putting one task on the queue"""
    sample_task = sample_create_dir_task
    task_queue.put_task(sample_task)
    assert sample_create_dir_task in task_queue.pending.queue
    assert len(task_queue.running) == 0
    assert len(task_queue.cancel) == 0

    task = task_queue.get_task()
    assert task == sample_task
    assert sample_create_dir_task not in task_queue.pending.queue
    assert task_queue.pending.qsize() == 0
    assert len(task_queue.running) == 1
    assert len(task_queue.cancel) == 0


def test_queue_statistics_synctask_count(sample_create_dir_task, task_queue):
    """Ensure that 'sync_task_count' returns the sum of all running and available tasks."""
    task_queue.put_task(sample_create_dir_task)
    task_queue.running.add(sample_create_dir_task)
    assert task_queue.statistics['sync_task_count'] == 2


def test_put_cancel(abc_sync_tasks, sample_create_dir_task):
    """When CancelSyncTask is issued, all tasks should be canceled."""
    ack_tasks = []
    queue = TaskQueue()
    abc_dummy_link = abc_sync_tasks[0].link

    # catch the calls to cancel
    sample_create_dir_task.cancel = mock.Mock()

    # set one running task
    queue.running.add(sample_create_dir_task)

    # put all other tasks on the queue and mock cancel.
    for task in abc_sync_tasks:
        task.set_ack_callback(ack_tasks.append)
        task.cancel = mock.MagicMock()
        queue.put_task(task)

    # cancel all tasks for the path a/b/c
    cancel_task = cc.synctask.CancelSyncTask(path=['a', 'b', 'c'])
    cancel_task.set_ack_callback(ack_tasks.append)
    cancel_task.link = abc_dummy_link
    queue.put_task(cancel_task)

    # has cancel arrived?
    assert cancel_task in queue.cancel.values()

    # has cancel been called
    for task in abc_sync_tasks:
        assert task.cancel.called

    assert sample_create_dir_task.cancel.called


def test_get_put_task(abc_sync_tasks):
    """Check get_task from TaskQueue."""
    ack_task = []
    queue = TaskQueue()

    # test preperations for signals
    put_callback_mock = mock.Mock()
    acked_callback_mock = mock.Mock()
    queue.task_putted.connect(put_callback_mock, weak=False)
    queue.task_acked.connect(acked_callback_mock, weak=False)

    # put all tasks in the queue
    for task in abc_sync_tasks:
        task.set_ack_callback(ack_task.append)
        queue.put_task(task)

        # check if signal was sent
        put_callback_mock.assert_any_call(task)

    # once worker asks for task, it is in the running list
    task = queue.get_task()
    assert task.state == cc.synctask.SyncTask.UNEXECUTED
    assert task in queue.running

    # after the worker has ack'ed the task, it is no longer in the running list
    queue.ack_task(task)
    assert task not in queue.running

    # check if signal was sent
    acked_callback_mock.assert_called_with(task)


def test_cancel_all_ack(abc_sync_tasks):
    """Ensure that after a cancel task has been added, the other task behave as expected."""
    queue = TaskQueue()
    abc_dummy_link = abc_sync_tasks[0].link

    # Where all task will report to
    ack_sink = []

    # list of task currently being worked on by workers.
    tasks_in_workers = []

    # setup mocked calls and put them on the queue.
    for task in abc_sync_tasks:
        task.cancel = mock.MagicMock()
        task.set_ack_callback(ack_sink.append)
        queue.put_task(task)

    # check the first task
    task = queue.get_task()
    tasks_in_workers.append(task)
    assert task.state == cc.synctask.SyncTask.UNEXECUTED
    assert task in queue.running

    # pass in the cancel
    cancel_task = cc.synctask.CancelSyncTask(path=['a', 'b', 'c'])
    cancel_task.link = abc_dummy_link
    cancel_task.set_ack_callback(ack_sink.append)

    queue.put_task(cancel_task)

    # now all sync tasks should be set to cancel
    for task in abc_sync_tasks:
        assert task.cancel.called

    # get the rest of the tasks as well, so we can ack them all
    for _ in range(len(abc_sync_tasks) - 1):
        tasks_in_workers.append(queue.get_task())

    # check the queues are correct.
    assert queue.pending.qsize() == 0
    assert len(queue.running) == len(abc_sync_tasks)
    assert set(tasks_in_workers) == set(abc_sync_tasks)

    # Once workers are finished they ack
    for task in tasks_in_workers:
        queue.ack_task(task)

    # now all tasks + cancel tasks should be in the ack sync
    expected = set(abc_sync_tasks)
    expected.add(cancel_task)
    assert set(expected) == set(ack_sink)
    assert len(expected) == len(set(ack_sink))

    # And the cancel should be successful
    assert cancel_task.state == cc.synctask.SyncTask.SUCCESSFUL


def test_cancel_running_task():
    """Ensure that canceling all tasks works as expected"""
    ack_tasks = []

    sync_tasks = [cc.synctask.DownloadSyncTask(path=['a', 'b', 'c'],
                                               source_storage_id=None,
                                               source_version_id=None),
                  cc.synctask.UploadSyncTask(path=['a', 'b', 'c'],
                                             target_storage_id=None,
                                             source_version_id=None)]

    queue = TaskQueue()
    for task in sync_tasks:
        task.link = dummy_link_with_id("local::remote")
        task.set_ack_callback(ack_tasks.append)
        queue.put_task(task)

    task = queue.get_task()
    assert task.state == cc.synctask.SyncTask.UNEXECUTED

    assert task in queue.running
    task.cancel = mock.MagicMock()

    # cancel the running synctask
    cancel_task = cc.synctask.CancelSyncTask(task.path)
    cancel_task.link = dummy_link_with_id("local::remote")
    cancel_task.set_ack_callback(ack_tasks.append)
    queue.put_task(cancel_task)

    assert task.cancel.called

    queue.ack_task(task)
    assert task not in queue.running

    assert task in ack_tasks
    assert cancel_task not in ack_tasks

    # get the next task -> this has to be set to cancelled
    task2 = queue.get_task()
    if task2.cancelled:
        task2.state = cc.synctask.SyncTask.CANCELLED
    else:
        assert False
    queue.ack_task(task2)
    assert task2 not in queue.running

    # this ack also acknowledges the cancel task
    assert task in ack_tasks
    assert task2 in ack_tasks
    assert cancel_task in ack_tasks


def test_cancel_ack_running_task():
    """Check that the cancel task is not acked if there are still running tasks """
    ack_tasks = []

    sync_tasks = [cc.synctask.DownloadSyncTask(path=['a', 'b', 'c'],
                                               source_storage_id=None,
                                               source_version_id=None),
                  cc.synctask.UploadSyncTask(path=['a', 'b', 'c'],
                                             target_storage_id=None,
                                             source_version_id=None)]

    queue = TaskQueue()
    for task in sync_tasks:
        task.link = dummy_link_with_id("local::remote")
        task.set_ack_callback(ack_tasks.append)
        queue.put_task(task)

    task = queue.get_task()
    assert task.state == cc.synctask.SyncTask.UNEXECUTED

    assert task in queue.running
    task.cancel = mock.MagicMock()

    task2 = queue.get_task()
    task2.cancel = mock.MagicMock()

    # cancel the running synctask
    cancel_task = cc.synctask.CancelSyncTask(task.path)
    cancel_task.link = dummy_link_with_id("local::remote")
    cancel_task.set_ack_callback(ack_tasks.append)
    queue.put_task(cancel_task)

    assert task.cancel.called
    assert task2.cancel.called

    queue.ack_task(task)
    assert task not in queue.running

    assert task in ack_tasks

    # this is the bug
    assert cancel_task not in ack_tasks


def test_queue_add():
    """Tests the improved path queue"""
    queue = cc.synchronization.models.HashPathQueue()
    path = 'test.txt'
    link_id = 'local::remote'

    download = cc.synctask.DownloadSyncTask(path, None, None)
    download.link = dummy_link_with_id(link_id)

    queue.put(download)
    assert len(queue.queue) == 1
    assert len(queue.path_queue) == 1

    # Add another task with the same path to the queue.
    upload = cc.synctask.UploadSyncTask(path, None, None, None)
    upload.link = dummy_link_with_id(link_id)

    queue.put(upload)
    assert len(queue.queue) == 2
    assert len(queue.path_queue) == 1

    # Add another task with the same path to the queue.
    compare = cc.synctask.CompareSyncTask(path, None)
    compare.link = dummy_link_with_id(link_id)

    queue.put(compare)
    assert len(queue.queue) == 3
    assert len(queue.path_queue) == 1

    # Ensure that we get them in the right order.
    assert queue.get() == download
    assert queue.get() == upload
    assert queue.get() == compare

    # The queue should be empty after 'getting' all tasks.
    assert len(queue.queue) == 0
    assert len(queue.path_queue) == 0


def test_queue_cancel_performance():
    """Performance Tests regarding the cancel all problems"""
    ack_tasks = []

    queue = TaskQueue()
    count = 1000
    start = time.time()
    for ind in range(count):
        name = '{}'.format(ind)
        task = cc.synctask.DownloadSyncTask(path=[name] * 10,
                                            source_storage_id=None,
                                            source_version_id=None)
        task.link = dummy_link_with_id("local::remote")
        task.set_ack_callback(ack_tasks.append)
        queue.put_task(task)
    print(time.time() - start)
    assert queue.statistics['sync_task_count'] == count
    assert len(ack_tasks) == 0

    start = time.time()
    for ind in range(count):
        name = '{}'.format(ind)
        cancel_task = cc.synctask.CancelSyncTask(path=[name] * 10)
        cancel_task.link = dummy_link_with_id("local::remote")
        cancel_task.set_ack_callback(ack_tasks.append)
        queue.put_task(cancel_task)
        assert len(queue.cancel) == ind + 1
    print(time.time() - start)

    assert queue.statistics['sync_task_count'] == count
    assert len(queue.cancel) == count
    assert len(ack_tasks) == 0

    start = time.time()
    while queue.statistics['sync_task_count'] > 0:
        task = queue.get_task()
        queue.ack_task(task)
    print(time.time() - start)

    assert queue.statistics['sync_task_count'] == 0
    assert len(queue.cancel) == 0
    assert len(ack_tasks) == 2 * count


@pytest.mark.skip(reason="Make this work when working on the shell extension server!")
def test_path_has_tasks_empty():
    """Ensures that path_has_tasks returns 'True' iff a given path_hash has associated tasks in
    either the running or pending queue."""

    queue = TaskQueue()
    path = []
    link_id = "local::remote"
    path_hash = cc.synctask.path_hash(link_id, path)

    assert queue.path_has_tasks(path_hash=path_hash, is_dir=True) is False
    assert queue.path_has_tasks(path_hash=path_hash, is_dir=False) is False


@pytest.mark.skip(reason="Make this work when working on the shell extension server!")
def test_path_has_tasks_with_one_pending_task(sample_create_dir_task):
    """Ensures that path_has_tasks returns 'True' iff a given path_hash has associated tasks in
    either the running or pending queue."""

    queue = TaskQueue()
    queue.put_task(sample_create_dir_task)
    assert queue.path_has_tasks(path_hash=sample_create_dir_task.operates_on(), is_dir=True)
    assert queue.path_has_tasks(path_hash=sample_create_dir_task.operates_on(), is_dir=False)

    path_hash = cc.synctask.path_hash("local::remote2", sample_create_dir_task.path)
    assert queue.path_has_tasks(path_hash=path_hash, is_dir=True) is False
    assert queue.path_has_tasks(path_hash=path_hash, is_dir=False) is False


@pytest.mark.skip(reason="Make this work when working on the shell extension server!")
def test_path_has_tasks_with_one_running_task(sample_create_dir_task):
    """Ensures that path_has_tasks returns 'True' iff a given path_hash has associated tasks in
    either the running or pending queue."""

    queue = TaskQueue()
    queue.running.add(sample_create_dir_task)
    assert queue.path_has_tasks(path_hash=sample_create_dir_task.operates_on(), is_dir=True)
    assert queue.path_has_tasks(path_hash=sample_create_dir_task.operates_on(), is_dir=False)

    path_hash = cc.synctask.path_hash("local::remote2", sample_create_dir_task.path)
    assert queue.path_has_tasks(path_hash=path_hash, is_dir=True) is False
    assert queue.path_has_tasks(path_hash=path_hash, is_dir=False) is False
