import React, { PropTypes } from 'react';
import TextField from 'material-ui/lib/text-field';
import { ipcRenderer } from 'electron';

import BaseDialog from './BaseDialog';
import Button from '../common/Button';

const INITIAL_STATE = {
  type: '',
  variableUrl: true,
  url: '',
  username: '',
  password: '',
};

const STYLES = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
  },
  button: {
    marginLeft: 8,
    marginBottom: 8,
  },
  input: {
    width: 240,
    fontSize: 12,
  },
  responseMessage: {
    marginLeft: 5,
    marginRight: 5,
    fontSize: 10,
  },
};

export default class AddAccountDialog extends React.Component {
  static propTypes = {
    addAccountResponse: PropTypes.object,
    onCancel: PropTypes.func.isRequired,
  };

  constructor(props, context) {
    super(props, context);
    this.state = {
      ...INITIAL_STATE,
    };
  }

  componentDidMount() {
    this.state = {
      ...INITIAL_STATE,
    };
    ipcRenderer.on('account-added', this.hide);
  }

  componentWillUnmount() {
    ipcRenderer.off('account-added', this.hide);
  }

  handleSubmitClick = () => {
    const { addAccountResponse } = this.props;
    ipcRenderer.send('addAccount', {
      ...this.state,
      // ignore warning if there was one in the last response
      ignoreWarnings:
        addAccountResponse && addAccountResponse.status === 'warning',
    });
  };

  handleCancel = () => {
    this.props.onCancel();
  };

  handleHide = () => {
    this.setState({
      ...INITIAL_STATE,
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

  /**
   * shows the dialog considering the given parameters
   * @param url: the url to initially display in the url field (e.g. https://)
   */
  show = (accountType, variableUrl = true, defaultUrl = '') => {
    this.setState({ type: accountType, url: defaultUrl, variableUrl });
    this.dialog.show();
  };

  ignoreWarnings() {
    this.setState({ ignoreWarnings: true });
  }

  renderError() {
    const { addAccountResponse } = this.props;
    if (!addAccountResponse) {
      return null;
    }
    const color = addAccountResponse.status === 'warning' ? 'orange' : 'red';
    return (
      <div style={{ ...STYLES.responseMessage, color }}>
        {addAccountResponse.message}
      </div>
    );
  }

  renderInput(field, label, fieldType) {
    return (
      <TextField
        floatingLabelText={label}
        onChange={// eslint-disable-line react/jsx-no-bind
        this.handleInputChange.bind(this, field)}
        onEnterKeyDown={this.handleSubmitClick}
        style={{
          ...STYLES.input,
          marginTop: -21,
        }}
        type={fieldType}
        value={this.state[field]}
      />
    );
  }

  render() {
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
        onHide={this.handleHide}
        ref={dialog => {
          this.dialog = dialog;
        }}
        title="Add account"
      >
        <div style={STYLES.container}>
          {this.state.variableUrl && this.renderInput('url', 'URL')}
          {this.renderInput('username', 'Username/Email')}
          {this.renderInput('password', 'Password', 'password')}
          {this.renderError()}
        </div>
      </BaseDialog>
    );
  }
}
