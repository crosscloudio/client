// getting autoupdater. NOTE: on MACOS, this uses the default electron squirrel
// updater, on WINDOWS, this is a custom updater using MSI installers!
// NOTE: be careful here -> if you mess it up this kills the updater!!!
// A logic cut into a separate module for easy mocking
let autoUpdater;

if (process.platform === 'darwin') {
  autoUpdater = require('electron').autoUpdater; // eslint-disable-line global-require
} else {
  autoUpdater = require('../winUpdater.js').autoUpdater; // eslint-disable-line global-require
}

module.exports = autoUpdater;
