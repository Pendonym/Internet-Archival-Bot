const { SlashCommandBuilder } = require('discord.js');
const { exec, execFile } = require("child_process");
const { glob } = require('glob')

module.exports = {
    data: new SlashCommandBuilder()
        .setName('git-archive')
        .setDescription('Downloads Git repos videos and uploads them to archive.org')
        .addStringOption((option) => option.setName('link').setDescription('The URL to the git repo.').setRequired(true))
        .addBooleanOption((option) =>
		    option.setName('include-wiki').setDescription('Clone and archive the repository wiki'),
	    )
        .addBooleanOption((option) =>
		    option.setName('all-releases').setDescription('Download all releases'),
	    )
        .addBooleanOption((option) =>
		    option.setName('all-branches').setDescription('Clone every branch in the repository'),
	    ),

    async execute(interaction) {
        const url = interaction.options.getString('link');
        const includewiki = interaction.options.getBoolean('include-wiki');
        const allreleases = interaction.options.getBoolean('all-releases');
        const allbranches = interaction.options.getBoolean('all-branches');

        console.log(allbranches, includewiki, allreleases)

        if (!/^https?:\/\//i.test(url)) {
            return interaction.reply('Please provide a valid URL.');
        }

        const sent = await interaction.reply({ content: 'Sending request...', withResponse: true });

        function uploadArchive() {
            const command = [ url ];

            if (includewiki) {
                console.log(`include wiki yes`)
                command.concat("--include-wiki")
            }
            if (allreleases) {
                console.log(`include release yes`)
                command.concat("--include-wiki")
            }
            if (allbranches) {
                console.log(`include branch yes`)
                command.concat("--include-wiki")
            }

            return new Promise((resolve, reject) => {
                execFile('iagitbetter', command, (error, stdout, stderr) => {
                    if (error) {
                        console.log(`node error: ${error.message}`);
                        return reject(error);
                    }
                    if (stderr) {
                        console.log(`error: ${stderr}`)
                        return reject(stderr)
                    }
                    interaction.reply({ content: 'Archived prolly', withResponse: true });
                    console.log(stdout);
                    resolve(stdout);
                });
            });
        }

        uploadArchive()
    },
};