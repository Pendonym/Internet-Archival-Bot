import importlib.util
import logging
import os
import argparse
import discord

from pathlib import Path
from dotenv import load_dotenv
from discord.ext import commands


logging.basicConfig(level=logging.INFO)
logging.getLogger("discord").setLevel(logging.WARNING)

BASE_DIR = Path(__file__).parent
EVENTS_DIR = BASE_DIR / "events"
COMMANDS_DIR = BASE_DIR / "commands"

load_dotenv(BASE_DIR / ".env")

_local_bin = BASE_DIR / ".local" / "bin"
if _local_bin.exists():
    os.environ["PATH"] = str(_local_bin) + os.pathsep + os.environ.get("PATH", "")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix=[], intents=intents)


def load_event_module(module_path: Path) -> None:
    module_name = f"events.{module_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load event module from {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    register = getattr(module, "register", None)
    if not callable(register):
        logging.warning("Skipping event module %s: missing register(bot)", module_name)
        return

    register(bot)
    logging.info("Loaded event module: %s", module_name)


async def load_command_extensions() -> None:
    for command_file in sorted(COMMANDS_DIR.glob("*.py")):
        if command_file.name.startswith("_"):
            continue

        extension = f"commands.{command_file.stem}"
        await bot.load_extension(extension)
        logging.info("Loaded command extension: %s", extension)


@bot.event
async def setup_hook() -> None:
    from discord import app_commands
    bot.tree.allowed_installs = app_commands.AppInstallationType(guild=True, user=True)
    bot.tree.allowed_contexts = app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True)

    for event_file in sorted(EVENTS_DIR.glob("*.py")):
        if event_file.name.startswith("_"):
            continue
        load_event_module(event_file)

    await load_command_extensions()
    await bot.tree.sync()
    logging.info("Synced slash commands")


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive Clanker Discord bot")
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging (command invocations, iagitbetter output, etc.)",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("discord").setLevel(logging.INFO)
        logging.debug("Verbose mode enabled")

    bot.verbose = args.verbose

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN environment variable is not set.")

    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()

