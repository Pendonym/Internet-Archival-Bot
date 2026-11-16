// add a retry mechanism if the upload fails (rare but possible)
// forgets messages after like 5 commands and will never reply or edit prev messages (maybe due to 15m limit?)
// check if time has been over 15 you need to go back to the message id then edit it instead of using editReply because the interaction token expired
const { SlashCommandBuilder } = require('discord.js');
const { addLog, updateLogFile, updateStatus } = require('../../helpers/data/queries');
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

        const trace_id = generateTraceId()
        const logFile = `${process.env.DOWNLOAD_PATH}/${trace_id}/latest.log`;

        let logContents = '';
        let logRecordCreated = false;

        async function log(text) {
            const entry = `[${new Date().toISOString()}] ${text}\n`;
            logContents += entry;
            await fs.promises.mkdir(`${process.env.DOWNLOAD_PATH}/${trace_id}`, { recursive: true });
            await fs.promises.appendFile(logFile, entry);

            if (logRecordCreated && !updateLogFile.get(logContents, trace_id)) {
                throw new Error(`Could not update the database log for trace ID ${trace_id}.`);
            }
        }

        if (!/^https?:\/\//i.test(url)) {
            await log(`User didn't provide a valid URL.`);
            return interaction.reply(`Please provide a valid URL.`);
        } else if (/[?&]list=/.test(url) || /\/(channel\/|c\/|@)/.test(url)) {
            await log(`User tried to submit a playlist or a channel.`);
            return interaction.reply(`Playlists and channels are currently not supported if you would like to help me cook that up you can go to https://github.com/Pendonym/Internet-Archival-Bot.`);
        } else if (!getYouTubeId(url)) {
            await log(`User didn't provide a valid YouTube URL.`);
            return interaction.reply('Please provide a valid YouTube video URL.');
        }

        await log(`Starting to send request for download.`);
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
                        error.stderr = stderr;
                        return reject(error);
                    }
                    resolve(stdout.length < 10);
                });
            });
        }

        const reply = await interaction.fetchReply();
        addLog.get(trace_id, url, interaction.user.id, interaction.channel.id, reply.id, "pending", logContents)
        logRecordCreated = true;
        await log(`Created the trace record in SQLite.`);

        let isNotArchived;
        try {
            isNotArchived = await checkArchive();
            await log(`Archive check completed; archived: ${!isNotArchived}.`);
        } catch (err) {
            await log(`Archive check failed: ${err.message}${err.stderr ? `\n${err.stderr}` : ''}`);
            console.error('Archive check failed:', err);
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
                ], (error, stdout, stderr) => {
                    if (error) {
                        error.stderr = stderr;
                        return reject(error);
                    }
                    resolve({ stdout, stderr });
                });
            });
        }

        if (!isNotArchived) {
            await log(`Video is already archived.`);
            updateStatus.get("already archived", trace_id)
            await interaction.editReply(`Video is already archived at: https://archive.org/details/youtube-${getYouTubeId(url)}\n\nTrace ID: ${trace_id}`);
        } else {
            updateStatus.get("downloading", trace_id)
            await log(`Started downloading the video.`);
            await interaction.editReply(`Downloading...\n\nTrace ID: ${trace_id}`);

            try {
                const downloadOutput = await new Promise((resolve, reject) => {
                    execFile('yt-dlp', [
                        '--restrict-filenames', '--continue', '--retries', '10', '--js-runtimes', 'node',
                        '--fragment-retries', '10', '--write-info-json', '--write-description', '--cookies', `${process.env.COOKIE_PATH}`,
                        '--write-thumbnail', '--write-subs', '--all-subs', '--ignore-errors', '--fixup',
                        'detect_or_warn', '--no-overwrites', '--no-update', '-o', `${process.env.DOWNLOAD_PATH}/${trace_id}/youtube-${getYouTubeId(url)}/%(id)s.%(ext)s`,
                        '--js-runtimes', 'deno', '--remote-components', 'ejs:github', url
                    ], (error, stdout, stderr) => {
                        if (error) {
                            error.stderr = stderr;
                            return reject(error);
                        }
                        resolve(stdout);
                    });
                });
                await log(`yt-dlp output:\n${downloadOutput}`);
            } catch (err) {
                await log(`yt-dlp failed: ${err.message}${err.stderr ? `\n${err.stderr}` : ''}`);
                updateStatus.get("download failed", trace_id)
                console.error('Downloading the video failed:', err);
                await interaction.followUp(`Download failed.\n\nTrace ID: ${trace_id}`);
                return;
            }

            await log(`Finished downloading the video; starting upload to Internet Archive.`);
            updateStatus.get("uploading", trace_id)
            await interaction.followUp(`Downloaded now uploading...\n\nTrace ID: ${trace_id}`);

            try {
                const files = await glob(`${process.env.DOWNLOAD_PATH}/${trace_id}/youtube-${getYouTubeId(url)}/${getYouTubeId(url)}.*`);
                if (files.length === 0) {
                    throw new Error('No downloaded files were found to upload.');
                }

                const uploadOutput = await uploadArchive(files);
                const output = [
                    uploadOutput.stdout && `stdout:\n${uploadOutput.stdout.trim()}`,
                    uploadOutput.stderr && `stderr:\n${uploadOutput.stderr.trim()}`,
                ].filter(Boolean).join('\n');
                if (output) {
                    await log(`Internet Archive upload output:\n${output}`);
                }
                try {
                    await fs.promises.rm(`${process.env.DOWNLOAD_PATH}/${trace_id}/youtube-${getYouTubeId(url)}`, { recursive: true, force: true });
                } catch (cleanupError) {
                    await log(`Upload succeeded, but downloaded files could not be removed: ${cleanupError.message}`);
                    console.error('Upload succeeded, but downloaded files could not be removed:', cleanupError);
                }

                updateStatus.get("uploaded", trace_id)
                await log(`Successfully uploaded the video. https://archive.org/details/youtube-${getYouTubeId(url)}`);
                await interaction.followUp(`Uploaded! https://archive.org/details/youtube-${getYouTubeId(url)}`);
            } catch (err) {
                updateStatus.get("uploading failed", trace_id)
                await log(`Upload failed: ${err.message}${err.stderr ? `\n${err.stderr}` : ''}`);
                console.error('Uploading the video failed:', err);
                await interaction.followUp(`Upload failed.\n\nTrace ID: ${trace_id}`);
            }
        }
    }
};
