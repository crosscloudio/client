// Lodash functions using setTimeout (like `throttle` and `debounce`)
// doesn't work with jest fake timers:
// https://github.com/lodash/lodash/issues/2893
// https://github.com/facebook/jest/issues/3465
//
// We mock it's throttle implementation with a sample one in order to be able
// to test code which uses it.

const lodashOrig = require.requireActual('lodash');

/* eslint-disable */
// Sample implementation from http://stackoverflow.com/a/27078401/2750114
function throttle(func, wait, options) {
  var context, args, result;
  var timeout = null;
  var previous = 0;
  if (!options) options = {};
  var later = function() {
    previous = options.leading === false ? 0 : Date.now();
    timeout = null;
    result = func.apply(context, args);
    if (!timeout) context = args = null;
  };
  function proc() {
    var now = Date.now();
    if (!previous && options.leading === false) previous = now;
    var remaining = wait - (now - previous);
    context = this;
    args = arguments;
    if (remaining <= 0 || remaining > wait) {
      if (timeout) {
        clearTimeout(timeout);
        timeout = null;
      }
      previous = now;
      result = func.apply(context, args);
      if (!timeout) context = args = null;
    } else if (!timeout && options.trailing !== false) {
      timeout = setTimeout(later, remaining);
    }
    return result;
  }

  proc.cancel = function() {
    if (timeout) {
      clearTimeout(timeout);
      timeout = null;
    }
  };

  return proc;
}

/* eslint-enable */

module.exports = Object.assign({}, lodashOrig, { throttle });
