'use strict';

// Define environment setup
const environment = process.defaultApp ? 'development' : 'production';

// Setup logging
const winston = require('winston');

winston.level = environment === 'production' ? 'warning' : 'debug';
const logger = winston;

const errorReporter = require('./utils/errorReporter'); // eslint-disable-line import/newline-after-import
errorReporter.init();
const shelloverlay = require('./shellIconOverlayIdentifiers.js');

// noinspection CodeAssistanceForCoreModules
const os = require('os');
// noinspection CodeAssistanceForCoreModules
const path = require('path');
const filepath = require('filepath');
const util = require('util');
const localStorage = require('electron-json-storage');

// electron imports
const electron = require('electron');

// importing electron components
const {
  BrowserWindow,
  Menu,
  Tray,
  app,
  dialog,
  ipcMain,
  systemPreferences,
} = electron;

// framework for autostarting the app at login on different plattforms
const AutoLaunch = require('auto-launch');

const co = require('co');
const { debounce } = require('lodash');
const { endsWith } = require('underscore.string');
const semver = require('semver');
const uuid = require('uuid/v4');

const autoUpdateHelper = require('./utils/autoUpdateHelper');
const getResponseFromRenderer = require('./rpcMethods/getResponseFromRenderer');
const moveWindow = require('./utils/moveWindow');
const service = require('./service');

// constants for determining the OS
const isWindows = process.platform === 'win32';
const isMac = os.platform() === 'darwin';

// checking if windows 10 or newer
let isWindows10OrNewer = false;
if (isWindows) {
  const mayorWinRelease = os.release().split('.')[0];
  if (parseInt(mayorWinRelease, 10) >= 10) {
    isWindows10OrNewer = true;
  }
}

// on windows, caches and cookies shall not be stored in %appdata% as this is
// roamed -> we set these paths
if (isWindows) {
  app.setPath('appData', process.env.LOCALAPPDATA);
}

// setting userData to electron subdir in appdata to keep things clean
app.setPath(
  'userData',
  path.join(app.getPath('appData'), app.getName(), 'electron')
);

// root path of the electron app
const ROOT_PATH = path.join(__dirname, '..');

// path to assets (images etc.)
const ASSETS_PATH = path.join(ROOT_PATH, 'assets');

// IDs of pages (=views) of the app
const PAGE_FILE_LIST = 'PAGE_FILE_LIST';
const PAGE_LOGIN = 'PAGE_LOGIN';
const WIN_SHELLEXT_SYNCED_NAME = '   CrossCloudSynced';

// mapping of state of the application to icon name
const STATE_ICON_MAPPING = {
  synced: 'idle',
  syncing: 'busy',
  paused: 'paused',
  offline: 'broken',
  indexing: 'busy',
};

// sizes of the menubar window (normal and extended - for selective sync dialog)
const MENUBAR_SIZES = {
  normal: {
    width: 360,
    height: 300,
  },
  expanded: {
    width: 360,
    height: 450,
  },
};

// Because we can't use a transparent window on ms windows (because of problems
// with blinking) we change its size and position manually in this file.
const WINDOWS_EXTRA_PADDING = 4;

// global variables
let globalTray;
let globalWindow;
let globalBalloonActionPath = '';

// should the menubar window be expanded? true if the selective sync dialog
// is showed
let isMenubarExpanded = false;

// configuration telling the electron app which features to enable for the
// user -> this is required to serve different configurations to different
// customers without having to change the sync core all the time
let featureConfig;

let isCoreStarted = false;

// On windows, if the menubar is already showed and a user clicks in the icon
// in the toolbar the `blur` event is invoked before the tray `clicked` event
// and the window is blinking. Create a debounced hiding function to force
// changed order and to have a possibility to cancel the hiding.
const hideDebouncedTime = isWindows ? 200 : 0;
const hideDebounced = debounce(
  () => {
    globalWindow && globalWindow.hide();
  },
  hideDebouncedTime,
  { leading: false, trailing: true }
);

// sends commands to the web-window
function sendToWidget(eventName, data) {
  globalWindow.webContents.send(eventName, data);
}

// dummy menu is necessary to make copy and paste possible under windows.
app.on('ready', () => {
  // defining menu supporting copy and paste and corresponding shortcuts
  const copyPasteMenu = [
    {
      label: '',
      submenu: [
        { label: '', accelerator: 'CmdOrCtrl+C', selector: 'copy:' },
        { label: '', accelerator: 'CmdOrCtrl+V', selector: 'paste:' },
      ],
    },
  ];
  // setting menu for the application -> this will enable copy and paste in
  // the app which would otherwise not be possible under macOS
  Menu.setApplicationMenu(Menu.buildFromTemplate(copyPasteMenu));
});

function registerWindowsOverlay() {
  logger.info('registering components');
  return Promise.all([
    shelloverlay.registerWindowsShellOverlay(
      WIN_SHELLEXT_SYNCED_NAME,
      '{75EC2AF1-C1A5-4CCD-96DC-2BB9FB2FE7F1}'
    ),
    shelloverlay.registerWindowsShellOverlay(
      '   CrossCloudUnSynced',
      '{C2B9C7C6-A5C1-49FD-9808-F03F2F697F6C}'
    ),
  ]);
}

const REGISTER_OVERLAY_EXTENSION = 'register_explorer_overlay';

function startRegisterWindowsOverlay() {
  if (isWindows) {
    const sudo = require('node-windows'); // eslint-disable-line global-require

    // escape app path - it won't work if there is a dot in the path otherwise
    const cmd = [`"${app.getPath('exe')}"`];

    if (app.getPath('exe').endsWith('electron.exe')) {
      cmd.push('.');
    }

    cmd.push(REGISTER_OVERLAY_EXTENSION);
    return new Promise(resolve => {
      sudo.elevate(cmd.join(' '), { detached: false }, resolve);
    });
  }

  return Promise.resolve();
}

const displayNotification = (title, description, imagePath, actionPath) => {
  // check if Windows 7 and display Bubble instead.
  if (isWindows) {
    const splitVersion = os.release().split('.');
    // TODO: replace `==` with `===` (ensure that `6` is a string here)
    // eslint-disable-next-line eqeqeq
    if (splitVersion[0] == 6 && splitVersion[1] <= 1) {
      if (actionPath) {
        globalBalloonActionPath = actionPath;
      }

      globalTray.displayBalloon({
        title,
        content: description,
        icon: imagePath,
      });

      return;
    }
  }

  sendToWidget('display-notification', {
    title,
    description,
    imagePath,
    actionPath,
  });
};

/**
 * adds the currently running crosscloud app to autostart items
 * This means that it ensures that crosscloud starts once the user logs in.
 */
function addCrosscloudToAutoStart() {
  // removing old autostart items if active and then adding new autostart item
  removeOldAutoStartItems().then(() => {
    // enable auto launch of app for all operating systems
    // only if production -> otherwise Electrop.app would be added, which we don't want
    if (environment === 'production') {
      // calling app api to set login item
      app.setLoginItemSettings({
        openAtLogin: true,
        path: getPathToApp(),
      });
    }
  });
}

/**
 * removes executable autostart entries written by prior crosscloud versions
 * returns a promise
 */
function removeOldAutoStartItems() {
  // creating node auto-launch element (this is how autolaunch was enabled in prior versions)
  const appLauncher = new AutoLaunch({
    name: 'CrossCloud',
    path: process.execPath.toString(),
  });

  // disabling item if enabled
  return appLauncher.isEnabled().then(enabled => {
    if (enabled) {
      // disabling item
      return appLauncher.disable();
    }
    return null;
  });
}

// main method
exports.main = function main() {
  if (process.argv[process.argv.length - 1] === REGISTER_OVERLAY_EXTENSION) {
    registerWindowsOverlay().then(app.quit, app.quit);
    return;
  }

  let logDir;
  if (isMac) {
    logDir = filepath
      .create(process.env.HOME, 'Library', 'Logs', 'CrossCloud')
      .mkdir();
  } else if (isWindows) {
    logDir = filepath.create(process.env.LOCALAPPDATA, 'CrossCloud').mkdir();
  } else {
    logDir = filepath.create(app.getPath('appData'), 'CrossCloud').mkdir();
  }
  const logfile = logDir.append('electron.log').toString();

  // adding parameters ot logfile such as max size, max number of files etc.
  winston.add(winston.transports.File, {
    filename: logfile,
    maxsize: 5 * 1024 * 1024,
    maxFiles: 5,
  });

  // getting a unique installation id used to identify users at update
  // (required for the auto updater)
  getUniqueId(uniqueInstallId => {
    logger.info(`Unique id: ${uniqueInstallId}`);

    // setting up updater
    autoUpdateHelper.init({
      displayNotification,
      uniqueInstallId,
    });
  });

  const shouldQuit = app.makeSingleInstance(() => {});
  if (shouldQuit) {
    app.quit();
    return;
  }

  app.on('ready', appReady);

  // closing the application -> if update is here -> installing it first
  app.on('will-quit', () => {
    logger.info('CrossCloud will quit.');
    // if autoUpdater is set and flag for updates available is set ->
    // installing update and restarting
    if (autoUpdateHelper.updateReady()) {
      autoUpdateHelper.applyUpdate();
    } else {
      // no updates here -> shutting down
      service.shutdown();
    }
  });

  process.on('unhandledRejection', (reason, promise) => {
    const errorInfo = reason.stack ? reason.stack : util.inspect(reason);
    logger.error(
      `Possibly Unhandled Rejection at: Promise ${promise}, reason: ${errorInfo}`
    );
  });

  // adding Crosscloud (current path) to autostart on mac
  // on Windows, this is done by the installer, on macOS we need
  // to do it at runtime
  if (isMac) {
    addCrosscloudToAutoStart();
  }
};

exports.featureConfig = {};
exports.displayNotification = displayNotification;

function appReady() {
  if (app.dock) {
    app.dock.hide();
  }
  globalTray = new Tray(getTrayIcon('synced'));
  globalTray.setToolTip('crosscloud');

  globalWindow = new BrowserWindow({
    width: MENUBAR_SIZES.normal.width,
    height: MENUBAR_SIZES.normal.height,
    show: false,
    frame: false,
    alwaysOnTop: true,
    resizable: false,
    // don't make the window transparent on windows because of problems
    // with blinking after clicking the tray icon
    transparent: !isWindows,
    skipTaskbar: true,
  });

  const appVersion = app.getVersion();
  logger.info('Started version %s', appVersion);

  // parsing version id and getting concrete update channel (assuming release channel here)
  const ver = semver(appVersion);
  let channel = 'release';
  if (ver.prerelease.length) {
    channel = ver.prerelease[0];
  }

  logger.info('Update channel: %s', channel);

  // generate feature config from channel (determines what features will be activated)
  featureConfig = generateConfig(channel);
  exports.featureConfig = featureConfig;
  logger.info('Feature Configuration: %s', JSON.stringify(featureConfig));

  // window events
  globalWindow.on('show', () => {
    globalTray.setHighlightMode('always');
  });
  globalWindow.on('hide', () => {
    globalTray.setHighlightMode('never');
  });

  globalWindow.on('blur', hideDebounced);

  globalTray.on('click', toggleWindow);
  globalTray.on('double-click', toggleWindow);

  // configuring balloon behaviour of tray
  // setting callback for balloon click actions on menubar -> if a balloon
  // is displayed and clicked -> the path should open which is handled here
  globalTray.on('balloon-click', () => {
    logger.info(`balloon clicked with action path: ${globalBalloonActionPath}`);
    // action path can be set when displaying the balloon
    if (globalBalloonActionPath) {
      service.openPath([globalBalloonActionPath]);
      globalBalloonActionPath = '';
    }
  });

  // resetting the global action path if balloon closed
  globalTray.on('balloon-closed', () => {
    globalBalloonActionPath = '';
  });

  // enable right click menu of tray for windows that will allow to quit the application
  if (isWindows) {
    // adding new event listener for right click to tray menu -> pop up a menu
    globalTray.on('right-click', () => {
      // creating menu to show upon right click with event of quitting app
      const rightClickMenu = Menu.buildFromTemplate([
        {
          label: 'Quit',
          click: () => {
            app.quit();
          },
        },
      ]);

      // showing menu
      globalTray.popUpContextMenu(rightClickMenu);
    });
  }

  // registering handlers for callbacks from core
  service.addHandlers([
    {
      // display a notification
      name: 'displayNotification',
      args: ['notifications'],
      method: ({ notifications }) => {
        const notificationList = Array.isArray(notifications)
          ? notifications
          : [notifications];
        notificationList.forEach(
          ({ title, description, imagePath, actionPath }) => {
            displayNotification(title, description, imagePath, actionPath);
          }
        );
      },
    },
    {
      // display recently synced items in GUI
      name: 'itemsHaveCompletedSyncing',
      args: ['syncedItems'],
      method: ({ syncedItems }) => {
        sendToWidget('new-recently-synced', {
          items: syncedItems,
        });
      },
    },
    {
      // state of the app has changed
      name: 'appStateHasChanged',
      args: ['state', 'syncingItemsCount'],
      method: ({ state, syncingItemsCount }) => {
        sendToWidget('update-state', { appState: state, syncingItemsCount });
        updateTrayIcon(state);
      },
    },
    {
      // The state of the accounts which are allowed to be added has changed.
      name: 'updateAccountTypes',
      args: ['accountTypes'],
      method: ({ accountTypes }) => {
        sendToWidget('update-state', { accountTypes });
      },
    },
    {
      name: 'selectSyncPaths',
      args: ['accountId'],
      method: accountId => {
        showWindow();
        return getResponseFromRenderer(globalWindow, 'selectSyncPaths', {
          accountId,
        });
      },
    },
    {
      // account was successfully added by core
      name: 'accountHasBeenAdded',
      method: accountsChangedHandler,
    },
    {
      // account has been renamed in core
      name: 'accountRenamed',
      method: accountsChangedHandler,
    },
    {
      // account has been deleted in core
      name: 'accountDeleted',
      method: accountsChangedHandler,
    },
    {
      // some information (credentials, oauth token, metrics etc. )
      // of an // account have been updated by core
      name: 'accountsUpdated',
      args: ['accounts'],
      method: ({ accounts }) => {
        sendToWidget('update-state', { accounts });
      },
    },
    {
      // user has logged in
      name: 'userLoggedIn',
      method: () => {
        sendToWidget('update-state', {
          currentPage: PAGE_FILE_LIST,
          isLoggedIn: true,
        });
      },
    },
    {
      // could not login user
      name: 'userLogInFailed',
      args: ['errorMessage'],
      method: errorMessage => {
        sendToWidget('login-failed', { errorMessage });
      },
    },
    {
      // the account needs reauthentication (e.g. credential based and
      // password is no longer valid)
      name: 'reAuthenticateAccount',
      args: ['storage_name', 'storage_id', 'display_name'],
      method: authData => {
        sendToWidget('update-state', { reAuthData: authData });
        showWindow();
      },
    },
    {
      // the user has logged out
      name: 'userLoggedOut',
      method: () => {
        sendToWidget('update-state', {
          currentPage: PAGE_LOGIN,
          isLoggedIn: false,
        });
      },
    },
    {
      // show the dialog to approve another device key
      name: 'showApproveDeviceDialog',
      args: ['device_id', 'fingerprint'],
      method: ({ device_id, fingerprint }) => {
        // informing user
        displayNotification(
          'Approval Requested',
          'Another device has requested your access approval.',
          '',
          ''
        );

        // displaying dialog to approve device
        sendToWidget('show-approve-device-dialog', {
          deviceId: device_id,
          fingerPrint: fingerprint,
        });
      },
    },
    {
      // show the dialog to request the approval of another device
      name: 'showApproveDeviceRequestedDialog',
      args: ['device_id', 'fingerprint'],
      method: ({ device_id, fingerprint }) => {
        // informing user
        displayNotification(
          'Approval from another device required',
          'You need to approve this device from another device.',
          '',
          ''
        );

        // displaying dialog to request device approval
        sendToWidget('show-approve-device-request-dialog', {
          deviceId: device_id,
          fingerPrint: fingerprint,
        });
      },
    },
    {
      // core tells to hide pw dialog
      name: 'hidePasswordDialog',
      method: () => {
        sendToWidget('hide-password-dialog', {});
      },
    },
    {
      // tells the application to quit
      name: 'quit',
      method: () => {
        app.quit();
      },
    },
    {
      // informer of that the core has started
      name: 'coreHasStarted',
      method: () => {
        co(function*() {
          logger.info('Core has started.');
          const state = yield* getCurrentState();
          sendToWidget('replace-state', state);
        });
      },
    },
  ]);

  // once the renderer process has loaded -> get the current status from core
  ipcMain.on('loaded', event => {
    co(function*() {
      sendToWidget('start-loading', {});
      yield* updateAppState(event.sender);
      sendToWidget('stop-loading', {});
    });
  });

  ipcMain.on('login', (event, data) => {
    co(function*() {
      const loginResult = yield service.login([data.email, data.password]);
      if (loginResult.status === 'success') {
        sendToWidget('start-loading', {});
        yield* updateAppState(event.sender);
        sendToWidget('stop-loading', {});
      }
    });
  });

  ipcMain.on('logout', event => {
    co(function*() {
      yield service.logout();
      isCoreStarted = false;
      event.sender.send('update-state', { currentPage: PAGE_LOGIN });
    });
  });

  ipcMain.on('display-login', event => {
    event.sender.send('update-state', { currentPage: PAGE_LOGIN });
  });

  ipcMain.on('addAccount', (event, data) => {
    co(function*() {
      const response = yield service.addAccount([
        data.type,
        data.url,
        data.username,
        data.password,
        data.ignoreWarnings,
        data.accountId,
      ]);

      if (
        response &&
        (response.status === 'error' || response.status === 'warning')
      ) {
        event.sender.send('update-state', { addAccountResponse: response });
        return;
      }
      event.sender.send('account-added');
      yield* updateAccountList(event.sender);
    });
  });

  ipcMain.on('open-path', (event, data) => {
    service.openPath([data.path]);
  });

  ipcMain.on('approve-device', (event, data) => {
    service.approveDevice([data.deviceID, data.fingerPrint]);
  });

  ipcMain.on('decline-device', (event, data) => {
    service.declineDevice([data.deviceID, data.fingerPrint]);
  });

  ipcMain.on('start-app', (event, data) => {
    logger.info('starting app with data', data);
    service.startApp();
  });

  ipcMain.on('delete-account', (event, data) => {
    co(function*() {
      logger.info('removing account with id %s', data.accountId);

      yield service.deleteAccount([data.accountId]);
      logger.info(
        'updating account list after removing account with id %s',
        data.accountId
      );
      yield* updateAccountList(event.sender);
      logger.info(
        'updated account list after removing account with id %s',
        data.accountId
      );
    });
  });

  ipcMain.on('openSyncdir', () => {
    service.openSyncdir();
  });

  ipcMain.on('setSyncDir', () => {
    dialog.showOpenDialog({ properties: ['openDirectory'] }, paths => {
      if (paths && paths[0]) {
        service.setSyncDir([paths[0]]);
      }
    });
  });

  ipcMain.on('togglePausing', (event, data) => {
    const { shouldPause } = data;
    const method = shouldPause ? service.pause : service.resume;
    method();
  });

  ipcMain.on('udpateWidget', (event, data) => {
    sendToWidget('update-state', data);
  });

  ipcMain.on('enableWindowsOverlay', () => {
    logger.debug('enabling overlay');
    startRegisterWindowsOverlay().then(error => {
      logger.debug('done; checking state', error);
      setTimeout(() => {
        shelloverlay.isRegistered(WIN_SHELLEXT_SYNCED_NAME).then(active => {
          logger.debug('sending update', active);
          sendToWidget('update-state', { windowsOverlayEnabled: active });
        });
      }, 2000);
    });
  });

  ipcMain.on('rpc-proxy-request', (event, data) => {
    co(function*() {
      const { uid, method, args } = data;
      try {
        const result = yield service[method](args);
        event.sender.send('rpc-proxy-response', { uid, result });
      } catch (error) {
        event.sender.send('rpc-proxy-response', { uid, error });
      }
    });
  });

  ipcMain.on('toggleMenubarExpanded', (event, { expand }) => {
    isMenubarExpanded = expand;
    showWindow();
  });

  // reading local storage keys
  localStorage.keys((error, keys) => {
    if (error) throw error;

    for (const key of keys) {
      logger.info(`There is a key called: ${key}`);
    }
  });

  // if devtools env variable is set -> display developer tools for debugging
  if (process.env.CC_DEVTOOLS) {
    globalWindow.webContents.openDevTools({
      detach: true,
    });
  }

  // on windows so called messages should be supported
  // to enable a proper shutdown
  // https://github.com/electron/electron/blob/master/docs/api/browser-window.md
  if (isWindows) {
    const WM_CLOSE = 0x0010;
    const WM_QUERYENDSESSION = 0x0011;
    const WM_ENDSESSION = 0x0016;
    const messageHandler = () => {
      logger.info('Quitting via windows message');
      app.quit();
    };

    globalWindow.hookWindowMessage(WM_QUERYENDSESSION, messageHandler);
    globalWindow.hookWindowMessage(WM_ENDSESSION, messageHandler);
    globalWindow.hookWindowMessage(WM_CLOSE, messageHandler);
  }

  // if it is the first run and no shell extension is active start the registration
  if (featureConfig.firstRun && isWindows) {
    shelloverlay.isRegistered(WIN_SHELLEXT_SYNCED_NAME).then(enabled => {
      if (!enabled) {
        startRegisterWindowsOverlay();
      }
    });
  }

  globalWindow.loadURL(`file://${path.join(app.getAppPath(), 'index.html')}`);
}

// handler for changed accounts -> triggered by core
function accountsChangedHandler() {
  return co(function*() {
    yield* updateAccountList(globalWindow.webContents);
  });
}

function* getCurrentState() {
  let state;
  const isLoggedIn = yield service.isLoggedIn();
  if (isLoggedIn) {
    if (!isCoreStarted) {
      isCoreStarted = true;
      logger.info('starting app');
      yield service.startApp();
    }
    state = yield {
      accountTypes: service.getAccountTypes(),
      accounts: service.getAccounts(),
      appState: service.getAppState(),
      isLoggedIn,
      recentlySynced: service.getRecentlySyncedItems(),
      userEmail: service.getUserEmail(),
    };
  } else {
    state = {
      isLoggedIn,
    };
  }

  // additional data required for both logged-in and not logged-in cases
  Object.assign(state, {
    config: featureConfig,
  });

  // on windows we get this via the registry on other systems we never need it so it is allways true
  if (isWindows) {
    state.winOverlay = yield shelloverlay.isRegistered(
      WIN_SHELLEXT_SYNCED_NAME
    );
  } else {
    state.winOverlay = true;
  }

  state.currentPage =
    state.isLoggedIn || !state.config.showLoginPane
      ? PAGE_FILE_LIST
      : PAGE_LOGIN;
  logger.info('state: %s', JSON.stringify(state, null, '\t'));
  return state;
}

function getTrayIcon(_state) {
  let state = _state;
  state = STATE_ICON_MAPPING[state];
  const suffix =
    isWindows10OrNewer || systemPreferences.isDarkMode() ? '_white' : '';
  if (state === 'indexing') {
    state = 'syncing';
  }
  return path.join(ASSETS_PATH, `crosscloudstatus_${state}${suffix}.png`);
}

function updateTrayIcon(state) {
  const stateName = state || 'synced';
  const iconPath = getTrayIcon(stateName);
  globalTray.setImage(iconPath);
}

function* updateAccountList(target) {
  const accounts = yield service.getAccounts();
  target.send('update-state', { accounts, addAccountResponse: null });
}

function* updateAppState(target) {
  const state = yield* getCurrentState();
  const currentPage = state.isLoggedIn ? PAGE_FILE_LIST : PAGE_LOGIN;
  target.send('update-state', Object.assign(state, { currentPage }));
}

/**
 * returns a string representing the path to the .app or application started
 */
function getPathToApp() {
  // determine path to App
  let launchPath = filepath.create('/');
  const segments = filepath.create(process.execPath).split();
  let segmentIter = 0;
  let segment = '';
  do {
    segment = segments[segmentIter];
    launchPath = launchPath.append(segment);
    segmentIter += 1;
  } while (
    endsWith(segment.toLowerCase(), '.app') === false &&
    segmentIter < segments.length
  );
  return launchPath.toString();
}

function generateConfig(channel) {
  const config = {};
  config.name = channel;
  config.enabledStorages = [];
  config.showLoginPane = true;
  config.threadCount = 5;

  if (channel === 'faircheck') {
    config.enabledStorages = ['fairdocs'];
    config.showLoginPane = false;
    config.threadCount = 1;
  } else {
    config.enabledStorages = [
      'dropbox',
      'owncloud',
      'box',
      'gdrive',
      'onedrive',
      'nextcloud',
      'cifs',
      'onedrivebusiness',
      'office365groups',
    ];
    config.showLoginPane = true;
  }

  localStorage.has('notFirstRun', (error, hasKey) => {
    if (error) throw error;
    config.firstRun = !hasKey;
    localStorage.set('notFirstRun', { value: true });
  });

  return config;
}

// todo: promise
// delivers a unique id for the client instance -> used to e.g. tell clients
// apart when updating
function getUniqueId(callback) {
  localStorage.has('userId', (error, hasKey) => {
    if (error) throw error;

    if (hasKey) {
      localStorage.get('userId', (localError, data) => {
        if (localError) {
          throw localError;
        }
        callback(data.value);
      });
    } else {
      const uid = uuid();
      localStorage.set('userId', { value: uid }, localError => {
        if (localError) {
          throw error;
        }
      });
      callback(uid);
    }
  });
}

function toggleWindow() {
  if (globalWindow) {
    // Cancel debounced hiding window. It happens on windows if the user clicks
    // in the tray icon and the window is already showed. Look for hideDebounced
    // for explanation
    hideDebounced.cancel();
    globalWindow.isVisible() ? globalWindow.hide() : showWindow();
  }
}

function showWindow() {
  // determine size based on if extended or not
  let sizes = isMenubarExpanded ? MENUBAR_SIZES.expanded : MENUBAR_SIZES.normal;

  if (isWindows) {
    sizes = {
      width: sizes.width - 2 * WINDOWS_EXTRA_PADDING,
      height: sizes.height - 2 * WINDOWS_EXTRA_PADDING,
    };
  }

  // extra padding the window will be moved
  const extraPadding = isWindows ? WINDOWS_EXTRA_PADDING : 0;

  // setting new size of windows animated (macOS only)
  globalWindow.setSize(sizes.width, sizes.height, true);
  // moving window to right position
  moveWindow(globalWindow, globalTray, sizes, extraPadding);

  // display window
  globalWindow.show();
}
