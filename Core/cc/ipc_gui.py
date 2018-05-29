"""
Implementation of methods needed to call methods of the gui
"""
# pylint: disable=not-callable
import logging
import mimetypes
import os
import threading
from time import strftime

import cc.synctask

# pylint: disable=invalid-name
logger = logging.getLogger(__name__)


class EventBatcher:
    """Processes events in a batched fashion to de-bounce event processing"""

    def __init__(self, event_processing_function, update_time, multi_event=True):
        """constructor
        :param event_processing_function the function to call to process events, this
        is assumed to only have one parameter matching the type of event_items
        :param update_time the update intervall of the batch processing. If an event is
        passed, the batch event will only be processed after update_time and will
        process all events submitted meanwhile
        :param if true, the batcher will process all events, if false, only the latest
        event will be processed"""
        # setting the function handling final events
        self.event_processor = event_processing_function

        # items to process
        self.event_items = []

        # creating lock
        self.lock = threading.Lock()

        # member for timer
        self.timer = None

        # processing time
        self.update_time = update_time

        # mutlievent flag
        self.multi_event = multi_event

    def process_event_batched(self, item):
        """processes the event debounced"""
        # appending item
        self.event_items.append(item)

        # setting timer for later execution
        with self.lock:
            if not self.timer:
                self.timer = threading.Timer(self.update_time, self._process, ())
                self.timer.start()

    # noinspection PyBroadException
    # pylint: disable=broad-except
    def _process(self):
        try:
            # setting timer so new one is created upon event
            with self.lock:
                self.timer = None

            # getting copy of items to update
            items = list(self.event_items)

            if self.multi_event:
                arg = items
            elif len(self.event_items) > 0:
                arg = items[len(self.event_items) - 1]

            # removing items in new list
            del self.event_items[:len(items)]

            # processing batched events
            self.event_processor(arg)
        except Exception:
            logger.exception('Error while processing')


def items_have_updated(items):
    """wrapper function for update items call to gui"""
    if rpc_object is not None:
        rpc_object(method="itemsHaveCompletedSyncing", args=(items,))


def send_notifications(notifications):
    """wrapper function for notification call to gui"""
    # pylint: disable=too-many-function-args
    if rpc_object is not None:
        rpc_object(method="displayNotification", args=(notifications,))


def send_status_update(update):
    """wrapper function for status_update call to gui"""
    if rpc_object is not None:
        rpc_object("appStateHasChanged", args=update, callback=None)


def account_has_updated(accounts):
    """wrapper function for account state update call to gui"""
    if rpc_object is not None:
        rpc_object('accountsUpdated', args=accounts)


# periods for the batcher
GUI_NOTIFICATION_UPDATE_PERIOD = 1
GUI_ITEM_UPDATE_PERIOD = 1
GUI_APP_STATUS_UPDATE_PERIOD = 1

# the ipc object (is set externally when created)
# pylint: disable=invalid-name
rpc_object = None

# item updates
# pylint: disable=invalid-name
update_item_batcher = EventBatcher(items_have_updated,
                                   GUI_ITEM_UPDATE_PERIOD)

# notifications
# pylint: disable=invalid-name
notification_batcher = EventBatcher(send_notifications,
                                    GUI_NOTIFICATION_UPDATE_PERIOD)

# status updates
# pylint: disable=invalid-name
app_status_update_batcher = EventBatcher(send_status_update,
                                         GUI_APP_STATUS_UPDATE_PERIOD, False)

# account update
# pylint: disable=invalid-name
account_update_batcher = EventBatcher(account_has_updated,
                                      GUI_APP_STATUS_UPDATE_PERIOD, False)

# icon names to display in the gui
MULTIPLE_CSP_ICON = 'multiple'
DROPBOX_CSP_ICON = 'dropbox'
GOOGLE_DRIVE_CSP_ICON = 'googledrive'
OWNCLOUD_CSP_ICON = 'owncloud'
NEXTCLOUD_CSP_ICON = 'nextcloud'
FAIRCHECK_CSP_ICON = 'owncloud'
ONEDRIVE_CSP_ICON = 'onedrive'
BOX_CSP_ICON = 'box'
LOCAL_CSP_ICON = 'local'

# names of extension icons (to construct image path)
FILE_TYPE_DOC = 'word'
FILE_TYPE_XLS = 'excel'
FILE_TYPE_GENERAL = 'file'
FILE_TYPE_IMAGE = 'image'
FILE_TYPE_PRESENTATION = 'ppt'
FILE_TYPE_PDF = 'pdf'
FILE_TYPE_FOLDER = 'folder'

# mime types of files to display the right icon
MIME_TYPES_WORD = ['application/msword',
                   'application/vnd.openxmlformats'
                   '-officedocument.wordprocessingml.document']
MIME_TYPES_EXCEL = ['application/vnd.ms-excel',
                    'application/vnd.openxmlformats'
                    '-officedocument.spreadsheetml.sheet']
MIME_TYPES_POWERPOINT = ['application/vnd.ms-powerpoint',
                         'application/vnd.openxmlformats'
                         '-officedocument.presentationml.presentation']
MIME_TYPES_PDF = ['application/pdf']


# function decorator to catch any exception -> none of these must incluence their
# caller!
def ipc_gui_exception_decorator(func):
    """decorator to catch exceptions -> they must not bother caller, no matter what"""

    def func_wrapper(*args, **kwargs):
        """function wrapper catching any exception"""
        try:
            return func(*args, **kwargs)
        except BaseException:
            logger.info('Exception while trying to make IPC call',
                        exc_info=True)
            return None

    return func_wrapper


def create_icon_name(item_path, csp_id):
    """creates an icon name based on csp name and file type
    :param item_path path to the item
    :param csp_id id of the csp the operation is performed to
    :returns the name of the apropriate icon to show in the gui"""
    # getting icon path component for storage
    csp_name = get_path_component_for_storage(csp_id=csp_id)

    # getting icon path component for file type
    file_type = get_path_component_for_file_type(item_path=item_path)

    # constructing icon path = csp + file_type + '.png'
    icon_name = file_type + "_" + csp_name + '.svg'
    return icon_name


def get_path_component_for_storage(csp_id):
    """determines the path component to the appropriate icon file for the csp
    :param csp_id: the id of the storage"""
    # defining default value
    csp_name = 'local'
    if 'dropbox' in csp_id:
        csp_name = DROPBOX_CSP_ICON
    elif 'gdrive' in csp_id:
        csp_name = GOOGLE_DRIVE_CSP_ICON
    elif 'owncloud' in csp_id:
        csp_name = OWNCLOUD_CSP_ICON
    elif 'box' in csp_id:
        csp_name = BOX_CSP_ICON
    elif 'onedrive' in csp_id:
        csp_name = ONEDRIVE_CSP_ICON
    elif 'local' in csp_id:
        csp_name = LOCAL_CSP_ICON
    elif 'faircheck' in csp_id:
        csp_name = FAIRCHECK_CSP_ICON
    elif 'nextcloud' in csp_id:
        csp_name = NEXTCLOUD_CSP_ICON
    else:
        logger.info('Icon for %s not here, taking default one (local without icon).',
                    csp_id)

    # returning result
    return csp_name


def get_path_component_for_file_type(item_path):
    """determines the path component to the appropriate icon file for the file type
    :param item_path: the path of the item to be synced"""
    # extracting file extension to determine logo
    # setting default value
    file_type = FILE_TYPE_GENERAL

    # getting mime type of path
    mime_type = mimetypes.guess_type(item_path[-1], strict=False)[0]
    mime_type_string = '' if mime_type is None else str(mime_type)

    # deciding which file type it is
    if mime_type_string in MIME_TYPES_WORD:
        file_type = FILE_TYPE_DOC
    elif mime_type_string in MIME_TYPES_EXCEL:
        file_type = FILE_TYPE_XLS
    elif mime_type_string in MIME_TYPES_POWERPOINT:
        file_type = FILE_TYPE_PRESENTATION
    elif mime_type_string in MIME_TYPES_PDF:
        file_type = FILE_TYPE_PDF
    elif mime_type_string is not None and 'image' in mime_type_string:
        file_type = FILE_TYPE_IMAGE
    elif os.path.splitext(item_path[-1])[1] == '':
        file_type = FILE_TYPE_FOLDER

    return file_type


@ipc_gui_exception_decorator
def displayNotification(title, description=None, image_path=None, action_path=None):
    """displays the notification with parameters"""

    if description is None:
        description = ''

    logger.info("RPC-CLIENT: display notification")
    # creating dict for parameters
    notification = {'title': title, 'description': description,
                    'imagePath': image_path}
    if action_path:
        notification['actionPath'] = action_path

    # shooting notification
    notification_batcher.process_event_batched(notification)


@ipc_gui_exception_decorator
def updateAccountTypes(current_storage_props):
    """Set the currently enabled account types in the gui."""
    return rpc_object("updateAccountTypes", args=(current_storage_props,))


@ipc_gui_exception_decorator
def appStateHasChanged(state, syncing_item_count=0):
    """informs the gui that the complete app state has changed"""
    argument = {'state': state, 'syncingItemsCount': syncing_item_count}
    logger.info("RPC-CLIENT: app state has changed to %s", state)
    app_status_update_batcher.process_event_batched(argument)


@ipc_gui_exception_decorator
def selectSyncPaths(storage_id):
    """ Gives the user the choice between syncing everything or sepcific selected paths
    the latter a list of list and if everything is selected None is returned """
    logger.info("RPC-CLIENT: asking user to select sync path")
    return rpc_object("selectSyncPaths", args=(storage_id), block=1)


@ipc_gui_exception_decorator
def hidePasswordDialog():
    """ hides password dialog """
    logger.info("RPC-CLIENT: hiding password dialog")
    return rpc_object("hidePasswordDialog", args=())


@ipc_gui_exception_decorator
def coreHasStarted():
    """ hides password dialog """
    logger.info("RPC-CLIENT: core has started")
    return rpc_object("coreHasStarted", args=())


@ipc_gui_exception_decorator
def accountAdded(account_id):
    """notifies the client of that an account has been added"""
    logger.info("RPC-CLIENT: accountHasBeenAdded")
    account = {'id': account_id}
    rpc_object("accountHasBeenAdded", args=account)
    logger.debug('after account added message')


@ipc_gui_exception_decorator
def encryptionEnabled():
    """notifies the gui of that encryption has been enabled"""
    logger.info("RPC-CLIENT: encryptionEnabled")
    rpc_object("encryptionEnabled", args=())


@ipc_gui_exception_decorator
def encryptionDisabled():
    """notifies the gui of that encryption has been disabled"""
    logger.info("RPC-CLIENT: encryptionDisabled")
    rpc_object("encryptionDisabled", args=())


@ipc_gui_exception_decorator
def userLoggedIn():
    """notifies the gui of that the user has been logged in"""
    logger.info("RPC-CLIENT: userLoggedIn")
    rpc_object("userLoggedIn", args=())


@ipc_gui_exception_decorator
def userLogInFailed(error_message=None):
    """notifies the gui of that the user has been logged in"""
    logger.info("RPC-CLIENT: userLogInFailed with message %s", error_message)
    rpc_object("userLogInFailed", args=(error_message))


@ipc_gui_exception_decorator
def userLoggedOut():
    """notifies the gui of that the user has been logged out"""
    logger.info("RPC-CLIENT: userLoggedIn")
    if rpc_object is not None:
        rpc_object("userLoggedOut", args=())


@ipc_gui_exception_decorator
def accountRenamed(account_id, new_name):
    """notifies the gui of that an account has been renamed"""
    logger.info("RPC-CLIENT: accountRenamed")
    args = {'id': account_id, 'new_name': new_name}
    rpc_object("accountRenamed", args=args)


@ipc_gui_exception_decorator
def accountDeleted(account_id):
    """notifies the gui of that an account has been renamed"""
    logger.info("RPC-CLIENT: accountDeleted")
    args = {'id': account_id}

    if rpc_object is not None:
        rpc_object("accountDeleted", args=args)
    else:
        logger.info('rpc_object is None.')


@ipc_gui_exception_decorator
def reAuthenticateAccount(storage_name, storage_id, display_name, auth_type):
    """notifies the gui that account is invalid"""
    logger.info("RPC-CLIENT: invalidAccount")
    args = {'display_name': display_name,
            'storage_name': storage_name,
            'storage_id': storage_id,
            'auth_type': auth_type}

    if rpc_object is not None:
        rpc_object("reAuthenticateAccount", args=args)


@ipc_gui_exception_decorator
def quitApp():
    """ quits the application  """
    rpc_object("quit")


@ipc_gui_exception_decorator
def accountsUpdated(client):
    """sends a message to update account information to the gui"""
    storages = client.get_storages()
    logger.info('RPC-Client: accountsUpdated')
    accounts = []
    for storage in storages:
        # getting metrics
        used_space = storage['total_space'] - storage['free_space']
        total_space = storage['total_space']

        # storing info dictionary
        account = {'type': storage['id'],
                   'display_name': storage['display_name'],
                   'unique_id': storage.get('unique_id'),
                   'user_name': storage.get('storage_user_name'),
                   'size': int(total_space),
                   'used': int(used_space),
                   'id': storage['id']}
        accounts.append(account)

    # processing event batched
    account_update_batcher.process_event_batched([accounts])


@ipc_gui_exception_decorator
def showApproveDeviceDialog(device_id, fingerprint):
    """ shows the approve another device dialog in the GUI"""
    # building arguments for the call
    args = {'device_id': device_id, 'fingerprint': fingerprint}

    # executing call
    rpc_object('showApproveDeviceDialog', args=args)


@ipc_gui_exception_decorator
def showApproveDeviceRequestedDialog(device_id, fingerprint):
    """ shows the approve another device dialog in the GUI"""
    # building arguments for the call
    args = {'device_id': device_id, 'fingerprint': fingerprint}

    # executing call
    rpc_object('showApproveDeviceRequestedDialog', args=args)


@ipc_gui_exception_decorator
def on_task_acked(task):
    """Process a completed task for the gui.

    Connected to the signal from the queue.
    """
    if task.display_in_ui and task.state == cc.synctask.SyncTask.SUCCESSFUL:
        # This needs to be rethought, so something like.task.remote_id can be used
        if isinstance(task, cc.synctask.DownloadSyncTask):
            storage_id = task.source_storage_id
        else:
            storage_id = task.target_storage_id

        path = [task.link.metrics.display_name] + task.target_path

        json_item = {'iconName': create_icon_name(item_path=task.path, csp_id=storage_id),
                     'path': path,
                     'operationType': task.DISPLAY_NAME,
                     'time': strftime("%H:%M")
                     }

        update_item_batcher.process_event_batched(json_item)
