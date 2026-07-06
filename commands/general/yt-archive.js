const { SlashCommandBuilder } = require('discord.js');
const { exec, execFile } = require("child_process");
const { glob } = require('glob')

module.exports = {
    data: new SlashCommandBuilder()
        .setName('yt-archive')
        .setDescription('Downloads YouTube videos and uploads them to archive.org')
        .addStringOption((option) => option.setName('link').setDescription('The URL to the YouTube video.').setRequired(true)),

    async execute(interaction) {
        const url = interaction.options.getString('link');

        if (!/^https?:\/\//i.test(url)) {
            return interaction.reply('Please provide a valid URL.');
        }

        const sent = await interaction.reply({ content: 'Sending request...', withResponse: true });

        function getYouTubeId(url) {
            const regex = /(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/|live\/|v\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})/;
            const match = url.match(regex);
            return match ? match[1] : null;
        }

        function checkArchive() {
            return new Promise((resolve, reject) => {
                exec(`ia metadata youtube-${getYouTubeId(url)}`, (error, stdout, stderr) => {
                    if (error) {
                        console.log(`node error: ${error.message}`);
                        return reject(error);
                    }
                    if (stderr) {
                        console.log(`error from my pc or sum`);
                        return reject(new Error(stderr));
                    }
                    console.log(stdout.length);
                    resolve(stdout.length < 10);
                });
            });
        }

        function uploadArchive(files) {
            return new Promise((resolve, reject) => {
                execFile('ia', [
                    'upload', `temp-u9032j3`,
                    ...files,
                    '-m', 'title:Test Upload For YouTube Bot',
                    '-m', 'collection:test_collection'
                ], (error, stdout, stderr) => {
                    if (error) {
                        console.log(`node error: ${error.message}`);
                        return reject(error);
                    }
                    console.log(stdout);
                    resolve(stdout);
                });
            });
        }

        async function downloadVideo(video) {
            let isNotArchived;
            try {
                isNotArchived = await checkArchive();
            } catch (err) {
                console.log(`shit broke in checkarchive gng: ${err.message}`);
                return;
            }

            if (isNotArchived) {
                await interaction.editReply(`Downloading...`);
                execFile('yt-dlp', [
                    '--restrict-filenames', '--continue', '--retries', '9001',
                    '--fragment-retries', '9001', '--write-info-json', '--write-description',
                    '--write-thumbnail', '--all-subs', '--ignore-errors', '--fixup', 'detect_or_warn',
                    '--no-overwrites', '--no-update', '-o', '%(id)s.%(ext)s', video
                ], async (error, stdout, stderr) => {
                    if (error) {
                        console.log(`node error: ${error.message}`);
                        return;
                    }
                    if (stderr) {
                        console.log(`error from my pc or sum: ${stderr}`);
                        return;
                    }
                    await interaction.editReply(`Downloaded now uploading...`);
                    try {
                        const files = await glob(`${getYouTubeId(url)}.*`);
                        await uploadArchive(files);
                        await interaction.editReply(`Uploaded! https://archive.org/details/test-${getYouTubeId(url)}`);
                    } catch (err) {
                        console.log(`upload failed: ${err.message}`);
                        await interaction.editReply('Upload failed.');
                    }
                });
            } else {
                interaction.editReply(`Already archived at: https://archive.org/details/youtube-${getYouTubeId(url)}`);
            }
        }

        downloadVideo(url)
    },
};