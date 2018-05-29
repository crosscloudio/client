"""
QT Client for internal debugging

This client implementation exists for the reason to debug and test crosscloud.
If it gets started with an argument this argument is used as a name for a virtual crosscloud
isntance, these instances have everything contained in ~/virtual-crosscloud/<name>.
"""
import contextlib
import logging
import os
import queue
import signal
import sys
import threading

import keyring
import pkg_resources
import PyQt5
import requests.exceptions
from keyrings.alt.file import PlaintextKeyring
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication

import cc.crypto
import cc.ipc_gui
import cc.settings_sync
import jars
from cc import config
from cc.client import Client, setup_logging
from utils import humanize_byte

try:
    import better_exceptions
except ImportError:
    logging.getLogger().info('unable to import better_exceptions, '
                             '`$pip install better_exceptions` for better exceptions')

# kill it with SIGINT/Ctr-C
signal.signal(signal.SIGINT, signal.SIG_DFL)

# never going to be productive code
# pylint: skip-file

logger = logging.getLogger(__name__)


back_queue = queue.Queue()


def add_to_back_queue(method, args, callback=None):
    back_queue.put((method, args))


cc.ipc_gui.rpc_object = add_to_back_queue


class LoginDialog(QtWidgets.QDialog):
    """Dialog used to log a user into the crosscloud backend."""

    def __init__(self, caption=None, url=None):
        logger.info('init login dialog')
        super().__init__()
        self.setMinimumWidth(400)
        self.setWindowTitle('CrossCloud')

        self.text_user_name = QtWidgets.QLineEdit(self)
        self.text_user_name.setPlaceholderText("username")
        self.text_password = QtWidgets.QLineEdit(self)
        self.text_password.setPlaceholderText("password")
        self.text_password.setEchoMode(QtWidgets.QLineEdit.Password)

        self.buttonLogin = QtWidgets.QPushButton('Login', self)
        self.buttonLogin.clicked.connect(self.close)
        layout = QtWidgets.QVBoxLayout(self)

        if caption is not None:
            self.caption = QtWidgets.QLabel(self)
            self.caption.setText(caption)
            layout.addWidget(self.caption)

        if url:
            self.text_url.setText(url)
            self.text_url.setDisabled(True)

        # layout.addWidget(self.text_url)
        layout.addWidget(self.text_user_name)
        layout.addWidget(self.text_password)
        layout.addWidget(self.buttonLogin)
        self.setLayout(layout)


class SyncLog(QtWidgets.QWidget):
    MAX_LOG_COUNT = 50

    def __init__(self, client):
        super().__init__()
        self.log_items = []
        self.client = client
        self.initUI()

    def initUI(self):
        """Add the tablewidget and set its size."""
        self.tableWidget = QtWidgets.QTableWidget()
        self.tableWidget.setRowCount(self.MAX_LOG_COUNT)
        self.tableWidget.setColumnCount(1)

        # Add box layout, add table to box layout and add box layout to widget
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addWidget(self.tableWidget)
        self.setLayout(self.layout)

        # Show widget
        self.show()

    def update_log(self, new_items):
        """Populate the log with new items and move older items down."""
        new_items = [self.format_item(item) for item in new_items]
        new_items.extend(self.log_items)
        self.log_items = new_items[:self.MAX_LOG_COUNT]
        for idx, log_item in enumerate(self.log_items):
            self.tableWidget.setItem(idx, 0, QtWidgets.QTableWidgetItem(log_item))

    def format_item(self, item):
        """Format the output on one item of the sync log.

        :param item: information about the sync_event ie.: path, time and operationType
                     see cc.ipc.gui.on_task_acked for more details.
        :type item: dict
        """
        template = '@ {time}   {operationType:^10.10}:    <{joined_path}>'
        return template.format(joined_path='/'.join(item['path']), **item)


class Menu(QtWidgets.QMenu):
    """The Menu of the client, which contains basic functionality for interacting with crosscloud.

    :param instance_name: The name which is displayed in the first menu item. This is usefull when
                          using multiple clients during testing.
    :param client: The QtClient object with which the menu interacts.
    :type instance_name: str
    :type client: QtClient

    """

    def __init__(self, instance_name, client):
        super().__init__()
        self.client = client

        # Add a title entry to the menu with the instance_name
        self.addAction(instance_name).setEnabled(False)
        self.addSeparator()

        self.pause_action = self.addAction("Pause")
        self.status_action = self.addAction("Status")
        self.status_action.setEnabled(False)
        self.backend_action = self.addAction("Backend")
        self.open_folder_action = self.addAction("Open Folder")
        self.accounts_menu = self.addMenu('Accounts')

        self.exit_action = self.addAction("Exit")

        self.pause_action.triggered.connect(self.client.on_pause)
        self.open_folder_action.triggered.connect(self.client.open_sync_root)
        self.exit_action.triggered.connect(self.client.on_quit)

    def set_status(self, status_msg):
        """Set the text of the current status."""
        self.status_action.setText(status_msg)

    def rebuild_storage_menu(self):
        """Build the storage submenu,
        This submenu is used to add accounts and display currently configured storages.
        """
        if not self.client.is_started:
            # Accounts can't be added if user is not logged into the backend.
            return

        self.accounts_menu.clear()

        # accounts menu
        add_account_menu = self.accounts_menu.addMenu('Add')
        for storage_class in jars.registered_storages:
            action = add_account_menu.addAction(storage_class.storage_name)
            action.triggered.connect(self.client.on_add_storage)
            action.setData({'auth': storage_class.auth,
                            'name': storage_class.storage_name})

        self.accounts_menu.addSeparator()

        for storage in self.client.get_storages():
            account_menu = self.accounts_menu.addMenu(storage.get('display_name',
                                                                  storage['id']))

            account_menu.addAction(
                "{} of {} used".format(
                    humanize_byte(storage['total_space'] - storage['free_space']),
                    humanize_byte(storage['total_space'])
                )).setEnabled(False)
            remove_action = account_menu.addAction("Remove")
            remove_action.setData(storage)
            remove_action.triggered.connect(self.client.on_remove_account)

    def toggle_backend_menu(self):
        """Toggle wether the backend menu allows the user to log in or log out of the backend."""
        logger.info('toggle_backend_menu')
        if cc.settings_sync.get_token(config=self.client.config):
            logger.info('Token found -> switch to logout')
            self.backend_action.setText('logout (Backend)')
            self.backend_action.triggered.connect(self.client.backend_logout)
        else:
            logger.info('No token found -> switch to logout')
            self.backend_action.setText('login (Backend)')
            self.backend_action.triggered.connect(self.client.backend_login)


class QtClient(QtCore.QObject, Client):
    REFRESH_FREQ = 15

    def __init__(self, qapp, instance_name):
        logger.info('init QtClient')
        self.icons = {
            'synced': QtGui.QIcon(
                pkg_resources.resource_filename('cc.assets', 'icon_16_none.png')),
            'paused': QtGui.QIcon(
                pkg_resources.resource_filename('cc.assets', 'icon_16_pause.png')),
            'syncing': QtGui.QIcon(
                pkg_resources.resource_filename('cc.assets', 'icon_16_sync.png')),
            'indexing': QtGui.QIcon(
                pkg_resources.resource_filename('cc.assets', 'icon_16_sync.png'))
        }

        self.IPC_MAPPING = {'displayNotification': self.show_notification,
                            'userLoggedOut': self.backend_logout,
                            'showApproveDeviceRequestedDialog': self.show_request,
                            'showApproveDeviceDialog': self.show_approval,
                            'appStateHasChanged': self.update_app_state,
                            'accountDeleted': self.delete_account,
                            'itemsHaveCompletedSyncing': self.log_items}
        super().__init__()

        logger.info('Super initialized')
        self.is_started = self.startup()
        self.qapp = qapp

        self.tray_icon = QtWidgets.QSystemTrayIcon(self.icons['synced'], self.qapp)

        self.menu = Menu(instance_name=instance_name, client=self)

        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.activated.connect(self.on_open_menu)
        self.sync_log = SyncLog(client=self)

        # auto refresh setup
        self.tray_icon.show()
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.on_update)
        self.update_timer.start(1 / self.REFRESH_FREQ * 1000)

        self.menu.rebuild_storage_menu()
        self.menu.toggle_backend_menu()

    def log_items(self, item_lists):
        """Log a list of items to the sync_log window."""
        for item_list in item_lists:
            self.sync_log.update_log(item_list)

    def backend_logout(self, *args, **kwargs):
        """Logout from the backend and toggle the option in the menu."""
        cc.settings_sync.logout()
        self.menu.toggle_backend_menu()
        logger.info('User has been logged out.')

    def backend_login(self):
        """Login to the backend and toggle the backend option in the menu."""
        logger.info('Backend_login started')
        traceback.print_stack()
        login_dialog = LoginDialog(caption="Admin Console Login: " + instance_name)
        login_dialog.exec()

        try:
            cc.settings_sync.authenticate_user(username=login_dialog.text_user_name.text(),
                                               password=login_dialog.text_password.text(),
                                               config=self.config)
        except requests.exceptions.HTTPError as error:
            logger.info('backend_login failed')
            if error.response.status_code == 401:
                QtWidgets.QMessageBox.critical(None, "Wrong Credentials",
                                               "please try again")
            else:
                raise error
        logger.info('backend_login successful')
        self.startup()
        self.menu.toggle_backend_menu()

    def on_remove_account(self):
        """React to the removal of an account."""
        storage = self.sender().data()
        self.remove_storage(storage['id'])
        self.menu.rebuild_storage_menu()

    def on_open_menu(self):
        """React to a click on the tray icon."""
        self.menu.rebuild_storage_menu()

    def on_add_storage(self):
        """React to a click to add a storage"""
        csp_type = self.sender().data()
        if 'AUTH_OAUTH' in csp_type['auth']:
            thread = threading.Thread(target=self.add_storage,
                                      args=(csp_type['name']), daemon=True)
            thread.start()
        else:
            if csp_type['name'] == 'faircheck':
                login_dialog = LoginDialog(caption='Faircheck Login',
                                           url='http://appstest.faircheck.at/appstest/'
                                               'fairdocs/owncloud')
            else:
                login_dialog = LoginDialog(caption='Login')
            login_dialog.exec()
            thread = threading.Thread(
                daemon=True,
                target=self.add_storage,
                args=(csp_type['name'],),
                kwargs=dict(url='https://owncloud.crosscloud.me',
                            username=login_dialog.text_user_name.text(),
                            password=login_dialog.text_password.text()))
            thread.start()

    def show_approval(self, device_id, fingerprint):
        """Show the dialog needed to approve a further device to access the user's account.

        :param device_id: The unique id of the device to be approved.
        :param fingerprint: The SHA-256 fingerprint of the device to approve
        :type device_id: str
        :type fingerprint: str
        """
        buttonReply = QtWidgets.QMessageBox.question(
            None, 'Device approval',
            "Do you want to approve the device {} with the fingerprint {}".format(device_id,
                                                                                  fingerprint),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No)
        if buttonReply == QtWidgets.QMessageBox.Yes:
            cc.settings_sync.confirm_device_approval(device_id=device_id,
                                                     public_key_fingerprint=fingerprint)
        else:
            cc.settings_sync.confirm_device_declination(device_id=device_id,
                                                        public_key_fingerprint=fingerprint)

    def show_request(self, device_id, fingerprint):
        """Display to the user that this device must be aproved by another."""
        buttonReply = QtWidgets.QMessageBox.question(
            None, 'Device needs to be approved',
            "This device ({}) needs to be approved ({})".format(device_id, fingerprint),
            QtWidgets.QMessageBox.Retry | QtWidgets.QMessageBox.Cancel,
            QtWidgets.QMessageBox.Retry)
        if buttonReply == QtWidgets.QMessageBox.Retry:
            self.startup()

    def on_update(self):
        """Process calls from the ipc if possible."""
        self._process_ipc_call()

        if not self.is_started:
            self._set_status(status_msg='Not logged in', state='synced')

    def _set_status(self, state, status_msg):
        """Update the status on all relevant parts of the ui."""
        self.menu.set_status(status_msg)
        self.tray_icon.setToolTip(status_msg)
        self.tray_icon.setIcon(self.icons[state])

    def update_app_state(self, state, syncingItemsCount, **kwargs):
        """Set the state of the ui."""
        if syncingItemsCount:
            status_msg = 'Syncing {} items'.format(syncingItemsCount)
        elif state == 'paused':
            status_msg = 'Paused'
            self.pause_action.setText('Resume')
        else:
            status_msg = 'Synced'
        self._set_status(state, status_msg)

    def delete_account(self, **kwargs):
        """React to the deletion of an account.

        This currently needs to be implemented to pass due to a hack in how the client updates the
        node ui.
        """
        # logger.info('### delete: %s', kwargs)
        pass

    def _process_ipc_call(self):
        """Pop a single ipc call from the queue and process it if avaliable."""

        with contextlib.suppress(queue.Empty):
            ipc_call, args = back_queue.get_nowait()
            try:
                if isinstance(args, dict):
                    self.IPC_MAPPING[ipc_call](**args)
                else:
                    self.IPC_MAPPING[ipc_call](args)
            except KeyError as error:
                logger.debug(error)
                logger.warning('UNKNOWN gui callback: %s, args=%s', ipc_call, args)

    def on_quit(self, _):
        """React to a click of the quit menu item."""
        self.shutdown()
        self.update_timer.stop()
        self.qapp.exit()
        os._exit(0)

    def on_pause(self):
        """React to a click on the pause sync button."""
        if self.is_paused:
            self.resume()
        else:
            self.pause()

    def show_notification(self, notifications):
        """Display a notificatio to the user."""
        try:
            for notifcation in notifications[0]:
                self.tray_icon.showMessage(notifcation['title'], notifcation['description'])
        except BaseException:
            logger.exception('could not show notification')


def main(instance_name):
    try:
        setup_logging()
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        client = QtClient(app, instance_name)
        app.exec()
    except BaseException as ex:
        logger.exception("Crashed in Qt Loop")


def qt_exception_handler(exctype, value, traceback):
    logger.error('problem in qt handler', exc_info=(exctype, value, traceback))
    sys.__excepthook__(exctype, value, traceback)


def setup_virtual_cc(virtual_name):
    """ to have multiple instances running at the same time """
    virtual_dir = os.path.join(os.path.expanduser('~'), 'virtual-crosscloud', virtual_name)
    config.log_dir = os.path.join(virtual_dir, 'log')
    config.sync_root = os.path.join(virtual_dir, 'sync_root')
    config.config_dir = os.path.join(virtual_dir, 'config')
    config.cache_dir = os.path.join(virtual_dir, 'cache')
    config.private_key_path = os.path.join(virtual_dir, 'private.pem')
    config.public_key_path = os.path.join(virtual_dir, 'public.pub')
    config.lock_file = os.path.join(virtual_dir, 'lock_file')
    config.config_file = os.path.join(config.config_dir, 'config.ini')

    plaintext = PlaintextKeyring()
    plaintext.file_path = os.path.join(config.config_dir, 'keyring.ini')
    keyring.set_keyring(plaintext)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        setup_virtual_cc(sys.argv[1])
        instance_name = sys.argv[1]
    else:
        instance_name = '<DEFAULT_INSTALL>'

    sys.excepthook = qt_exception_handler
    main(instance_name)
