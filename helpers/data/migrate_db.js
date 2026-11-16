const migrations = [
   {
      version: 1,
      up(database) {
         const tableExists = database.prepare(`
            SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?
         `);
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
      }
   },
   {
      version: 2,
      up(database) {
         const columns = database.prepare("PRAGMA table_info(log)").all();
         if (!columns.some((column) => column.name === "storage")) {
            database.exec("ALTER TABLE log ADD COLUMN storage INTEGER");
         }
      }
   }
];

function migrateDatabase(database) {
   const currentVersion = database.prepare("PRAGMA user_version").get().user_version;
   const latestVersion = migrations[migrations.length - 1].version;

   if (currentVersion > latestVersion) {
      throw new Error(`Database version ${currentVersion} is newer than supported version ${latestVersion}.`);
   }

   for (const migration of migrations) {
      if (migration.version <= currentVersion) {
         continue;
      }

      database.exec("BEGIN IMMEDIATE");
      try {
         migration.up(database);
         database.exec(`PRAGMA user_version = ${migration.version}`);
         database.exec("COMMIT");
      } catch (error) {
         database.exec("ROLLBACK");
         throw error;
      }
   }
}

module.exports = {
   migrateDatabase
};
