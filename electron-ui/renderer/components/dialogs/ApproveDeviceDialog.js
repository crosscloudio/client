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

/**
 * Dialog asking the user to approve another device based on other device id and public device key
 */
export default class ApproveDeviceDialog extends BaseDialog {
  static propTypes = {
    deviceId: PropTypes.string,
    fingerPrint: PropTypes.string,
  };

  /**
  * Called when the user clicks on approve
  */
  handleApproveClick = () => {
    // sending approve device event
    ipcRenderer.send('approve-device', {
      deviceID: this.props.deviceId,
      fingerPrint: this.props.fingerPrint,
    });
    // this is shown in expanded menu, so we need to shrink it down again
    ipcRenderer.send('toggleMenubarExpanded', { expand: false });
    // hiding dialog
    this.dialog.hide();
  };

  /**
  * Called when the user clicks on approve
  */
  handleDeclineClick = () => {
    // sending decline event
    ipcRenderer.send('decline-device', {
      deviceID: this.props.deviceId,
      fingerPrint: this.props.fingerPrint,
    });
    // this is shown in expanded menu, so we need to shrink it down again
    ipcRenderer.send('toggleMenubarExpanded', { expand: false });
    // hiding this dialog
    this.dialog.hide();
  };

  show = () => {
    this.dialog.show();
    ipcRenderer.send('toggleMenubarExpanded', { expand: true });
  };

  render() {
    const actions = [
      <Button
        label="Approve"
        onClick={this.handleApproveClick}
        style={STYLES.button}
      />,
    ];

    return (
      <BaseDialog
        cancelText="Decline"
        onCancel={this.handleDeclineClick}
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
            One of of your devices has requested approval. Please compare the
            values below with the ones on the device and accept or decline.
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
