from __future__ import annotations

import asyncio
import logging
import os
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


def _detect_link_type(link: str) -> str:
    if "list=" in link or "/playlist" in link:
        return "playlist"
    if re.search(r"(?:youtube\.com|youtu\.be)/(@|c/|channel/|user/)", link):
        return "channel"
    return "video"


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
        description="Archive a video, playlist, or channel to the Internet Archive using tubeup.",
    )
    @app_commands.describe(
        link="URL to archive — supports YouTube videos, playlists, channels, and any other yt-dlp compatible site."
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

        link_type = _detect_link_type(link)
        link_label = link_type.capitalize()
        is_multi = link_type in ("playlist", "channel")

        init_embed = (
            EmbedBuilder(
                title="Archive Request",
                description=(
                    f"Initializing archive request for `{link}`...\n"
                    f"Sending request to preserve {link_type}..."
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
        _cookies = os.getenv("TUBEUP_COOKIES")
        try:
            try:
                process = await asyncio.create_subprocess_exec(
                    "tubeup",
                    link,
                    "--dir", str(job_dir),
                    *([f"--cookies={_cookies}"] if _cookies else []),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    env={**os.environ, "PYTHONIOENCODING": "utf-8"},
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
                _cookies_str = f" --cookies={_cookies}" if _cookies else ""
                logging.debug("[tubeup-archive] running: tubeup %s --dir %s%s", link, job_dir, _cookies_str)

            assert process.stdout is not None
            archived_urls: list[str] = []
            already_exists_count: int = 0
            ia_identifier: str | None = None
            error_count: int = 0
            total_count: int = 0
            rate_limited: bool = False
            connection_error: bool = False
            _url_queue: asyncio.Queue[str] = asyncio.Queue()

            async def _drain_stdout() -> None:
                nonlocal already_exists_count, ia_identifier, error_count, total_count, rate_limited, connection_error
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
                            already_exists_count += 1
                        if "please reduce your request rate" in line.lower() or "appears to be spam" in line.lower():
                            rate_limited = True
                        if "readtimeouterror" in line.lower() or ("connectionerror" in line.lower() and "archive.org" in line.lower()):
                            connection_error = True
                        if re.match(r"ERROR:", line):
                            error_count += 1
                        m = re.search(r"Downloading item \d+ of (\d+)", line)
                        if m:
                            total_count = max(total_count, int(m.group(1)))
                        m = re.search(r"https://archive\.org/details/\S+", line)
                        if m:
                            url = m.group(0).rstrip(".,;)'\"")
                            if url not in archived_urls:
                                archived_urls.append(url)
                                if is_multi:
                                    await _url_queue.put(url)
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
                                title=f"Archiving {link_label}...",
                                description="Video is being preserved...",
                                color=discord.Color.yellow(),
                            )
                            .set_timestamp()
                            .build()
                        )
                    except Exception:
                        pass

            async def _progress_notifier() -> None:
                use_dm = False
                while True:
                    try:
                        new_url = await asyncio.wait_for(_url_queue.get(), timeout=60)
                    except asyncio.TimeoutError:
                        continue
                    except asyncio.CancelledError:
                        return
                    count = len(archived_urls)
                    embed = (
                        EmbedBuilder(
                            title=f"Archiving {link_label}...",
                            description=(
                                f"Archived **{count}** item{'s' if count != 1 else ''} so far...\n"
                                f"Latest: {new_url}"
                            ),
                            color=discord.Color.yellow(),
                        )
                        .set_timestamp()
                        .build()
                    )
                    if not use_dm:
                        try:
                            await msg.edit(embed=embed)
                            continue
                        except discord.HTTPException:
                            use_dm = True
                    try:
                        await interaction.user.send(embed=embed)
                    except discord.HTTPException:
                        pass

            drain_task = asyncio.create_task(_drain_stdout())
            update_task = asyncio.create_task(_progress_notifier() if is_multi else _heartbeat())
            try:
                await drain_task
            finally:
                update_task.cancel()

            await process.wait()

            if verbose:
                logging.debug(
                    "[tubeup-archive] tubeup exited with code %s | archived=%s | errors=%s | total=%s",
                    process.returncode,
                    len(archived_urls),
                    error_count,
                    total_count,
                )

            if not archived_urls and ia_identifier:
                archived_urls.append(f"https://archive.org/details/{ia_identifier}")
            if not archived_urls:
                yt_id = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", link)
                if yt_id:
                    archived_urls.append(f"https://archive.org/details/youtube-{yt_id.group(1)}")

            succeeded = len(archived_urls)
            all_already_existed = already_exists_count > 0 and already_exists_count >= succeeded and not error_count

            def _build_url_list(urls: list[str], limit: int = 1024) -> str:
                lines: list[str] = []
                total_len = 0
                for i, u in enumerate(urls):
                    if total_len + len(u) + 1 > limit - 20:
                        lines.append(f"\u2026 and {len(urls) - i} more")
                        break
                    lines.append(u)
                    total_len += len(u) + 1
                return "\n".join(lines)

            if process.returncode == 0 or (succeeded > 0 and not connection_error):
                if is_multi:
                    if error_count:
                        title = "⚠️ Partially Archived"
                        color = discord.Color.orange()
                    elif all_already_existed:
                        title = "✅ Already Archived"
                        color = discord.Color.green()
                    else:
                        title = "✅ Archive Complete"
                        color = discord.Color.green()
                    summary = f"**{succeeded}** archived"
                    if already_exists_count:
                        summary += f" ({already_exists_count} already existed)"
                    if error_count:
                        summary += f", **{error_count}** failed"
                    builder = (
                        EmbedBuilder(title=title, description=summary, color=color)
                        .add_field(name=link_label, value=link)
                    )
                    if archived_urls:
                        builder.add_field(name="Archive URLs", value=_build_url_list(archived_urls))
                    final_embed = builder.set_timestamp().build()
                else:
                    if all_already_existed:
                        status_text = "**Status:** Already archived"
                        title = "✅ Already Archived"
                    else:
                        status_text = "**Status:** Archive succeeded"
                        title = "✅ Archive Complete"
                    builder = (
                        EmbedBuilder(title=title, description=status_text, color=discord.Color.green())
                        .add_field(name=link_label, value=link)
                    )
                    if archived_urls:
                        builder.add_field(name="Archive URL", value=archived_urls[0])
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
                    .add_field(name=link_label, value=link)
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
                    .add_field(name=link_label, value=link)
                    .set_timestamp()
                    .build()
                )
            else:
                final_embed = (
                    EmbedBuilder(
                        title="❌ Archive Failed",
                        description=f"**{link_label}:** {link}",
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
