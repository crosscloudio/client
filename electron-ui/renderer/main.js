import os from 'os';

import React from 'react';
import ReactDOM from 'react-dom';
import injectTapEventPlugin from 'react-tap-event-plugin';
import { ipcRenderer } from 'electron';

import App from './containers/App';

if (process.platform === 'win32') {
  const windowsVersion = os.release().split('.')[0];
  document.body.classList.add(`win${windowsVersion}`);
}

document.body.classList.add(process.platform);

injectTapEventPlugin();

const MAX_RECENTLY_SYNCED = 15;

let state = {
  initialized: false,
  isLoading: true,
  paused: false,
};

const render = () => {
  ReactDOM.render(
    <App data={state} updateState={updateState} />,
    document.getElementById('app')
  );
};

function updateState(data) {
  state = {
    ...state,
    ...data,
  };

  render();
}

ipcRenderer.on('replace-state', (event, data) => {
  state = {
    initialized: true,
    isLoading: false,
    paused: state.paused,
    passwordRequestUid: state.passwordRequestUid,
    errorMessage: state.errorMessage,
    reAuthData: state.reAuthData,
    recentlySynced: [],
    config: state.config,
    ...data,
  };

  render();
});

ipcRenderer.on('start-loading', () => {
  updateState({
    isLoading: true,
  });
});

ipcRenderer.on('stop-loading', () => {
  updateState({
    isLoading: false,
  });
});

ipcRenderer.on('update-state', (event, data) => {
  updateState(data);
});

ipcRenderer.on('new-recently-synced', (event, data) => {
  const oldList = state.recentlySynced || [];
  let newList = [...data.items, ...oldList];
  newList = newList.slice(0, MAX_RECENTLY_SYNCED);
  updateState({
    recentlySynced: newList,
  });
});

ipcRenderer.on('display-notification', (event, data) => {
  const { title, description, imagePath, actionPath } = data;
  const notification = new Notification(title, {
    body: description,
    icon: imagePath,
  });
  if (actionPath) {
    notification.onclick = () => {
      ipcRenderer.send('open-path', { path: actionPath });
    };
  }
});

ipcRenderer.on('get-password', (event, data) => {
  const { uid, errorMessage } = data;
  updateState({
    passwordRequestUid: uid,
    errorMessage,
  });
});

render();
ipcRenderer.send('loaded');
