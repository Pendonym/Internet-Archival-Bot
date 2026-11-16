const { database } = require('./database.js');

const addLog = database.prepare(`
   INSERT INTO log(trace_id, url, user_id, channel_id, message_id, status, log)
   VALUES (?, ?, ?, ?, ?, ?, ?)
   RETURNING trace_id, url, message_id, status, log
`);

const getInformationByTraceId = database.prepare(`
    SELECT * FROM log WHERE trace_id = ?
`);

const getAllYouTubeVideos = database.prepare(`
    SELECT * FROM log
    WHERE url LIKE '%youtube.com/%'
       OR url LIKE '%youtu.be/%'
       OR url LIKE '%yt.be/%'
`);

const getTotalYouTubeStorage = database.prepare(`
    SELECT COALESCE(SUM(storage), 0) AS total_storage_bytes
    FROM log
    WHERE url LIKE '%youtube.com/%'
       OR url LIKE '%youtu.be/%'
       OR url LIKE '%yt.be/%'
`);

const updateStorage = database.prepare(`
    UPDATE log
    SET storage = ?
    WHERE trace_id = ?
    RETURNING trace_id, storage
`);

const getLogByTraceId = database.prepare(`
    SELECT log FROM log WHERE trace_id = ?
`);

const updateLogFile = database.prepare(`
   UPDATE log SET log = ? WHERE trace_id = ?
   RETURNING trace_id, url, log 
`);

const updateStatus = database.prepare(`
   UPDATE log SET status = ? WHERE trace_id = ?
   RETURNING trace_id, url, status 
`);

const deleteLog = database.prepare(`
   DELETE FROM log WHERE trace_id = ?
`);

module.exports = {
    addLog,
    getInformationByTraceId,
    getAllYouTubeVideos,
    getTotalYouTubeStorage,
    updateStorage,
    getLogByTraceId,
    updateLogFile,
    updateStatus,
    deleteLog
}