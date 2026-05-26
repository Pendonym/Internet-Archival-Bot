from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable

import discord


class EmbedBuilder:
    def __init__(
        self,
        *,
        title: str | None = None,
        description: str | None = None,
        color: discord.Color | int | None = None,
        url: str | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        self.embed = discord.Embed(
            title=title,
            description=description,
            color=self.normalize_color(color),
            url=url,
            timestamp=timestamp,
        )
        self.footer_text: str | None = None
        self.footer_icon_url: str | None = None

    def apply_footer(self) -> None:
        if not self.footer_text:
            self.embed.remove_footer()
            return

        self.embed.set_footer(text=self.footer_text, icon_url=self.footer_icon_url)

    @staticmethod
    def normalize_color(color: discord.Color | int | None) -> discord.Color | None:
        if color is None:
            return None
        if isinstance(color, discord.Color):
            return color
        return discord.Color(color)

    def set_title(self, title: str | None) -> EmbedBuilder:
        self.embed.title = title
        return self

    def set_description(self, description: str | None) -> EmbedBuilder:
        self.embed.description = description
        return self

    def set_url(self, url: str | None) -> EmbedBuilder:
        self.embed.url = url
        return self

    def set_color(self, color: discord.Color | int | None) -> EmbedBuilder:
        self.embed.color = self.normalize_color(color)
        return self

    def set_timestamp(self, timestamp: datetime | None = None, style: str = "F") -> EmbedBuilder:
        _ = style
        ts = timestamp or datetime.now(UTC)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)

        self.embed.timestamp = ts
        return self

    def set_author(
        self,
        *,
        name: str,
        url: str | None = None,
        icon_url: str | None = None,
    ) -> EmbedBuilder:
        self.embed.set_author(name=name, url=url, icon_url=icon_url)
        return self

    def set_footer(self, *, text: str, icon_url: str | None = None) -> EmbedBuilder:
        self.footer_text = text
        if icon_url is not None:
            self.footer_icon_url = icon_url
        elif self.footer_icon_url is None:
            self.footer_icon_url = self.embed.footer.icon_url

        self.apply_footer()
        return self

    def set_thumbnail(self, url: str | None) -> EmbedBuilder:
        self.embed.set_thumbnail(url=url)
        return self

    def set_image(self, url: str | None) -> EmbedBuilder:
        self.embed.set_image(url=url)
        return self

    def add_field(self, *, name: str, value: str, inline: bool = False) -> EmbedBuilder:
        self.embed.add_field(name=name, value=value, inline=inline)
        return self

    def add_fields(
        self, fields: Iterable[tuple[str, str] | tuple[str, str, bool]]
    ) -> EmbedBuilder:
        for field in fields:
            if len(field) == 2:
                name, value = field
                inline = False
            else:
                name, value, inline = field

            self.embed.add_field(name=name, value=value, inline=inline)
        return self

    def clear_fields(self) -> EmbedBuilder:
        self.embed.clear_fields()
        return self

    def build(self) -> discord.Embed:
        return self.embed.copy()

