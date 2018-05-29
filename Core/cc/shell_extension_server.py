""" For the communication with the native shell extension of the os.
"""
import logging
import os
import queue
import sys
import threading
import webbrowser

import bourne_rpc
import bourne_rpc.transport
import pyperclip
from jars.fs.filesystem import fs_to_cc_path

from cc.configuration import constants
import cc.ipc_gui
from cc.synchronization.syncengine import normalize_path
from cc.synchronization.syncfsm import FILESYSTEM_ID, STORAGE
from cc.synctask import SyncTask, path_hash

# rpc transports
if sys.platform == 'win32':
    from cc import winapi

    # Time to wait between win32 explorer file change notification events
    CHANGE_NOTIFY_PUMP_INTERVAL = 3

PYKKA_CALL_TIMEOUT = 0.5

ACTION_BROWSER_OPEN_PREFIX = 'browser_open_'
ACTION_CREATE_LINK_PREFIX = 'create_link_'
ACTION_ADD_TO_PREFIX = 'addTo_'
ACTION_REMOVE_FROM_PREFIX = 'removeFrom_'
ACTION_REMOVE_ALL = 'RemoveAll'
ACTION_ADD_TO_ALL = 'addToAll'

# status for items -> these strings are returned in status calls
ITEM_STATUS_SYNCING = 'Syncing'
ITEM_STATUS_SYNCED = 'Synced'
ITEM_STATUS_ERROR = 'Error'
ITEM_STATUS_IGNORE = 'Ignore'

# application id for shell extension server
IPC_APPLICATION_ID = 'crosscloud.shellextension'

logger = logging.getLogger(__name__)


class ShellExtensionInterface:
    """Class providing the interface for shell extension."""

    def __init__(self, sync_graph, config):
        self.config = config

        self.sync_graph = sync_graph

        # queue for status updates
        self.task_status_update_queue = queue.Queue()

        # initialising callbacks in step
        self.initialize_callbacks()

        if sys.platform == constants.WINDOWS_PLATFORM_CODE:
            self.change_notify_thread = threading.Thread(target=self.change_notify_pump,
                                                         daemon=True)
            self.change_notify_thread.start()
            self.stop_event = threading.Event()

    def stop(self):
        """
        On Windows, this stops the change_notify_pump thread.
        On other OS, this does nothing.
        """
        if sys.platform == constants.WINDOWS_PLATFORM_CODE:
            self.stop_event.set()

            self.change_notify_thread.join()

    # pylint: disable=no-self-use,unused-argument
    def get_sync_directory(self):
        """ :return the current configured sync directory """
        # pylint: disable=no-self-use
        return self.config.sync_root

    def get_path_status(self, fs_path):
        """Return whether a path is syncing or not."""
        # convert string to internal path
        logger.debug('Trying to get status for: %s', fs_path)
        cc_path = fs_to_cc_path(fs_path, self.config.sync_root)
        cc_path_normalized = normalize_path(fs_to_cc_path(fs_path, self.config.sync_root))
        display_name = cc_path[0]

        from cc.configuration.helpers import get_storage_by_displayname
        storage_config = get_storage_by_displayname(self.config, display_name)
        if not storage_config:
            logger.info("Encountered path with no link.")
            return ITEM_STATUS_IGNORE
        link_id = 'local::{}'.format(storage_config.get('id', 'unknown'))
        logger.debug("Searching for link named '%s'", link_id)

        link = self.sync_graph.links.get(link_id, None)
        # if link is None path doesn't belong to a synclink -> doesn't need syncing -> ignore
        if link:
            logger.debug('Link found.')
            # checking if directory
            is_dir = os.path.isdir(fs_path)
            hashed_path = path_hash(link_id=link.link_id, path=cc_path_normalized[1:])
            # returning status based on current sync status
            tasks = self.sync_graph.bademeister.queue.path_has_tasks(hashed_path, is_dir)
            if tasks:
                logger.debug('Item %s syncing.', fs_path)
                return ITEM_STATUS_SYNCING
            else:
                logger.debug('Item %s synced.', fs_path)
                return ITEM_STATUS_SYNCED
        else:
            logger.debug('Item %s sync error.', fs_path)
            return ITEM_STATUS_IGNORE

    def get_context_menu(self, selected_paths):
        """ returns a context menu for the selected path

        The menu contains two main menus:
            - Sharing
            - Displaying data (e.g. in browser)

        :param selected_paths: the paths selected in the shell
        """
        logger.debug('getting context menu for: %s', selected_paths)

        # result will be a list of dicts, each presenting a menu item
        result = []

        # only show context menu if only one item is selected
        if len(selected_paths) > 1:
            return result
        # convert all selected paths to cc format
        selected_path = normalize_path(fs_to_cc_path(selected_paths[0],
                                                     self.config.sync_root))

        # if path is one of the storage folders -> no context menu
        if len(selected_path) < 2:
            return result

        # first element of path identifies the storage (=storage folder)
        path_root = selected_path[:1]

        link = self.sync_graph.get_synclink_by_displayname(display_name=path_root[0])
        if not link:
            return result
        # get all properties for the cc paths
        props = link.sync_engine.query(path_root).get(PYKKA_CALL_TIMEOUT)

        # getting storage ids, if none except file system -> no context menu
        storage_ids = props.get(STORAGE, {}).keys() - {FILESYSTEM_ID}
        if not storage_ids:
            return result

        # storage id of storage the path is on
        storage_id, = storage_ids
        storage = link.remote

        # getting items for sharing
        result.extend(create_sharing_menu_items(storage_id=storage_id, storage=storage))

        # getting items for displaying data
        result.extend(create_displaying_menu_items(storage_id=storage_id,
                                                   storage=storage))

        return result

    def get_status_updates(self):
        """
        endpoint for the extension to get status updates on items. Status changes of
        items (e.g. synced, error)
        :return: a list of status updates for a client (e.g. {'/a/file.txt': 'SYNCED'})
        """
        logger.debug('Requesting all task updates.')
        # returning all available updates
        return self.get_all_task_updates()

    def get_all_task_updates(self, max_items=100):
        """
        retrieves all tasks from the update queue up to a maximum number of elements
        :param max_items: the maximum number of items to get
        :return: a list of items from the quene of maximum size max_items
        """
        # result list
        items = []
        # iterating till max number
        for read_items in range(0, max_items):
            try:
                # breaking if maximum reached
                if read_items == max_items:
                    break
                # getting item off queue and adding to results
                items.append(self.task_status_update_queue.get_nowait())
            except queue.Empty:
                break
        return items

    def report_item_syncing(self, task):
        """Callback method that reports an item syncing."""
        if not isinstance(task, SyncTask):
            logger.info("Received STOP_TOKEN. Skip report handling.")
            return

        if not task.display_in_ui:
            logger.debug('Not handling task: %s', task.__class__.__name__)
            return
        # notifying shell extension based on platform
        path = self.get_absolute_task_path(task)
        logger.debug('item syncing for path: %s', path)
        self.add_update_to_queue(path=path, status=ITEM_STATUS_SYNCING)

    def report_item_synced(self, task):
        """Callback method that reports an item synced."""
        if not isinstance(task, SyncTask):
            logger.info("Received STOP_TOKEN. Skip report handling.")
            return

        if not task.display_in_ui:
            logger.debug('Not handling task: %s', task.__class__.__name__)
            return

        if task.state != SyncTask.SUCCESSFUL:
            logger.info("Task was not successfully executed. Ignoring update.")
            return
        # notifying shell extension based on platform
        path = self.get_absolute_task_path(task)
        logger.debug('item synced for path: %s', path)
        self.add_update_to_queue(path=path, status=ITEM_STATUS_SYNCED)

    def report_item_error(self, task):
        """Callback method that reports the error status of an item."""
        if not isinstance(task, SyncTask):
            logger.info("Received STOP_TOKEN. Skip report handling.")
            return

        if not task.display_in_ui:
            logger.debug('Not handling task: %s', task.__class__.__name__)
            return

        path = self.get_absolute_task_path(task)
        logger.debug('item sync error for path: %s', path)
        # notifying shell extension based on platform
        self.add_update_to_queue(path=path, status=ITEM_STATUS_ERROR)

    def add_update_to_queue(self, path, status):
        """
        adds a status update item to the queue to be obtained by clients
        :param path: the path to the item to add an update about
        :param status: the status reported in this update
        """
        # path and status need to be there
        if path is None or status is None:
            return

        # creating path string
        path_string = os.path.join(self.config.sync_root, os.path.sep.join(path))

        # putting path string into queue
        self.task_status_update_queue.put({'path': path_string, 'status': status})

    def change_notify_pump(self):
        """
        Runs in a background thread and notifies the Windows filesystem of
        changes to files/folders so it can update icons etc.
        """
        logger.debug("Starting up win32 change_notify thread.")

        while True:
            # Remove duplicate paths
            changed_paths = set()
            items = self.get_all_task_updates()
            for item in items:
                changed_paths.add(item['path'])

            logger.debug("Notifying win32 explorer about changes: %s", changed_paths)

            for path in changed_paths:
                # TODO This is ugly af.
                # We strip & split the path after we joined & extended it in
                # add_update_to_queue. We do this because MacOS expects
                # full paths, while Windows needs to be notified about every
                # part in a path.
                # Do not do this. Seriously.
                path = os.path.relpath(path, self.config.sync_root)
                path = os.path.normpath(path).split(os.path.sep)

                the_path = []
                for element in path:
                    the_path.append(element)
                    pathname = os.path.join(self.config.sync_root, os.path.sep.join(the_path))
                    logger.debug('winapi call "%s"', pathname)
                    winapi.SHChangeNotify(winapi.SHCNE_UPDATEITEM, winapi.SHCNF_PATH |
                                          winapi.SHCNF_FLUSHNOWAIT, pathname, None)

            self.stop_event.wait(CHANGE_NOTIFY_PUMP_INTERVAL)

            if self.stop_event.is_set():
                logger.debug("Stopping change_notify_pump!")
                break

    # pylint: disable=too-many-branches, too-many-statements
    def perform_action(self, action_id, selected_paths):
        """ this is supposed to be called if a user clicks on a menu item"""
        logger.debug('perform action %s %s', action_id, str(selected_paths))

        # only actions on one element are supported (should not happen at all btw)
        if len(selected_paths) > 1:
            return
        # getting cc format selected path
        selected_path = fs_to_cc_path(selected_paths[0], self.config.sync_root)

        # create link action
        if action_id.startswith(ACTION_CREATE_LINK_PREFIX):
            self._action_create_link(action_id, selected_path)

        # display item in browser action
        elif action_id.startswith(ACTION_BROWSER_OPEN_PREFIX):
            self._action_browser_open(action_id, selected_path)

    def _action_browser_open(self, action_id, selected_path):
        """ opens a browser window with the path gotten from the csp x via its method
        create_web_link
        :param action_id the action id of the defined action
        :param selected_path the paths to be executed on"""
        # getting storage id
        storage_id = action_id[len(ACTION_BROWSER_OPEN_PREFIX):]

        link = self.sync_graph.get_synclink_by_displayname(display_name=selected_path[0])

        # the path needs to be normalized to the csps representation
        norm_path = link.sync_engine.query_storage_path(selected_path).get(
            timeout=PYKKA_CALL_TIMEOUT)[storage_id]

        # getting storage object
        storage = link.remote
        web_link = storage.create_open_in_web_link(path=norm_path)

        # opening link in browser
        webbrowser.open(web_link)

    def _action_create_link(self, action_id, selected_path):
        """ creates a sharable link using a csp's `create_public_sharing_link` method and
        copies it to the clipboard
        :param action_id the action id of the defined action
        :param selected_path the paths to be executed on"""
        storage_id = action_id[len(ACTION_CREATE_LINK_PREFIX):]

        link = self.sync_graph.get_synclink_by_displayname(display_name=selected_path[0])
        # the path needs to be normalized to the csps representation
        norm_path = link.sync_engine.query_storage_path(selected_path).get(
            timeout=PYKKA_CALL_TIMEOUT)[storage_id]

        # getting storage object
        storage = link.remote

        # getting sharing link
        sharing_link = storage.create_public_sharing_link(path=norm_path)
        if sharing_link is not None:
            # copy to clipboard and shoot notification
            logger.debug('copying %s to clipboard', sharing_link)
            pyperclip.copy(sharing_link)

            # sending notification
            cc.ipc_gui.displayNotification(title='Sharing Link',
                                           description='Your public sharing link '
                                                       'has been copied to the '
                                                       'clipboard.',
                                           action_path=sharing_link)

    def get_absolute_task_path(self, task):
        """Return a task path from a given task."""
        from cc.configuration.helpers import get_storage
        storage_config = get_storage(self.config, task.link.remote.storage_id)
        return [storage_config['display_name']] + task.path

    def initialize_callbacks(self):
        """Initialize callbacks for all links."""
        self.sync_graph.bademeister.queue.task_acked.connect(self.report_item_synced)
        self.sync_graph.bademeister.queue.task_putted.connect(self.report_item_syncing)


def create_sharing_menu_items(storage_id, storage):
    """
    Creates the menu items related to sharing data
    :param storage_id the id of the relevant storage
    :param storage the relevant storage object
    :return a list of menu items to include in the context menu
    """
    # resulting items
    resulting_items = []

    # if storage supports sharing - appending item or info that it does not support
    if storage.supports_sharing_link:
        resulting_items.append({
            'name': 'Create public link',
            'enabled': True,
            'children': [],
            'actionId': '{}{}'.format(ACTION_CREATE_LINK_PREFIX, storage_id)})
    else:
        resulting_items.append(
            {'name': 'Public link not supported by storage',
             'enabled': False,
             'children': [],
             'actionId': ''})

    return resulting_items


def create_displaying_menu_items(storage_id, storage):
    """
    Creates the menu items related to displaying data in different forms
    :param storage_id the id of the relevant storage
    :param storage the relevant storage object
    :return:
    """
    # resulting items
    resulting_items = []

    # if storage supports open in web link - appending item or info that it does not
    # support
    if storage.supports_open_in_web_link:
        resulting_items.append({
            'name': 'Show in browser',
            'enabled': True,
            'children': [],
            'actionId': '{}{}'.format(ACTION_BROWSER_OPEN_PREFIX, storage_id)
        })
    else:
        resulting_items.append({
            'name': 'Show in browser not supported by storage',
            'enabled': False,
            'children': [],
            'actionId': ''
        })

    return resulting_items


class IPCCoreServer:
    """ Server class for shell extension ipc server on all platforms over multiple
    channels"""

    def __init__(self, sync_graph, config):
        # creating handler dealing with requests -> all requests will be forwarded if
        # matching method signatures are found
        self.sei = ShellExtensionInterface(sync_graph, config)

        # get transport path
        transport_path = bourne_rpc.get_transport_path(
            application_id=IPC_APPLICATION_ID)

        logger.debug('IPC server listening on "%s"', transport_path)
        # creating transport based on platform (library handles this internally)
        transport = bourne_rpc.StreamingTransport(transport_path)

        # binding transport
        transport.bind()

        logger.debug('Creating server using transport: %s', transport)

        # creating and starting server
        self.srv = bourne_rpc.RpcServer(
            obj=self.sei,
            transport=transport)
        self.thread = threading.Thread(target=self.srv.serve, daemon=True)

    def serve(self):
        """ serves until doomsday """
        self.thread.start()

    def close(self):
        """ stops the sever """
        self.sei.stop()
        self.srv.stop()

    def update(self, sync_graph):
        """ updates the members step and sync_engine, this is for legacy reasons"""
        self.sei.sync_graph = sync_graph
