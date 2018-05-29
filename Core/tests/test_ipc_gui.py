"""Test the JSONRPC implementation to communicate with the GUI process."""

from time import sleep
import unittest

import pytest
from mock import MagicMock, call, Mock
from jars import StorageMetrics

import cc
from cc import synctask
from cc.ipc_gui import EventBatcher, ipc_gui_exception_decorator, on_task_acked
from cc.synctask import SyncTask


def test_exception_decorator():
    """tests that the exception wrapper works"""
    # assert that usual operation does not throw
    assert decorated_divide(10, 2) == 5

    # calling exception method
    assert decorated_divide(1, 0) is None


@ipc_gui_exception_decorator
def decorated_divide(divisor, divider):
    """example function that throws exception"""
    return divisor / divider


def test_batched_processing():
    """tests the batch processing"""
    period = 1
    mock = MagicMock()
    mock.dummy_method.return_value = None
    batcher = EventBatcher(mock.dummy_method, period)
    batcher.process_event_batched('1')
    batcher.process_event_batched('2')
    batcher.process_event_batched('3')
    batcher.process_event_batched('4')
    batcher.process_event_batched('5')
    assert len(mock.dummy_method.mock_calls) == 0
    sleep(2)
    assert len(mock.dummy_method.mock_calls) == 1
    assert mock.dummy_method.mock_calls[0] == call(['1', '2', '3', '4', '5'])
    assert len(batcher.event_items) == 0
    batcher.process_event_batched('6')
    batcher.process_event_batched('7')
    batcher.process_event_batched('8')
    batcher.process_event_batched('9')
    batcher.process_event_batched('10')
    assert len(mock.dummy_method.mock_calls) == 1
    sleep(2)
    assert len(mock.dummy_method.mock_calls) == 2
    assert mock.dummy_method.mock_calls[1] == call(['6', '7', '8', '9', '10'])
    assert len(batcher.event_items) == 0


def test_batched_processing_single():
    """tests the batch processing single event functionality"""
    period = 1
    mock = MagicMock()
    mock.dummy_method.return_value = None
    batcher = EventBatcher(mock.dummy_method, period, False)
    batcher.process_event_batched('1')
    batcher.process_event_batched('2')
    batcher.process_event_batched('3')
    batcher.process_event_batched('4')
    batcher.process_event_batched('5')
    assert len(mock.dummy_method.mock_calls) == 0
    sleep(2)
    assert len(mock.dummy_method.mock_calls) == 1
    assert mock.dummy_method.mock_calls[0] == call('5')
    assert len(batcher.event_items) == 0
    batcher.process_event_batched('6')
    batcher.process_event_batched('7')
    batcher.process_event_batched('8')
    batcher.process_event_batched('9')
    batcher.process_event_batched('10')
    assert len(mock.dummy_method.mock_calls) == 1
    sleep(2)
    assert len(mock.dummy_method.mock_calls) == 2
    assert mock.dummy_method.mock_calls[1] == call('10')
    assert len(batcher.event_items) == 0


def test_show_notification():
    """tests the functionality of showing notifications"""
    # creating mock ipc object
    rpc_mock = MagicMock()
    cc.ipc_gui.rpc_object = rpc_mock

    title = 'title'
    description = 'description'
    path_to_image = ['path', 'to', 'image.png']
    path_to_action = ['path', 'to', 'action']
    cc.ipc_gui.displayNotification(
        title, description, path_to_image, path_to_action)

    args = {'title': title, 'description': description, 'imagePath': path_to_image,
            'actionPath': path_to_action}

    sleep(3)

    # checking call
    rpc_mock.assert_called_once()
    _, kwargs = rpc_mock.call_args
    assert kwargs['method'] == 'displayNotification'

    # checking arguments
    arguments = kwargs['args'][0][0]
    assert arguments == args


def test_icon_path_creation():
    """tests the creation of icons for synced elements in the gui"""
    icon_path = cc.ipc_gui.create_icon_name(['path', 'to', 'some', 'image.png'],
                                            'dropbox')
    assert icon_path == icon_path == cc.ipc_gui.FILE_TYPE_IMAGE + "_" + \
        cc.ipc_gui.DROPBOX_CSP_ICON + \
        '.svg'

    icon_path = cc.ipc_gui.create_icon_name(['path', 'to', 'some', 'excel.xls'],
                                            'gdrive')

    assert icon_path == icon_path == cc.ipc_gui.FILE_TYPE_XLS + "_" + \
        cc.ipc_gui.GOOGLE_DRIVE_CSP_ICON \
        + '.svg'

    icon_path = cc.ipc_gui.create_icon_name(
        ['path', 'to', 'some', 'word.doc'], 'gdrive')
    assert icon_path == icon_path == cc.ipc_gui.FILE_TYPE_DOC + "_" + \
        cc.ipc_gui.GOOGLE_DRIVE_CSP_ICON \
        + '.svg'

    icon_path = cc.ipc_gui.create_icon_name(['path', 'to', 'some', 'adobe.pdf'],
                                            'onedrive')
    assert icon_path == icon_path == cc.ipc_gui.FILE_TYPE_PDF + "_" + \
        cc.ipc_gui.ONEDRIVE_CSP_ICON + \
        '.svg'

    icon_path = cc.ipc_gui.create_icon_name(['path', 'to', 'some',
                                             'unknown.chricreatesextensions'], 'onedrive')
    assert icon_path == icon_path == cc.ipc_gui.FILE_TYPE_GENERAL + "_" + \
        cc.ipc_gui.ONEDRIVE_CSP_ICON + \
        '.svg'


def download_task(path):
    """Factory for download task."""
    return synctask.DownloadSyncTask(path=path,
                                     source_storage_id=None,
                                     source_version_id=None,
                                     target_path=[elm.upper() for elm in path])


def upload_task(path):
    """Factory for upload task."""
    return synctask.UploadSyncTask(path=path,
                                   target_storage_id=None,
                                   source_version_id=None,
                                   target_path=[elm.upper() for elm in path])


def delete_task(path):
    """Factory for upload task."""
    return synctask.DeleteSyncTask(path=path,
                                   target_storage_id=None,
                                   original_version_id=None,
                                   target_path=[elm.upper() for elm in path])


def create_dir_sync_task(path):
    """Factory for upload tasks."""
    return synctask.CreateDirSyncTask(path=path,
                                      source_storage_id=None,
                                      target_storage_id=None,
                                      source_version_id=None,
                                      target_path=[elm.upper() for elm in path])


@pytest.mark.parametrize('task_factory', [upload_task,
                                          download_task,
                                          delete_task,
                                          create_dir_sync_task],
                         ids=['upload', 'download', 'delete', 'create'])
def test_on_task_acked(mocker, task_factory):
    """Test that various tasks are processed correctly when passed to on_task_acked."""
    path = ['test.path.txt']
    task = task_factory(path)

    mock_item_batcher = mocker.patch('cc.ipc_gui.update_item_batcher')

    task.link = Mock()
    task.state = SyncTask.SUCCESSFUL
    task.link.metrics = StorageMetrics('blaid', 0)
    task.link.metrics.display_name = 'Holalala'
    task.state = SyncTask.SUCCESSFUL

    # time.strftime is used in on_task_acked
    freeze_time = '12:12'
    mocker.patch('cc.ipc_gui.strftime', return_value=freeze_time)

    # create_icon_name requires the csp_id.
    mocker.patch('cc.ipc_gui.create_icon_name', return_value='icon_name')

    # Make the call
    on_task_acked(task)

    expected_item = {'path': ['Holalala'] + [elm.upper() for elm in task.path],
                     'iconName': unittest.mock.ANY,
                     'operationType': task.DISPLAY_NAME,
                     'time': '12:12'}

    mock_item_batcher.process_event_batched.assert_called_once_with(expected_item)


@pytest.mark.parametrize('task_factory', [upload_task,
                                          download_task,
                                          delete_task,
                                          create_dir_sync_task])
@pytest.mark.parametrize('state', [SyncTask.UNEXECUTED,
                                   SyncTask.CURRENTLY_NOT_POSSIBLE,
                                   SyncTask.NOT_AVAILABLE,
                                   SyncTask.INVALID_OPERATION,
                                   SyncTask.INVALID_AUTHENTICATION,
                                   SyncTask.VERSION_ID_MISMATCH,
                                   SyncTask.CANCELLED,
                                   SyncTask.BLOCKED,
                                   SyncTask.ENCRYPTION_ACTIVATION_REQUIRED])
def test_on_task_acked_not_successful(task_factory, state, mocker):
    """Test that various tasks are processed correctly when passed to on_task_acked."""
    path = ['test.path.txt']
    task = task_factory(path)
    task.state = state

    task.link = Mock()
    task.link.metrics = StorageMetrics('blaid', 0)
    task.link.metrics.display_name = 'Holalala'

    mock_item_batcher = mocker.patch('cc.ipc_gui.update_item_batcher')

    # create_icon_name requires the csp_id.
    mocker.patch('cc.ipc_gui.create_icon_name', return_value='icon_name')

    # Make the call
    on_task_acked(task)

    assert not mock_item_batcher.process_event_batched.called


def compare_task(path):
    """Factory for compare tasks."""
    return synctask.CompareSyncTask(path, [])


def fetch_file_tree_task(path):
    """Factory for fetch tree tasks."""
    return synctask.FetchFileTreeTask(path)


def sync_task(path):
    """Factory for sync tasks."""
    return synctask.SyncTask(path)


def move_task(path):
    """Factory for move tasks."""
    return synctask.MoveSyncTask(path,
                                 source_version_id=None,
                                 source_storage_id=None, source_path=None, target_path=None)


@pytest.mark.parametrize('task_factory', [compare_task,
                                          fetch_file_tree_task,
                                          sync_task,
                                          move_task],
                         ids=['upload', 'download', 'delete', 'create'])
def test_ignore_on_task_ack(mocker, task_factory):
    """The Gui should ignore the following tasks:
        * CompareSyncTasks
        * FetchFileTreeTask
        * SyncTask
        * CopySyncTask
        * MoveSyncTask
    """
    path = ['test.path.txt']
    # task = synctask.CancelSyncTask(path)
    task = task_factory(path)

    task.link = Mock()
    task.link.metrics = StorageMetrics('blaid', 0)
    task.link.metrics.display_name = 'Holalala'

    task.display_in_ui = False
    mock_item_batcher = mocker.patch('cc.ipc_gui.update_item_batcher')
    on_task_acked(task)
    assert not mock_item_batcher.process_event_batched.called
