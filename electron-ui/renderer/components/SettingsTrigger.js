import { ipcRenderer, remote, shell } from 'electron';

import appEventBus from '../utils/appEventBus';
import createMenuTrigger from '../utils/createMenuTrigger';

export default createMenuTrigger('SettingsTrigger', props => {
  const { Menu } = remote.require('electron');

  // get only unique accounts
  const addedAccounts = new Set();

  if (props && props.accounts) {
    const accountsSubmenu = Object.keys(
      props.accounts
    ).reduce((result, accIndex) => {
      const account = props.accounts[accIndex];
      const accountId = account.id;

      if (accountId && addedAccounts.has(accountId) === false) {
        addedAccounts.add(accountId);

        result.push(
          {
            label: account.display_name,
          },
          {
            label: `   ${account.user_name}`,
            enabled: false,
          },
          {
            label: `   ${(account.size === 0
              ? 0
              : account.used / account.size * 100).toFixed(
              1
            )}% of ${(account.size / (1024 * 1024 * 1024)).toFixed(1)} GB used`,
            enabled: false,
          },
          {
            label: '   Selective Sync',
            click: () => {
              appEventBus.emit('selectSyncPaths', { accountId });
            },
          },
          {
            label: '   Remove Account',
            click: () => {
              ipcRenderer.send('delete-account', { accountId });
            },
          }
        );
      }
      return result;
    }, []);
    const accountMenu = !Object.keys(props.accounts).length
      ? {
          label: 'No Accounts Added',
          enabled: false,
        }
      : {
          label: 'Accounts',
          role: 'submenu',
          submenu: accountsSubmenu,
        };

    const menu = [accountMenu];
    menu.push({
      label: props.paused ? 'Resume Sync' : 'Pause Sync',
      click: () => {
        props.onTogglePausingClicked();
      },
    });

    menu.push({
      label: 'Change Sync Dir',
      click: () => {
        ipcRenderer.send('setSyncDir');
      },
    });
    menu.push({
      label: 'Help',
      click: () => {
        shell.openExternal('https://crosscloud.io/support');
      },
    });
    if (props.loggedIn != null) {
      menu.push({
        label: props.loggedIn ? 'Logout' : 'Login',
        click: () => {
          props.onToggleLoginClicked();
        },
      });
    }
    if (props.loggedInUser) {
      menu.push({
        label: props.loggedInUser,
        enabled: false,
      });
    }
    if (!props.windowsOverlayEnabled) {
      menu.push({
        label: 'Enable Overlays (admin privileges)',
        click: () => {
          ipcRenderer.send('enableWindowsOverlay');
        },
      });
    }

    menu.push({
      label: `Version ${remote.app.getVersion()}`,
      enabled: false,
      click: () => {
        shell.openExternal('https://crosscloud.io/support');
      },
    });

    menu.push({
      label: 'Quit',
      click: () => {
        remote.app.quit();
      },
    });

    return Menu.buildFromTemplate(menu);
  }

  return Menu.buildFromTemplate([]);
});
