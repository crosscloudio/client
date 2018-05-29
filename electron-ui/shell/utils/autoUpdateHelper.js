const fs = require('fs');
const os = require('os');
const path = require('path');

const { app } = require('electron');
const logger = require('winston');
const { throttle } = require('lodash');

// Getting autoupdater for the platform the app is running.
// A separate module for easy mocking
const autoUpdater = require('./platformAutoUpdater');
const service = require('../service');

// NOTE: be careful here -> if you mess it up this kills the updater!!!

// url to the update server (same for mac and win)
const UPDATE_SERVER = 'https://update-2.crosscloud.me';

class AutoUpdateHelper {
  constructor() {
    // flag indicating if an update is ready to install. The update process:
    // 1) it is checked for updates at startup and every 4 hours after that
    // 2) if an update is available -> it is downloaded, a notification is displayed
    // to the user and the core is shutdown
    // 3) when the core dies -> the electron app dies as well and "will-quit" is
    // called -> in will quit, we need to decide whether just to quit or install the
    // update and quit -> this flag dies the job
    this.updateReadyToInstall = false;

    // variable for the unique installation id used to identify users at update
    this.uniqueInstallId = '';

    // setInterval id for checking updates
    this.intervalCookie = null;

    // A throttled function for checking updates - it will be invoked at most
    // once every 5 minutes.
    // It should be invoked in two places:
    // - `setUpUpdater` function - in one hour interval (checks will be done every hour
    // if there was no errors during previous checks)
    // - `error` handler for `autoUpdater` - a next check will be submitted
    // if the previous one was unsuccessful (but no often than once every 5 minutes)
    this.internalCheckForUpdates = throttle(() => {
      logger.info(`checking for updates ${new Date()}`);

      // gets the version of the app (version ID used for updating etc.)
      const appVersion = app.getVersion();
      // setting update url for auto updater
      autoUpdater.setFeedURL(
        getUpdateFeedURL(appVersion, this.uniqueInstallId)
      );
      autoUpdater.checkForUpdates();
    }, 5 * 60 * 1000); // do the update check at most once every 5 minutes
  }

  // Sets up the auto updater. It takes an object with the following props
  // as an argument:
  // * displayNotification - a function for displaying notification
  // * uniqueInstallId - a unique string of the installation
  init({ displayNotification, uniqueInstallId: uid }) {
    this.uniqueInstallId = uid;

    // Disable updater on Mac if the user running the app doesn’t have rights
    // to the app folder.
    // NOTE: the following code won't run in jest tests (process.resourcesPath
    // is undefined there)
    if (process.platform === 'darwin' && process.resourcesPath) {
      const appBundlePath = path.resolve(
        path.dirname(process.resourcesPath),
        '..'
      );
      try {
        fs.accessSync(
          appBundlePath,
          fs.constants.X_OK | fs.constants.W_OK // eslint-disable-line no-bitwise
        );
      } catch (error) {
        logger.error(
          "Current user doesn't have write access to the app folder. Disabling updater"
        );
        return;
      }
    }

    // for debugging and testing purposes let the install_id be overwritten by an env variable
    if (process.env.CC_INSTALL_ID) {
      this.uniqueInstallId = process.env.CC_INSTALL_ID;
    }

    autoUpdater.addListener('error', error => {
      logger.error('Update error', error);
      // error while downloading -> submit next check
      this.internalCheckForUpdates();
    });

    autoUpdater.addListener('update-available', () => {
      // stop the updater
      clearInterval(this.intervalCookie);
      // cancel the throttled check invocation
      this.internalCheckForUpdates.cancel();
      logger.info('Update available');
    });

    autoUpdater.addListener('checking-for-update', () => {
      logger.info('Checking for update :)');
    });

    autoUpdater.addListener('update-not-available', () => {
      logger.info('Update not available');
    });

    autoUpdater.addListener('update-downloaded', () => {
      logger.info('Update downloaded');

      // setting flag that update was downloaded
      this.updateReadyToInstall = true;

      // shutting down core and the app
      // setTimeout is used to make the notification visible
      setTimeout(() => {
        app.quit();
        service.shutdown();
      }, 1000);
      displayNotification(
        'Update Found',
        'Installing an update for CrossCloud and restarting soon.',
        '',
        ''
      );
    });

    // defining default update interval of 1 hour = 60 * 60 * 1000 ms!
    let updateInterval = 60 * 60 * 1000;

    // checking if update interval environment variable has been passed and setting value if so
    if (
      process.env.CC_UPDATE_POLL_TIME &&
      process.env.CC_UPDATE_POLL_TIME > 0
    ) {
      updateInterval = process.env.CC_UPDATE_POLL_TIME;
    }

    // scheduling an update check every hour
    this.intervalCookie = setInterval(
      this.internalCheckForUpdates,
      updateInterval
    );

    // actually check for the updates
    this.internalCheckForUpdates();
  }

  // Check if there is an update ready to install
  updateReady() {
    return !!(autoUpdater && this.updateReadyToInstall);
  }

  // Install an update if there is downloaded one
  applyUpdate() {
    if (this.updateReady()) {
      autoUpdater.quitAndInstall();
    }
  }
}

// constructs the update feed url used in the autoupdater
function getUpdateFeedURL(appVersion, uniqueInstallId) {
  // getting architecture of current system
  let arch = os.arch();
  if (os.platform() === 'win32') {
    arch = 'x64';
  }

  // creating base feedurl
  let feedUrl = `${UPDATE_SERVER}/updates/${os.platform()}_${arch}/${appVersion}`;

  // if user unique id determined (done at startup), setting it
  if (uniqueInstallId !== '') {
    feedUrl = `${feedUrl}?installId=${uniqueInstallId}`;
  }

  logger.info(`Determined feed URL: ${feedUrl}`);
  return feedUrl;
}

module.exports = new AutoUpdateHelper();
