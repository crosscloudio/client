/* eslint-disable global-require */

jest.useFakeTimers();

// Use mocks for modules invoking electron code
jest.mock('electron');
jest.mock('lodash');
jest.mock('../platformAutoUpdater');
jest.mock('../../service');

const FIVE_MINUTES_IN_MS = 5 * 60 * 1000;
const ONE_HOUR_IN_MS = 60 * 60 * 1000;
// a sample static value for uniqueInstallId
const UNIQUE_INSTALL_ID = '1234-5678';

describe('autoUpdateHelper', () => {
  // autoUpdateHelper and autoUpdater are singleton modules so don't import
  // them globally but per test
  let autoUpdateHelper;
  let autoUpdater;

  // a sample mock for `displayNotification` function
  let displayNotification;

  beforeEach(() => {
    jest.resetModules();
    autoUpdateHelper = require('../autoUpdateHelper');
    autoUpdater = require('../platformAutoUpdater');

    displayNotification = jest.fn();
    autoUpdateHelper.init({
      displayNotification,
      uniqueInstallId: UNIQUE_INSTALL_ID,
    });
  });

  afterEach(() => {
    autoUpdater.removeAllListeners();
  });

  it('should setup correct feed url', () => {
    expect(
      // eslint-disable-next-line no-underscore-dangle
      autoUpdater.__feedURL.startsWith(
        'https://update-2.crosscloud.me/updates/'
      )
    ).toBe(true);
    expect(
      // eslint-disable-next-line no-underscore-dangle
      autoUpdater.__feedURL.endsWith('?installId=1234-5678')
    ).toBe(true);
  });

  it('should check for updates on startup', () => {
    expect(autoUpdater.checkForUpdates).toHaveBeenCalledTimes(1);
  });

  it('should check for updates every hour', () => {
    expect(autoUpdater.checkForUpdates).toHaveBeenCalledTimes(1);
    jest.runTimersToTime(ONE_HOUR_IN_MS * 2);
    expect(autoUpdater.checkForUpdates).toHaveBeenCalledTimes(2);
    jest.runTimersToTime(ONE_HOUR_IN_MS * 3);
    expect(autoUpdater.checkForUpdates).toHaveBeenCalledTimes(5);
  });

  it('should submit next update check if an error happened', () => {
    autoUpdater.emit('error');
    expect(autoUpdater.checkForUpdates).toHaveBeenCalledTimes(1);
    jest.runTimersToTime(FIVE_MINUTES_IN_MS);
    expect(autoUpdater.checkForUpdates).toHaveBeenCalledTimes(2);
  });

  it('should throttle update checks in case of errors', () => {
    autoUpdater.emit('error');
    autoUpdater.emit('error');
    expect(autoUpdater.checkForUpdates).toHaveBeenCalledTimes(1);
    jest.runTimersToTime(FIVE_MINUTES_IN_MS);
    expect(autoUpdater.checkForUpdates).toHaveBeenCalledTimes(2);
    autoUpdater.emit('error');
    autoUpdater.emit('error');
    jest.runTimersToTime(FIVE_MINUTES_IN_MS * 3);
    expect(autoUpdater.checkForUpdates).toHaveBeenCalledTimes(3);
  });

  it('should stop checking for updates if there is already found one', () => {
    autoUpdater.emit('update-available');
    jest.runTimersToTime(ONE_HOUR_IN_MS * 5);
    expect(autoUpdater.checkForUpdates).toHaveBeenCalledTimes(1);
  });

  it('should display a notification if an update is downloaded', () => {
    autoUpdater.emit('update-downloaded');
    expect(displayNotification).toHaveBeenCalledTimes(1);
    expect(displayNotification.mock.calls[0][0]).toBe('Update Found');
  });

  it('should close the app if an update is downloaded', () => {
    const { app } = require('electron');
    const service = require('../../service');

    autoUpdater.emit('update-downloaded');
    jest.runOnlyPendingTimers();
    expect(app.quit).toHaveBeenCalledTimes(1);
    expect(service.shutdown).toHaveBeenCalledTimes(1);
  });

  describe('updateReady', () => {
    it('should return `false` if the update was not downloaded', () => {
      expect(autoUpdateHelper.updateReady()).toBe(false);
    });

    it('should return `true` if the update was downloaded', () => {
      autoUpdater.emit('update-downloaded');
      expect(autoUpdateHelper.updateReady()).toBe(true);
    });
  });

  describe('applyUpdate', () => {
    it('should do nothing if the update was not downloaded', () => {
      autoUpdateHelper.applyUpdate();
      expect(autoUpdater.quitAndInstall).not.toHaveBeenCalled();
    });

    it('quit the app and install the update if it was downloaded', () => {
      autoUpdater.emit('update-downloaded');
      autoUpdateHelper.applyUpdate();
      expect(autoUpdater.quitAndInstall).toHaveBeenCalledTimes(1);
    });
  });
});
