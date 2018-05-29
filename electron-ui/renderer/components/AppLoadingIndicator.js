import CircularProgress from 'material-ui/lib/circular-progress';
import React from 'react';

import { SECONDARY_COLOR } from '../styles/constants';

const STYLES = {
  container: {
    position: 'relative',
    display: 'flex',
    width: '100%',
    height: '100%',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'white',
  },
  logo: {
    position: 'absolute',
    top: '50%',
    left: '50%',
    width: 40,
    height: 40,
    transform: 'translate(-50%, -50%)',
  },
};

export default function AppLoadingIndicator() {
  return (
    <div style={STYLES.container}>
      <CircularProgress color={SECONDARY_COLOR} size={2.5} />
      <img src="assets/logo_black.svg" style={STYLES.logo} alt="logo" />
    </div>
  );
}
