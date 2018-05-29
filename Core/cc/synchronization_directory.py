"""Tools to manage the synchronization directory in crosscloud."""
import os

import logging

import blinker

from cc.configuration.helpers import get_storage, write_config
from cc.configuration.constants import HIDDEN_FILE_PREFIX

logger = logging.getLogger(__name__)


class SynchronizationDirectoryWatcher:
    """This helps crosscloud to recognize changes in the sync directory."""

    def __init__(self, config):
        self.config = config
        self.storage_directory_deleted = blinker.Signal()
        self.storage_directory_renamed = blinker.Signal()

    def migrate_old_config(self):
        """Migrate config from hidden file strategy to inode strategy

        This is done by finding a directory+a hidden file and safe the inode into the
        local_unique_id field. Afterwards it deletes the hidden file to avoid doing this
        procedure again."""
        entry_paths = set()

        logger.debug('Starting migration')

        # first get all, directories which also have a hidden file
        for entry in os.listdir(self.config.sync_root):
            # every entry is potentially an account
            entry_path = os.path.join(self.config.sync_root, entry)
            if not os.path.isdir(entry_path):
                continue
            for sub_entry in os.listdir(entry_path):
                sub_entry_path = os.path.join(entry_path, sub_entry)
                if sub_entry.startswith(HIDDEN_FILE_PREFIX):
                    _, storage_id = sub_entry.split('_', 1)
                    # I hope there is only one
                    get_storage(self.config, storage_id)['local_unique_id'] = \
                        os.stat(entry_path).st_ino

            # try to find as id file here, if it is a directory
            if os.path.isdir(entry_path):
                for sub_entry in os.listdir(entry_path):
                    sub_entry_path = os.path.join(entry_path, sub_entry)
                    if sub_entry.startswith(HIDDEN_FILE_PREFIX):
                        splitted_sub_entry = sub_entry.split('_', 1)
                        if len(splitted_sub_entry) == 2:
                            logger.info('Found hidden id file, going to migrate')
                            _, storage_id = splitted_sub_entry
                            get_storage(self.config, storage_id)['local_unique_id'] = \
                                os.stat(entry_path).st_ino

                            entry_paths.add(sub_entry_path)
                    break

        if entry_paths:
            write_config(self.config)

        for entry_path in entry_paths:
            logger.info('Deleting old marker entry: %s', entry_path)
            os.unlink(entry_path)

    def get_fs_entries(self):
        """Collect the information about the current state of storage provider dirs.

        This function has the friend `get_config_items()` which returns the same format.

        :return: a set with tuples with (display_name, local_unique_id)
        """
        fs_entries = {}
        for entry in os.listdir(self.config.sync_root):
            display_name = entry
            local_unique_id = os.stat(os.path.join(self.config.sync_root, display_name)).st_ino
            fs_entries[local_unique_id] = display_name
        return fs_entries

    def get_config_entries(self):
        """Collect the information about the config of storage provider dirs.

        This function has the friend `get_fs_entries()` which returns the same format.

        :return: a set with tuples with (display_name, local_unique_id)
        """
        config_entries = {}
        for entry in self.config.csps:
            config_entries[entry['local_unique_id']] = entry['display_name']
        return config_entries

    def check(self):
        """Check for changes between the config and the fs reality.

        Items which are in the config, but not found in the same form in the filesystem are either
        deleted or renamed. In case of deletion it fires the signal folder_deleted, in case of a
        rename it fires the signal folder_renamed.
        """
        fs_entries_by_local_unique_id = self.get_fs_entries()
        conf_entries_by_local_unique_id = self.get_config_entries()
        logger.debug('Config entries: %s, Fs entries: %s', fs_entries_by_local_unique_id,
                     conf_entries_by_local_unique_id)

        # check for renamed items, so take the intesected set of
        for local_unique_id in fs_entries_by_local_unique_id.keys() &\
                conf_entries_by_local_unique_id.keys():
            # check if the name is different
            if fs_entries_by_local_unique_id[local_unique_id] != \
                    conf_entries_by_local_unique_id[local_unique_id]:
                new_local_display_name = fs_entries_by_local_unique_id.get(local_unique_id)
                logger.debug('Sending renamed signal for %s:%s', local_unique_id,
                             fs_entries_by_local_unique_id[local_unique_id])
                self.storage_directory_renamed.send(self, new_name=new_local_display_name,
                                                    local_unique_id=local_unique_id)

        # iterate thought all items not existing in the filesystem but in the config
        for deleted_local_unique_id in conf_entries_by_local_unique_id.keys() - \
                fs_entries_by_local_unique_id.keys():
            logger.debug('Sending delete signal for %s', deleted_local_unique_id)
            self.storage_directory_deleted.send(self, local_unique_id=deleted_local_unique_id)
