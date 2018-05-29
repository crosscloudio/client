import EventEmitter from 'events';

import { ipcRenderer } from 'electron';

const redirectedRpcEmitter = new EventEmitter();

class Resolver {
  constructor(uid) {
    this.uid = uid;
  }

  respondWith(result) {
    ipcRenderer.send('redirected-rpc-response', {
      uid: this.uid,
      result,
    });
  }

  respondWithError(error) {
    ipcRenderer.send('redirected-rpc-response', {
      uid: this.uid,
      error,
    });
  }
}

ipcRenderer.on('redirected-rpc-request', (event, data) => {
  const { uid, method, params } = data;
  const resolver = new Resolver(uid);
  redirectedRpcEmitter.emit(method, resolver, params);
});

export default redirectedRpcEmitter;
