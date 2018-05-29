'use strict';

const os = require('os');
const path = require('path');
const request = require('request');
const util = require('util');

// glob allows file pattern mathing in shell style
const glob = require('glob');
const { app } = require('electron');
const winston = require('winston');

const { EventEmitter } = require('events');
const fs = require('fs');
const { spawn } = require('child_process');

// prefix of all update artifacts that are downloaded
const TEMP_PREFIX = 'cc-updater-';

/**
 * checks for and performs update on any windows platform
 * @constructor
 */
function CCWindowsUpdater() {
  // iniitalising update feed url
  this.feedUrl = null;

  // delete all old downloads = matching prefix
  glob(path.join(os.tmpdir(), `${TEMP_PREFIX}*`), (er, files) => {
    for (const file of files) {
      winston.info(`deleting ${file}`);
      fs.unlink(file);
    }
  });
}

/**
 * setter for the update feed url
 * @param feedUrl the new feed url to set
 */
CCWindowsUpdater.prototype.setFeedURL = function(feedUrl) {
  this.feedUrl = feedUrl;
};

/**
 * method checks if updates are available (with the configured parameters)
 */
CCWindowsUpdater.prototype.checkForUpdates = function() {
  this.emit('checking-for-update');
  const updater = this;

  // checking feed url for updates
  request.get({ url: this.feedUrl, json: true }, (error, response, body) => {
    if (error) {
      updater.emit('error', error);
    } else {
      // 200 = update available -> this returns the url to download the update from (body.url)
      // TODO remove eslint disable and test
      // eslint-disable-next-line no-lonely-if
      if (response.statusCode === 200) {
        updater.emit('update-available');

        // preventing update when currently running app is not packaged.
        // We don't want to trigger updates
        // during development all the time...
        if (app.getPath('exe').endsWith('electron.exe')) {
          winston.info('not running as executable, not updating');
          return;
        }

        // if not dev -> downloading file to temp dir
        updater.downloadPath = path.join(
          os.tmpdir(),
          TEMP_PREFIX + body.url.split('/').pop()
        );
        request
          .get(body.url)
          .on('response', resp => {
            // actually starting update
            if (resp.statusCode === 200) {
              winston.info('downloading update');
              resp.pipe(fs.createWriteStream(updater.downloadPath));
              resp.on('error', err => {
                updater.emit('error', `Error while downloading: ${err}`);
              });
              // end is called if the stream is ended OR simply
              // closed -> this can cause problems
              resp.on('end', () => {
                updater.emit('update-downloaded');
              });
            } else {
              // anything else = error
              updater.emit(
                'error',
                `HTTP status ${resp.statusCode} while downloading`
              );
            }
          })
          .on('error', localError => {
            winston.log('error while downloading', localError);
            updater.emit('error', `HTTP status ${error} while downloading`);
          });
      } else if (response.statusCode === 204) {
        // 204 -> all up to date
        updater.emit('update-not-available');
      } else {
        // unknown status code -> do nothing
        winston.info('back from request', body, response.statusCode);
        updater.emit('error', `status Code: ${response.statusCode}`);
      }
    }
  });
};

/**
 * equivalent of the squirrel like quit and install
 * Starts the installation of any update available and quits
 */
CCWindowsUpdater.prototype.quitAndInstall = function() {
  // if update has been downloaded -> spawn installer detached and quit
  winston.info('Quit and install');
  if (this.downloadPath) {
    winston.info('Starting installer');
    winston.info(this.downloadPath);
    spawn(
      'msiexec',
      ['/i', this.downloadPath, '/log', 'MsiCrossCloudUpdate.log'],
      {
        detached: true,
        cwd: app.getPath('temp'),
      }
    );
  }
};

util.inherits(CCWindowsUpdater, EventEmitter);

module.exports.autoUpdater = new CCWindowsUpdater();
