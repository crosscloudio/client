'use strict';

const { createService } = require('./rpc');

module.exports = createService({
  requests: [
    'startApp',
    'approveDevice',
    'declineDevice',
    'getAppState',
    'getAccountTypes',
    'isLoggedIn',
    'getUserEmail',
    'login',
    'logout',
    'addAccount',
    'renameAccount',
    'getAccounts',
    'deleteAccount',
    'openPath',
    'openSyncdir',
    'getSyncdir',
    'setSyncDir',
    'getRecentlySyncedItems',
    'getSelectedSyncPaths',
    'setSelectedSyncPaths',
    'getStorageChildren',
    'pause',
    'resume',
    'shutdown',
  ],
});
