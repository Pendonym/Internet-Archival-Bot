const { database } = require('./database.js');

const addLog = database.prepare(`
   INSERT INTO yt_log(trace_id, url, user_id, channel_id, message_id, status, log) 
   VALUES (?, ?, ?, ?, ?, ?, ?)
   RETURNING trace_id, url, message_id, status, log
`);

const getLogByTraceId = database.prepare(`
    SELECT * FROM yt_log WHERE trace_id = ?
`);

const updateLogFile = database.prepare(`
   UPDATE yt_log SET log = ? WHERE trace_id = ?
   RETURNING trace_id, url, log 
`);

const updateStatus = database.prepare(`
   UPDATE yt_log SET status = ? WHERE trace_id = ?
   RETURNING trace_id, url, status 
`);

const deleteLog = database.prepare(`
   DELETE FROM yt_log WHERE trace_id = ? 
`);

module.exports = {
    addLog,
    getLogByTraceId,
    updateLogFile,
    updateStatus,
    deleteLog
}