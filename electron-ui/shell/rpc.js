'use strict';

const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { app } = require('electron');

const co = require('co');
const logger = require('winston');
const split = require('split');

const defer = require('./utils/defer');
const errorReporter = require('./utils/errorReporter');
const main = require('./main');
const timeout = require('./utils/timeout');

// how big the combined stderr could be?
// important, because out of memory error could happen otherwise
const COMBINED_STDERR_MAX_LENGTH = 4096; // 4 KB
// how long to wait for a child process to quit after sending `TERM` signal
// to it and before `KILL` signal
const FORCEFULLY_KILL_WAIT_MS = 20000;
// how often to send a `ping` request
const PING_INTERVAL = 2000;
// how long to wait for a response for `ping`
const PING_RESPONSE_WAIT_MS = 15000;
// how many times to try to restart the core before closing with an error
const MAX_RESTART_TRIES = 4;

const RPC_ERRORS = {
  PARSE: -32700,
  INVALID_REQUEST: -32600,
  METHOD_NOT_FOUND: -32601,
  PARAMS: -32602,
  INTERNAL: -32603,
};

const quitWithDelay = (errorCode, delay = 3000) => {
  // quit with delay (e.g. to give notifications some time)
  setTimeout(() => {
    // process.exit(errorCode);
    app.quit();
  }, delay);
};

const quitAppImmediatelly = () => {
  app.exit(1);
};

const quitWithErrorMessage = ({ code, signal, combinedStderr }) => {
  logger.debug('Quiting because of previous Core errors');

  const textReport = `Cannot start daemon.
Exit code: ${code}
Signal: ${signal}
Stderr:
${combinedStderr}`;

  Promise.all([
    new Promise(resolve => {
      main.displayNotification(
        'Oh Snap - CrossCloud cannot start',
        'Sorry! Our team has been notified and will look into this immediately.'
      );
      setTimeout(() => {
        resolve();
      }, 4000);
    }),
    new Promise(resolve => {
      errorReporter.capture(textReport, resolve);
    }),
  ]).then(quitAppImmediatelly, quitAppImmediatelly);
};

const DAEMON_BASE_PATH = path.join(__dirname, '..', 'daemon');
let daemonExecutable;
let daemonArgs;
let daemonEnv;
const productionExecutableName =
  process.platform === 'win32' ? 'CrossCloudSync.exe' : 'CrossCloudSync';
const productionExecutablePath = path.join(
  DAEMON_BASE_PATH,
  'prod',
  productionExecutableName
);
let hasProductionExecutable = false;

try {
  fs.accessSync(path.join(productionExecutablePath));
  hasProductionExecutable = true;
} catch (error) {
  hasProductionExecutable = false;
}

if (hasProductionExecutable) {
  // production config
  daemonExecutable = productionExecutablePath;
  daemonArgs = [];
} else if (process.env.DAEMON_EXEC) {
  // if passed by environment
  daemonExecutable = process.env.DAEMON_EXEC;
  daemonArgs = [path.join(__dirname, '..', '..', 'Core', 'cc', 'ipc_core.py')];
} else {
  // automatically for debug purposes
  daemonExecutable =
    process.platform === 'win32'
      ? '../Core/.venv/scripts/python'
      : '../Core/.venv/bin/python';
  daemonArgs = [path.join(__dirname, '..', '..', 'Core', 'cc', 'ipc_core.py')];
  daemonEnv = { PYTHONPATH: '../Core' };
}

let nextId = 1;
const pending = {};

const createService = options => {
  const requests = options.requests || [];
  const handlers = {};
  let daemon;
  let forcefullyKillTimeout;
  let healthCheckTimeout;

  // Which time are we trying to restart the daemon?
  // It's zeroed after a successful health check.
  let restartTryCounter = 0;
  // Are we waiting for the daemon restart? In that case we should ignore
  // (or postpone) requests.
  let isWaitingForRestart = false;

  const getDaemon = () => {
    if (isWaitingForRestart) {
      throw new Error('Waiting for the daemon restart');
    }

    if (daemon) {
      return daemon;
    }

    // Used to decide if the daemon should be restarted or the app
    // should be closed and error displayed for the user.
    // Set to `true` after a response to a `ping` request.
    let hadCorrectResponse = false;

    // Stderr before the first response  to a `ping` request.
    // Send to Sentry if the core cannot start.
    let combinedStderr = '';

    // clone daemonArgs because `--threads` arg would be added many times
    // in a case of restart otherwise
    const finalDaemonArgs = [...daemonArgs];
    finalDaemonArgs.push('--threads');
    finalDaemonArgs.push(main.featureConfig.threadCount);
    logger.debug(
      'Starting daemon with ',
      daemonExecutable,
      ' ',
      finalDaemonArgs.join(' ')
    );
    const fullDaemonEnv = {};
    Object.assign(fullDaemonEnv, daemonEnv);
    Object.assign(fullDaemonEnv, process.env);
    daemon = spawn(daemonExecutable, finalDaemonArgs, { env: fullDaemonEnv });

    const splittedStdout = daemon.stdout.pipe(split());

    splittedStdout.on('data', processMessage);
    splittedStdout.on('error', onStdoutError);
    daemon.stderr.on('data', onStderrData);
    daemon.on('close', onDaemonClose);
    daemon.on('error', onDaemonError);

    scheduleHealthCheck();

    function onDaemonClose(code, signal) {
      logger.error(
        `child process terminated with code ${code} due to receipt of signal: ${signal}`
      );

      if (!hadCorrectResponse) {
        quitWithErrorMessage({
          code,
          signal,
          combinedStderr,
        });
        return;
      }

      // cancel forcefully kill
      if (forcefullyKillTimeout) {
        clearTimeout(forcefullyKillTimeout);
        forcefullyKillTimeout = null;
      }

      // cancel health check
      if (healthCheckTimeout) {
        clearTimeout(healthCheckTimeout);
        healthCheckTimeout = null;
      }

      // remove event listeners because of possible memory leaks
      daemon.removeListener('close', onDaemonClose);
      daemon.removeListener('error', onDaemonError);
      splittedStdout.removeListener('data', processMessage);
      splittedStdout.removeListener('error', onStdoutError);
      daemon.stderr.removeListener('data', onStderrData);

      tryRestartDaemon();
    }

    function onDaemonError() {
      logger.error('Daemon error event');
      if (!hadCorrectResponse) {
        quitWithErrorMessage({ combinedStderr });
        return;
      }
    }

    function tryRestartDaemon() {
      daemon = null;
      restartTryCounter += 1;
      if (restartTryCounter >= MAX_RESTART_TRIES) {
        quitWithErrorMessage({ combinedStderr });
        return;
      }

      isWaitingForRestart = true;
      // try to start daemon again after 1s, then after 2s, 4s and 8s
      // eslint-disable-next-line no-restricted-properties
      const tryToRunAfter = 1000 * Math.pow(2, restartTryCounter - 1);
      logger.debug(
        `Daemon closed. We'll try to restart it in ${tryToRunAfter} ms`
      );
      setTimeout(() => {
        isWaitingForRestart = false;
        getDaemon();
      }, tryToRunAfter);
    }

    function processMessage(rawMessage) {
      if (!rawMessage) {
        logger.debug('Got empty message');
        return;
      }

      logger.debug('Got message: %s', rawMessage);

      let message;
      try {
        message = JSON.parse(rawMessage);
      } catch (error) {
        logger.error('Cannot process JSON');
        return;
      }

      // request
      if (message.method) {
        co(function*() {
          // logger.debug('Executing method %s with params "%s" (%s):',
          // message.method, message.params, rawMessage);
          const handler = handlers[message.method];
          let result;
          let errorCode;
          let errorMessage;

          if (handler) {
            try {
              result = yield handler(message.params);
            } catch (_error) {
              errorCode = RPC_ERRORS.INTERNAL;
              errorMessage = _error.message;
            }
          } else {
            logger.warn(`Unsupported rpc method: ${message.method}`);
            errorCode = RPC_ERRORS.METHOD_NOT_FOUND;
            errorMessage = 'Unsupported rpc method';
          }

          // notification
          if (message.id == null) {
            // eslint-disable-line eqeqeq
            return;
          }

          const response = {
            jsonrpc: '2.0',
            id: message.id,
          };

          if (errorCode) {
            response.error = {
              code: errorCode,
              message: errorMessage,
            };
          } else {
            // result member is required on success according to spec
            response.result = result || null;
          }

          daemon.stdin.write(`${JSON.stringify(response)}\n`);
        });
        return;
      }

      // response
      const deferred = message.id && pending[message.id];
      if (!deferred) {
        return;
      }
      delete pending[message.id];

      if (message.error) {
        deferred.reject(message.error);
      } else {
        deferred.resolve(message.result);
      }
    }

    function scheduleHealthCheck() {
      healthCheckTimeout = setTimeout(healthCheck, PING_INTERVAL);
    }

    function healthCheck() {
      co(function*() {
        try {
          yield Promise.race([timeout(PING_RESPONSE_WAIT_MS), request('ping')]);
        } catch (error) {
          killDaemon();
          return;
        }

        hadCorrectResponse = true;
        restartTryCounter = 0;
        scheduleHealthCheck();
      });
    }

    function killDaemon() {
      daemon.kill();
      forcefullyKillTimeout = setTimeout(() => {
        // Child did not exit in time, forcefully killing it
        daemon.kill('SIGKILL');
      }, FORCEFULLY_KILL_WAIT_MS);
    }

    function onStdoutError(error) {
      logger.error('Error during processing daemon stdout:', error);
      quitWithDelay(102);
    }

    function onStderrData(data) {
      // respect COMBINED_STDERR_MAX_LENGTH and limt the length of the combined
      // stderr data to prevent out of memory error
      const dataAsString = data.toString(
        'utf8',
        Math.max(0, data.length - COMBINED_STDERR_MAX_LENGTH)
      );
      combinedStderr += dataAsString;
      if (combinedStderr.length > COMBINED_STDERR_MAX_LENGTH) {
        combinedStderr = combinedStderr.substr(
          combinedStderr.length - COMBINED_STDERR_MAX_LENGTH
        );
      }

      logger.debug(`DAEMON stderr: ${dataAsString}`);

      if (data.toString().indexOf('filelock.Timeout') !== -1) {
        const title = 'CrossCloud cannot be started.';
        const description = 'An instance of CrossCloud is already running.';
        main.displayNotification(title, description);
        quitWithDelay(101);
      }
    }

    return daemon;
  };

  function request(method, params) {
    // logger.info('sending request ' + method + ' Params: ' + JSON.stringify(params));

    const id = getNextId();
    const deferred = defer();
    pending[id] = deferred;
    getDaemon().stdin.write(
      `${JSON.stringify({
        jsonrpc: '2.0',
        id,
        method,
        params,
      })}\n`
    );
    return deferred.promise;
  }

  const service = {};
  requests.forEach(method => {
    service[method] = params => {
      return request(method, params);
    };
  });

  const addHandlers = handlerDefinitions => {
    handlerDefinitions.forEach(({ args, method, name }) => {
      handlers[name] = params => {
        let handlerParams;
        if (args && Array.isArray(params)) {
          handlerParams = args.reduce((result, argName, index) => {
            result[argName] = params[index];
            return result;
          }, {});
        } else {
          handlerParams = params;
        }
        return method(handlerParams);
      };
    });
  };

  service.addHandlers = addHandlers;
  return service;
};

function getNextId() {
  return nextId++; // eslint-disable-line no-plusplus
}

module.exports = { createService };
