import React, { PropTypes } from 'react';
import { ipcRenderer } from 'electron';

import Avatar from 'material-ui/lib/avatar';
import Fingerprint from 'material-ui/lib/svg-icons/action/fingerprint';
import { white, black } from 'material-ui/lib/styles/colors';

import BaseDialog from './BaseDialog';
import Button from '../common/Button';

const STYLES = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    padding: 15,
    justifyContent: 'center',
    alignItems: 'center',
  },
  button: {
    marginLeft: 8,
    marginBottom: 8,
  },
  subheader: {
    marginBottom: 8,
    fontSize: 14,
  },
  topIcon: {
    // borderStyle: 'solid',
    // borderWidth: '2px',
  },
  iconStyle: {
    width: 50,
    height: 50,
  },
  approveName: {
    fontSize: 12,
  },
  approveValue: {
    backgroundColor: '#C2C2C2',
    borderRadius: 12,
    paddingTop: 5,
    paddingBottom: 5,
    paddingLeft: 15,
    paddingRight: 15,
    overflow: 'auto',
    wordBreak: 'break-all',
    fontSize: 12,
    fontWeight: 'bold',
    fontFamily: 'monospace',
  },
};

export default class RequestDeviceApprovalDialog extends BaseDialog {
  static propTypes = {
    deviceId: PropTypes.string,
    fingerPrint: PropTypes.string,
  };

  handleRetryClick = () => {
    ipcRenderer.send('start-app', {});
    ipcRenderer.send('toggleMenubarExpanded', { expand: false });
    this.dialog.hide();
  };

  handleLogoutClick = () => {
    // remote.app.quit();
    ipcRenderer.send('toggleMenubarExpanded', { expand: false });
    ipcRenderer.send('logout');
  };

  show = () => {
    this.dialog.show();
    ipcRenderer.send('toggleMenubarExpanded', { expand: true });
  };

  render() {
    const actions = [
      <Button
        label="Check for Approval"
        onClick={this.handleRetryClick}
        style={{
          ...STYLES.button,
        }}
      />,
    ];

    return (
      <BaseDialog
        cancelText="Logout"
        onCancel={this.handleLogoutClick}
        actions={actions}
        title=""
        ref={dialog => {
          this.dialog = dialog;
        }}
      >
        <div style={STYLES.container}>
          <Avatar
            icon={<Fingerprint style={STYLES.iconStyle} />}
            size={70}
            color={black}
            backgroundColor={white}
            style={STYLES.topIcon}
          />

          <p style={STYLES.subheader}>
            The approval of another device is required to proceed. Please
            approve from another device and make sure to compare the values
            below.
          </p>

          <div>
            <p style={STYLES.approveName}>Device ID:</p>
            <div style={STYLES.approveValue}>
              {this.props.deviceId}
            </div>
          </div>

          <div>
            <p style={STYLES.approveName}>Fingerprint:</p>
            <div style={STYLES.approveValue}>
              {this.props.fingerPrint}
            </div>
          </div>
        </div>
      </BaseDialog>
    );
  }
}
