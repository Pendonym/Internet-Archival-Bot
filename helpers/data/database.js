const { DatabaseSync } = require("node:sqlite");

const database = new DatabaseSync("./log.db")

const tableExists = database.prepare(`
   SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?
`);

database.exec("BEGIN IMMEDIATE");
try {
   const hasYtLog = tableExists.get("yt_log");
   const hasLog = tableExists.get("log");

   if (hasYtLog && hasLog) {
      throw new Error("Both yt_log and log tables exist; refusing to migrate automatically.");
   }

   if (hasYtLog) {
      database.exec("ALTER TABLE yt_log RENAME TO log");
   }

   database.exec(`
      CREATE TABLE IF NOT EXISTS log(
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
   database.exec("COMMIT");
} catch (error) {
   database.exec("ROLLBACK");
   throw error;
}

module.exports = {
   database
}