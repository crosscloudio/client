import os from 'os';

import AppBar from 'material-ui/lib/app-bar';
import IconButton from 'material-ui/lib/icon-button';
import React, { PropTypes } from 'react';
import Toolbar from 'material-ui/lib/toolbar/toolbar';
import ToolbarGroup from 'material-ui/lib/toolbar/toolbar-group';
import { ipcRenderer, remote } from 'electron';

import { PRIMARY_COLOR } from '../styles/constants';
import AddAccountDialog from '../components/dialogs/AddAccountDialog';
import AddAccountTrigger from '../components/AddAccountTrigger';
import AppLoadingIndicator from '../components/AppLoadingIndicator';
import FileList from '../components/FileList';
import LoginForm from '../components/LoginForm';

import InvalidAccountDialog from '../components/dialogs/InvalidAccountDialog';
import SelectiveSyncDialog from '../components/dialogs/SelectiveSyncDialog';
import ApproveDeviceDialog from '../components/dialogs/ApproveDeviceDialog';
import RequestDeviceApprovalDialog from '../components/dialogs/RequestDeviceApprovalDialog';

import SettingsTrigger from '../components/SettingsTrigger';
import theme from '../styles/theme';

import './App.css';

// determines if current platform is mac
const PLATFORM_MAC = process.platform === 'darwin';
const CONTENT_BORDER = '1px solid rgba(158, 158, 158, 0.68)';

const BASE_ICON_BUTTON_STYLE = {
  width: 32,
  height: 32,
  padding: 8,
};

const STYLES = {
  app: {
    display: 'flex',
    height: '100vh',
    flexDirection: 'column',
  },
  appBarIconButton: {
    ...BASE_ICON_BUTTON_STYLE,
    marginTop: 8,
  },
  appBarLogo: {
    width: 10,
    height: 10,
    marginRight: 4,
  },
  fileListContainer: {
    display: 'flex',
    width: '100%',
    flex: 1,
    overflowY: 'auto',
    background: 'white',
    borderTop: CONTENT_BORDER,
    borderBottom: CONTENT_BORDER,
  },
  icon: {
    width: 16,
    height: 16,
    fill: 'gray',
  },
  iconHover: {
    width: 20,
    height: 20,
    fill: 'black',
  },
  contentLogo: {
    position: 'absolute',
    top: '53%',
    left: '50%',
    width: 100,
    height: 100,
    transform: 'translate(-50%, -50%)',
    opacity: 0.1,
  },
  contentAccounts: {
    position: 'absolute',
    bottom: 45,
    left: 27,
    height: 19,
  },
  contentSettings: {
    position: 'absolute',
    bottom: 45,
    right: 27,
    height: 19,
  },
  contentFolder: {
    position: 'absolute',
    top: 61,
    right: 29,
    height: 19,
  },
  contentStatus: {
    position: 'absolute',
    top: 61,
    left: 27,
    height: 16,
  },
  loginFormContainer: {
    display: 'flex',
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    background: 'white',
    borderTop: CONTENT_BORDER,
  },
  topArrowContainer: {
    position: 'absolute',
    width: '100%',
    height: 15,
  },
  topArrowBase: {
    position: 'absolute',
    bottom: '100%',
    left: '50%',
    width: 0,
    height: 0,
    border: 'solid transparent',
    pointerEvents: 'none',
  },
  topArrowLeft: {
    marginLeft: -11,
  },
  topArrowRight: {
    marginLeft: -10,
    borderBottomColor: PRIMARY_COLOR,
    borderWidth: 10,
  },
};

// styles for helper screen at the beginning (arrows etc.)
const HELP_MAC_STYLE_ACCOUNT = {
  position: 'absolute',
  bottom: 45,
  left: 27,
  height: 19,
};

const HELP_MAC_STYLE_SETTINGS = {
  position: 'absolute',
  bottom: 45,
  right: 27,
  height: 19,
};

const HELP_MAC_STYLE_FOLDER = {
  position: 'absolute',
  top: 61,
  right: 29,
  height: 19,
};

const HELP_MAC_STYLE_STATUS = {
  position: 'absolute',
  top: 61,
  left: 27,
  height: 16,
};

const HELP_WIN_STYLE_ACCOUNT = {
  position: 'absolute',
  bottom: 55,
  left: 37,
  height: 19,
};

const HELP_WIN_STYLE_SETTINGS = {
  position: 'absolute',
  bottom: 55,
  right: 40,
  height: 19,
};

const HELP_WIN_STYLE_FOLDER = {
  position: 'absolute',
  top: 61,
  right: 39,
  height: 19,
};

const HELP_WIN_STYLE_STATUS = {
  position: 'absolute',
  top: 61,
  left: 40,
  height: 16,
};

// General app styles (container, positions etc.) dependent on platform
const APP_MAC_STYLES = {
  height: 'calc(100vh - 15px)',
  marginTop: 15,
};

const APP_WIN_STYLES = {
  height: 'calc(100vh - 2px)',
  border: 'solid',
  borderColor: 'black',
  borderWidth: 1,
};

// configuring custom layout for windows versions above 7
if (process.platform === 'win32') {
  if (os.release().split('.')[0] >= 10) {
    APP_WIN_STYLES.boxShadow =
      'rgba(0, 0, 0, 0.156863) 0px 3px 10px, rgba(0, 0, 0, 0.227451) 0px 3px 10px';
    APP_WIN_STYLES.borderColor = '#1883d7';
  }
}

const APP_BAR_MAC_STYLES = {
  boxShadow: 'none',
  borderTopLeftRadius: 5,
  borderTopRightRadius: 5,
};

const APP_BAR_WIN_STYLES = {
  boxShadow: 'none',
  background: 'white',
};

const TITLE_LOGIN_STYLES = {
  fontSize: 12,
  color: 'black',
};

const TITLE_STATUS_STYLES = {
  fontSize: 12,
  textAlign: 'left',
  color: 'black',
};

const TOOL_BAR_MAC_STYLES = {
  height: 32,
  background: PRIMARY_COLOR,
};

const TOOL_BAR_WIN_STYLES = {
  height: 32,
  background: 'white',
};

// login id's to use for page identification
const PAGE_LOGIN = 'PAGE_LOGIN';
const PAGE_FILE_LIST = 'PAGE_FILE_LIST';

export default class App extends React.Component {
  // data is what to display, updateState what to trigger to update
  // the current state (page)
  static propTypes = {
    data: PropTypes.object.isRequired,
    updateState: PropTypes.func.isRequired,
  };

  static childContextTypes = {
    muiTheme: React.PropTypes.object,
  };

  constructor(props, context) {
    super(props, context);
    this.state = {};
  }

  getChildContext() {
    return {
      muiTheme: theme,
    };
  }

  componentDidMount() {
    const { data } = this.props;
    ipcRenderer.on('get-password', this.handleGetPassword);
    if (data.passwordRequestUid) {
      this.handleGetPassword();
    }

    // event handler for if approve device dialog shall be shown
    ipcRenderer.on('show-approve-device-dialog', this.handleShowApproveDialog);
    ipcRenderer.on(
      'show-approve-device-request-dialog',
      this.handleShowApprovalRequestDialog
    );
  }

  componentDidUpdate() {
    const { data } = this.props;

    // checking if we are authorized
    if (data.reAuthData) {
      this.handleInvalidAccount();
    }
  }

  componentWillUnmount() {
    ipcRenderer.off('get-password', this.handleGetPassword);

    // de-registering from this event
    ipcRenderer.off('show-approve-device-dialog', this.handleShowApproveDialog);
    ipcRenderer.off(
      'show-approve-device-request-dialog',
      this.handleShowApprovalRequestDialog
    );
  }

  getTitle() {
    if (this.isLoginPage()) {
      return 'Login';
    } else if (this.isLoading()) {
      return 'CROSSCLOUD';
    }

    if (this.isSyncing() && this.props.data.syncingItemsCount) {
      return `${this.props.data.syncingItemsCount} items syncing...`;
    } else if (this.isIndexing()) {
      return 'Getting file info...';
    } else if (this.isPaused()) {
      return 'Paused';
    } else if (this.isOffline()) {
      return 'No Connection. Trying to connect...';
    }
    return 'All files in sync';
  }

  handleAddAccountCancel = () => {
    // TODO: replace with mobx
    this.props.updateState({ addAccountResponse: null });
  };

  /**
   * handles adding a credential account with variable URL
   */
  handleAddCredentialsAccount = accountType => {
    // determining if we should pre fill our url
    let prefilledUrl = '';
    if (['owncloud', 'nextcloud'].indexOf(accountType) > -1) {
      prefilledUrl = 'https://';
    }

    // showing add account dialog with variable url
    this.addAccountDialog &&
      this.addAccountDialog.show(accountType, true, prefilledUrl);
  };

  /**
   * handles adding a credential account with fixed URL (by storage type)
   */
  handleAddCrendentialsFixedUrlAccount = accountType => {
    this.addAccountDialog && this.addAccountDialog.show(accountType, false);
  };

  handleInvalidAccount = () => {
    const dialog = this.invalidAccountDialog;
    if (dialog) {
      dialog.show();
    }
  };

  handleShowApproveDialog = (event, { deviceId, fingerPrint }) => {
    this.setState({ deviceId, fingerPrint }, () => {
      this.approvalDialog && this.approvalDialog.show();
    });
  };

  handleShowApprovalRequestDialog = (event, { deviceId, fingerPrint }) => {
    this.setState({ deviceId, fingerPrint }, () => {
      this.approvalRequestDialog && this.approvalRequestDialog.show();
    });
  };

  handleGetPassword = () => {
    this.passwordDialog && this.passwordDialog.show();
  };

  handleItemClick = path => {
    ipcRenderer.send('open-path', { path });
  };

  handleLogin = (email, password) => {
    ipcRenderer.send('login', { email, password });
  };

  handleOpenSyncdir = () => {
    ipcRenderer.send('openSyncdir');
  };

  handleSkipLogin = () => {
    ipcRenderer.send('skip-login');
  };

  handleQuit = () => {
    remote.app.quit();
  };

  isFileListPage() {
    return this.props.data && this.props.data.currentPage === PAGE_FILE_LIST;
  }

  isLoginPage() {
    return this.props.data && this.props.data.currentPage === PAGE_LOGIN;
  }

  isLoading() {
    return this.props.data.isLoading;
  }

  isPaused() {
    return this.props.data && this.props.data.appState === 'paused';
  }

  isLoggedIn() {
    return this.props.data && this.props.data.isLoggedIn;
  }

  isOffline() {
    return this.props.data && this.props.data.appState === 'offline';
  }

  isSyncing() {
    return this.props.data && this.props.data.appState === 'syncing';
  }

  isIndexing() {
    return this.props.data && this.props.data.appState === 'indexing';
  }

  togglePausing = () => {
    ipcRenderer.send('togglePausing', {
      shouldPause: !this.isPaused(),
    });
  };

  togglLoggedIn = () => {
    // deciding what to do based on current status of login
    if (this.isLoggedIn()) {
      // simply send logout
      ipcRenderer.send('logout');
    } else {
      // displaying login pages
      ipcRenderer.send('display-login');
    }
  };

  renderContent() {
    const { data } = this.props;
    if (data.isLoading) {
      return <AppLoadingIndicator />;
    }

    if (this.isFileListPage()) {
      if (data.recentlySynced && data.recentlySynced.length <= 0) {
        return (
          <div style={STYLES.fileListContainer}>
            <img
              alt=""
              style={STYLES.contentLogo}
              src="assets/logo_black.svg"
            />
            <img
              alt=""
              style={
                PLATFORM_MAC ? HELP_MAC_STYLE_ACCOUNT : HELP_WIN_STYLE_ACCOUNT
              }
              src="assets/add account.svg"
            />
            <img
              alt=""
              style={
                PLATFORM_MAC ? HELP_MAC_STYLE_SETTINGS : HELP_WIN_STYLE_SETTINGS
              }
              src="assets/settings.svg"
            />
            <img
              alt=""
              style={
                PLATFORM_MAC ? HELP_MAC_STYLE_FOLDER : HELP_WIN_STYLE_FOLDER
              }
              src="assets/open folder.svg"
            />
            <img
              alt=""
              style={
                PLATFORM_MAC ? HELP_MAC_STYLE_STATUS : HELP_WIN_STYLE_STATUS
              }
              src="assets/status.svg"
            />
          </div>
        );
      }

      // perparing recently synced variable
      const recentlySynced = data.recentlySynced ? data.recentlySynced : [];

      return (
        <div style={STYLES.fileListContainer}>
          <FileList files={recentlySynced} onItemClick={this.handleItemClick} />
        </div>
      );
    } else if (this.isLoginPage()) {
      return (
        <div style={STYLES.loginFormContainer}>
          <LoginForm onLogin={this.handleLogin} />
        </div>
      );
    }

    return null;
  }

  renderAppBar() {
    // setting left icon
    let leftIconImg;
    const showLeftIcon = !this.isLoading() && this.isFileListPage();

    if (this.isSyncing() || this.isIndexing()) {
      leftIconImg = (
        <img
          alt=""
          className="rotatingImage"
          style={STYLES.icon}
          src="assets/icon_sync.svg"
        />
      );
    } else if (this.isPaused()) {
      leftIconImg = (
        <img alt="" style={STYLES.icon} src="assets/icon_pause.svg" />
      );
    } else if (this.isOffline()) {
      leftIconImg = (
        <img
          alt=""
          className="rotatingImage"
          style={STYLES.icon}
          src="assets/icon_sync.svg"
        />
      );
    } else {
      leftIconImg = (
        <img alt="" style={STYLES.icon} src="assets/icon_check.svg" />
      );
    }

    let rightIconImg;
    let rightIconClickHandler;
    let showRightIcon = true;

    if (this.isLoggedIn() && !this.isLoading() && this.isFileListPage()) {
      rightIconClickHandler = this.handleOpenSyncdir;
      rightIconImg = (
        <img alt="" style={STYLES.icon} src="assets/icon_folder.svg" />
      );
    } else if (!this.isLoggedIn()) {
      rightIconClickHandler = this.handleQuit;
      rightIconImg = (
        <img alt="" style={STYLES.icon} src="assets/icon_cross.svg" />
      );
    } else {
      showRightIcon = false;
    }

    let leftIcon = <span style={{ display: 'none' }} />;
    if (showLeftIcon) {
      leftIcon = (
        <IconButton
          iconStyle={STYLES.icon}
          style={STYLES.appBarIconButton}
          disableTouchRipple
        >
          {leftIconImg}
        </IconButton>
      );
    }

    let rightIcon = <span style={{ display: 'none' }} />;
    if (showRightIcon) {
      rightIcon = (
        <IconButton
          iconStyle={STYLES.icon}
          onClick={rightIconClickHandler}
          style={STYLES.appBarIconButton}
        >
          {rightIconImg}
        </IconButton>
      );
    }

    return (
      <div>
        <AppBar
          iconElementLeft={leftIcon}
          iconElementRight={rightIcon}
          iconStyleRight={{
            marginLeft: 8,
          }}
          style={PLATFORM_MAC ? APP_BAR_MAC_STYLES : APP_BAR_WIN_STYLES}
          title={
            <span>
              {this.getTitle()}
            </span>
          }
          titleStyle={
            this.isFileListPage() && !this.isLoading()
              ? TITLE_STATUS_STYLES
              : TITLE_LOGIN_STYLES
          }
        />
      </div>
    );
  }

  renderToolbar() {
    const { data } = this.props;

    if (data.isLoading) {
      return null;
    }

    if (!this.isFileListPage() && data.config) {
      return null;
    }

    return (
      <Toolbar style={PLATFORM_MAC ? TOOL_BAR_MAC_STYLES : TOOL_BAR_WIN_STYLES}>
        <ToolbarGroup>
          <AddAccountTrigger
            accountTypes={data.accountTypes}
            onAddCredentialsAccount={this.handleAddCredentialsAccount}
            onAddCrendentialsFixedUrlAccount={
              this.handleAddCrendentialsFixedUrlAccount
            }
            config={data.config}
          >
            <IconButton
              iconStyle={STYLES.icon}
              style={{ ...BASE_ICON_BUTTON_STYLE, marginLeft: -16 }}
            >
              <img alt="" style={STYLES.icon} src="assets/icon_plus.svg" />;
            </IconButton>
          </AddAccountTrigger>
        </ToolbarGroup>
        <ToolbarGroup float="right">
          <SettingsTrigger
            accounts={data.accounts}
            onTogglePausingClicked={this.togglePausing}
            paused={this.isPaused()}
            config={data.config}
            loggedIn={data.isLoggedIn}
            loggedInUser={data.userEmail}
            windowsOverlayEnabled={data.winOverlay}
            onToggleLoginClicked={this.togglLoggedIn}
          >
            <IconButton
              iconStyle={STYLES.icon}
              style={{ ...BASE_ICON_BUTTON_STYLE, marginRight: -16 }}
            >
              <img alt="" style={STYLES.icon} src="assets/icon_settings.svg" />;
            </IconButton>
          </SettingsTrigger>
        </ToolbarGroup>
      </Toolbar>
    );
  }

  renderTopArrow() {
    if (!PLATFORM_MAC) {
      return null;
    }
    return (
      <div style={STYLES.topArrowContainer}>
        <div
          style={{
            ...STYLES.topArrowBase,
            ...STYLES.topArrowLeft,
          }}
        />
        <div
          style={{
            ...STYLES.topArrowBase,
            ...STYLES.topArrowRight,
          }}
        />
      </div>
    );
  }

  renderAddAccountDialog() {
    return (
      <AddAccountDialog
        addAccountResponse={this.props.data.addAccountResponse}
        onCancel={this.handleAddAccountCancel}
        ref={addAccountDialog => {
          this.addAccountDialog = addAccountDialog;
        }}
      />
    );
  }

  // renders the dialog to approve the device approval request from another device
  renderApproveDeviceDialog() {
    return (
      <ApproveDeviceDialog
        deviceId={this.state.deviceId}
        fingerPrint={this.state.fingerPrint}
        title={'Approve another device'}
        ref={approvalDialog => {
          this.approvalDialog = approvalDialog;
        }}
      />
    );
  }

  // renders the dialog to request device approval from another device
  renderRequestDeviceApprovalDialog() {
    return (
      <RequestDeviceApprovalDialog
        deviceId={this.state.deviceId}
        fingerPrint={this.state.fingerPrint}
        title={'Requesting device approval'}
        ref={approvalRequestDialog => {
          this.approvalRequestDialog = approvalRequestDialog;
        }}
      />
    );
  }

  renderInvalidAccountDialog() {
    return (
      <InvalidAccountDialog
        reAuthData={this.props.data.reAuthData}
        onAddCredentialsAccount={this.handleAddCredentialsAccount}
        ref={invalidAccountDialog => {
          this.invalidAccountDialog = invalidAccountDialog;
        }}
      />
    );
  }

  renderSelectiveSyncDialog() {
    return (
      <SelectiveSyncDialog
        ref={selectiveSyncDialog => {
          this.selectiveSyncDialog = selectiveSyncDialog;
        }}
      />
    );
  }

  render() {
    const style = {
      ...STYLES.app,
      ...(PLATFORM_MAC ? APP_MAC_STYLES : APP_WIN_STYLES),
    };

    return (
      <div style={style}>
        {this.renderTopArrow()}
        {this.renderAppBar()}
        {this.renderContent()}
        {this.renderToolbar()}
        {this.renderAddAccountDialog()}
        {this.renderApproveDeviceDialog()}
        {this.renderRequestDeviceApprovalDialog()}
        {this.renderInvalidAccountDialog()}
        {this.renderSelectiveSyncDialog()}
      </div>
    );
  }
}
