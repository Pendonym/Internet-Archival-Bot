const { Events, PresenceUpdateStatus, ActivityType } = require('discord.js');
const { getAllYouTubeVideos, getTotalYouTubeStorage } = require('../helpers/data/queries.js');

module.exports = {
	name: Events.ClientReady,
	once: true,
	execute(client) {
		const youtubeLogs = getAllYouTubeVideos.all();
		const uploadedVideos = youtubeLogs.filter((row) => row.status === 'uploaded').length;
		const { total_storage_bytes: storageBytes } = getTotalYouTubeStorage.get();
		const storageTB = (storageBytes / 1e12).toFixed(2);

		console.log(`Ready! Logged in as ${client.user.tag}`);

		client.user.setPresence({
			activities: [{
			  name: 'Internet Archival Bot',
			  state: `${uploadedVideos} videos and ${storageTB} TB of data`,
			  type: ActivityType.Watching,
			}],
			status: PresenceUpdateStatus.DoNotDisturb,
		});
	},
};