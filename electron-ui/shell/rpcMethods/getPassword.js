const { ipcMain } = require('electron');
const uuid = require('uuid/v4');

const defer = require('../utils/defer');

const pendingRequests = {};

// TODO: replace with './getResponseFromRenderer' and 'redirectedRpc'
ipcMain.on('password-response', (event, data) => {
  const { error, password, passwordRequestUid } = data;
  const deferred = pendingRequests[passwordRequestUid];

  if (!deferred) {
    return;
  }
  if (error) {
    deferred.reject(new Error(error));
    return;
  }

  deferred.resolve(password);
});

function getPassword(window, errorMessage) {
  const passwordRequestUid = uuid();
  const deferred = defer();
  pendingRequests[passwordRequestUid] = deferred;
  window.webContents.send('get-password', {
    uid: passwordRequestUid,
    errorMessage,
  });

  return deferred.promise;
}

module.exports = getPassword;
