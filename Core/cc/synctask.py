"""A Collection of task which can be issued to the worker in order to handle synchronization."""
import contextlib
import hashlib
import logging
import mimetypes
from collections import namedtuple

from jars.streaming_utils import LimitedFileReader

import cc.synchronization
from cc.mime_type_stream import MimeTypeDetectingFileObject
from cc.synchronization.exceptions import PolicyError

logger = logging.getLogger(__name__)

FILESYSTEM_ID = 'local'
MIMETYPE_CC_FOLDER = 'application/vdn.crosscloud.folder'
DEFAULT_MIME_TYPE = 'application/octet-stream'
STOP_TOKEN = 0xDEADBEEF

__author__ = "crosscloud GmbH"


# pylint: disable=too-many-arguments, redefined-builtin
# pylint: disable=too-many-instance-attributes
# TODO: refactor the synctask states into an enum


class SyncTask(object):
    """SyncTask Base Class"""
    UNEXECUTED = 'unexecuted'
    SUCCESSFUL = 'success'
    CURRENTLY_NOT_POSSIBLE = 'currently_not_possible'
    NOT_AVAILABLE = 'not_available'
    INVALID_OPERATION = 'invalid_operation'
    INVALID_AUTHENTICATION = 'invalid_authentication'
    VERSION_ID_MISMATCH = 'version_id_mismatch'
    CANCELLED = 'cancelled'
    BLOCKED = 'blocked'
    ENCRYPTION_ACTIVATION_REQUIRED = 'encryption_activation_required'

    # DISPLAY_NAME = 'sync'
    """Used when the user is informed about tasks i.e.: ipc_gui"""

    display_in_ui = False

    def __init__(self, path):
        self.state = SyncTask.UNEXECUTED
        self.path = path
        self.cancelled = False
        self.execute_after = 0
        self.tries = 0
        self.ack_callback = None
        self.link = None

    @property
    def mime_type(self):
        """Return the MIME type of the path.

        ..Note: This property is used by :py:class: cc.settings_sync.SyncTaskLogEntry
        """
        file_name = self.path[-1]
        try:
            mime_type, _ = mimetypes.guess_type(file_name)
        except TypeError as exception:
            logger.debug('failed to guess mimetype of %s: %s', file_name, exception)
            mime_type = None

        if mime_type is None:
            mime_type = DEFAULT_MIME_TYPE
        return mime_type

    def operates_on(self):
        """Return a hashable of the complete link identifier and path combination."""
        assert self.link is not None
        return path_hash(self.link.link_id, self.path)

    def __eq__(self, other):
        return isinstance(other, self.__class__) \
               and self.path == other.path

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        repr = [type(self).__name__]
        repr.extend(['{}={}'.format(*item) for item in self.__dict__.items()])
        return '<' + ' '.join(repr) + '>'

    def __hash__(self):
        return hash(tuple(self.path)) ^ \
               hash(self.__class__.__name__) ^\
               hash(self.link.link_id)

    def cancel(self):
        """Mark the task to be cancelled. (non-blocking)"""
        self.cancelled = True

    def set_ack_callback(self, callback):
        """Set the callback which is to be called once the task has completed."""
        self.ack_callback = callback

    def execute(self):
        """Performs the action the task is supposed to do."""
        raise NotImplementedError(
            "Execute not implemented. This should be implemented by the child.")


class CopySyncTask(SyncTask):
    """Copy Task as a base class for Uploads, Downloads and CreateDirs."""

    display_in_ui = True

    def __init__(self, path,
                 target_storage_id,
                 target_version_id,
                 target_path,
                 source_storage_id,
                 source_version_id,
                 source_path,
                 original_version_id=None):
        super().__init__(path)
        self.target_storage_id = target_storage_id
        self.target_version_id = target_version_id

        if target_path is None:
            target_path = path
        self.target_path = target_path

        self.source_storage_id = source_storage_id
        self.source_version_id = source_version_id

        if source_path is None:
            source_path = path
        self.source_path = source_path

        self.original_version_id = original_version_id

        self.bytes_transferred = 0

    def __eq__(self, other):
        return super().__eq__(other) and \
               self.target_storage_id == other.target_storage_id and \
               self.source_storage_id == other.source_storage_id

    def __hash__(self):
        return super().__hash__() ^ \
               hash(self.target_storage_id) ^ \
               hash(self.source_storage_id)

    def execute(self):
        """This is the Baseclass for Up/Download and createDir tasks."""
        super().execute()


class UploadSyncTask(CopySyncTask):
    """Task for uploading file."""
    DISPLAY_NAME = 'Upload'

    def __init__(self, path, target_storage_id,
                 source_version_id, target_path=None, source_path=None,
                 original_version_id=None):
        super().__init__(path=path,
                         target_storage_id=target_storage_id,
                         target_version_id=None,
                         target_path=target_path,
                         source_storage_id=FILESYSTEM_ID,
                         source_version_id=source_version_id,
                         source_path=source_path,
                         original_version_id=original_version_id)

    def check_mime(self, mime_type: str) -> None:
        """Check if the mime type should be blocked"""
        if mime_type in self.link.client_config.blocked_mime_types:
            raise PolicyError(self.source_path)

    def execute(self):
        """Perform the actions necessary to upload a resource."""
        logger.info("Execute 'UploadSyncTask'.")

        extension = self.source_path[-1].rsplit('.', 1)
        if extension and extension[-1].casefold() in self.link.client_config.blocked_extensions:
            raise PolicyError(self.source_path)

        # open the file from the target storage
        file_src = self.link.storages[self.source_storage_id].open_read(
            path=self.source_path,
            expected_version_id=self.source_version_id)

        with contextlib.closing(file_src) as file_src:
            # the wrapper makes it possible to cancel the transfer
            f_control_wrapper = cc.synchronization.models.ControlFileWrapper(file_src, self)

            f_wrapper = MimeTypeDetectingFileObject(f_control_wrapper, self.check_mime)

            size = self.link.storages[self.source_storage_id].get_props(self.target_path)['size']

            self.target_version_id = self.link.storages[self.target_storage_id].write(
                path=self.target_path,
                file_obj=f_wrapper,
                original_version_id=self.original_version_id,
                size=size)

            self.bytes_transferred = f_control_wrapper.tell()

        assert self.target_version_id is not None


class DownloadSyncTask(CopySyncTask):
    """Task for downloading file."""
    DISPLAY_NAME = 'Download'

    def __init__(self, path, source_storage_id,
                 source_version_id, target_path=None, source_path=None,
                 original_version_id=None):
        super().__init__(path=path,
                         target_storage_id=FILESYSTEM_ID,
                         target_version_id=None,
                         target_path=target_path,
                         source_storage_id=source_storage_id,
                         source_version_id=source_version_id,
                         source_path=source_path,
                         original_version_id=original_version_id)

    def execute(self):
        """ will execute an download """
        file_src = self.link.storages[self.source_storage_id].open_read(
            path=self.source_path,
            expected_version_id=self.source_version_id)
        with contextlib.closing(file_src) as file_src:
            f_wrapper = cc.synchronization.models.ControlFileWrapper(file_src, self)
            self.target_version_id = self.link.storages[self.target_storage_id].write(
                path=self.target_path,
                file_obj=f_wrapper,
                original_version_id=self.original_version_id)
            self.bytes_transferred = f_wrapper.tell()


class CreateDirSyncTask(CopySyncTask):
    """Task for creating directory on storage."""
    DISPLAY_NAME = 'Create Directory'
    display_in_ui = True

    def __init__(self, path, target_storage_id, source_storage_id, target_path=None,
                 source_path=None, target_version_id='is_dir', source_version_id='is_dir',
                 original_version_id='is_dir'):
        super().__init__(path=path,
                         target_storage_id=target_storage_id,
                         target_version_id=target_version_id,
                         target_path=target_path,
                         source_storage_id=source_storage_id,
                         source_version_id=source_version_id,
                         source_path=source_path,
                         original_version_id=original_version_id)

    @property
    def mime_type(self):
        """Use a custom mime type for folders because CreateDirSyncTask operate on folders."""
        return MIMETYPE_CC_FOLDER

    def execute(self):
        """Run the necessary create operations on the storage."""
        storage = self.link.storages[self.target_storage_id]
        self.target_version_id = storage.make_dir(path=self.target_path)


class DeleteSyncTask(SyncTask):
    """Task for deleting file on storage."""
    DISPLAY_NAME = 'Delete'
    display_in_ui = True

    def __init__(self, path, target_storage_id, original_version_id, target_path=None):
        super().__init__(path)
        self.target_storage_id = target_storage_id
        if target_path is not None:
            self.target_path = target_path
        else:
            self.target_path = path
        self.original_version_id = original_version_id

    def __hash__(self):
        return super().__hash__() ^ hash(self.target_storage_id)

    def __eq__(self, other):
        return super().__eq__(other) and self.target_storage_id == other.target_storage_id

    def execute(self):
        """ will be called to execute a delete """
        try:
            self.link.storages[self.target_storage_id].delete(
                path=self.target_path,
                original_version_id=self.original_version_id)
        except FileNotFoundError:
            logger.info("File not found! Deletion of %s on %s not possible.",
                        self.path,
                        self.target_storage_id)
            # this is a success because the file does not exist


class MoveSyncTask(SyncTask):
    """To move or rename a file or diretory."""
    # pylint: disable=too-many-instance-attributes
    DISPLAY_NAME = 'Move'

    def __init__(self, path, source_version_id, source_storage_id, source_path,
                 target_path,
                 target_version_id=None):
        super().__init__(path)
        self.target_path = target_path
        self.source_path = source_path
        self.source_storage_id = source_storage_id
        self.source_version_id = source_version_id
        self.target_version_id = target_version_id

    def __hash__(self):
        return super().__hash__() ^ \
               hash(tuple(self.target_path)) ^ \
               hash(self.source_storage_id)

    def __eq__(self, other):
        return super().__eq__(other) and \
               self.target_path == other.target_path and \
               self.source_path == other.source_path and \
               self.source_storage_id == other.source_storage_id

    def execute(self):
        """ will be called to execute a move operation """
        storage = self.link.storages[self.source_storage_id]
        storage.move(source=self.source_path, target=self.target_path,
                     expected_source_vid=self.source_version_id)


class CancelSyncTask(SyncTask):
    """Task for cancelling other task."""

    DISPLAY_NAME = 'Cancel'

    def __init__(self, path):
        super().__init__(path)

    def execute(self):
        """CancelSyncTask cannot be executed.

        It is used as an indicator to run ~:py:meth:`TaskQueue._handle_cancel_sync_task`()`"""
        super().execute()


PathWithStorageAndVersion = namedtuple('PathWithStorageAndVersion',
                                       ['storage_id', 'path', 'expected_version_id',
                                        'is_dir'])


class CompareSyncTask(SyncTask):
    """This task is intended to compare different files on different csps."""

    def __init__(self, path, storage_id_paths):
        super().__init__(path)
        # a list of tuples with the (storage_id, case_path)
        self.storage_id_paths = storage_id_paths
        # iterable of iterable where the inner iterable represent equal files
        self.equivalents = []

    def execute(self):
        """ compare all files by downloading them and md5hash it, then summarizes """
        # pylint: disable=redefined-variable-type

        result = {}

        # all files
        file_storage_id_paths = [sip for sip in self.storage_id_paths if not sip.is_dir]

        # dirs are equivalent anyways
        all_dirs = [sip.storage_id for sip in self.storage_id_paths if sip.is_dir]
        if all_dirs:
            result['dir'] = all_dirs

        # creates a md5 hash objects to all files
        open_hashes = [hashlib.md5() for _ in file_storage_id_paths]

        for sip, hash_ in zip(file_storage_id_paths, open_hashes):
            storage = self.link.storages[sip.storage_id]
            file_in = storage.open_read(path=sip.path, expected_version_id=sip.expected_version_id)

            try:
                file_in = cc.crypto2.DecryptionFileWrapper(
                    file_in, self.link.client_config.get_private_key_pem_by_subject)
            except cc.crypto2.HeaderError as header_error:
                file_in = cc.synchronization.models.ControlFileWrapper(
                    LimitedFileReader(file_in, pre_buffer=header_error.read_data), self)

            while True:
                buf = file_in.read(1024 * 512)
                if not buf:
                    break
                hash_.update(buf)

        for sip, hash_ in zip(self.storage_id_paths, open_hashes):
            result.setdefault(hash_.hexdigest(), []).append(sip.storage_id)

        self.equivalents = result.values()


class FetchFileTreeTask(SyncTask):
    """Task for fetching file tree of given storage."""

    def __init__(self, storage_id, path=None):
        if path is None:
            path = []
        super().__init__(path)
        self.storage_id = storage_id
        self.file_tree = None

    def __hash__(self):
        return super().__hash__() ^ \
               hash(self.storage_id)

    def __eq__(self, other):
        return super().__eq__(other) and \
               self.storage_id == other.storage_id

    def execute(self):
        """Will be called to execute a fetch tree operation """
        storage = self.link.storages[self.storage_id]

        # order is important!
        # noinspection PyBroadException
        try:
            storage.update()
        except BaseException:
            logger.exception('Error updating model for %s', self.storage_id, exc_info=True)

        # getting cached tree and starting events on storage
        self.file_tree = storage.get_tree(cached=True)
        storage.start_events()


def path_hash(link_id, path):
    """Return a hashable of the link identifier and path combination."""
    return tuple([link_id]) + tuple(path)
