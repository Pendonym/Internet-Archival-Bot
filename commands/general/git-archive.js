// todo: use software heritiage api
const { SlashCommandBuilder } = require('discord.js');
const { exec, execFile } = require("child_process");
const { glob } = require('glob')
const axios = require('axios')
const fs = require('node:fs');
const { error } = require('node:console');

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

        function checkRequest(request_id) {
            console.log(request_id)

            axios.get(
                `https://archive.softwareheritage.org/api/1/origin/save/${encodeURIComponent(request_id)}`
            )
        }

        function sendRequest() {
            // holy fucking inefficent ass code

            axios.post(
                `https://archive.softwareheritage.org/api/1/origin/save/?visit_type=git&origin_url=${encodeURIComponent(url)}`,
                null,
                {
                    headers: {
                        'User-Agent': 'Internet Archival Bot +https://internet-archival.xyz/',
                        'Authorization': `Bearer ${process.env.SOFT_HERITAGE_TOKEN}`
                    }
                }
            ).then((response) => {
                checkRequest(response.data.id)
            })
        }

        sendRequest()
    }
};
