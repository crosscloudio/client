"""Basic functionallity for the crosscloud client."""

# pylint: disable=invalid-name,wrong-import-order,too-many-arguments,too-many-locals
# pylint: disable=too-many-lines,ungrouped-imports,too-many-instance-attributes
import cmd
import contextlib
import logging
import os
import platform
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from copy import copy
from pprint import pprint

import jars
import shutil
from jars.oauth_http_server import OAuthHTTPServer
from send2trash import send2trash

from cc.periodic_scheduler import PeriodicScheduler
from cc.synchronization.models import SynchronizationGraph
from cc.synchronization.syncengine import SyncEngineState
from cc.synchronization_directory import SynchronizationDirectoryWatcher

from cc.shell_extension_server import IPCCoreServer

if hasattr(sys, 'frozen'):
    import pkg_resources
    import certifi
    import certifi.core

    import cryptography.hazmat.backends.openssl
    from cryptography.hazmat.backends.multibackend import MultiBackend


    def patched_resource_filename(_, resource_name):
        """ returns the resource name, related to the frozen executable, ignoring
         the module name"""
        return os.path.join(os.path.dirname(sys.executable), resource_name)


    def cerify_patch():
        """ patch to make certifi work, which then is used by requests """
        return os.path.join(os.path.dirname(sys.executable), 'cacert.pem')


    certifi.where = cerify_patch
    certifi.core.where = cerify_patch
    pkg_resources.resource_filename = patched_resource_filename

    import cc.crypto

    cc.crypto.default_backend = lambda: MultiBackend(
        [cryptography.hazmat.backends.openssl.backend])

    # set the working diretory to the cache dir
    #  (there are some funny modules writing files)
    from cc.configuration.constants import CACHE_DIR

    os.makedirs(CACHE_DIR, exist_ok=True)
    os.chdir(CACHE_DIR)

if os.name == 'nt':
    from cc.native.windows_explorer import register_quick_access as platform_start
elif sys.platform == 'darwin':
    from cc.native.osx_finder import init_findersync as platform_start
else:
    def platform_start():
        """ dummy fun """

import filelock
from requests import HTTPError
from requests import RequestException
from json import JSONDecodeError

from cc import STORAGE_LABELS
from cc.configuration.helpers import DuplicatedAccountError, write_config, get_storage_cache_dir, \
    get_storage, determine_csp_display_name, get_storage_class
# import all storages to make them available in the client
import cc.ipc_gui

import cc.crypto
import cc.ipc_core
import cc.settings_sync

# pylint: disable=invalid-name
logger = logging.getLogger(__name__)
SYNC_STATE_FILE = 'sync_state.dat'
SYNC_STATE_SAVE_PERIOD = 60
SYNC_ADMIN_CONSOLE_PERIOD = 30

class Client:
    """Interface for frontends"""

    def __init__(self, config):
        self.config = config

        # read configuration
        self.config = self.config.read_config()
        # try to aquire the single instance lock
        self.lock = filelock.FileLock(str(self.config.lock_file))
        self.lock.acquire(timeout=0.1)

        # lock for protecting the methods which are changing the run config
        self.run_lock = threading.RLock()

        # creating ipc server field
        self.ipc_server = None

        # flags indicating state of client
        self.is_paused = False

        self.periodic_ac_sync = None

        self.periodic_gui_update = None

        self.synchronization_graph = None

        self.synchronization_directory_watcher = None

        self.synchronization_directory_watcher_sched = None

        self.periodic_conf_fetch = None

    def open_sync_root(self):
        """ opens the sync directory in the os specific browser """
        # pylint: disable=no-self-use
        path = self.config.sync_root
        self.open_path(path)

    # pylint: disable=R0201
    def open_path(self, path):
        """opens the specified path in the system file explorer
        :param path the path to be opened"""
        if platform.system() == "Windows":
            os.startfile(path) # pylint: disable=no-member
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def restart(self):
        """Helper to restart client."""
        self.shutdown()
        self.startup()

    def startup(self):
        """ starts everything"""
        with self.run_lock:
            logger.debug('starting client')

            # detecting if the first startup (=no config file)
            if not os.path.isfile(self.config.config_file):
                # showing welcome notification
                cc.ipc_gui.displayNotification('Welcome to CrossCloud!',
                                               'CrossCloud is now running in the '
                                               'background. Press the icon to add '
                                               'storage accounts')

            # sync configuration with backend
            try:
                cc.settings_sync.fetch_and_apply_configuration(config=self.config)
            except cc.UnauthenticatedUserError:
                logger.debug('user not logged in or admin console not available '
                             '--> not starting up')
                # logging out user and quitting startup
                cc.ipc_gui.userLoggedOut()
                return False
            except cc.DeviceApprovalRequiredError:
                logger.debug('device requires approval from another device.')

                # displaying confirmation dialog in gui
                cc.ipc_gui.showApproveDeviceRequestedDialog(
                    device_id=self.config.device_id,
                    fingerprint=cc.crypto.calculate_sha256(
                        self.config.device_public_key).decode('ascii'))
                return False
            except RequestException:
                logger.debug('Unable to reach admin console.')

                # informing the user of the problem
                cc.ipc_gui.displayNotification('Server Offline.', 'Connection '
                                                                  'to the crosscloud server '
                                                                  'could not be established.')
            except BaseException:
                logger.exception('got the exception and cannot start')
                return False

            self.synchronization_graph = SynchronizationGraph.using(self.config)
            logger.info("Synchronization graph set up. Calling 'startup'...")
            self.synchronization_graph.startup()
            logger.info("Synchronization graph running.")

            # explorer and finder icons, should happen after the makedir of the syncroot
            platform_start()

            # SynchronizationDirectoryWatcher helps to detect changes in the sync-root
            self.synchronization_directory_watcher = SynchronizationDirectoryWatcher(self.config)
            # first try to migrate the old config
            self.synchronization_directory_watcher.migrate_old_config()
            self.synchronization_directory_watcher.storage_directory_deleted.connect(
                self.on_storage_directory_deleted)
            self.synchronization_directory_watcher.storage_directory_renamed.connect(
                self.on_storage_directory_renamed)
            self.synchronization_directory_watcher_sched = \
                PeriodicScheduler(1.0, target=self.synchronization_directory_watcher.check)
            self.synchronization_directory_watcher_sched.start()

            # launch shell extension server
            if not self.ipc_server:
                self.ipc_server = IPCCoreServer(sync_graph=self.synchronization_graph,
                                                config=self.config)
                self.ipc_server.serve()
            else:
                self.ipc_server.update(sync_graph=self.synchronization_graph)

            self.initialize_periodic_tasks()

            return True

    def initialize_periodic_tasks(self):
        """Initialize all the tasks that use the periodic_scheduler here."""
        # This is launched with a polling time of 1 second. This interval
        # is automatically adjusted after the first sync was successful
        self.periodic_ac_sync = PeriodicScheduler(1, self.admin_console_sync)
        self.periodic_ac_sync.target_args = (self.periodic_ac_sync,)
        self.periodic_ac_sync.start()

        # Create a periodic refresh of the gui to update the metrics display
        self.periodic_gui_update = PeriodicScheduler(interval=1, target=self.update_ui)
        self.periodic_gui_update.start()

    def update_ui(self):
        """Update all the state in the ui(storage metrics, sync_state and task count)"""
        try:
            # this causes the ui to re-fetch all accounts
            logger.debug('refreshing account list')
            cc.ipc_gui.accountDeleted('')

            logger.debug('refreshing sync state')
            MAPPING = {SyncEngineState.STATE_SYNC: cc.ipc_core.APP_STATE_INDEXING,
                       SyncEngineState.STOPPED: cc.ipc_core.APP_STATE_PAUSED,
                       SyncEngineState.RUNNING: cc.ipc_core.APP_STATE_SYNCED,
                       SyncEngineState.OFFLINE: cc.ipc_core.APP_STATE_OFFLINE}

            # get the aggreated state of all sync-engins within the link
            state = self.synchronization_graph.aggregate_state()
            state_ui = MAPPING.get(state, cc.ipc_core.APP_STATE_OFFLINE)

            sync_tasks = None
            if state == SyncEngineState.RUNNING:
                # TODO: Shorten this calling chain!
                sync_tasks = self.synchronization_graph.bademeister.queue. \
                             statistics['sync_task_count']
                if sync_tasks != 0:
                    state_ui = cc.ipc_core.APP_STATE_SYNCING

            logger.debug('state: %s, sync_tasks:%s', state_ui, sync_tasks)
            cc.ipc_gui.appStateHasChanged(state_ui, sync_tasks)
        except BaseException:
            logger.warning('Updating the ui failed', exc_info=True)

    def admin_console_sync(self, scheduler):
        """Sync the sharing information with the administrator console.

        :return:
        """
        try:
            if self.synchronization_graph.state == 'RUNNING':
                logger.debug("Performing Admin Console Sync")
                # cc.settings_sync.fetch_and_apply_configuration()
                cc.settings_sync.fetch_admin_console_configuration(config=self.config)

                # check encryption status changes
                cc.settings_sync.check_encryption_change(self.restart)

                # apply the changes
                cc.settings_sync.apply_configuration(config=self.config)

                # updating share information in administrator console
                cc.settings_sync.update_share_information(self.get_links_remote(),
                                                          config=self.config)

                # update which storages are currently enabled.
                cc.settings_sync.update_enabled_storages(config=self.config)

                # After first successful sync increase polling interval
                scheduler.interval = SYNC_ADMIN_CONSOLE_PERIOD
            else:
                logger.debug("Skipping Admin Console Sync since SE is not yet ready.")
        except cc.UnauthenticatedUserError:
            logger.debug('Encountered unauthorized error while syncing admin console')

            # logging out user
            cc.ipc_gui.userLoggedOut()

            # notifying user
            cc.ipc_gui.displayNotification('Logged Out', 'You were logged out.')

            # shutting down core
            self.shutdown()
        except (RequestException, JSONDecodeError):
            logger.warning('Could not sync admin console settings from %s', cc.settings_sync.HOST,
                           exc_info=True)

    def get_storages(self):
        """Return a list of configured storages."""
        storages = []
        metric_dict = {}
        for link in list(self.synchronization_graph.links.values()):
            metric_value = link.engine.storage_metrics.get()

            metric_dict[metric_value.storage_id] = {'free space': metric_value.free_space,
                                                    'total space': metric_value.total_space}
        for csp in self.config.csps:
            csp = copy(csp)
            try:
                csp['free_space'] = round(float(metric_dict[csp['id']]['free space']), 1)
                csp['total_space'] = round(float(metric_dict[csp['id']]['total space']), 1)
            except KeyError:
                csp['free_space'] = 0
                csp['total_space'] = 0
            storages.append(csp)
        return storages

    def get_links_remote(self):
        """Return remote storages from the links."""
        storages = []
        for link in self.synchronization_graph.links.values():
            storages.append(link.remote)
        return storages

    def add_storage(self, storage_name, url=None, username=None, password=None,
                    ignore_warnings=False, storage_id=None):
        """Adds one of the possible storage providers.

        :throws: :class:`ConnectionError` if not connected to the internet
        :throws: :class:`Warning` if authentication is only possible with warnings.
            Call again with ignore_warnings=True in order to add storage
        :throws: :ValueError: if wrong credentials or url was entered.
        :throws: :AuthenticationFailed: if authentification is interrupted.
        :throws: :AssertionError: for any other error
        """
        # Check if the account type is disabled
        if storage_name not in self.config.enabled_storage_types:
            # notify the user
            logger.warning(
                'Cannot add %s, account has been disabled by administrator.', storage_name)
            desc = STORAGE_LABELS[storage_name] + ' accounts are disabled.'
            cc.ipc_gui.displayNotification(
                title='Disabled Account', description=desc)
            return None
        with self.run_lock:
            # authenticate the user and get the information that we want to store.
            auth_handler = StorageAuthenticator(storage_name=storage_name,
                                                ignore_warnings=ignore_warnings,
                                                client_config=self.config,
                                                username=username,
                                                password=password,
                                                url=url,
                                                storage_id=storage_id)
            auth_data = auth_handler.authenticate()
            try:
                self.config.add_csp(auth_data)

                logger.debug('Let the user choose the paths to sync')
                selected_sync_dirs = self.get_selected_paths_from_user(auth_data['new_storage_id'])
                self.config.set_csp_selected_sync_dirs(auth_data['new_storage_id'],
                                                     selected_sync_dirs)
                logger.debug('The user selected the following sync paths %s', selected_sync_dirs)

            except DuplicatedAccountError as error:
                # rollback the created directory
                os.rmdir(auth_data['sp_dir'])

                # notify the user
                logger.warning(
                    'wanted to add duplicate account %s, %s', error.unique_id, error.acc_type)
                desc = 'Wanted to add ' + error.acc_type + 'account a second time.'
                cc.ipc_gui.displayNotification(
                    title='Duplicate Account', description=desc)

            self.restart_sync_graph()
            return auth_data['new_storage_id']

    def remove_storage(self, storage_id):
        """Remove storage from the client.

        Internally this only moves the storage directory to the trash.
        The directory watcher then takes care about deleting stuff from the config.
        """
        logger.info('Removing storage by sending the storage folder to the trash')
        storage = get_storage(self.config, storage_id)
        storage_directory = os.path.join(self.config.sync_root, storage['display_name'])
        try:
            send2trash(storage_directory)
        except OSError:
            if os.path.exists(storage_directory):
                # Folder exists but it's blocked
                cc.ipc_gui.displayNotification('Problem removing account',
                                               'Could not remove "%s", please close all open files'
                                               ' and try again.' % storage['display_name'])
            else:
                # root folder doesn't exist, we need to remove it from the config
                self.on_storage_directory_deleted(None, storage['local_unique_id'])

    def pause(self):
        """Send pause request."""
        self.synchronization_graph.pause()
        self.is_paused = True

    def resume(self):
        """Send a resume request."""
        self.synchronization_graph.resume()
        self.is_paused = False

    def shutdown(self):
        """Shut down everything."""

        logger.info('Shutting down client')

        with self.run_lock:

            if self.periodic_ac_sync:
                logger.debug("sending stop event to periodic admin console sync")
                self.periodic_ac_sync.stop()

            if self.periodic_gui_update:
                self.periodic_gui_update.stop()

            if self.synchronization_directory_watcher_sched:
                self.synchronization_directory_watcher_sched.stop()

            logger.debug("Stopping Shell Extension IPC Server")
            if self.ipc_server:
                self.ipc_server.close()
                self.ipc_server = None

            if self.synchronization_graph:
                self.synchronization_graph.shutdown()

            logger.info("shutdown done")

    def get_selected_paths_from_user(self, storage_id):
        """Fetch the selected path via ipc from the user interface."""
        return cc.ipc_gui.selectSyncPaths(storage_id)

    def set_selected_paths(self, storage_id, sync_paths):
        """Write the selected path for a specified storage id into the config."""
        self.shutdown()
        self.config.get_storage(storage_id)['selected_sync_directories'] = sync_paths

        logger.debug('Writing config...')
        self.config.write_config()

        self.startup()

    def on_storage_directory_deleted(self, _, local_unique_id):
        """Delete the storage from the config and restarts"""
        logger.info('Detected deletion of storage directory "%s"', local_unique_id)
        config_index, display_name, storage_id = next(
            ((index, item['display_name'], item['id'])
             for item, index in zip(self.config.csps, range(len(self.config.csps)))
             if item['local_unique_id'] == local_unique_id))
        del self.config.csps[config_index]

        cc.ipc_gui.displayNotification(
            'Storage Provider Deleted',
            description='Your storage provider "{}" got deleted. Your data is still available'
                        ' on the storage itself'.format(display_name))

        # write the config and apply it be restarting the graph
        write_config(self.config)
        self.restart_sync_graph()

        # as last step we delete the cache directory (otherwise the shutdown of the storage will
        # write it again)
        try:
            storage_cache_dir = get_storage_cache_dir(self.config, storage_id)
            logger.debug('Trying to delete the storage cache "%s"', storage_cache_dir)
            shutil.rmtree(storage_cache_dir)
        except OSError:
            logger.info('Was not able to delete the file (maybe never existed)', exc_info=True)

    def restart_sync_graph(self):
        """Reinitalize and starts a syncgraph from scratch."""
        self.synchronization_graph.shutdown()
        self.synchronization_graph = SynchronizationGraph.using(self.config)
        self.synchronization_graph.startup()

    def on_storage_directory_renamed(self, _, new_name, local_unique_id):
        """Change the config according to the new name."""
        logger.info('Detected rename of storage directory "%s"', new_name)
        config_item = next((item for item in self.config.csps
                            if item['local_unique_id'] == local_unique_id))
        old_name = config_item['display_name']
        config_item['display_name'] = new_name

        cc.ipc_gui.displayNotification(
            'Storage Provider Renamed',
            description='Your storage provider "{}" has been renamed to "{}"'.format(old_name,
                                                                                new_name))
        write_config(self.config)
        self.restart_sync_graph()


class CmdClient(Client, cmd.Cmd):
    """Implementation of a the client on a shell."""
    prompt = 'crosscloud> '

    # pylint: disable=no-self-use

    def __init__(self):
        Client.__init__(self)
        cmd.Cmd.__init__(self)
        logging.basicConfig(level=logging.DEBUG)

    def do_start(self, _):
        """Call startup."""
        # logging.basicConfig(level=logging.DEBUG)
        self.startup()

    def do_status(self, _):
        """Get the status."""

    def do_csps(self, _):
        """List all configured csps."""
        for storage in self.get_storages():
            pprint(storage)

    def do_add_csp(self, arg):
        """Add a csps."""
        self.add_storage(arg)

    def do_pause(self, _):
        """Send pause request."""
        self.pause()

    def do_resume(self, _):
        """Send a resume request."""
        self.resume()

    def do_quit(self, _):
        """Quit the client."""
        return True

    def show_notification(self, title, text, action_url=None):
        """Show a user notification."""
        logger.info("Notification: [%s]: %s, action: %s", title, text, action_url)


class StreamToLogger(object):
    """ Fake file-like stream object that redirects writes to a logger instance. """

    def __init__(self, logger_obj, log_level=logging.INFO):
        self.logger = logger_obj
        self.log_level = log_level

    def write(self, buf):
        """File object write method"""
        if buf != '\n':
            self.logger.log(self.log_level, buf.rstrip())

# class CleanupThread(threading.Thread):
#     """Thread to cleanup all running stuff for a clean shutdown."""
#
#     def __init__(self):
#         super().__init__(daemon=True)
#
#     def run(self):
#         logger.debug('Closing all sockets')
#         for obj in gc.get_objects():
#             try:
#                 if isinstance(obj, socket.socket):
#                     obj.shutdown(socket.SHUT_RDWR)
#                     obj.close()
#             except BaseException:
#                 logger.debug('Failed forceful socket shutdown')


def main():
    """Main function."""
    client = CmdClient()
    try:
        client.cmdloop()
    except KeyboardInterrupt:
        pass
    finally:
        client.shutdown()


if __name__.endswith('__main__'):
    main()


class AuthenticationFailed(Exception):
    """Raised when auth was initiated but cannot be completed."""
    pass

class StorageAuthenticator:
    """Take care of the authentication process in the client.

    This returns a dict with the authentication information:
    ========================================================
    >>> auth_data = {'storage': 'storage instance', 'credentials': 'token',
    >>>              'identifier': 'storage unique id', 'new_storage_id': 'storage id',
    >>>              'display_name: 'name to display in FS/GUI', 'sp_dir': 'path to folder'}
    """
    OAUTH_TIMEOUT = 120
    """Seconds until oauth_server is terminated if no action is taken by the user."""

    def __init__(self, storage_name, ignore_warnings, client_config=None, username=None,
                 password=None, url=None, storage_id=None):
        self.client_config = client_config
        self.storage_name = storage_name
        self.storage = get_storage_class(storage_name)
        self.oauth_webserver = None
        self.username = username
        self.password = password
        self.url = url
        self.storage_id = storage_id
        self.ignore_warnings = ignore_warnings
        self.auth_data = {'credentials': False,
                          'identifier': False}

    @property
    def completed(self):
        """If credentials and identifier have not been set, authentication has failed."""
        return self.auth_data['credentials'] and self.auth_data['identifier']

    @property
    def new_storage_id(self):
        """Return the id used to identify the storage in the config."""
        return self.storage_id or "{}_{}".format(self.storage.storage_name, time.time())

    @property
    def display_name(self):
        """Return the name used to represent the storage to the user."""
        return determine_csp_display_name(config=self.client_config,
                                          sp_type=self.storage.storage_name,
                                          display_name=self.storage.storage_display_name)

    @property
    def sp_dir(self):
        """Return the local path to which this storage syncs."""
        return os.path.join(self.client_config.sync_root, self.display_name)

    def _webserver_shutdown(self):
        """Check if the webserver is running and shut it down."""
        if self.oauth_webserver is not None:
            self.oauth_webserver.done_event.set()
            time.sleep(1)
            self.oauth_webserver = None

    def authenticate(self):
        """Authenticate the storage and return auth info."""

        if not self.storage:
            logger.debug('No such storage with name %s.', self.storage_name)
            return self.auth_data

        self.auth_data['storage'] = self.storage

        force_adding = self.storage_id is not None
        self.auth_data['new_storage_id'] = self.new_storage_id

        self._storage_authentication(force_adding=force_adding)


        if not self.completed:
            logger.info('Authentication failed. %s', self.storage)
            raise AuthenticationFailed

        logger.info('Adding storage with id %s (force:%s)',
                    self.auth_data['new_storage_id'], force_adding)

        self.auth_data['display_name'] = self.display_name

        # informing user of that account is being added
        cc.ipc_gui.displayNotification('Adding account {}'.format(self.auth_data['display_name']),
                                       'Your account will be available shortly')

        self.auth_data['sp_dir'] = self.sp_dir
        return self.auth_data

    def _storage_authentication(self, force_adding):
        """Execute the the correct authenthication process."""
        logger.debug('Performing Oauth authentication.')
        if (jars.BasicStorage.AUTH_CREDENTIALS in self.storage.auth) or \
            jars.BasicStorage.AUTH_CREDENTIALS_FIXED_URL in self.storage.auth:
            # non OAuth
            self._non_oauth_authentication(force_adding=force_adding)
        elif jars.BasicStorage.AUTH_OAUTH in self.storage.auth:
            #  OAuth
            self._oauth_authentication(force_adding=force_adding)
        else:
            logger.fatal("unknown authentication method")

    def _non_oauth_authentication(self, force_adding):
        """Authenticate using a url, username and password."""
        try:
            (warnings, credentials, identifier) = \
                self.storage.authenticate(url=self.url, username=self.username,
                                          password=self.password, verify=not self.ignore_warnings,
                                          force=force_adding)

            if warnings:
                # Are handled below see `except BaseException`
                raise Warning(*warnings)
            else:
                self.auth_data['credentials'] = credentials
                self.auth_data['identifier'] = identifier

        except jars.CertificateValidationError as error:
            logger.warning("The server's certificate for '%s' could not be verified!", self.url)
            raise ValueError("Server certificate is not trusted!")

        except HTTPError as error:
            status_code = error.response.status_code
            if status_code == 401 or status_code == 403:
                raise ValueError('Wrong credentials')
            elif status_code == 404:
                raise ValueError('Wrong URL')

        except AssertionError as error:
            raise ValueError(error.args)

        except BaseException:
            logger.info('Got error while adding account', exc_info=True)
            raise ValueError('Connection cannot be established')

    def _oauth_authentication(self, force_adding):
        """Authenticate using oauth.

        #. Open webserver.
        #. Wait for user to input credentials.
        #. Shut webserver down.
        #. Proceed with the authentication process with the log in results.
        """
        logger.debug('Performing oauth authentication.')
        grant_url = self.storage.grant_url()
        oauth_webserver = Webserver(grant_url.check_function)
        with oauth_webserver:
            # open the webbrowser for the user
            webbrowser.open(grant_url.grant_url)
            # wait till oauth timeout.
            logger.info('Launch oauth callback server with timeout: %s', self.OAUTH_TIMEOUT)
            oauth_webserver.server.done_event.wait(self.OAUTH_TIMEOUT)
            logger.info('Shutting down oauth callback server')
            # shut down the webserver anyways
            with contextlib.suppress(OSError):
                oauth_webserver.server.shutdown()
                oauth_webserver.server.socket.close()
                oauth_webserver.server.socket.shutdown(socket.SHUT_RDWR)
            if not oauth_webserver.server.result:
                logger.info("Timeout or stop, no account added")
                return
            logger.info("[OAUTH] %s callback_url:  %s",
                self.storage_name,
                oauth_webserver.server.result)
            (_, credentials, identifier) = \
                self.storage.authenticate(grant_url, oauth_webserver.server.result,
                                            force=force_adding)

            logger.info('[OAUTH] Adding credentials for %s', self.storage_name)
            self.auth_data['credentials'] = credentials
            self.auth_data['identifier'] = identifier


class Webserver():
    """Implementation of webserver with custom magic methods."""

    def __init__(self, url):
        self.server = None
        self.url = url

    def __enter__(self):
        """Start the webserver."""
        self.server = OAuthHTTPServer(self.url)
        server_thread = threading.Thread(target=self.server.serve_forever)
        server_thread.start()

    def __exit__(self, *args):
        """Shut down the webserver."""
        logger.info('Shutting down oauth callback server.')
        self.server.done_event.set()
        time.sleep(1)
        self.server = None
