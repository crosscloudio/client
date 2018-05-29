import React, { PropTypes } from 'react';

import { SECONDARY_COLOR } from '../../styles/constants';

const STYLES = {
  button: {
    boxSizing: 'border-box',
    height: 30,
    padding: '0 16px',
    fontFamily: 'Roboto, sans-serif',
    fontSize: 10,
    fontWeight: 'bold',
    letterSpacing: 0,
    textTransform: 'uppercase',
    color: 'white',
    background: '#9e9e9e',
    border: 0,
    borderRadius: 2,
    outline: 0,
    boxShadow: '0 1px 6px rgba(0,0,0,0.12), 0 1px 4px rgba(0,0,0,0.12)',
  },
  inner: {
    display: 'flex',
    width: '100%',
    height: '100%',
    alignItems: 'center',
    justifyContent: 'center',
  },
  large: {
    height: 36,
    fontSize: 12,
  },
  small: {
    height: 30,
    fontSize: 10,
  },
  secondary: {
    color: SECONDARY_COLOR,
    background: 'white',
  },
};

export default function Button(props) {
  const { label, large, secondary, style, ...otherProps } = props;
  return (
    <button
      style={{
        ...STYLES.button,
        ...(secondary ? STYLES.secondary : {}),
        ...(large ? STYLES.large : {}),
        ...style,
      }}
      {...otherProps}
    >
      <span style={STYLES.inner}>
        {label}
      </span>
    </button>
  );
}

Button.propTypes = {
  label: PropTypes.string.isRequired,
  large: PropTypes.bool,
  secondary: PropTypes.bool,
  style: PropTypes.object,
};
