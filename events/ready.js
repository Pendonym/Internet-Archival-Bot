const { Events, PresenceUpdateStatus, ActivityType } = require("discord.js");
const { getAllYouTubeVideos, getTotalYouTubeStorage } = require("../helpers/data/queries.js");

module.exports = {
    name: Events.ClientReady,
    once: true,
    execute(client) {
        const youtubeLogs = getAllYouTubeVideos.all();
        const uploadedVideos = youtubeLogs.filter((row) => row.status === "uploaded").length;
        const { total_storage_bytes: storageBytes } = getTotalYouTubeStorage.get();
        let storage, unit;

        if (storageBytes >= 1e12) {
            storage = (storageBytes / 1e12).toFixed(2);
            unit = "TB";
        } else if (storageBytes >= 1e9) {
            storage = (storageBytes / 1e9).toFixed(2);
            unit = "GB";
        } else {
            storage = (storageBytes / 1e6).toFixed(2);
            unit = "MB";
        }

        console.log(`Ready! Logged in as ${client.user.tag}`);

        client.user.setPresence({
            activities: [
                {
                    name: "Internet Archival Bot",
                    state: `${uploadedVideos} videos and ${storage} ${prefixunit} of data`,
                    type: ActivityType.Watching,
                },
            ],
            status: PresenceUpdateStatus.DoNotDisturb,
        });
    },
};
