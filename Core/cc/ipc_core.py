"""Communicate with gui using JSON RPC via stdin/stdout"""
# This import is here because client.py does the whole monkey patching for the freeze
# process
# pylint: disable=wrong-import-order
import io
import logging
import os
import shutil
import sys
import time
import webbrowser
from threading import Thread

import requests

import jars

import cc.client
import cc.crypto
import cc.ipc_gui
import cc.settings_sync
from cc import jsonrpc
from cc.configuration.helpers import get_storage_class, update_inodes
from cc.log_utils import setup_logging
from cc.synchronization.models import instantiate_storage
from cc.utils import current_storage_props

APP_STATE_SYNCED = 'synced'
APP_STATE_SYNCING = 'syncing'
APP_STATE_OFFLINE = 'offline'
APP_STATE_PAUSED = 'paused'
APP_STATE_INDEXING = 'indexing'

SUCCESS_OPERATION_RESPONSE = {'status': 'success', 'message': 'Operation successful'}
FAILED_OPERATION_RESPONSE = {'status': 'failed', 'message': 'Could not perform operation'}

# pylint: disable=invalid-name
logger = logging.getLogger(__name__)


# function decorator to catch any exception -> none of these must incluence their
# caller!
def ipc_core_exception_decorator(func):
    """decorator to catch exceptions -> they must not bother caller, no matter what"""

    def func_wrapper(*args, **kwargs):
        """function wrapper catching any exception"""
        try:
            return func(*args, **kwargs)
        except BaseException:
            logger.info('Exception while trying to execute IPC call',
                        exc_info=True)
            return {'status': 'error', 'message': 'Problem while performing operation'}

    return func_wrapper

# pylint: disable=too-many-public-methods


class CrossCloudCore:
    """The ipc server for functions to be called from the gui"""

    def __init__(self, cc_client):
        """constructor
        :param cc_client the CrossCloud client"""
        self.client = cc_client

        # flag indicating if the app has been started
        self.client_started = False

    # pylint: disable=no-self-use
    @ipc_core_exception_decorator
    def getAccountTypes(self):
        """Return the available types of accounts."""
        logger.info("RPC-SERVER: get account types called")
        return current_storage_props(config=self.client.config,
                                     registered_storages=jars.registered_storages)

    # pylint: disable=no-self-use
    @ipc_core_exception_decorator
    def getRecentlySyncedItems(self):
        """Return items that have currently been synced"""
        logger.info("RPC-SERVER: get recently synced items")
        # returning empty list -> the items will be updated from another method as they
        # appear
        return []

    # pylint: disable=no-self-use
    @ipc_core_exception_decorator
    def isLoggedIn(self):
        """State if the user is logged in on the admin console"""
        logger.info("RPC-SERVER: is logged in")

        # checking if user is logged in
        login_valid = cc.settings_sync.check_login(self.client.config)
        if not login_valid:
            cc.ipc_gui.displayNotification('Logged Out', 'There was a problem logging you '
                                                         'in. Please try again.')
        return login_valid

    # pylint: disable=no-self-use
    @ipc_core_exception_decorator
    def getUserEmail(self):
        """Return the user's email address"""
        logger.info("RPC-SERVER: get user email")
        return self.client.config.user_email

    # pylint: disable=no-self-use
    # pylint: disable=broad-except
    @ipc_core_exception_decorator
    def login(self, username, password):
        """Log the user in at the specific domain"""
        logger.info("RPC-SERVER: log in")
        # noinspection PyBroadException
        try:
            cc.settings_sync.authenticate_user(username=username,
                                               password=password,
                                               config=self.client.config)
            cc.ipc_gui.userLoggedIn()
        except requests.exceptions.ConnectionError:
            cc.ipc_gui.userLogInFailed('No connection to server.')
            logger.debug('No connection to server.', exc_info=True)
            return FAILED_OPERATION_RESPONSE
        except cc.UnauthenticatedUserError:
            logger.debug('Wrong credentials', exc_info=True)
            cc.ipc_gui.userLogInFailed('Wrong credentials')
            return FAILED_OPERATION_RESPONSE
        except requests.exceptions.HTTPError as err:
            if err.response.status_code == 418:
                cc.ipc_gui.userLogInFailed('Outdated version, please update.')
            else:
                cc.ipc_gui.userLogInFailed('An unknown problem occurred. Please try '
                                           'later.')
            logger.debug('HTTP error', exc_info=True)

            return FAILED_OPERATION_RESPONSE
        except Exception:
            logger.exception('Unknown error while logging user in')
            cc.ipc_gui.userLogInFailed('An unknown problem occurred. Please try '
                                       'later.')
            return FAILED_OPERATION_RESPONSE

        return SUCCESS_OPERATION_RESPONSE

    @ipc_core_exception_decorator
    def logout(self):
        """logs the user out"""
        cc.settings_sync.logout(self.client.config)
        logger.info("RPC-SERVER: logout")

        # stopping client
        # shutting down client -> models are written etc.
        if self.client_started:
            self.client_started = False
            self.client.shutdown()

        # shooting event
        cc.ipc_gui.userLoggedOut()
        return SUCCESS_OPERATION_RESPONSE

    # pylint: disable=unused-argument
    # pylint: disable=too-many-arguments
    @ipc_core_exception_decorator
    def addAccount(self, type_name, server_url=None, username=None, password=None,
                   cont=False, account_id=None):
        """adds an account to the system"""

        logger.info("RPC-SERVER: add account %s acc_id: %s", type_name, account_id)

        # not performing this if not started -> should not be called
        if not self.client_started:
            return

        # account based on oauth
        if server_url is None and username is None and password is None:
            # defining function to add oauth account
            def add_oauth_account():
                """method to add oauth account in a separate thread"""
                # adding oauth account
                try:
                    new_id = self.client.add_storage(storage_name=type_name,
                                                     storage_id=account_id)

                    # if adding successful, sending notification and informing GUI
                    if new_id:
                        cc.ipc_gui.displayNotification('Account added',
                                                       'Your account has been added '
                                                       'and is synced now.')
                        # informing client of change
                        cc.ipc_gui.accountAdded(new_id)

                except cc.client.AuthenticationFailed:
                    cc.ipc_gui.displayNotification('Unable to add {} account'.format(type_name),
                                                   'Please try again later.')
                except BaseException:
                    logger.error("could not add storage due to an exception",
                                 exc_info=True)

            # starting the thread
            Thread(target=add_oauth_account, args=()).start()
        else:
            try:
                new_id = self.client.add_storage(storage_name=type_name, url=server_url,
                                                 username=username, password=password,
                                                 ignore_warnings=cont,
                                                 storage_id=account_id)
            except cc.client.AuthenticationFailed:
                cc.ipc_gui.displayNotification('Unable to add {} account.'.format(type_name),
                                               'Please try again later.')
                return {'status': 'error', 'message': error.args}
            except (ConnectionError, ValueError, AssertionError) as error:
                # error messages -> GUI
                logger.debug('error connection', exc_info=True)
                return {'status': 'error', 'message': error.args}
            except Warning as warning:
                # warning message -> GUI
                logger.debug('warning connection')
                return {'status': 'warning', 'message': warning.args}

            # if adding successful, sending notification and informing GUI
            if new_id:
                cc.ipc_gui.displayNotification('Account added', 'Your account has been '
                                                                'added '
                                                                'and is synced now.')
                # informing gui of added account
                cc.ipc_gui.accountAdded(new_id)

        # returning success
        return SUCCESS_OPERATION_RESPONSE

    # pylint: disable=no-self-use
    @ipc_core_exception_decorator
    def renameAccount(self, account_id, new_display_name):
        """renames a given account"""
        logger.info("RPC-SERVER: rename account")

        csp = None
        for storage in self.client.config.csps:
            if storage['id'] == account_id:
                csp = storage
                break
        csp['display_name'] = new_display_name

        # restart syncengine with new name
        self.client.shutdown()
        self.client.config.write_config()
        self.client.startup()

        cc.ipc_gui.accountRenamed(account_id, new_display_name)
        return SUCCESS_OPERATION_RESPONSE

    @ipc_core_exception_decorator
    def getAccounts(self):
        """returns the currently added accounts"""
        logger.info("RPC-SERVER: get accounts")
        accounts = {}
        if self.client_started:
            for dict_value in self.client.get_storages():
                # getting metrics
                used_space = dict_value['total_space'] - dict_value['free_space']
                total_space = dict_value['total_space']
                # storing info dictionary
                accounts[dict_value['id']] = {
                    'type': dict_value['id'],
                    'display_name': dict_value['display_name'],
                    'unique_id': dict_value['unique_id'],
                    'user_name': dict_value.get('storage_user_name', dict_value['unique_id']),
                    'size': int(total_space),
                    'used': int(used_space),
                    'id': dict_value['id']}

            logger.info("RPC-SERVER: returning accounts %s", accounts)
        return accounts

    @ipc_core_exception_decorator
    def deleteAccount(self, account_id):
        """deletes an accounts if present"""

        # not performing this if not started -> should not be called
        if not self.client_started:
            logger.info("not deleting %s, since client is not started", account_id)
            return

        logger.info("Deleting account with id %s", account_id)
        self.client.remove_storage(account_id)

        # removing storage directory, this gets recognized by the watcher and all
        # other steps will be taken in the handler there
        # send2trash(os.path.join(config.sync_root, display_name))

        return SUCCESS_OPERATION_RESPONSE

    @ipc_core_exception_decorator
    def openSyncdir(self):
        """opens the sync dir in the os file explorer"""
        logger.info("RPC-SERVER: open sync dir")
        self.client.open_sync_root()
        return SUCCESS_OPERATION_RESPONSE

    @ipc_core_exception_decorator
    def openPath(self, path):
        """opens the specied path in the os file explorer
        :param path the path to open"""
        # constructing absolute path
        absolute_path = os.path.join(self.client.config.sync_root, os.path.sep.join(path))
        # opening parent path in file explorer
        self.client.open_path(os.path.dirname(absolute_path))
        return SUCCESS_OPERATION_RESPONSE

    # pylint: disable=no-self-use
    @ipc_core_exception_decorator
    def openWebsite(self, url):
        """opens the provided link in the webbrowser
        :param url the url to be opened"""
        logger.info("RPC-SERVER: open website")
        webbrowser.open(url)
        return SUCCESS_OPERATION_RESPONSE

    # pylint: disable=no-self-use
    @ipc_core_exception_decorator
    def getSyncdir(self):
        """returns the sync dir"""
        logger.info("RPC-SERVER: get sync dir")
        return self.client.config.sync_root

    @ipc_core_exception_decorator
    def setSyncDir(self, new_syncdir):
        """sets a new sync dir"""
        logger.info("RPC-SERVER: set sync dir xxxx")

        # idea here: the destination folder needs to be empty
        if os.listdir(new_syncdir):
            cc.ipc_gui.displayNotification('Problem moving sync dir', 'The new sync dir '
                                                                      'needs to be empty')
            return

        # not doing this if app not started
        if not self.client_started:
            return

        # restarting client
        self.client.shutdown()

        # storing old dir
        old_syncdir = self.client.config.sync_root

        try:
            # removing new syncdir
            os.rmdir(new_syncdir)

            # dont' ask
            time.sleep(0.5)

            # copying old files to new location
            shutil.copytree(self.client.config.sync_root, new_syncdir)

            # setting new syncdir in config
            self.client.config.sync_root = new_syncdir
            update_inodes(self.client.config)
            self.client.config.write_config()
            try:
                shutil.rmtree(old_syncdir, ignore_errors=True)
            except BaseException:
                logger.exception('Cannot delete old dir')
        except BaseException:
            logger.exception('Cannot move dir')
            cc.ipc_gui.displayNotification('Problem moving sync dir', 'A problem '
                                                                      'occurred while '
                                                                      'moving your sync '
                                                                      'dir. Please try '
                                                                      'again.')
            return
        finally:
            self.client.startup()

        # displaying notification for user
        cc.ipc_gui.displayNotification('Sync directory moved', 'Successfully moved '
                                                               'your sync directory')

    @ipc_core_exception_decorator
    def shutdown(self):
        """shuts down the core"""
        logger.info("RPC-SERVER: shutdown")

        # shutting down client -> models are written etc.
        if self.client_started:
            # setting started flag
            self.client_started = False
            self.client.shutdown()

        # shutting down rpc -> writer and reader on stdin stdout are closed
        logger.debug('shutting down gui ipc')
        cc.ipc_gui.rpc_object.shut_down()

        logger.debug('exiting application, bye bye now...')

        # quitting the core
        # sys.exit(0)
        # pylint: disable=W0212
        os._exit(0)

        logger.debug('ok i am still here...i saw the light')

    @ipc_core_exception_decorator
    def getSelectedSyncPaths(self, storage_id):
        """Fetches the selected sync paths for a storage_id from the running client config."""
        link_id = 'local::' + storage_id
        filter_tree = self.client.synchronization_graph.links[link_id].remote.filter_tree
        return list(jars.utils.tree_to_config(filter_tree))

    @ipc_core_exception_decorator
    def setSelectedSyncPaths(self, storage_id, paths):
        """
        Sets the selected sync paths for a storage id in the running config
        this triggers a restart of the client
        """
        # not performing this if not started -> should not be called
        if not self.client_started:
            return

        self.client.set_selected_paths(storage_id, paths)

    @ipc_core_exception_decorator
    def getStorageChildren(self, storage_id, path):
        """ get children of a specific storage """
        logger.debug('Getting children for "%s"', storage_id)

        storage_class = get_storage_class(storage_id.split('_')[0])
        storage_inst = instantiate_storage(storage_class, storage_id=storage_id,
                                           config=self.client.config)
        result = []

        for name, props in storage_inst.get_tree_children(path):
            if props['is_dir']:
                obj = {'name': name}
                result.append(obj)

        logger.debug('Returning children for "%s"', storage_id)
        return result

    @ipc_core_exception_decorator
    def pause(self):
        """pauses the synchronisation"""
        logger.info("RPC-SERVER: pause")

        # not performing this if not started -> should not be called
        if not self.client_started:
            return

        self.client.pause()
        cc.ipc_gui.appStateHasChanged(APP_STATE_PAUSED)

    @ipc_core_exception_decorator
    def resume(self):
        """resumes the synchronisation"""
        logger.info("RPC-SERVER: resume")

        # not performing this if not started -> should not be called
        if not self.client_started:
            return

        self.client.resume()
        cc.ipc_gui.appStateHasChanged(APP_STATE_SYNCED)
        return SUCCESS_OPERATION_RESPONSE

    @ipc_core_exception_decorator
    def getAppState(self):
        """returns the app state"""
        logger.info("RPC-SERVER: get app state")

        # checking if we are up and running
        return APP_STATE_SYNCED

        # if not self.client.conn_state.online:
        #     return APP_STATE_OFFLINE

        # if not self.client.sync_engine.initialized:
        #     return APP_STATE_INDEXING

        # if self.client.is_paused \
        #         and len(self.client.get_storages()) > 0:
        #     return APP_STATE_PAUSED

        # if len(self.client.step.get_active_tasks()) > 0:
        #     return APP_STATE_SYNCING

        # return APP_STATE_SYNCED

    @ipc_core_exception_decorator
    def ping(self):
        """a simple ping/pong mechanism used for health checking"""
        # logger.info('RPC-SERVER: ping')
        return 'pong'

    @ipc_core_exception_decorator
    def startApp(self):
        """starts the application (synchronisation etc.)"""
        logger.debug('starting app was called')
        # starting client if not already running
        if not self.client_started:
            # setting flag
            self.client_started = True

            # starting up client
            started = self.client.startup()

            # checking if startup was successful -> otherwise resetting flag
            if not started:
                self.client_started = False
        else:
            logger.debug('Running Core was tried to start again - '
                         'this should not happen')

        # reporting back that core has started
        cc.ipc_gui.coreHasStarted()

    @ipc_core_exception_decorator
    def approveDevice(self, device_id, fingerprint):
        """ is called when the user approves another device in the GUI"""
        # calling the corresponding settings sync method
        cc.settings_sync.confirm_device_approval(device_id=device_id,
                                                 public_key_fingerprint=fingerprint,
                                                 config=self.client.config)

    @ipc_core_exception_decorator
    def declineDevice(self, device_id, fingerprint):
        """ is called when the user declines a device approval request"""
        # calling method to decline request
        cc.settings_sync.confirm_device_declination(device_id=device_id,
                                                    public_key_fingerprint=fingerprint,
                                                    config=self.client.config)


def start_crosscloud():
    """starts crosscloud with ipc server"""
    # fixing stdout and stdin encoding issues
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
    sys.stdin = io.TextIOWrapper(sys.stdin.detach(), encoding='utf-8')

    client_config = cc.configuration.get_basic_config()
    client_config.init_config_dirs()

    # logging should be setup here for production.
    # In order to allow other configurations for testing.
    setup_logging(log_dir=client_config.log_dir)

    # creating the client
    cc_client = cc.client.Client(config=client_config)

    try:
        # starting rpc server
        rpc_object = jsonrpc.BidirectionalRPC(server=CrossCloudCore(cc_client),
                                              out_stream=sys.stdout,
                                              in_stream=sys.stdin)

        # setting rpc object in gui ipc module
        cc.ipc_gui.rpc_object = rpc_object

    except BaseException:
        logger.exception('Could not start communication with GUI', exc_info=True)


if __name__.endswith('__main__'):
    start_crosscloud()
