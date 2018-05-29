"""
Unit tests for tasks
"""
from unittest import mock

import pytest
from hypothesis import strategies as st
from hypothesis import given

from cc import synctask
from tests.synchronization import dummy_link_with_id

from .conftest import CSP_1, FILE_A


def test_add_ack_callback(test_sync_task):
    """Ensure that setting and calling the callback on the synctask works."""
    callback = mock.Mock()
    test_sync_task.set_ack_callback(callback)
    test_sync_task.ack_callback('something')
    print(callback.call_args_list)
    callback.assert_called_once_with('something')


def test_upload_sync_task(mock_link):
    """Test for uploading sync task."""

    upload_task = synctask.UploadSyncTask(path=FILE_A, target_storage_id=CSP_1.storage_id,
                                          source_version_id=12)
    upload_task.link = mock_link

    upload_task_same = synctask.UploadSyncTask(path=FILE_A, target_storage_id=CSP_1.storage_id,
                                               source_version_id=12)
    upload_task_same.link = mock_link

    assert upload_task == upload_task_same
    assert hash(upload_task) == hash(upload_task_same)
    upload_task_same.source_storage_id = '123'
    assert upload_task != upload_task_same
    assert hash(upload_task) != hash(upload_task_same)

# XXX: are these tests still needed? fix them
# @pytest.mark.skip("temp not working")
# def test_download_sync_task():
#     """
#     Test for download task.
#     """
#     download_task_dec_default = DownloadSyncTask(path=FILE_A,
#                                                  storage_id=CSP_1.storage_id)
#     assert not download_task_dec_default.decrypt
#     download_task_dec_enabled = DownloadSyncTask(path=FILE_A,
#                                                  storage_id=CSP_1.storage_id,
#                                                  decrypt=True)
#     assert download_task_dec_enabled.decrypt
#
#     assert download_task_dec_default != download_task_dec_enabled
#     assert hash(download_task_dec_default) != hash(download_task_dec_enabled)
#
#     download_task_dec_enabled.decrypt = False
#     assert not download_task_dec_enabled.decrypt
#
#     assert download_task_dec_default == download_task_dec_enabled
#     assert hash(download_task_dec_default) == hash(download_task_dec_enabled)
#
#     file_sync_task_test(sync_task=download_task_dec_default)
#
#
# @pytest.mark.skip("temp not working")
# def test_delete_sync_task():
#     """
#     Test for deletion task.
#     """
#     delete_task = DeleteSyncTask(FILE_A, CSP_1.storage_id)
#     file_sync_task_test(delete_task)
#
#
# @pytest.mark.skip("temp not working")
# def test_move_sync_task():
#     """
#     Test for move task.
#     """
#     move_task = MoveSyncTask(path=FILE_A, storage_id=CSP_1.storage_id, new_path=DIR_B)
#     assert move_task.new_path == DIR_B
#
#     other_move_task = MoveSyncTask(path=FILE_A,
#                                    storage_id=CSP_1.storage_id,
#                                    new_path=DIR_B)
#     assert move_task == other_move_task
#     assert hash(other_move_task) == hash(move_task)
#
#     move_task.new_path = FILE_A
#     assert move_task.new_path == FILE_A
#
#     assert move_task != other_move_task
#     assert hash(other_move_task) != hash(move_task)
#
#     assert move_task
#
#     file_sync_task_test(sync_task=move_task)
#
#
# @pytest.mark.skip("temp not working")
# def test_create_dir_task():
#     """
#     Test move creating directory task.
#     """
#     create_dir_task = CreateDirSyncTask(path=FILE_A, storage_id=CSP_1.storage_id)
#     assert create_dir_task.path == FILE_A
#     assert create_dir_task.storage_id == CSP_1.storage_id
#
#     file_sync_task_test(create_dir_task)
#
#
# @pytest.mark.skip("temp not working")
# def test_delete_dir_task():
#     """
#     Test for deleting directory task.
#     """
#     delete_dir_task = DeleteSyncTask(path=FILE_A, storage_id=CSP_1.storage_id)
#     assert delete_dir_task.path == FILE_A
#     assert delete_dir_task.storage_id == CSP_1.storage_id
#
#     file_sync_task_test(delete_dir_task)
#
#
# @pytest.mark.skip("temp not working")
# def test_cancel_task():
#     """
#     Test for cancel task.
#     """
#     cancel_task = CancelSyncTask(path=FILE_A, storage_id=CSP_1.storage_id)
#     assert cancel_task.path == FILE_A
#     assert cancel_task.storage_id == CSP_1.storage_id
#
#     file_sync_task_test(cancel_task)
#
#
# @pytest.mark.skip("temp not working")
# def test_fetch_file_tree_task():
#     """
#     Test for file tree fetching task.
#     """
#     file_tree_task = FetchFileTreeTask(storage=CSP_1.storage_id)
#     assert file_tree_task.storage_id == CSP_1.storage_id
#     assert file_tree_task.file_tree is None
#
#     # test setter
#     root_node = Node(name='wurzel')
#     file_tree_task.storage_id = CSP_2_ID
#     file_tree_task.file_tree = root_node
#     assert file_tree_task.storage_id == CSP_2_ID
#     assert file_tree_task.file_tree == root_node
#
#     # test equals and hash
#     file_tree_task = FetchFileTreeTask(storage=CSP_1.storage_id)
#     other_task = FetchFileTreeTask(storage=CSP_1.storage_id)
#
#     assert file_tree_task == other_task
#     assert hash(file_tree_task) == hash(other_task)
#
#     file_tree_task.storage_id = CSP_2_ID
#     file_tree_task.file_tree = Node('wurzel_1')
#     other_task.file_tree = Node('wurzel_2')
#     assert file_tree_task != other_task
#     assert hash(file_tree_task) != hash(other_task)
#
#
# @pytest.mark.skip("temp not working")
# def file_sync_task_test(sync_task):
#     """
#     Tests getter and setter of sync task.
#     :param sync_task:
#     """
#     sync_task.path = FILE_A
#     sync_task.storage = CSP_1.storage_id
#
#     assert sync_task.path == FILE_A
#     assert sync_task.storage == CSP_1.storage_id
#
#     sync_task.path = DIR_B
#     assert sync_task.path == DIR_B
#
#     sync_task.storage = CSP_2_ID
#     assert sync_task.storage == CSP_2_ID


@pytest.mark.parametrize("path, expected_mimetype", [
    (['sub_path', 'test.txt'], 'text/plain'),
    (['sub_path', 'test.mp3'], 'audio/mpeg'),
    (['thing.exe'], synctask.DEFAULT_MIME_TYPE),
    (['danger.zip'], 'application/zip'),
    (['*.docx'], synctask.DEFAULT_MIME_TYPE),
    (['danger.gzip'], synctask.DEFAULT_MIME_TYPE),
    ([12], synctask.DEFAULT_MIME_TYPE),

])
def test_mime_type(path, expected_mimetype):
    """Test calling mime_type on SyncTask for a few different paths

    .. Note: the parametrizations are more to document current behaviours than anything else.
    """
    task = synctask.SyncTask(path)
    assert task.mime_type == expected_mimetype


@pytest.mark.parametrize('path', [
    (['test']),
    # the following path should not be passed to a CreateDirSyncTask under normal circumstances,
    # but if it does the mime_type will still be our custom folder type.
    (['something.txt']),
    (['a', 'very', 'long', 'path'])
])
def test_mime_type_for_folders(path):
    """When the synctask is a CreateDirSyncTask, the mime_type must be our custom folder type
    """
    task = synctask.CreateDirSyncTask(path,
                                      source_storage_id=None,
                                      target_storage_id=None)
    assert task.mime_type == synctask.MIMETYPE_CC_FOLDER


@given(link_id=st.text(), path=st.lists(st.text()))
def test_operates_on_returns_tuple(link_id, path):
    """Ensure that operates_on returns a tuple containing link_id and path."""
    download = synctask.DownloadSyncTask(path, None, None)
    download.link = dummy_link_with_id(link_id)
    assert isinstance(download.operates_on(), tuple)


@given(link_id=st.text(), path=st.lists(st.text()))
def test_operates_only_differentiates_by_path(link_id, path):
    """Ensure that operates_on returns a task-independent hash for a given link_id and path."""
    download = synctask.DownloadSyncTask(path, None, None)
    download.link = dummy_link_with_id(link_id)

    upload = synctask.UploadSyncTask(path, None, None, None)
    upload.link = dummy_link_with_id(link_id)

    assert upload.operates_on() == download.operates_on()
