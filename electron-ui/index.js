'use strict';

// eslint-disable-next-line global-require
if (require('./shell/utils/squirrelStartup')) {
  return;
}

const main = require('./shell/main').main;

main();
