'use strict';

const electron = require('electron');
const logger = require('winston');

module.exports = function moveWindow(window, tray, menubarSize, extraPadding) {
  // From https://github.com/mike-schultz/materialette/blob/master/index.js
  // MIT licensed
  //
  // Determine orientation.
  let orientation = 'top-right';
  let x = 0;
  let y = 0;

  const { screen } = electron;
  const taskbarHeight = process.platform === 'win32' ? 40 : 0;

  const screenBounds = screen.getDisplayNearestPoint(
    screen.getCursorScreenPoint()
  ).bounds;
  const trayBounds = tray.getBounds();

  // log with the `warning` level - should be saved in production logs
  logger.warn('Setting window position', {
    screenX: screenBounds.x,
    screenY: screenBounds.y,
    screenWidth: screenBounds.width,
    screenHeight: screenBounds.height,
    trayX: trayBounds.x,
    trayY: trayBounds.y,
    trayWidth: trayBounds.width,
    trayHeight: trayBounds.height,
  });

  const normalizedScreenWidth = screenBounds.width + screenBounds.x;
  const normalizedScreenHeight = screenBounds.height + screenBounds.y;
  const normalizedTrayX = trayBounds.x - screenBounds.x;
  const normalizedTrayY = trayBounds.y - screenBounds.y;
  // Orientation is either not on top or OS is windows.

  if (process.platform === 'win32') {
    if (normalizedTrayY > screenBounds.height / 2) {
      orientation =
        normalizedTrayX > screenBounds.width / 2
          ? 'bottom-right'
          : 'bottom-left';
    } else {
      orientation =
        normalizedTrayX > screenBounds.width / 2 ? 'top-right' : 'top-left';
    }
  } else if (process.platform === 'darwin') {
    orientation = 'top';
  }

  switch (orientation) {
    case 'top':
      x = Math.floor(
        trayBounds.x - menubarSize.width / 2 + trayBounds.width / 2
      );
      y = screenBounds.y + trayBounds.height;
      break;
    case 'top-right':
      x = normalizedScreenWidth - menubarSize.width - extraPadding;
      y = taskbarHeight + screenBounds.y + extraPadding;
      break;
    case 'bottom-left':
      x = taskbarHeight + screenBounds.x + extraPadding;
      y = normalizedScreenHeight - menubarSize.height - extraPadding;
      break;
    case 'bottom-right':
      y =
        normalizedScreenHeight -
        menubarSize.height -
        taskbarHeight -
        extraPadding;
      x = normalizedScreenWidth - menubarSize.width - taskbarHeight;
      break;
    case 'top-left':
    default:
      x = taskbarHeight + screenBounds.x;
      y = taskbarHeight + screenBounds.y + extraPadding;
  }

  // Normalize any out of bounds
  // maxX and maxY account for multi-screen setups where x and y are
  // the coordinate across multiple screens.
  const maxX = screenBounds.width + screenBounds.x;
  const maxY = screenBounds.height + screenBounds.y;
  x = x > maxX ? maxX - menubarSize.width : x;
  y = y > maxY ? maxY - menubarSize.height : y;

  window.setPosition(x, y);
};
