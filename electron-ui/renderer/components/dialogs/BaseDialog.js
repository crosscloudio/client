import MuiDialog from 'material-ui/lib/dialog';
import React, { PropTypes } from 'react';

import Button from '../common/Button';

const PLATFORM_MAC = process.platform === 'darwin';

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
};

const EMPTY_FUNCTION = () => {};

export default class BaseDialog extends React.Component {
  static propTypes = {
    actions: PropTypes.array,
    cancelText: PropTypes.string.isRequired,
    children: PropTypes.node.isRequired,
    onCancel: PropTypes.func.isRequired,
    onHide: PropTypes.func.isRequired,
    title: PropTypes.string.isRequired,
  };

  static defaultProps = {
    onCancel: EMPTY_FUNCTION,
    onHide: EMPTY_FUNCTION,
    cancelText: 'Cancel',
  };

  constructor(props, context) {
    super(props, context);
    this.state = {
      open: false,
    };
  }

  handleCancel = () => {
    this.hide();
    this.props.onCancel();
  };

  hide = () => {
    this.setState({
      open: false,
    });
    this.props.onHide();
  };

  show() {
    this.setState({
      open: true,
    });
  }

  render() {
    const { actions, children, title, cancelText, ...otherProps } = this.props;

    const cancelAction = (
      <Button
        label={cancelText}
        onClick={this.handleCancel}
        secondary
        style={STYLES.button}
      />
    );

    return (
      <MuiDialog
        actions={[cancelAction, ...actions]}
        actionsContainerStyle={{ height: 48 }}
        autoDetectWindowHeight={false}
        repositionOnUpdate
        bodyStyle={{ padding: 0 }}
        contentStyle={{ transform: 'translate3d(0px, 12px, 0px)' }}
        modal
        open={this.state.open}
        overlayStyle={{ top: PLATFORM_MAC ? 15 : 0, borderRadius: 5 }}
        title={title}
        titleStyle={{ paddingTop: 12, fontSize: 12 }}
        {...otherProps}
      >
        {children}
      </MuiDialog>
    );
  }
}
