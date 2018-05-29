const { ipcMain } = require('electron');
const uuid = require('uuid/v4');

const defer = require('../utils/defer');

const pendingRequests = {};

ipcMain.on('redirected-rpc-response', (event, data) => {
  const { error, result, uid } = data;
  const deferred = pendingRequests[uid];

  if (!deferred) {
    return;
  }
  if (error) {
    deferred.reject(new Error(error));
    return;
  }

  deferred.resolve(result);
});

function getResponseFromRenderer(window, method, params) {
  const requestUid = uuid();
  const deferred = defer();
  pendingRequests[requestUid] = deferred;
  window.webContents.send('redirected-rpc-request', {
    uid: requestUid,
    method,
    params,
  });

  return deferred.promise;
}

module.exports = getResponseFromRenderer;
