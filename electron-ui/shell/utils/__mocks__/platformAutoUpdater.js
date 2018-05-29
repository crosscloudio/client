const { EventEmitter } = require('events');

class AutoUpdaterMock extends EventEmitter {
  constructor() {
    super();
    this.checkForUpdates = jest.fn();
    this.quitAndInstall = jest.fn();
  }

  setFeedURL(url) {
    this.__feedURL = url; // eslint-disable-line no-underscore-dangle
  }
}

module.exports = new AutoUpdaterMock();
