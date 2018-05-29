const path = require('path');
const { spawn } = require('child_process');

const { app } = require('electron');
const debug = require('debug')('electron-squirrel-startup');

let elevate;
try {
  elevate = require('node-windows').elevate; // eslint-disable-line global-require
} catch (error) {
  // empty
}

function run(command, args, done) {
  spawn(command, args, {
    detached: true,
  }).on('close', done);
}

function runUpdate(args, done) {
  const updateExe = path.resolve(
    path.dirname(process.execPath),
    '..',
    'Update.exe'
  );
  run(updateExe, args, done);
}

function runRegisterDll(cmdSwitch) {
  const dllPath = path.join(
    path.dirname(process.execPath),
    'resources',
    'app',
    'daemon',
    'prod',
    'CCShellExt_x64.dll'
  );
  elevate(`regsvr32.exe ${cmdSwitch} ${dllPath}`, {
    detached: true,
  });
}

function check() {
  if (process.platform === 'win32') {
    const cmd = process.argv[1];
    debug('processing squirrel command `%s`', cmd);
    const target = path.basename(process.execPath);

    if (cmd === '--squirrel-install' || cmd === '--squirrel-updated') {
      runUpdate([`--createShortcut=${target}`], app.quit);
      runRegisterDll('/s');
      return true;
    }
    if (cmd === '--squirrel-uninstall') {
      runUpdate([`--removeShortcut=${target}`], app.quit);
      runRegisterDll('/s /u');
      return true;
    }
    if (cmd === '--squirrel-obsolete') {
      app.quit();
      return true;
    }
  }
  return false;
}

module.exports = check();
