"""A virtual filesystem which encrypts data while reading and decrypts while writing."""
import contextlib
import logging
from collections import namedtuple

import jars.fs.filesystem
from jars import VERSION_ID
from jars.streaming_utils import LimitedFileReader

from cc import configuration
import cc.crypto
import cc.crypto2
from cc.settings_sync import KEY_SUBJECT_SHARE, KEY_SUBJECT_USER
from cc.synchronization.syncengine import ItemHasNoStorageException
from cc.synchronization.syncfsm import FILESYSTEM_ID, STORAGE, SHARE_ID, get_storage_path

logger = logging.getLogger(__name__)


class EncryptedVersionTag(namedtuple('EncryptedVersionTag',
                                     ['version_id', 'key_subjects'])):
    """Tag to be wrapped arround version_id to mark them as encrypted."""

    # should not get __dict__ (saves memory)
    __slots__ = ()

    def __new__(cls, version_id, key_subjects):
        """Extra __new__ to ensure props do not get double wrapped."""
        if isinstance(version_id, EncryptedVersionTag):
            # merge values
            if version_id.key_subjects == key_subjects:
                return version_id
            else:
                return super(EncryptedVersionTag, cls).__new__(cls,
                                                               version_id.version_id, key_subjects)
        else:
            return super(EncryptedVersionTag, cls).__new__(cls, version_id, key_subjects)


class _EncryptionEventSinkWrapper:
    """Wraps the encryption around a sink for events."""

    def __init__(self, event_sink, enc_wrapper):
        self.event_sink = event_sink
        self.enc_wrapper = enc_wrapper

    def __getattr__(self, item):
        """If a attribute is not provided by this class, pass it to the wrapped one."""
        return getattr(self.event_sink, item)

    def storage_create(self, storage_id, path, event_props):
        """Create event sink method."""
        event_props = self.enc_wrapper.wrap_props(path, event_props)
        self.event_sink.storage_create(storage_id=storage_id, path=path,
                                       event_props=event_props)

    def storage_move(self, storage_id, source_path, target_path, event_props):
        """Move event sink method."""
        event_props = self.enc_wrapper.wrap_props(source_path, event_props)
        self.event_sink.storage_move(
            storage_id=storage_id, source_path=source_path, target_path=target_path,
            event_props=self.enc_wrapper.wrap_props(target_path, event_props))

    def storage_modify(self, storage_id, path, event_props):
        """Modify event sink method."""
        event_props = self.enc_wrapper.wrap_props(path, event_props)
        self.event_sink.storage_modify(storage_id=storage_id, path=path,
                                       event_props=event_props)


def _has_different_share_id(storage_id, old_props, new_props):
    """Check if the storage file has changed its storage id.

    :param storage_id: the name of the event source
    :param old_props: the dict of the former props
    :param new_props: the dict for the new props

    1. the storage_id will be checked if local
    2. if the version id is different, let the file first be synced by content
    3. check if the share_id is the same as before
    """
    if storage_id == FILESYSTEM_ID:
        return False
    elif old_props.get(STORAGE, {}).get(storage_id, {}).get(VERSION_ID, None) != \
            new_props.get(STORAGE, {}).get(storage_id, {}).get(VERSION_ID, None):
        return False
    elif old_props.get(STORAGE, {}).get(storage_id, {}).get(SHARE_ID, None) != \
            new_props.get(STORAGE, {}).get(storage_id, {}).get(SHARE_ID, None):
        return True
    else:
        return False


class EncryptionWrapper:
    """Mixin for a storage provider it encrypts read data and decrypts written data."""

    # this is a mix-in
    # pylint: disable=no-member
    def __init__(self, event_sink, syncengine, public_key_getter, private_key_getter, *args,
                 **kwargs):
        """Constructor similar to strage provdier.

        :param event_sink the sink of the event for storage_modify etc.
        :param syncengine used to query shared state of items and register on signal slots
        :param get_public_key_fun function which provides keys from key subjects
        """
        wrapped_event_sink = _EncryptionEventSinkWrapper(event_sink, self)
        self._syncengine = syncengine
        self.public_key_getter = public_key_getter
        self.private_key_getter = private_key_getter

        signal = self._syncengine.on_node_props_change.get()
        signal.connect(self.on_shared_state_changed, weak=False)

        super().__init__(*args, event_sink=wrapped_event_sink, **kwargs)

    def on_shared_state_changed(self, sender, old_props, node, storage_id):
        """Triggered by SyncEngine, checks if key subjects needs to be updated.

        If the storage id is different then FILESYSTEM and the version on the other storage has not
        been changed, this function checks if 'share_id' is the same as before. If it is different
        it emits a change event as FILESYSTEM with the updated key_subjects in the
        EncryptedVersionTag. In case the path has children it will recurse and also propagates
        a change for all children.

        **RUNS IN SYNC ENGINE CONTEXT**
        (DO TAKE CARE THIS FUNCTION DOES NOTHING taking TOO LONG (no io)) (its over 9000 here)
        """
        logger.debug('on_node_props_change callback %s %s %s', old_props, node.props, node.path)
        # not interested in filesystem changes
        if _has_different_share_id(storage_id, old_props, node.props):
            # if there is no local version, we download it first anyways (do nothing here)
            try:
                storage_id, share_id, _ = sender.query_shared_state(node.path)
            except ItemHasNoStorageException:
                logger.debug('was not able to get share info from path', exc_info=True)
                return
            key_subjects = get_key_subjects(share_id=share_id,
                                            storage_id=storage_id,
                                            config=self.client_config)
            logger.debug('Key subjects %s for path %s', key_subjects, node.path)
            if key_subjects:
                for child_node in node:
                    props = child_node.props[STORAGE].get(FILESYSTEM_ID)
                    if not props:
                        # if there are no properties on the filesystem, this is uninteresting
                        continue
                    # wrap the version id and trigger a change event
                    props = dict(props)
                    if not props.get(jars.IS_DIR, False):
                        props['version_id'] = EncryptedVersionTag(props['version_id'],
                                                                  key_subjects=key_subjects)
                        logger.debug('Propagating new version id %s to %s', props['version_id'],
                                     child_node.path)
                        fs_path = get_storage_path(child_node, FILESYSTEM_ID)
                        self._syncengine.storage_modify(
                            storage_id=FILESYSTEM_ID, path=fs_path, event_props=props)

    def wrap_props(self, path, props):
        """Wrap the event properties."""
        logger.debug('wrapping event props for %s', path)
        if 'version_id' in props and not props.get(jars.IS_DIR, False):
            if not isinstance(props['version_id'], EncryptedVersionTag):
                try:
                    storage_id, share_id, _ = \
                        self._syncengine.query_shared_state(path).get()
                except ItemHasNoStorageException:
                    # nothing to wrap here
                    logger.info('was not wrapping %s (ItemHasNoStorageException)', path)
                    return props

                key_subjects = get_key_subjects(share_id=share_id,
                                                storage_id=storage_id,
                                                config=self.client_config)

                props['version_id'] = EncryptedVersionTag(
                    version_id=props['version_id'],
                    key_subjects=key_subjects)
                logger.debug('Key subjects %s for path %s', key_subjects, path)
                if key_subjects:
                    props['size'] += cc.crypto2.calc_header_size(props['version_id'].key_subjects)

        return props

    def get_props(self, path):
        """Wrap the filesize as well as the version_id.

        :return: The original property dict, but with updated version_id and size
        """
        props = super().get_props(path)
        return self.wrap_props(path, props)

    def write(self, path, file_obj, original_version_id=None, size=None):
        """Decrypt file_obj while writing to the storage.

        :param path: path to the file
        :param file_obj: the file object, it tries to decrypt it, if it is plaintext it will just
            pass it through
        """
        # unwrap version id
        if original_version_id:
            (original_version_id, _) = original_version_id

        subject_ids = ()

        try:
            wrapped_file_obj = cc.crypto2.DecryptionFileWrapper(
                file_obj, self.private_key_getter)
            subject_ids = tuple(sorted(wrapped_file_obj.subject_ids))
        except cc.crypto2.HeaderError as ex:
            # the object is not encrypted remotely, so return a LimitedFileReader with the
            # already read data
            # pylint:disable=redefined-variable-type
            wrapped_file_obj = LimitedFileReader(file_obj, pre_buffer=ex.read_data)

        if subject_ids and size is not None:
            size += cc.crypto2.calc_header_size(subject_ids)

        new_version_id = super().write(path, wrapped_file_obj, original_version_id, size=size)
        logger.info("File was encrypted with the ids: %s", subject_ids)

        return EncryptedVersionTag(new_version_id, subject_ids)

    def open_read(self, path, expected_version_id=None):
        """Return an EncryptionFileWrapper around the one returned by the wrapped storage.

        That means that the content read from the storage will be encrypted.
        """
        # parameter determining if encrypted, default false
        key_subjects = ()
        # unwrap version id assuming its crypto version id
        if expected_version_id and isinstance(expected_version_id, EncryptedVersionTag):
            (expected_version_id, key_subjects) = expected_version_id
        else:
            logger.warning('Not encrypting "%s" since there is no EncryptedVersionTag', path)

        # getting FLO from assumed superclass of this mixin
        f_in = super().open_read(path=path, expected_version_id=expected_version_id)

        if key_subjects:
            # get the public keys for this operation
            try:
                keys = {subject_id: self.public_key_getter(subject_id)
                        for subject_id in key_subjects}
            except KeyError:
                logger.warning("No key for subjects %s found", key_subjects)
                raise cc.crypto2.NoKeyError

            f_in = cc.crypto2.EncryptionFileWrapper(
                f_in, public_keys=keys)

        # returning potentially wrapped FLO
        return f_in

    # TODO: if move operations are supported (CC-350)
    # def move(self, source, target, expected_source_vid=None, expected_target_vid=None):
    #     """Move wrapper.
    #
    #     This is quite complicated since the key subjects might change with a move operation.
    #     """
    #     key_subjects = ()
    #
    #     if isinstance(expected_target_vid, EncryptedVersionTag):
    #         (original_version_id, key_subjects) = expected_target_vid
    #
    #     if isinstance(expected_target_vid, EncryptedVersionTag):
    #         (original_version_id, key_subjects) = expected_target_vid
    #
    #     return EncryptedVersionTag(
    #         super().move(source, target, expected_source_vid, expected_target_vid), key_subjects)

    def delete(self, path, original_version_id):
        """Delete wrapper.

        Removes the tag before passing to the real storage provider
        """
        if isinstance(original_version_id, EncryptedVersionTag):
            (original_version_id, _) = original_version_id
        super().delete(path, original_version_id)

    def make_dir(self, path):
        """make_dir wrapper.

        There is not much to wrap, a directory is not encrypted
        """
        return EncryptedVersionTag(super().make_dir(path), True)

    def get_tree(self, *args, **kwargs):
        """Get tree wrapper."""
        tree = super().get_tree(*args, **kwargs)
        for node in tree:
            with contextlib.suppress(KeyError):
                self.wrap_props(node.path, node.props)
        return tree


class EncryptingFileSystem(EncryptionWrapper, jars.fs.Filesystem):
    # pylint: disable=too-many-ancestors
    """Encryption file system class which simply places a encryptionwrapper around FileSystem."""

    def create_public_sharing_link(self, path):
        raise NotImplementedError

    def create_open_in_web_link(self, path):
        raise NotImplementedError


def get_key_subjects(storage_id, share_id, config):
    """Return the relevant key subjects.

    - if disabled in general it will return an empty tuple
    - always contains the master key object
    - if there is a share id, will contain the share id subject
    - if not it will be the user subject
    """
    #  pylint: disable=no-member
    # check if it should be encrypted for the specific storage
    storage_type = configuration.helpers.get_storage(config, storage_id)['type']

    # if encryption is disabled return immediately
    if not config.encryption_csp_settings.get(storage_type, False) or\
            not config.encryption_enabled:
        return ()

    logger.debug('Shares with external users:%s', config.shares_with_external_users)

    # Check if share has external users and
    if not config.encrypt_external_shares and \
            (storage_type, share_id) in config.shares_with_external_users:
        return ()

    result = [config.master_key_subject]

    if not share_id:
        result.append(KEY_SUBJECT_USER.format(0, config.user_id, config.organization_id))
    else:
        result.append(KEY_SUBJECT_SHARE.format(0, storage_type, share_id))

    result.sort()
    return tuple(result)
