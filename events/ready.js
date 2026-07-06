const { Events, PresenceUpdateStatus, ActivityType } = require('discord.js');

module.exports = {
	name: Events.ClientReady,
	once: true,
	execute(client) {
		console.log(`Ready! Logged in as ${client.user.tag}`);
		client.user.setActivity('https://internet-archival.xyz/', { type: ActivityType.Watching });
		client.user.setStatus(PresenceUpdateStatus.DoNotDisturb);
	},
};