import { ipcRenderer } from 'electron';
import uuid from 'uuid/v4';

// TODO: move defer to a shared folder and unify all similar functions

function defer() {
  const deferred = {};
  deferred.promise = new Promise((resolve, reject) => {
    deferred.resolve = resolve;
    deferred.reject = reject;
  });

  return deferred;
}

const pendingRequests = Object.create(null);

ipcRenderer.on('rpc-proxy-response', (event, data) => {
  const { uid, error, result } = data;
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

export default {
  request(method, ...args) {
    const deferred = defer();
    const uid = uuid();
    pendingRequests[uid] = deferred;
    ipcRenderer.send('rpc-proxy-request', {
      uid,
      method,
      args,
    });
    return deferred.promise;
  },
};
