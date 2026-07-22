// todo: use software heritiage api
const { SlashCommandBuilder } = require('discord.js');
const { exec, execFile } = require("child_process");
const { glob } = require('glob')
const http = require('node:http')

module.exports = {
    data: new SlashCommandBuilder()
        .setName('git-archive')
        .setDescription('Downloads Git repos videos and uploads them to archive.org')
        .addStringOption((option) => option.setName('link').setDescription('The URL to the git repo.').setRequired(true)),

    async execute(interaction) {
        const url = interaction.options.getString('link');

        if (!/^https?:\/\//i.test(url)) {
            return interaction.reply('Please provide a valid URL.');
        }

        await interaction.reply({ content: 'Sending request...', withResponse: true });

        function sendRequest() {
			
		}
    },
};
