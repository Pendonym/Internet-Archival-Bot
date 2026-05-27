# Internet Archival Bot

A Discord bot for archiving content to the [Internet Archive](https://archive.org). Supports archiving git repositories, videos, and web pages via slash commands.

## Commands

| Command | Description |
|---|---|
| `/ping` | Check bot latency |
| `/git-archive link: [all_files:] [include_wiki:] [all_releases:] [all_branches:]` | Archive a git repository via [iagitbetter](https://github.com/Andres9890/iagitbetter) |
| `/tubeup-archive link:` | Archive a video (YouTube or any yt-dlp source) via [tubeup](https://github.com/bibanon/tubeup) |
| `/web-archive link: [outlinks:] [error_pages:] [screenshot:] [disable_adblocker:] [my_web_archive:]` | Save a web page to the Wayback Machine via Save Page Now |

## Setup

> [!TIP]
> Don't want to host it yourself? [Add the already-running bot to your account or server.](https://discord.com/oauth2/authorize?client_id=1508783480266293439)
> Archived content is uploaded under the [@yt-dlp_bot](https://archive.org/details/@yt-dlp_bot) Internet Archive account.

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Internet Archive credentials

Log in with the `ia` CLI:

```bash
ia configure
```

### 3. Create a `.env` file

```env
DISCORD_TOKEN=your_discord_bot_token
IA_CONFIG_FILE=/path/to/ia.ini
```

### 4. Run the bot

```bash
python main.py
python main.py -v  # verbose logging
```

## Installation

The bot supports both guild and user installs, and can be used in servers, DMs, and group DMs.

