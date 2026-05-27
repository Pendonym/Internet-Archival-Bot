from __future__ import annotations

import asyncio
import logging
import re
import shutil
import time
import uuid
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands, tasks

from modules.embed_builder import EmbedBuilder

_DOWNLOAD_BASE = Path(__file__).parent.parent / "tubeup_downloads"


class TubeupArchive(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._active_job_dirs: set[Path] = set()
        _DOWNLOAD_BASE.mkdir(exist_ok=True)
        self._stale_cleanup.start()

    def cog_unload(self) -> None:
        self._stale_cleanup.cancel()

    @tasks.loop(minutes=15)
    async def _stale_cleanup(self) -> None:
        """Delete job dirs older than 30 min that are not actively uploading."""
        cutoff = 30 * 60
        for job_dir in list(_DOWNLOAD_BASE.iterdir()):
            if not job_dir.is_dir() or job_dir in self._active_job_dirs:
                continue
            try:
                if time.time() - job_dir.stat().st_mtime > cutoff:
                    shutil.rmtree(job_dir, ignore_errors=True)
            except OSError:
                pass

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

        job_dir = _DOWNLOAD_BASE / str(uuid.uuid4())
        job_dir.mkdir(parents=True, exist_ok=True)
        self._active_job_dirs.add(job_dir)
        try:
            try:
                process = await asyncio.create_subprocess_exec(
                    "tubeup",
                    link,
                    "--dir", str(job_dir),
                    "--cookies-from-browser", "chrome",
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
                logging.debug("[tubeup-archive] running: tubeup %s --dir %s --cookies-from-browser chrome", link, job_dir)

            assert process.stdout is not None
            archive_url: str | None = None
            already_exists: bool = False
            ia_identifier: str | None = None
            rate_limited: bool = False
            connection_error: bool = False

            async def _drain_stdout() -> None:
                nonlocal archive_url, already_exists, ia_identifier, rate_limited, connection_error
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
                        if "please reduce your request rate" in line.lower() or "appears to be spam" in line.lower():
                            rate_limited = True
                        if "readtimeouterror" in line.lower() or ("connectionerror" in line.lower() and "archive.org" in line.lower()):
                            connection_error = True
                        if archive_url is None:
                            m = re.search(r"https://archive\.org/details/\S+", line)
                            if m:
                                archive_url = m.group(0).rstrip(".,;)'\"")
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
            elif connection_error:
                final_embed = (
                    EmbedBuilder(
                        title="❌ Connection Error",
                        description=(
                            "Could not reach `archive.org` — the server timed out during the upload.\n"
                            "This is a network issue with the host, not the video. Try again later."
                        ),
                        color=discord.Color.red(),
                    )
                    .add_field(name="Video", value=link)
                    .set_timestamp()
                    .build()
                )
            elif rate_limited:
                final_embed = (
                    EmbedBuilder(
                        title="⏳ Upload Rate Limited",
                        description=(
                            "The Internet Archive rejected this upload — your account is being rate limited or flagged as spam.\n"
                            "Try again later, or contact `info@archive.org` if this keeps happening."
                        ),
                        color=discord.Color.orange(),
                    )
                    .add_field(name="Video", value=link)
                    .set_timestamp()
                    .build()
                )
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
                if exc.status == 401:
                    try:
                        await interaction.user.send(embed=final_embed)
                    except discord.HTTPException:
                        pass
                else:
                    raise

        finally:
            self._active_job_dirs.discard(job_dir)
            shutil.rmtree(job_dir, ignore_errors=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TubeupArchive(bot))
