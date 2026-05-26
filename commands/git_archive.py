from __future__ import annotations

import asyncio
import logging
import re

import discord
from discord import app_commands
from discord.ext import commands

from modules.embed_builder import EmbedBuilder

_SUPPORTED_DOMAINS = (
    "github.com",
    "gist.github.com",
    "gitlab.com",
    "codeberg.org",
    "gitea.com",
    "bitbucket.org",
    "gitflic.ru",
    "gitee.com",
    "notabug.org",
    "sourceforge.net",
    "git.launchpad.net",
)


class GitArchive(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="git-archive",
        description="Archive a git repository using iagitbetter.",
    )
    @app_commands.describe(
        link=(
            "Repository URL to archive — supports GitHub, GitLab, Codeberg, Gitea, "
            "Bitbucket, GitFlic, Gitee, SourceForge, and self-hosted instances."
        )
    )
    async def git_archive(self, interaction: discord.Interaction, link: str) -> None:
        verbose: bool = getattr(self.bot, "verbose", False)
        if verbose:
            logging.debug(
                "[git-archive] invoked by %s (id=%s) in guild=%s channel=%s | link=%s",
                interaction.user,
                interaction.user.id,
                interaction.guild_id,
                interaction.channel_id,
                link,
            )
        await interaction.response.defer()

        init_embed = (
            EmbedBuilder(
                title="Archive Request",
                description=(
                    f"Initializing archive request for `{link}`...\n"
                    "Sending request to preserve repository..."
                ),
                color=discord.Color.yellow(),
            )
            .set_timestamp()
            .build()
        )
        msg = await interaction.followup.send(embed=init_embed, wait=True)

        try:
            process = await asyncio.create_subprocess_exec(
                "iagitbetter",
                link,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except FileNotFoundError:
            err_embed = (
                EmbedBuilder(
                    title="❌ Archive Failed",
                    description=(
                        "`iagitbetter` is not installed or not found in PATH.\n"
                        "Install it with: `pip install iagitbetter`"
                    ),
                    color=discord.Color.red(),
                )
                .set_timestamp()
                .build()
            )
            await msg.edit(embed=err_embed)
            return

        if verbose:
            logging.debug("[git-archive] running: iagitbetter %s", link)

        assert process.stdout is not None
        archive_url: str | None = None
        async for raw in process.stdout:
            line = raw.decode(errors="replace")
            if verbose:
                logging.debug("[iagitbetter] %s", line.rstrip())
            if archive_url is None:
                match = re.search(r"https://archive\.org/\S+", line)
                if match:
                    archive_url = match.group(0).rstrip(".,;)")

        await process.wait()

        if verbose:
            logging.debug("[git-archive] iagitbetter exited with code %s | archive_url=%s", process.returncode, archive_url)

        if process.returncode == 0:
            builder = (
                EmbedBuilder(
                    title="✅ Archive Complete",
                    description="**Status:** Archive succeeded",
                    color=discord.Color.green(),
                )
                .add_field(name="Repository", value=link)
            )
            if archive_url:
                builder.add_field(name="Archive URL", value=archive_url)
            final_embed = builder.set_timestamp().build()
        else:
            final_embed = (
                EmbedBuilder(
                    title="❌ Archive Failed",
                    description=f"**Repository:** `{link}`",
                    color=discord.Color.red(),
                )
                .set_timestamp()
                .build()
            )

        await msg.edit(embed=final_embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GitArchive(bot))
