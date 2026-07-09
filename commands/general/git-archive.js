// apparently these are the issues for the crash (thank you vad for lmk but i have zero clue how to implement)
//- git logs sometimes hit 1mb+, pass { maxBuffer: 1024 * 1024 * 50 } with execFile
//- await and trycatch uploadArchive cause if any functions fail inside it, the process gets termed
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
            ///lily
			try
			{
				///pendonym
				const command = [ url ];

	            if (includewiki) {
	                console.log(`include wiki yes`)
	                command.push("--include-wiki")
	            }
	            if (allreleases) {
	                console.log(`include release yes`)
	                command.push("--include-wiki")
	            }
	            if (allbranches) {
	                console.log(`include branch yes`)
	                command.push("--include-wiki")
	            }
	
	            return new Promise((resolve, reject) => {
                    console.log(command)
	                execFile('iagitbetter', command, (error, stdout, stderr) => {
	                    if (error) {
                            interaction.editReply(`Archived prolly error`);
	                        console.log(`node error: ${error.message}`);
	                        return reject(error);
	                    }
	                    if (stderr) {
                            interaction.editReply(`Archived prolly stderr`);
	                        console.log(`error: ${stderr}`)
	                        return reject(stderr)
	                    }
	                    if (stdout) {
                            interaction.editReply(`Archived prolly stdout`);
                            console.log(stdout);
                            resolve(stdout);
                        }
                        interaction.editReply(`Archived prolly none of those 3`);
	                });
	            });
			}

			catch (err)
			{
				console.log("bad stuf:", err);
			}
        }

        uploadArchive()
			.then((value) => {
			    console.log(value);
			})
			.catch((err) => {
			    console.error("bad stuf (part 2):",err);
			});
    },
};
