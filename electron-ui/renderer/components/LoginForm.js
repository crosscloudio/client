import React, { PropTypes } from 'react';
import { ipcRenderer, shell } from 'electron';
import TextField from 'material-ui/lib/text-field';
import CircularProgress from 'material-ui/lib/circular-progress';

import { SECONDARY_COLOR } from '../styles/constants';
import Button from './common/Button';

const STYLES = {
  form: {
    display: 'flex',
    flexDirection: 'column',
  },
  button: {
    marginTop: 20,
    background: SECONDARY_COLOR,
  },
  input: {
    fontSize: 12,
    color: 'black',
  },
  linkGroup: {
    marginTop: 15,
    marginBottom: 8,
    display: 'flex',
    justifyContent: 'space-between',
  },
  link: {
    WebkitAppearance: 'none',
    padding: 0,
    margin: 0,
    cursor: 'default',
    fontFamily: 'Arial, sans-serif',
    fontSize: 12,
    fontWeight: 'inherit',
    lineHeight: 'inherit',
    textDecoration: 'none',
    color: 'black',
    background: 'none',
    border: 0,
    outline: 0,
  },
  progress: {
    position: 'relative',
    display: 'flex',
    height: '15px',
    width: '100%',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'white',
  },
};

export default class LoginForm extends React.Component {
  static propTypes = {
    onLogin: PropTypes.func.isRequired,
  };

  constructor(props, context) {
    super(props, context);
    this.state = {
      email: '',
      password: '',
      isLoading: false,
      errorMessage: '',
    };
  }

  componentDidMount() {
    ipcRenderer.on('login-failed', this.loginFailed);
  }

  componentWillUnmount() {
    ipcRenderer.removeAllListeners(['login-failed']);
  }

  onKeyDown = event => {
    const code = event.keyCode || event.which;
    if (code === 13) {
      this.handleLoginClick();
    }
  };

  handleHelp(event) {
    event.preventDefault();
    shell.openExternal('https://crosscloud.io/support');
  }

  handleForgotPassword(event) {
    event.preventDefault();
    shell.openExternal('https://admin.crosscloud.io/forgot-password');
  }

  handleRegister(event) {
    event.preventDefault();
    shell.openExternal('https://admin.crosscloud.io/register');
  }

  handleChange(field, event) {
    this.setState({
      [field]: event.target.value,
    });
  }

  handleLoginClick = () => {
    const { email, password } = this.state;
    this.props.onLogin(email, password);
    this.setState({
      isLoading: true,
      errorMessage: '',
    });
  };

  loginFailed = (event, data) => {
    this.setState({
      errorMessage: data.errorMessage,
    });
    this.setState({
      isLoading: false,
    });
  };

  handleTextFieldClick = () => {
    this.disableErrorMessage();
  };

  disableErrorMessage() {
    this.setState({
      errorMessage: '',
    });
  }

  renderLoadingIndicator() {
    if (!this.state.isLoading) return null;

    return <CircularProgress color={SECONDARY_COLOR} size={0.4} />;
  }

  render() {
    const { email, password, errorMessage } = this.state;

    return (
      <div style={STYLES.form}>
        <TextField
          floatingLabelText="Email"
          onChange={// eslint-disable-line react/jsx-no-bind
          this.handleChange.bind(this, 'email') // eslint-disable-line react/jsx-no-bind
          }
          onClick={this.handleTextFieldClick}
          onKeyDown={this.onKeyDown}
          style={{
            ...STYLES.input,
            marginTop: -10,
          }}
          value={email}
        />
        <TextField
          floatingLabelText="Password"
          onChange={// eslint-disable-line react/jsx-no-bind
          this.handleChange.bind(this, 'password') // eslint-disable-line react/jsx-no-bind
          }
          onClick={this.handleTextFieldClick}
          onKeyDown={this.onKeyDown}
          errorText={errorMessage}
          style={{
            ...STYLES.input,
            marginTop: -16,
            marginBottom: 13,
          }}
          type="password"
          value={password}
        />
        <div style={STYLES.progress}>
          {this.renderLoadingIndicator()}
        </div>
        <Button
          label="Login"
          large
          onClick={this.handleLoginClick}
          style={STYLES.button}
        />

        <div>
          <div style={STYLES.linkGroup}>
            <button onClick={this.handleHelp} style={STYLES.link}>
              Help
            </button>
            <div>
              <button onClick={this.handleForgotPassword} style={STYLES.link}>
                Forgot Password
              </button>
              <span> | </span>
              <button onClick={this.handleRegister} style={STYLES.link}>
                Register
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
