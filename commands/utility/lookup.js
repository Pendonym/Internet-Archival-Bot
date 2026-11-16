const { SlashCommandBuilder } = require('discord.js');
const { getInformationByTraceId } = require('../../helpers/data/queries');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('lookup')
        .setDescription('Gives you information about a specific trace ID.')
        .addStringOption((option) => option.setName('id').setDescription('The trace id.').setRequired(true)),

	async execute(interaction) {
        const traceId = interaction.options.getString('id', true);
        const info = getInformationByTraceId.get(traceId);

        if (!info) {
            return interaction.reply('No record found for that trace ID.');
        }

        const { url, user_id, channel_id, status, timestamp } = info;

        function getYouTubeId(url) {
            const regex = /(?:(?:music\.)?youtube\.com\/(?:watch\?v=|embed\/|shorts\/|live\/|v\/)|youtu\.be\/|yt\.be\/)([a-zA-Z0-9_-]{11})/;
            const match = url.match(regex);
            return match ? match[1] : null;
        }

        const lines = [
            `URL: <${url}>`,
            ...(status === 'uploaded' || status === 'already archived'
                ? [`Archive URL: <https://archive.org/details/${getYouTubeId(url)}>`]
                : []),
            `Archiver: <@${user_id}>`,
            `Channel: <#${channel_id}>`,
            `Status: ${status}`,
            `Timestamp: ${timestamp}`,
        ];

        await interaction.reply(lines.join('\n'));
	},
};