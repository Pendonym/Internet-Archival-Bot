const { DatabaseSync } = require("node:sqlite");

const database = new DatabaseSync("./log.db")

database.exec(`
   CREATE TABLE IF NOT EXISTS yt_log(
    trace_id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    user_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    status TEXT NOT NULL,
    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    log TEXT
   )  
`);

module.exports = {
   database
}