"""Tests covering the functionality of cc.sychronization.bademeister."""
import io
import logging
import pytest
import mock
import cc

from cc.synchronization.bademeister import Bademeister
from cc.synchronization.worker import Worker
from cc.synchronization.models import TaskQueue

from tests.synchronization import dummy_link_with_id

logger = logging.getLogger(__name__)


@mock.patch('cc.synchronization.bademeister.Bademeister.prepare_workers',
            return_value=[mock.Mock(spec=Worker) for _ in range(5)])
def test_start_stop(mock_worker_list):
    """Test the start stop function of the Bademeister"""
    assert len(mock_worker_list()) == 5

    bademeister = Bademeister(queue=cc.synchronization.models.TaskQueue())

    # mock start and stop of each worker
    for worker in bademeister.workers:
        worker.start = mock.Mock()
        worker.stop = mock.Mock()

    bademeister.start()

    assert len(bademeister.workers) == 5

    # have all the workers been started?
    for worker in bademeister.workers:
        assert worker.start.called

    bademeister.stop()
    assert len(bademeister.workers) == 0

    # have all the workers been stoped?
    for worker in bademeister.workers:
        assert worker.stop.called


@pytest.mark.skip(reason="shell extension does not know the link")
def test_step_path_has_tasks():
    """ checks if the has_tasks function is working """
    ack_tasks = []

    sync_tasks = [cc.synctask.DownloadSyncTask(path=['a', 'b', 'c'],
                                               source_storage_id=None,
                                               source_version_id=None),
                  cc.synctask.UploadSyncTask(path=['a', 'b'],
                                             target_storage_id=None,
                                             source_version_id=None)]

    task_queue = TaskQueue()
    for task in sync_tasks:
        task.link = dummy_link_with_id("local::remote")
        task.set_ack_callback(ack_tasks.append)
        task_queue.put_task(task)

    # this puts one task on the execution set
    task_queue.get_task()

    # elements in the queue
    assert task_queue.path_has_tasks(['a', 'b'], False)
    assert task_queue.path_has_tasks(['a', 'b'], True)

    # elements in the working set
    assert not task_queue.path_has_tasks(['a', 'x'], False)
    assert task_queue.path_has_tasks(['a', 'b', 'c'], False)
    assert task_queue.path_has_tasks(['a', 'b', 'c'], True)

    assert task_queue.path_has_tasks(['a'], True)
    assert not task_queue.path_has_tasks(['b'], True)


def test_extension_policy_wrapper():
    """Tests the filename check of the policy wrapper"""
    # pylint: disable=unused-variable
    policies = [{'name': '123',
                 'type': 'fileextension',
                 'criteria': 'zip',
                 'is_enabled': True,
                 'createdAt': 'bla',
                 'updatedAt': 'bla'}]

    f_test = io.StringIO("0" * 200)
    path1 = ['a', 'b', 'c.txt']
    path2 = ['a', 'b', 'c.zip']

    task1 = cc.synctask.UploadSyncTask(path1, None, None)
    wrapper1 = cc.synchronization.models.PolicyWrapper(f_test, task1, policies)

    with pytest.raises(cc.synchronization.exceptions.PolicyError):
        task2 = cc.synctask.UploadSyncTask(path2, None, None)
        wrapper2 = cc.synchronization.models.PolicyWrapper(f_test, task2, policies)

    # Disabled Policy
    policies[0]['is_enabled'] = False

    task1 = cc.synctask.UploadSyncTask(path1, None, None)
    wrapper1 = cc.synchronization.models.PolicyWrapper(f_test, task1, policies)

    task2 = cc.synctask.UploadSyncTask(path2, None, None)
    wrapper2 = cc.synchronization.models.PolicyWrapper(f_test, task2, policies)
