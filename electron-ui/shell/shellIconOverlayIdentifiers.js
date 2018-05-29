const REG_KEY =
  '\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\ShellIconOverlayIdentifiers\\';

const winston = require('winston');

function registerWindowsShellOverlay(identifier, clsid) {
  const Registry = require('winreg'); // eslint-disable-line global-require

  const regKey = new Registry({
    arch: 'x64',
    hive: Registry.HKLM,
    key: `${REG_KEY}${identifier}`,
  });

  const syncedEntryKey = new Promise((accept, error) => {
    winston.debug('syncedEntryKey');
    regKey.create(errorMessage => {
      errorMessage ? error(errorMessage) : accept();
    });
  });

  return syncedEntryKey.then(
    new Promise((accept, error) => {
      winston.debug('value', clsid);
      regKey.set('', Registry.REG_SZ, clsid, errorMessage => {
        errorMessage ? error(errorMessage) : accept();
      });
    })
  );
}

function isRegistered(identifier) {
  const Registry = require('winreg'); // eslint-disable-line global-require

  const regKey = new Registry({
    arch: 'x64',
    hive: Registry.HKLM,
    key: `${REG_KEY}${identifier}`,
  });

  return new Promise((accept, error) => {
    regKey.keyExists((err, exists) => {
      winston.info('exists ', exists);
      err ? error(err) : accept(exists);
    });
  });
}

module.exports = { registerWindowsShellOverlay, isRegistered };
