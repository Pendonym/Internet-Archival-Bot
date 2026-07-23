// todo
// add progress bar for upload (prob download too)
// add a retry mechanism if the upload fails

const { SlashCommandBuilder } = require('discord.js');
const { exec, execFile } = require("child_process");
const { glob } = require('glob')
const fs = require('node:fs');
const { json } = require('node:stream/consumers');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('yt-archive')
        .setDescription('Downloads YouTube videos and uploads them to archive.org')
        .addStringOption((option) => option.setName('link').setDescription('The URL to the YouTube video.').setRequired(true)),

    async execute(interaction) {
        const url = interaction.options.getString('link');

        if (!/^https?:\/\//i.test(url)) {
            return interaction.reply('Please provide a valid YouTube URL.');
        } else if (/[?&]list=/.test(url) | /\/(channel\/|c\/|@)/.test(url)) {
            return interaction.reply('Playlists and channels are currently not supported if you would like to help me cook that up you can go to https://github.com/Pendonym/Internet-Archival-Bot.');
        }

        await interaction.reply({ content: 'Sending request...', withResponse: true });

        function getYouTubeId(url) {
            const regex = /(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/|live\/|v\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})/;
            const match = url.match(regex);
            return match ? match[1] : null;
        }

        function checkArchive() {
            return new Promise((resolve, reject) => {
                exec(`ia metadata youtube-${getYouTubeId(url)}`, (error, stdout, stderr) => {
                    if (error) {
                        console.log(`node error: ${error}`);
                        return reject(error);
                    }
                    if (stderr) {
                        console.log(`error from my pc or sum: ${stderr}`);
                        return reject(new Error(stderr));
                    }
                    resolve(stdout.length < 10);
                });
            });
        }

        function uploadArchive(files) {
            return new Promise((resolve, reject) => {
                fs.readFile(`${process.env.DOWNLOAD_PATH}/youtube-${getYouTubeId(url)}/${getYouTubeId(url)}.info.json`, 'utf8', (err, data) => {
                    if (err) {
                        console.error(`yo i broke: ${err}`);
                        return;
                    }

                    const jsonData = JSON.parse(data);
                    const metaTags = `${jsonData.tags.join(`;`)}`;
                    const dateYear = jsonData.upload_date.slice(0,4);
                    const dateDay = jsonData.upload_date.slice(4,6);
                    const dateMonth = jsonData.upload_date.slice(6,8);

                    if (jsonData.description === "") {
                        jsonData.description = "Description was not provided in this video. While you're here try out the bot that uploaded this video at https://internet-archival.xyz";
                    };

                    execFile('ia', [
                        'upload', `youtube-${getYouTubeId(url)}`,
                        ...files,
                        '-m', `title:${jsonData.title}`,
                        '-m', `description:${jsonData.description}`,
                        '-m', `subject:Youtube;video;${metaTags}`,
                        '-m', 'collection:opensource_movies', // opensource_movies and test_collection
                        '-m', 'scanner:TubeUp Video Stream Mirroring Application 2026.5.8',
                        '-m', `channel:${jsonData.channel_url}`,
                        '-m', `originalurl:${jsonData.webpage_url}`,
                        '-m', `creator:${jsonData.uploader}`,
                        '-m', "mediatype:movies",
                        '-m', `year:${dateYear}`,
                        '-m', `date:${dateYear}-${dateDay}-${dateMonth}`
                    ], (error, stdout, stderr) => {
                        if (error) {
                            console.log(`node error: ${error}`);
                            return reject(error);
                        }
                        resolve(stdout);
                    });
                });
            });
        }

        async function downloadVideo(video) {
            let isNotArchived;
            try {
                isNotArchived = await checkArchive();
            } catch (err) {
                console.log(`shit broke in checkarchive gng: ${err}`);
                return;
            }

            if (isNotArchived) {
                await interaction.editReply(`Downloading...`);
                execFile('yt-dlp', [
                    '--restrict-filenames', '--continue', '--retries', '9001', '--js-runtimes', 'deno',
                    '--fragment-retries', '9001', '--write-info-json', '--write-description', '--cookies', `${process.env.COOKIE_PATH}`,
                    '--write-thumbnail', '--write-subs', '--all-subs', '--ignore-errors', '--fixup', 'detect_or_warn', '--remote-components', 'ejs:github',
                    '--no-overwrites', '--no-update', '-o', `${process.env.DOWNLOAD_PATH}/youtube-${getYouTubeId(url)}/%(id)s.%(ext)s`, video
                ], async (error, stdout, stderr) => {
                    if (error) {
                        console.log(`node error: ${error.message}`);
                        return;
                    }
                    if (stderr) {
                        console.log(`error from my pc or sum: ${stderr}`);
                        return;
                    }
                    await interaction.followUp(`Downloaded now uploading...`);
                    try {
                        const files = await glob(`${process.env.DOWNLOAD_PATH}/youtube-${getYouTubeId(url)}/${getYouTubeId(url)}.*`);
                        await uploadArchive(files).then(() => fs.rm(`${process.env.DOWNLOAD_PATH}/youtube-${getYouTubeId(url)}`, { recursive: true }, (err, data) => {
                        if (err) {
                            console.log(err);
                        } else if (data) {
                            console.log(data);
                        };
                    }));
                        await interaction.followUp(`Uploaded! https://archive.org/details/youtube-${getYouTubeId(url)}`);
                    } catch (err) {
                        console.log(`upload failed: ${err.message}`);
                        await interaction.followUp('Upload failed.');
                    }
                });
            } else {
                interaction.editReply(`Already archived at: https://archive.org/details/youtube-${getYouTubeId(url)}`);
            }
        }

        downloadVideo(url)
    },
};