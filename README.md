# Discord Music Bot

A music-focused Discord bot for private servers with queue management, reaction-based playback controls and optional Ollama-powered chat support.

## Overview

This project is a custom Discord bot built primarily for music playback on private servers. In addition to standard music features such as queue handling, pause/resume, skip, looping and shuffle, it also includes a few extra utilities like Watch2Gether integration, public IP retrieval and optional local LLM chat via Ollama.

## Features

- Music playback for private Discord servers
- Queue-based song management
- Embedded “now playing” message with thumbnail preview
- Pause, resume, stop, skip, move, remove and loop controls
- Shuffle support via reactions
- Optional Nightcore mode
- Optional Ollama-based chat command
- Watch2Gether helper command
- Public IP command for local/private hosting setups
- Automatic song request channel setup with reaction controls

## Tech Stack

- Python
- discord.py
- yt-dlp
- FFmpeg / ffprobe
- NumPy
- Ollama (optional)
- systemd / shell scripts for Linux deployment

## Commands

Prefix: `pot`

### General
- `pot help` — show available commands
- `pot setup` — create the song request channel and control message
- `pot join` — join your current voice channel
- `pot chat [message]` — chat with the bot through Ollama
- `pot w2g` — send a Watch2Gether room link
- `pot get_ip` — return the public IP of the host system

### Music
- `pot play [url or search]`
- `pot stop`
- `pot pause`
- `pot resume`
- `pot skip`
- `pot loop`
- `pot move [from] [to]`
- `pot remove [index]`
- `pot counter`
- `pot get_song [index]`

## Reaction Controls

The bot also supports reaction-based control inside the configured `songrequest` channel:

- `⏯` pause / resume
- `⏹` stop
- `⏩` skip
- `🔁` loop modes
- `🔀` shuffle
- `👮` toggle special mode
- `😞` toggle Nightcore mode
- `🎅` reserved / seasonal reaction

## Requirements

Before running the bot, make sure the following are installed:

- Python 3
- FFmpeg
- ffprobe
- A Discord bot token
- Required Python packages:
  - `discord.py`
  - `yt-dlp`
  - `numpy`
  - `public-ip`
  - `ollama` (optional, only if you want chat support)

## Installation

Clone the repository:

```bash
git clone https://github.com/hoffmann-luca/Discord-Music-Bot.git
cd Discord-Music-Bot
```

Install the required Python packages:

```bash
pip install discord.py yt-dlp numpy public-ip ollama
```

Install FFmpeg on Linux:

```bash
sudo apt update
sudo apt install ffmpeg
```

## Configuration

This project currently uses a few hardcoded values inside the Python script, so some manual configuration is required before starting the bot.

### 1. Insert your Discord bot token

At the bottom of the script, replace the empty token string:

```python
client.run("YOUR_DISCORD_BOT_TOKEN")
```

### 2. Configure the bot storage path

The bot stores the created message and channel IDs in text files.  
By default, the script expects the following files under:

```text
/root/bot/
```

Used files:

- `/root/bot/message_id.txt`
- `/root/bot/channel_id.txt`
- `/root/bot/guild.txt`

Create the directory first if it does not exist:

```bash
sudo mkdir -p /root/bot
```

If you want to use a different location, update the file paths inside the Python script.

### 3. Configure Ollama (optional)

The `chat` command uses a locally reachable Ollama instance.  
In the current script, the host is set to:

```python
host='http://192.168.178.33:11434'
```

and the model is set to:

```python
model='deepseek-potato'
```

If you want to use this feature, make sure:

- Ollama is installed and running
- the host IP is reachable from the bot
- the selected model exists locally

If you do not need the chat feature, you can simply leave it unused or remove the `chat` command section.

### 4. Configure the Watch2Gether link (optional)

The `w2g` command currently sends an embed with an empty description.  
Add your Watch2Gether room link inside the script where the embed is created.

### 5. Adjust bot-specific placeholders

Depending on your setup, you may also want to replace or review:

- the bot name placeholder
- the empty embed image placeholder
- hardcoded paths
- any private/local-only values

## Running the Bot

Start the bot with:

```bash
python3 PotatoeBot2.0.py
```

## Linux Deployment

This repository also includes a shell script and a systemd service file for Linux-based deployment.

A typical setup might look like this:

```bash
sudo cp myapp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable myapp.service
sudo systemctl start myapp.service
```

Adjust paths, Python locations and permissions to match your system.

## Usage

1. Invite the bot to your Discord server
2. Join a voice channel
3. Run `pot setup`
4. Use the `songrequest` channel for playback control
5. Send song links or use commands to manage playback
