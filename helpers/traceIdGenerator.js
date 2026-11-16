
const crypto = require('node:crypto');

function generateTraceId(num = 8) {
    return crypto.randomBytes(Math.ceil(num / 2)).toString('hex').slice(0, num);
}

module.exports = generateTraceId;