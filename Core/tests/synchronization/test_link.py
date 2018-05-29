"""Unit tests for sync links."""
from unittest import mock

import pytest

from cc.synchronization.models import SynchronizationLink


@pytest.mark.skip
def test_create_sync_link_from_config_dictionary(storage_configuration):
    """Setup a link and assert that it is correctly configured."""

    task_queue = mock.Mock()
    link = SynchronizationLink.using(None, storage_configuration, task_queue=task_queue)
    assert link.link_id == "local-dropbox1"

    # Ensure state is configured and the configuration is valid
    assert link.is_properly_configured()

    link2 = SynchronizationLink.using(None, storage_configuration, task_queue=task_queue)
    assert link2.link_id == "local-dropbox1"

    # Ensure state is configured and the configuration is valid
    assert link2.is_properly_configured()
    link2.startup()
    link.startup()
    link.pause()
    link.resume()
    link.shutdown()
    link2.shutdown()


def test_task_sink():
    """when setting up the Link, ensure that the tasksink can be called correctly"""
    engine = mock.Mock()
    task = mock.Mock()
    task_queue = mock.Mock()

    link = SynchronizationLink(local=None, remote=None, actor=None,
                               engine=engine, state=None, task_queue=task_queue,
                               metrics=None, config_dir=None)

    # add a task to the link.queue
    link.task_sink(task)

    # This will only be called once acked.
    engine.ack_task.assert_not_called()

    # But But it must be added to the queue
    task_queue.put_task.assert_called_once_with(task)

    # The callback must be set correctly.
    task.set_ack_callback.assert_called_once_with(engine.ack_task)
