const { DatabaseSync } = require("node:sqlite");
const { migrateDatabase } = require("./migrate_db.js");

const database = new DatabaseSync("./log.db");
migrateDatabase(database);

module.exports = {
   database
}