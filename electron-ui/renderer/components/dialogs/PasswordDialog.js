import React, { PropTypes } from 'react';
import TextField from 'material-ui/lib/text-field';
import { ipcRenderer } from 'electron';

import BaseDialog from './BaseDialog';
import Button from '../common/Button';

const STYLES = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 40,
  },
  button: {
    marginLeft: 8,
    marginBottom: 8,
  },
  input: {
    width: 240,
    fontSize: 12,
  },
};

export default class PasswordDialog extends React.Component {
  static propTypes = {
    passwordRequestUid: PropTypes.string,
  };

  constructor(props, context) {
    super(props, context);
    this.state = {
      password: '',
    };
  }

  componentDidMount() {
    ipcRenderer.on('hide-password-dialog', this.hide);
  }

  componentWillUnmount() {
    ipcRenderer.off('hide-password-dialog', this.hide);
  }

  onKeyDown = event => {
    const code = event.keyCode || event.which;
    if (code === 13) {
      this.handleSubmitClick();
    }
  };

  handleCancel = () => {
    const { passwordRequestUid } = this.props;
    ipcRenderer.send('password-response', {
      error: 'Rejected',
      passwordRequestUid,
    });
    this.setState({
      password: '',
    });
  };

  handleSubmitClick = () => {
    const { passwordRequestUid } = this.props;
    const { password } = this.state;
    if (!password) {
      return;
    }

    ipcRenderer.send('password-response', {
      password,
      passwordRequestUid,
    });
    this.setState({
      password: '',
    });
  };

  handleInputChange(field, event) {
    this.setState({
      [field]: event.target.value,
    });
  }

  hide = () => {
    this.dialog.hide();
  };

  show = () => {
    this.dialog.show();
  };

  render() {
    const { password } = this.state;
    const submitAction = (
      <Button
        label="Submit"
        onClick={this.handleSubmitClick}
        style={STYLES.button}
      />
    );

    return (
      <BaseDialog
        actions={[submitAction]}
        onCancel={this.handleCancel}
        ref={dialog => {
          this.dialog = dialog;
        }}
        title="Encryption Password is required"
        cancelText="Quit"
      >
        <div style={STYLES.container}>
          <TextField
            floatingLabelText="Password"
            onEnterKeyDown={this.handleSubmitClick}
            onChange={// eslint-disable-line react/jsx-no-bind
            this.handleInputChange.bind(this, 'password') // eslint-disable-line react/jsx-no-bind
            }
            onKeyDown={this.onKeyDown}
            style={{
              ...STYLES.input,
              marginTop: -16,
              marginBottom: 20,
            }}
            type="password"
            value={password}
          />
        </div>
      </BaseDialog>
    );
  }
}
