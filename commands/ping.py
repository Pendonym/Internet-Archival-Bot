import discord
from discord import app_commands
from discord.ext import commands

from modules.embed_builder import EmbedBuilder


class Ping(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Replies with the bot's latency.")
    async def ping(self, interaction: discord.Interaction) -> None:
        latency_ms = round(self.bot.latency * 1000)
        embed = (
            EmbedBuilder(
                title="Pong!",
                description=f"**Response delay**: {latency_ms}ms",
                color=discord.Color.green(),
            )
            .set_timestamp()
            .build()
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Ping(bot))
