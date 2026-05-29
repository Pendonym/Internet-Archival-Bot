from __future__ import annotations

import asyncio
import configparser
import logging
import os

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from modules.embed_builder import EmbedBuilder

_SPN_SAVE_URL = "https://web.archive.org/save"
_SPN_STATUS_URL = "https://web.archive.org/save/status/{job_id}"
_POLL_INTERVAL = 5
_MAX_POLLS = 72
_HEARTBEAT_EVERY = 6


class WebArchive(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _get_credentials(self) -> tuple[str, str] | None:
        config_path = os.environ.get("IA_CONFIG_FILE")
        if not config_path:
            return None
        cfg = configparser.ConfigParser()
        cfg.read(config_path)
        try:
            return cfg["s3"]["access"], cfg["s3"]["secret"]
        except KeyError:
            return None

    @app_commands.command(
        name="web-archive",
        description="Save a web page to the Wayback Machine via Save Page Now.",
    )
    @app_commands.describe(
        link="URL of the page to archive.",
        outlinks="Save linked pages (default: True).",
        error_pages="Save 4xx/5xx error pages (default: True).",
        screenshot="Save a screenshot of the page (default: False).",
        disable_adblocker="Disable the Wayback ad blocker during capture (default: False).",
        my_web_archive="Save to your personal web archive (default: True).",
    )
    async def web_archive(
        self,
        interaction: discord.Interaction,
        link: str,
        outlinks: bool = True,
        error_pages: bool = True,
        screenshot: bool = False,
        disable_adblocker: bool = False,
        my_web_archive: bool = True,
    ) -> None:
        verbose: bool = getattr(self.bot, "verbose", False)
        if verbose:
            logging.debug(
                "[web-archive] invoked by %s (id=%s) in guild=%s channel=%s | link=%s outlinks=%s error_pages=%s screenshot=%s disable_adblocker=%s my_web_archive=%s",
                interaction.user,
                interaction.user.id,
                interaction.guild_id,
                interaction.channel_id,
                link,
                outlinks,
                error_pages,
                screenshot,
                disable_adblocker,
                my_web_archive,
            )

        creds = self._get_credentials()
        if creds is None:
            await interaction.response.send_message(
                embed=EmbedBuilder(
                    title="❌ Not Configured",
                    description=(
                        "Internet Archive credentials not found.\n"
                        "Ensure `IA_CONFIG_FILE` is set in `.env` and points to a valid `ia.ini`."
                    ),
                    color=discord.Color.red(),
                )
                .set_timestamp()
                .build(),
                ephemeral=True,
            )
            return

        access, secret = creds
        await interaction.response.defer()

        msg = await interaction.followup.send(
            embed=EmbedBuilder(
                title="📸 Archive Request",
                description="Submitting page to the Wayback Machine...",
                color=discord.Color.yellow(),
            )
            .add_field(name="URL", value=link)
            .set_timestamp()
            .build(),
            wait=True,
        )

        auth_headers = {
            "Authorization": f"LOW {access}:{secret}",
            "Accept": "application/json",
        }

        async with aiohttp.ClientSession(headers=auth_headers) as session:
            post_data: dict[str, str] = {"url": link}
            if outlinks:
                post_data["capture_outlinks"] = "1"
            if error_pages:
                post_data["capture_all"] = "on"
            if screenshot:
                post_data["capture_screenshot"] = "on"
            if disable_adblocker:
                post_data["disable_adblocker"] = "on"
            if my_web_archive:
                post_data["wm-save-mywebarchive"] = "on"

            async with session.post(_SPN_SAVE_URL, data=post_data) as resp:
                if resp.status not in (200, 201):
                    body = await resp.text()
                    if verbose:
                        logging.debug("[web-archive] SPN submit failed: HTTP %s — %s", resp.status, body)
                    try:
                        err_payload = await resp.json(content_type=None)
                        api_message: str | None = err_payload.get("message")
                    except Exception:
                        api_message = None
                    if resp.status == 401:
                        description = api_message or "Internet Archive credentials are invalid or expired."
                        await msg.edit(
                            embed=EmbedBuilder(
                                title="❌ Unauthorized",
                                description=(
                                    f"{description}\n"
                                    "Re-run `ia configure` or check your keys at https://archive.org/account/s3.php"
                                ),
                                color=discord.Color.red(),
                            )
                            .add_field(name="URL", value=link)
                            .set_timestamp()
                            .build()
                        )
                    elif resp.status == 429:
                        description = api_message or "You have too many active Save Page Now sessions. Wait a moment and try again."
                        await msg.edit(
                            embed=EmbedBuilder(
                                title="⏳ Rate Limited",
                                description=description,
                                color=discord.Color.orange(),
                            )
                            .add_field(name="URL", value=link)
                            .set_timestamp()
                            .build()
                        )
                    else:
                        description = api_message or f"Save Page Now rejected the request (HTTP {resp.status})."
                        await msg.edit(
                            embed=EmbedBuilder(
                                title="❌ Archive Failed",
                                description=description,
                                color=discord.Color.red(),
                            )
                            .add_field(name="URL", value=link)
                            .set_timestamp()
                            .build()
                        )
                    return

                payload = await resp.json(content_type=None)
                job_id: str | None = payload.get("job_id")

                if not job_id:
                    if verbose:
                        logging.debug("[web-archive] no job_id in response: %s", payload)
                    api_message: str | None = payload.get("message")
                    description = api_message if api_message else "The Wayback Machine declined to archive this URL."
                    await msg.edit(
                        embed=EmbedBuilder(
                            title="❌ Archive Failed",
                            description=description,
                            color=discord.Color.red(),
                        )
                        .add_field(name="URL", value=link)
                        .set_timestamp()
                        .build()
                    )
                    return

                if verbose:
                    logging.debug("[web-archive] job submitted | job_id=%s", job_id)

            status_text = "pending"
            archive_url: str | None = None
            screenshot_url: str | None = None
            outlink_count: int | None = None
            embed_count: int | None = None

            for attempt in range(_MAX_POLLS):
                await asyncio.sleep(_POLL_INTERVAL)

                async with session.get(
                    _SPN_STATUS_URL.format(job_id=job_id)
                ) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json(content_type=None)

                status_text = data.get("status", "unknown")
                if verbose:
                    logging.debug("[web-archive] poll #%s | status=%s", attempt + 1, status_text)

                if status_text == "success":
                    timestamp = data.get("timestamp")
                    original = data.get("original_url", link)
                    if timestamp:
                        archive_url = f"https://web.archive.org/web/{timestamp}/{original}"
                        if screenshot:
                            screenshot_url = f"https://web.archive.org/web/{timestamp}/http://web.archive.org/screenshot/{original}"
                    counters = data.get("counters", {})
                    outlink_count = counters.get("outlinks")
                    embed_count = counters.get("embeds")
                    break

                if status_text == "error":
                    break

                if attempt % _HEARTBEAT_EVERY == _HEARTBEAT_EVERY - 1:
                    try:
                        await msg.edit(
                            embed=EmbedBuilder(
                                title="📸 Archiving...",
                                description=f"**Status:** `{status_text}`",
                                color=discord.Color.yellow(),
                            )
                            .add_field(name="URL", value=link)
                            .set_timestamp()
                            .build()
                        )
                    except Exception:
                        pass

        if status_text == "success":
            builder = (
                EmbedBuilder(
                    title="✅ Page Archived",
                    description="**Status:** Archive succeeded",
                    color=discord.Color.green(),
                )
                .add_field(name="URL", value=link)
            )
            if archive_url:
                builder.add_field(name="Archive URL", value=archive_url)
            if screenshot_url:
                builder.add_field(name="Screenshot", value=screenshot_url)
            if outlinks and (outlink_count is not None or embed_count is not None):
                parts: list[str] = []
                if outlink_count is not None:
                    parts.append(f"{outlink_count} outlink{'s' if outlink_count != 1 else ''}")
                if embed_count is not None:
                    parts.append(f"{embed_count} embed{'s' if embed_count != 1 else ''}")
                builder.add_field(name="Resources Captured", value=", ".join(parts))
            final_embed = builder.set_timestamp().build()

        elif status_text == "error":
            final_embed = (
                EmbedBuilder(
                    title="❌ Archive Failed",
                    description="**Status:** Save Page Now encountered an error.",
                    color=discord.Color.red(),
                )
                .add_field(name="URL", value=link)
                .set_timestamp()
                .build()
            )

        else:
            final_embed = (
                EmbedBuilder(
                    title="⏱️ Archive Timed Out",
                    description=f"**Status:** Still `{status_text}` after 6 minutes.",
                    color=discord.Color.orange(),
                )
                .add_field(name="URL", value=link)
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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WebArchive(bot))
