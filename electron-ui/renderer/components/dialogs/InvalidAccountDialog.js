import React, { PropTypes } from 'react';
import { ipcRenderer } from 'electron';

import BaseDialog from './BaseDialog';
import Button from '../common/Button';

const STYLES = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
  },
  info: {
    paddingLeft: 25,
    paddingRight: 25,
    fontSize: 11,
  },
};

export default class InvalidAccountDialog extends React.Component {
  static propTypes = {
    onAddCredentialsAccount: PropTypes.func.isRequired,
    reAuthData: PropTypes.object,
  };

  constructor(props, context) {
    super(props, context);
    this.state = {};
  }

  componentDidMount() {
    this.state = {};
  }

  componentWillUnmount() {}

  handleSubmitClick = () => {
    const { reAuthData } = this.props;

    if (reAuthData.auth_type === 'AUTH_CREDENTIALS') {
      this.props.onAddCredentialsAccount(
        reAuthData.storage_name,
        reAuthData.storage_id
      );
    } else {
      ipcRenderer.send('addAccount', {
        type: reAuthData.storage_name,
        accountId: reAuthData.storage_id,
      });
    }

    ipcRenderer.send('udpateWidget', { reAuthData: null });
    this.hide();
  };

  hide = () => {
    this.dialog.hide();
  };

  show = () => {
    this.dialog.show();
  };

  render() {
    const submitAction = (
      <Button
        label="Re-add"
        onClick={this.handleSubmitClick}
        style={STYLES.button}
      />
    );

    let dspName = '';
    if (this.props.reAuthData) {
      dspName = this.props.reAuthData.display_name;
    }
    const message = `Your account ${dspName} was invalidaded. Please add the account again.`;

    return (
      <BaseDialog
        actions={[submitAction]}
        ref={dialog => {
          this.dialog = dialog;
        }}
        title="Invalid Account"
      >
        <div style={STYLES.container}>
          <p style={STYLES.info}>
            {message}
          </p>
        </div>
      </BaseDialog>
    );
  }
}
