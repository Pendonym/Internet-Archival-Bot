// todo: use software heritiage api
const { SlashCommandBuilder } = require('discord.js');
const { exec, execFile } = require("child_process");
const { glob } = require('glob')
const axios = require('axios')

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
            return axios.post(
                `https://archive.softwareheritage.org/api/1/origin/save/?visit_type=git&origin_url=${encodeURIComponent(url)}`,
                null,
                {
                    headers: {
                        'User-Agent': 'Internet Archival Bot +https://internet-archival.xyz/'
                    }
                }
            ).then((response) => {
                // send GET request to /api/1/origin/save/(request_id)/ and interaction.followUp when the task has succeeded/failed
                interaction.followUp(`URL submitted to Software Heritage: ${response.data.request_url}`);
                console.log(response.data.request_url);
            }).catch((error) => {
                interaction.followUp(`An error occured when uploading to Software Heritage.\nSent URL: ${url}`);
                console.log(`Error: ${error}`);
            });
        }

        sendRequest()
    },
};
