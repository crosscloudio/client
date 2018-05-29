import { ipcRenderer, remote } from 'electron';

import createMenuTrigger from '../utils/createMenuTrigger';

export default createMenuTrigger('AddAccountTrigger', props => {
  const { Menu, MenuItem } = remote.require('electron');

  const config = props.config;

  const menu = new Menu();
  if (props.accountTypes) {
    props.accountTypes.forEach(accountType => {
      const menuItem = new MenuItem({
        label: accountType.display_name,
        click: () => {
          // 1) credentials account (with url input) -> calling handler
          if (accountType.auth[0] === 'AUTH_CREDENTIALS') {
            props.onAddCredentialsAccount(accountType.name);
            return;
            // 2) credentials account (with fixed url) -> calling handler
          } else if (accountType.auth[0] === 'AUTH_CREDENTIALS_FIXED_URL') {
            props.onAddCrendentialsFixedUrlAccount(accountType.name);
            return;
          }
          // 3) OAuth account -> direcly calling core to handle the authentication
          ipcRenderer.send('addAccount', { type: accountType.name });
        },
        enabled: accountType.enabled === true,
      });

      // checking that only enabled storages for this config are added
      if (
        accountType.name &&
        accountType.display_name &&
        config &&
        config.enabledStorages.indexOf(accountType.name) >= 0
      ) {
        menu.append(menuItem);
      }
    });
  }
  return menu;
});
