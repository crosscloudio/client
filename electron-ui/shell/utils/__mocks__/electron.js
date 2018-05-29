const packageJson = require('../../../package.json');

module.exports = {
  app: {
    getVersion() {
      return packageJson.version;
    },
    quit: jest.fn(),
  },
};
