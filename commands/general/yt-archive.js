// todo: have a trace id, log everything to the trace id folder, never delete trace id folder, lookup command for trace id (or mabye just save to sqlite db)
// add progress bar for upload (prob download too)
// add a retry mechanism if the upload fails
// forgets messages after like 5 commands and will never reply or edit prev messages
// check if time has been over 15 you need to go back to the message id then edit it instead of using editReply because the interaction token expired
const { SlashCommandBuilder } = require('discord.js');
const { addLog, updateStatus } = require('../../helpers/data/queries');
const generateTraceId = require("../../helpers/traceIdGenerator.js");
const { exec, execFile } = require("child_process");
const { glob } = require('glob')
const fs = require('node:fs');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('yt-archive')
        .setDescription('Downloads YouTube videos and uploads them to archive.org.')
        .addStringOption((option) => option.setName('link').setDescription('The URL to the YouTube video.').setRequired(true)),

    async execute(interaction) {
        const url = interaction.options.getString('link');

        if (!/^https?:\/\//i.test(url)) {
            return interaction.reply(`Please provide a valid YouTube URL.`);
        } else if (/[?&]list=/.test(url) || /\/(channel\/|c\/|@)/.test(url)) {
            return interaction.reply(`Playlists and channels are currently not supported if you would like to help me cook that up you can go to https://github.com/Pendonym/Internet-Archival-Bot.`);
        } else if (!getYouTubeId(url)) {
            return interaction.reply('Please provide a valid YouTube video URL.');
        }

        await interaction.reply({ content: 'Sending request...', withResponse: true });

        function getYouTubeId(url) {
            const regex = /(?:(?:music\.)?youtube\.com\/(?:watch\?v=|embed\/|shorts\/|live\/|v\/)|youtu\.be\/|yt\.be\/)([a-zA-Z0-9_-]{11})/;
            const match = url.match(regex);
            return match ? match[1] : null;
        }

        function checkArchive() {
            return new Promise((resolve, reject) => {
                exec(`ia metadata youtube-${getYouTubeId(url)}`, (error, stdout, stderr) => {
                    if (error) {
                        console.log(`Error occured in Node: ${error.message}`);
                        return reject(error);
                    }
                    resolve(stdout.length < 10);
                });
            });
        }

        const trace_id = generateTraceId()
        const reply = await interaction.fetchReply();
        addLog.get(trace_id, url, interaction.user.id, interaction.channel.id, reply.id, "pending", null)

        let isNotArchived;
        try {
            isNotArchived = await checkArchive();
        } catch (err) {
            console.log(`Error occursed inside of checkArchive: ${err}`);
            updateStatus.get("archive check failed", trace_id);
            await interaction.editReply(`Could not check archive.org.\n\nTrace ID: ${trace_id}`);
            return;
        }

        async function uploadArchive(files) {
            const data = await fs.promises.readFile(`${process.env.DOWNLOAD_PATH}/${trace_id}/youtube-${getYouTubeId(url)}/${getYouTubeId(url)}.info.json`, 'utf8');
            const jsonData = JSON.parse(data);
            const metaTags = Array.isArray(jsonData.tags) ? jsonData.tags.join(';') : '';
            const dateYear = jsonData.upload_date.slice(0, 4);
            const dateMonth = jsonData.upload_date.slice(4, 6);
            const dateDay = jsonData.upload_date.slice(6, 8);

            if (jsonData.description === "") {
                jsonData.description = "Description was not provided in this video. While you're here try out the bot that uploaded this video at https://internet-archival.xyz";
            };

            return new Promise((resolve, reject) => {
                execFile('ia', [
                    'upload', `youtube-${getYouTubeId(url)}`,
                    ...files,
                    '-m', `title:${jsonData.title}`,
                    '-m', `description:${jsonData.description}`,
                    '-m', `subject:Youtube;video;${metaTags}`,
                    '-m', 'collection:test_collection', // opensource_movies and test_collection
                    '-m', 'scanner:Internet Archival Bot +https://internet-archival.xyz',
                    '-m', `channel:${jsonData.channel_url}`,
                    '-m', `originalurl:${jsonData.webpage_url}`,
                    '-m', `creator:${jsonData.uploader}`,
                    '-m', "mediatype:movies",
                    '-m', `year:${dateYear}`,
                    '-m', `date:${dateYear}-${dateMonth}-${dateDay}`
                ], (error, stdout) => {
                    if (error) {
                        console.log(`Error occured in Node: ${error.message}`);
                        return reject(error);
                    }
                    resolve(stdout);
                });
            });
        }

        if (!isNotArchived) {
            updateStatus.get("already archived", trace_id)
            await interaction.editReply(`Video is already archived at: https://archive.org/details/youtube-${getYouTubeId(url)}\n\nTrace ID: ${trace_id}`);
        } else {
            updateStatus.get("downloading", trace_id)
            await interaction.editReply(`Downloading...\n\nTrace ID: ${trace_id}`);

            try {
                await new Promise((resolve, reject) => {
                    execFile('yt-dlp', [
                        '--restrict-filenames', '--continue', '--retries', '9001', '--js-runtimes', 'node',
                        '--fragment-retries', '9001', '--write-info-json', '--write-description', '--cookies', `${process.env.COOKIE_PATH}`,
                        '--write-thumbnail', '--write-subs', '--all-subs', '--ignore-errors', '--fixup',
                        'detect_or_warn', '--no-overwrites', '--no-update', '-o', `${process.env.DOWNLOAD_PATH}/${trace_id}/youtube-${getYouTubeId(url)}/%(id)s.%(ext)s`,
                        '--restrict-filenames', '--continue', '--retries', '9001', '--js-runtimes', 'deno',
                        '--fragment-retries', '9001', '--write-info-json', '--write-description', '--cookies', `${process.env.COOKIE_PATH}`,
                        '--write-thumbnail', '--write-subs', '--all-subs', '--ignore-errors', '--fixup', 'detect_or_warn', '--remote-components', 'ejs:github',
                        '--no-overwrites', '--no-update', '-o', `${process.env.DOWNLOAD_PATH}/${trace_id}/youtube-${getYouTubeId(url)}/%(id)s.%(ext)s`, url
                    ], (error, stdout) => {
                        if (error) {
                            console.log(`Error occured in Node: ${error.message}`);
                            return reject(error);
                        }
                        resolve(stdout);
                    });
                });
            } catch (err) {
                updateStatus.get("download failed", trace_id)
                console.log(`Downloading the video has failed: ${err.message}`);
                await interaction.followUp(`Download failed.\n\nTrace ID: ${trace_id}`);
                return;
            }

            updateStatus.get("uploading", trace_id)
            await interaction.followUp(`Downloaded now uploading...\n\nTrace ID: ${trace_id}`);

            try {
                const files = await glob(`${process.env.DOWNLOAD_PATH}/${trace_id}/youtube-${getYouTubeId(url)}/${getYouTubeId(url)}.*`);
                if (files.length === 0) {
                    throw new Error('No downloaded files were found to upload.');
                }

                await uploadArchive(files);
                updateStatus.get("uploaded", trace_id)
                try {
                    await fs.promises.rm(`${process.env.DOWNLOAD_PATH}/${trace_id}/youtube-${getYouTubeId(url)}`, { recursive: true, force: true });
                } catch (cleanupError) {
                    console.log(`Upload succeeded, but downloaded files could not be removed: ${cleanupError.message}`);
                }
                await interaction.followUp(`Uploaded! https://archive.org/details/youtube-${getYouTubeId(url)}`);
            } catch (err) {
                updateStatus.get("uploading failed", trace_id)
                console.log(`Uploading the video has failed: ${err.message}`);
                await interaction.followUp(`Upload failed.\n\nTrace ID: ${trace_id}`);
            }
        }
    }
};
