"""Syncengine integration tests for pausing and resuming operations."""
##################
# Helper Methods #
##################
import datetime

from jars import FILESYSTEM_ID

from cc.synctask import DeleteSyncTask, DownloadSyncTask, UploadSyncTask

from .conftest import MBYTE


def _create_fs_move_event(syncengine, file, new_path, storage_id):
    """
    Triggers a move event on the syncengine
    :param se:
    :param file:
    :param new_path:
    :param storage_id:
    :param other_storage:
    :return:
    """

    if storage_id == FILESYSTEM_ID:
        version_id = file.version_id
    else:
        version_id = file.version_id * 2
    fut = syncengine.storage_move(storage_id, source_path=file.path, target_path=new_path,
                                  event_props=dict(modified_date=datetime.datetime.now(),
                                                   is_dir=file.is_dir,
                                                   storage_id=storage_id,
                                                   size=MBYTE,
                                                   version_id=version_id))

    if storage_id == FILESYSTEM_ID:
        expected_sync_tasks = [UploadSyncTask(syncengine.normalize_path(new_path), file.csps[0],
                                              source_version_id=file.version_id),
                               DeleteSyncTask(path=syncengine.normalize_path(file.path),
                                              target_storage_id=file.csps[0],
                                              target_path=file.path,
                                              original_version_id=file.version_id * 2)]
    else:
        expected_sync_tasks = [DownloadSyncTask(syncengine.normalize_path(new_path), file.csps[0],
                                                source_version_id=file.version_id * 2),
                               DeleteSyncTask(syncengine.normalize_path(file.path), FILESYSTEM_ID,
                                              original_version_id=file.version_id)]
    return fut, expected_sync_tasks
