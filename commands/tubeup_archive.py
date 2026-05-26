from __future__ import annotations

import asyncio
import logging
import re

import discord
from discord import app_commands
from discord.ext import commands

from modules.embed_builder import EmbedBuilder


class TubeupArchive(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="tubeup-archive",
        description="Archive a video to the Internet Archive using tubeup.",
    )
    @app_commands.describe(
        link="Video URL to archive — supports YouTube and any other yt-dlp compatible site."
    )
    async def tubeup_archive(self, interaction: discord.Interaction, link: str) -> None:
        verbose: bool = getattr(self.bot, "verbose", False)
        if verbose:
            logging.debug(
                "[tubeup-archive] invoked by %s (id=%s) in guild=%s channel=%s | link=%s",
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
                    "Sending request to preserve video..."
                ),
                color=discord.Color.yellow(),
            )
            .set_timestamp()
            .build()
        )
        msg = await interaction.followup.send(embed=init_embed, wait=True)

        try:
            process = await asyncio.create_subprocess_exec(
                "tubeup",
                link,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except FileNotFoundError:
            err_embed = (
                EmbedBuilder(
                    title="❌ Archive Failed",
                    description=(
                        "`tubeup` is not installed or not found in PATH.\n"
                        "Install it with: `pip install tubeup`"
                    ),
                    color=discord.Color.red(),
                )
                .set_timestamp()
                .build()
            )
            await msg.edit(embed=err_embed)
            return

        if verbose:
            logging.debug("[tubeup-archive] running: tubeup %s", link)

        assert process.stdout is not None
        archive_url: str | None = None
        already_exists: bool = False
        ia_identifier: str | None = None

        async def _drain_stdout() -> None:
            nonlocal archive_url, already_exists, ia_identifier
            buf = b""
            while True:
                chunk = await process.stdout.read(4096)
                if not chunk:
                    break
                buf += chunk
                
                parts = re.split(rb"[\r\n]", buf)
                buf = parts[-1]
                for part in parts[:-1]:
                    line = part.decode(errors="replace").strip()
                    if not line:
                        continue
                    if verbose:
                        logging.debug("[tubeup] %s", line)
                    if "already exists" in line.lower():
                        already_exists = True
                    if archive_url is None:
                        m = re.search(r"https://archive\.org/\S+", line)
                        if m:
                            archive_url = m.group(0).rstrip(".,;)")
                    if ia_identifier is None:
                        m = re.search(r"(?:identifier|item):\s*([\w-]+)", line, re.IGNORECASE)
                        if m:
                            ia_identifier = m.group(1).strip()

        async def _heartbeat() -> None:
            while True:
                await asyncio.sleep(15)
                try:
                    await msg.edit(
                        embed=EmbedBuilder(
                            title="Archiving Video...",
                            description="Video is being preserved...",
                            color=discord.Color.yellow(),
                        )
                        .set_timestamp()
                        .build()
                    )
                except Exception:
                    pass

        drain_task = asyncio.create_task(_drain_stdout())
        heartbeat_task = asyncio.create_task(_heartbeat())
        try:
            await drain_task
        finally:
            heartbeat_task.cancel()

        await process.wait()

        if verbose:
            logging.debug(
                "[tubeup-archive] tubeup exited with code %s | archive_url=%s | already_exists=%s",
                process.returncode,
                archive_url,
                already_exists,
            )

        if archive_url is None and ia_identifier:
            archive_url = f"https://archive.org/details/{ia_identifier}"
        if archive_url is None:
            yt_id = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", link)
            if yt_id:
                archive_url = f"https://archive.org/details/youtube-{yt_id.group(1)}"

        if process.returncode == 0:
            if already_exists:
                status_text = "**Status:** Already archived"
                title = "✅ Already Archived"
            else:
                status_text = "**Status:** Archive succeeded"
                title = "✅ Archive Complete"
            builder = (
                EmbedBuilder(
                    title=title,
                    description=status_text,
                    color=discord.Color.green(),
                )
                .add_field(name="Video", value=link)
            )
            if archive_url:
                builder.add_field(name="Archive URL", value=archive_url)
            final_embed = builder.set_timestamp().build()
        else:
            final_embed = (
                EmbedBuilder(
                    title="❌ Archive Failed",
                    description=f"**Video:** {link}",
                    color=discord.Color.red(),
                )
                .set_timestamp()
                .build()
            )

        try:
            await msg.edit(embed=final_embed)
        except discord.HTTPException as exc:
            if exc.status == 401 and interaction.channel is not None:
                await interaction.channel.send(
                    content=interaction.user.mention,
                    embed=final_embed,
                )
            else:
                raise


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TubeupArchive(bot))
