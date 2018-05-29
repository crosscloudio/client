// return a promise which is rejected automatically after `ms` milliseconds
function timeout(ms) {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      reject(new Error('Timeout error'));
    }, ms);
  });
}

module.exports = timeout;
