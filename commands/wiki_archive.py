from __future__ import annotations

import asyncio
import configparser
import logging
import os
import re
import shutil
import uuid
from pathlib import Path

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from modules.embed_builder import EmbedBuilder

_DUMP_BASE = Path(__file__).parent.parent / "wiki_dumps"

_TYPE_LABELS: dict[str, str] = {
    "mediawiki": "MediaWiki",
    "dokuwiki": "DokuWiki",
    "pukiwiki": "PukiWiki",
}


async def _detect_wiki_type(url: str) -> str | None:
    """Returns 'mediawiki', 'dokuwiki', 'pukiwiki', or None if unknown."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=15),
                allow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; ArchiveBot/1.0)"},
            ) as resp:
                html = await resp.text(errors="replace")
    except Exception:
        return None

    html_lower = html.lower()

    # MediaWiki: generator meta tag, MW.config JS object, or ResourceLoader
    if (
        'name="generator" content="mediawiki' in html_lower
        or "mw.config" in html_lower
        or "w/load.php" in html_lower
        or "/mediawiki/" in html_lower
    ):
        return "mediawiki"

    # DokuWiki: doku.php in links or DOKU_BASE JS var
    if "doku.php" in html_lower or "var doku_base" in html_lower:
        return "dokuwiki"

    # PukiWiki: pukiwiki in source
    if "pukiwiki" in html_lower:
        return "pukiwiki"

    return None


class WikiArchive(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        _DUMP_BASE.mkdir(exist_ok=True)

    @app_commands.command(
        name="wiki-archive",
        description="Archive a wiki (MediaWiki, DokuWiki, or PukiWiki) to the Internet Archive.",
    )
    @app_commands.describe(
        link="URL of the wiki to archive.",
        wiki_type="Wiki software type (default: auto-detect).",
    )
    @app_commands.choices(wiki_type=[
        app_commands.Choice(name="Auto-detect", value="auto"),
        app_commands.Choice(name="MediaWiki", value="mediawiki"),
        app_commands.Choice(name="DokuWiki", value="dokuwiki"),
        app_commands.Choice(name="PukiWiki", value="pukiwiki"),
    ])
    async def wiki_archive(
        self,
        interaction: discord.Interaction,
        link: str,
        wiki_type: str = "auto",
    ) -> None:
        verbose: bool = getattr(self.bot, "verbose", False)
        if verbose:
            logging.debug(
                "[wiki-archive] invoked by %s (id=%s) | link=%s wiki_type=%s",
                interaction.user, interaction.user.id, link, wiki_type,
            )

        await interaction.response.defer()

        # ── Detect wiki type ─────────────────────────────────────────────────
        if wiki_type == "auto":
            msg = await interaction.followup.send(
                embed=EmbedBuilder(
                    title="🔍 Detecting Wiki Type...",
                    description=f"Analyzing `{link}`...",
                    color=discord.Color.yellow(),
                )
                .set_timestamp()
                .build(),
                wait=True,
            )
            detected_type = await _detect_wiki_type(link)
            if detected_type is None:
                await msg.edit(
                    embed=EmbedBuilder(
                        title="❌ Unknown Wiki Type",
                        description=(
                            "Could not detect the wiki software at that URL.\n"
                            "Use the `wiki_type` option to specify it manually."
                        ),
                        color=discord.Color.red(),
                    )
                    .add_field(name="Wiki", value=link)
                    .set_timestamp()
                    .build()
                )
                return
        else:
            detected_type = wiki_type
            msg = await interaction.followup.send(
                embed=EmbedBuilder(
                    title="Archive Request",
                    description=f"Initializing archive request for `{link}`...",
                    color=discord.Color.yellow(),
                )
                .set_timestamp()
                .build(),
                wait=True,
            )

        type_label = _TYPE_LABELS.get(detected_type, detected_type)
        if verbose:
            logging.debug("[wiki-archive] wiki type: %s", detected_type)

        await msg.edit(
            embed=EmbedBuilder(
                title=f"Archiving {type_label}...",
                description=f"Detected: **{type_label}**\nStarting dump, this may take a while...",
                color=discord.Color.yellow(),
            )
            .add_field(name="Wiki", value=link)
            .set_timestamp()
            .build()
        )

        # ── Per-job working directory ─────────────────────────────────────────
        job_dir = _DUMP_BASE / str(uuid.uuid4())
        job_dir.mkdir(parents=True, exist_ok=True)
        try:
            # ── Build command ─────────────────────────────────────────────────
            if detected_type == "mediawiki":
                cmd = ["wikiteam3dumpgenerator", link, "--xml", "--images", "--xmlrevisions"]
                tool_name = "wikiteam3dumpgenerator"
            elif detected_type == "dokuwiki":
                cmd = ["dokuWikiDumper", link, "--auto", "--path", str(job_dir), "-u"]
                tool_name = "dokuWikiDumper"
            else:  # pukiwiki
                cmd = ["pukiWikiDumper", link, "--auto", "--path", str(job_dir), "-u"]
                tool_name = "pukiWikiDumper"

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    cwd=str(job_dir),
                    env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                )
            except FileNotFoundError:
                pip_name = {
                    "wikiteam3dumpgenerator": "wikiteam3",
                    "dokuWikiDumper": "dokuWikiDumper",
                    "pukiWikiDumper": "pukiWikiDumper",
                }[tool_name]
                await msg.edit(
                    embed=EmbedBuilder(
                        title="❌ Archive Failed",
                        description=(
                            f"`{tool_name}` is not installed or not found in PATH.\n"
                            f"Install it with: `pip install {pip_name}`"
                        ),
                        color=discord.Color.red(),
                    )
                    .add_field(name="Wiki", value=link)
                    .set_timestamp()
                    .build()
                )
                return

            if verbose:
                logging.debug("[wiki-archive] running: %s", " ".join(cmd))

            assert process.stdout is not None
            archive_url: str | None = None

            async def _drain(proc_stdout: asyncio.StreamReader, log_prefix: str) -> None:
                nonlocal archive_url
                buf = b""
                while True:
                    chunk = await proc_stdout.read(4096)
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
                            logging.debug("[%s] %s", log_prefix, line)
                        if archive_url is None:
                            m = re.search(r"https://archive\.org/details/\S+", line)
                            if m:
                                archive_url = m.group(0).rstrip(".,;)'\"")

            async def _heartbeat() -> None:
                while True:
                    await asyncio.sleep(20)
                    try:
                        await msg.edit(
                            embed=EmbedBuilder(
                                title=f"Archiving {type_label}...",
                                description="Dump in progress, this may take a while...",
                                color=discord.Color.yellow(),
                            )
                            .add_field(name="Wiki", value=link)
                            .set_timestamp()
                            .build()
                        )
                    except Exception:
                        pass

            drain_task = asyncio.create_task(_drain(process.stdout, tool_name))
            heartbeat_task = asyncio.create_task(_heartbeat())
            try:
                await drain_task
            finally:
                heartbeat_task.cancel()

            await process.wait()

            if verbose:
                logging.debug(
                    "[wiki-archive] %s exited with code %s | archive_url=%s",
                    tool_name, process.returncode, archive_url,
                )

            # ── MediaWiki: separate upload step ───────────────────────────────
            if detected_type == "mediawiki" and process.returncode == 0 and archive_url is None:
                dump_subdirs = [d for d in job_dir.iterdir() if d.is_dir()]
                if dump_subdirs:
                    dump_path = dump_subdirs[0]

                    # Write wikiteam3 IA keys file if missing
                    keys_file = Path.home() / ".wikiteam3_ia_keys.txt"
                    if not keys_file.exists():
                        ia_cfg_path = os.environ.get("IA_CONFIG_FILE")
                        if ia_cfg_path:
                            cfg = configparser.ConfigParser()
                            cfg.read(ia_cfg_path)
                            try:
                                keys_file.write_text(
                                    f"{cfg['s3']['access']}:{cfg['s3']['secret']}\n"
                                )
                            except (KeyError, OSError):
                                pass

                    try:
                        await msg.edit(
                            embed=EmbedBuilder(
                                title=f"Uploading {type_label}...",
                                description="Dump complete. Uploading to Internet Archive...",
                                color=discord.Color.yellow(),
                            )
                            .add_field(name="Wiki", value=link)
                            .set_timestamp()
                            .build()
                        )
                    except Exception:
                        pass

                    try:
                        upload_proc = await asyncio.create_subprocess_exec(
                            "wikiteam3uploader", str(dump_path),
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.STDOUT,
                            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                        )
                        assert upload_proc.stdout is not None
                        upload_drain = asyncio.create_task(
                            _drain(upload_proc.stdout, "wikiteam3uploader")
                        )
                        upload_heartbeat = asyncio.create_task(_heartbeat())
                        try:
                            await upload_drain
                        finally:
                            upload_heartbeat.cancel()
                        await upload_proc.wait()
                        if verbose:
                            logging.debug(
                                "[wiki-archive] wikiteam3uploader exited with code %s | archive_url=%s",
                                upload_proc.returncode, archive_url,
                            )
                    except FileNotFoundError:
                        if verbose:
                            logging.debug("[wiki-archive] wikiteam3uploader not found, skipping upload")

            # ── Final embed ───────────────────────────────────────────────────
            if process.returncode == 0:
                builder = (
                    EmbedBuilder(
                        title="✅ Wiki Archived",
                        description=f"**Type:** {type_label}\n**Status:** Archive succeeded",
                        color=discord.Color.green(),
                    )
                    .add_field(name="Wiki", value=link)
                )
                if archive_url:
                    builder.add_field(name="Archive URL", value=archive_url)
                final_embed = builder.set_timestamp().build()
            else:
                final_embed = (
                    EmbedBuilder(
                        title="❌ Archive Failed",
                        description=f"**Type:** {type_label}",
                        color=discord.Color.red(),
                    )
                    .add_field(name="Wiki", value=link)
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
            shutil.rmtree(job_dir, ignore_errors=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WikiArchive(bot))
