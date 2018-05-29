import React, { PropTypes } from 'react';
import { remote } from 'electron';

export default function createMenuTrigger(displayName, createMenu) {
  return class MenuTrigger extends React.Component {
    static displayName = displayName;
    static propTypes = {
      children: PropTypes.node.isRequired,
    };

    componentDidUpdate() {
      // ensure old menu is disposed if props were changed
      this.invalidateMenu();
    }

    componentWillUnmount() {
      this.invalidateMenu();
    }

    setupMenu() {
      this.invalidateMenu();
      this.menu = createMenu(this.props);
    }

    invalidateMenu() {
      this.menu && disposeMenu(this.menu);
      this.menu = null;
    }

    handleClick = () => {
      if (!this.menu) {
        // create a menu on demand to not create to many temporary menu objects
        // menu properties can be changes often
        this.setupMenu();
      }
      this.menu && this.menu.popup(remote.getCurrentWindow());
    };

    render() {
      return (
        <span onClick={this.handleClick}>
          {this.props.children}
        </span>
      );
    }
  };
}

// Dispose menu and submenus recursively to prevent memory leaks
// https://github.com/electron/electron/issues/9823
function disposeMenu(menu) {
  if (menu.items) {
    for (const item of menu.items) {
      if (item.submenu) {
        disposeMenu(item.submenu);
      }
      item.destroy && item.destroy();
    }
  }
  menu.destroy();
}
