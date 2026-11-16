// todo: log everything into sql log (maybe?)
// (most likely) forgets messages after like 5 commands and will never reply or edit prev messages
// check if time has been over 15 you need to go back to the message id then edit it instead of using editReply because the interaction token expired
const { SlashCommandBuilder } = require('discord.js');
const axios = require('axios')
const { setTimeout: sleep } = require('node:timers/promises');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('git-archive')
        .setDescription('Sends git repositories to Software Heritage.')
        .addStringOption((option) => option.setName('link').setDescription('The URL to the git repo.').setRequired(true)),

    async execute(interaction) {
        const url = interaction.options.getString('link');

        if (!/^https?:\/\//i.test(url)) {
            return interaction.reply('Please provide a valid URL.');
        } else if (/^https?:\/\/[^/?#]+\/[^/?#]+\/?(?:[?#].*)?$|^https?:\/\/(?:www\.)?github\.com\/(?:orgs|users)\/[^/?#]+(?:\/[^?#]*)?$/i.test(url)) {
            return interaction.reply('Profile and organization URLs are not supported. Please provide a repository URL. <https://github.com/Pendonym/Internet-Archival-Bot>');
        }

        await interaction.reply({ content: 'Sending request...', withResponse: true });

        async function checkTask(request_id) {
            let save_task_status = "not created"
            let save_request_status = "pending"

            while (save_task_status != "succeeded" || save_task_status != "failed") {
                await axios.get(
                    `https://archive.softwareheritage.org/api/1/origin/save/${encodeURIComponent(request_id)}`,
                    null,
                    {
                        headers: {
                            'User-Agent': 'Internet Archival Bot +https://internet-archival.xyz/',
                            'Authorization': `Bearer ${process.env.SOFT_HERITAGE_TOKEN}`
                        }
                    }
                ).then((reaponse) => {
                    save_task_status = reaponse.data.save_task_status
                    save_request_status = reaponse.data.save_request_status
                })

                if (save_task_status == "succeeded") {
                    interaction.editReply("Request was successfully sent to Software Heritage!")
                    break
                } else if (save_task_status == "failed") {
                    interaction.editReply(`Request was successfully sent to Software Heritage but failed!\n\nhttps://archive.softwareheritage.org/api/1/origin/save/${encodeURIComponent(request_id)}`)
                    break
                } else if (save_request_status == "rejected") {
                    interaction.editReply(`Software Heritage has rejected this request.\n\nhttps://archive.softwareheritage.org/api/1/origin/save/${encodeURIComponent(request_id)}`)
                }

                await sleep(5_000);
            }
        }

        await axios.post(
            `https://archive.softwareheritage.org/api/1/origin/save/?visit_type=git&origin_url=${encodeURIComponent(url)}`,
            null,
            {
                headers: {
                    'User-Agent': 'Internet Archival Bot +https://internet-archival.xyz/',
                    'Authorization': `Bearer ${process.env.SOFT_HERITAGE_TOKEN}`
                }
            }
        ).then((response) => {
            checkTask(response.data.id)
        }).catch((error) => {
            if (axios.isAxiosError(error) && error.response?.status == 403) {
                interaction.editReply(`Software Heritage rejected this request for the following reason: ${error.response?.data.reason}`)
                console.error(`git-archive Request forbidden. | ${error.response?.data.reason}`)
                return null;
            }
            throw error;
        })
    }
};
