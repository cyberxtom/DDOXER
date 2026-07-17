# DDOXER

Multi-server distributed network stress testing tool controlled via Telegram.

## Architecture

One Telegram bot, unlimited servers. Deploy on multiple servers with the same bot token -- every server receives every command simultaneously. A single `/attack` command triggers all your servers to attack the target at once.

```
Telegram Bot  <--  You send one command
    |
    +-- Server 1 (VPS/cloud)  -->  SYN flood + HTTP + ICMP
    +-- Server 2 (VPS/cloud)  -->  SYN flood + HTTP + ICMP
    +-- Server 3 (VPS/cloud)  -->  SYN flood + HTTP + ICMP
    +-- ...                   -->  ...
```

## Attack Modules

| Module | Type | Description |
|--------|------|-------------|
| SYN Flood | L4 | Raw TCP SYN packet flood via Scapy (requires root) |
| HTTP Flood | L7 | Concurrent HTTP request flood via threads |
| ICMP Flood | L3 | Ping flood via multiprocessing workers |
| Nmap Scan | Recon | TCP Null scan (-T5 -sN) |
| Full Attack | All | Launches all modules in parallel |

## Installation (per server)

```bash
# Install nmap
sudo apt-get update && sudo apt-get install -y nmap

# Clone repo
git clone https://github.com/cyberxtom/DDOXER
cd DDOXER

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Telegram Bot Setup

### 1. Create a Telegram bot

Talk to [@BotFather](https://t.me/BotFather) on Telegram and create a new bot. Copy the bot token.

### 2. Set environment variables

On every server, set these before running the bot:

```bash
export DDOXER_BOT_TOKEN="your_bot_token_from_botfather"
export DDOXER_BOT_PASSWORD="your_secret_password"

# Optional: restrict to specific Telegram user IDs (comma separated)
export DDOXER_ALLOWED_USERS="123456789,987654321"
```

### 3. Run the bot (on every server)

```bash
sudo venv/bin/python bot.py
```

All servers share the same bot token. When you send a command, every server receives it and acts.

## Bot Commands

| Command | Description |
|---------|-------------|
| `/login <password>` | Authenticate (first command) |
| `/target <ip> [port]` | Set target IP and optional port |
| `/attack` | Show attack type selection menu |
| `/stop` | Stop current attack on all servers |
| `/status` | Show current target and attack state |
| `/config` | Show full configuration |
| `/help` | Show help message |

## Usage Example

```
1. /login mypassword           (on any chat with the bot)
2. /target 203.0.113.50 80     (sets target on all servers)
3. /attack -> select Full      (all servers attack simultaneously)
4. /stop                        (stops all servers)
```

## Requirements

- Python 3.8+
- Nmap: `sudo apt-get install nmap`
- Linux with root access (SYN flood requires raw sockets)
- Multiple VPS/cloud servers for distributed attacks

## Notes

- SYN flood and ICMP flood require root privileges.
- HTTP-only mode runs automatically when not running as root.
- The bot uses the same python-telegram-bot library -- all servers poll the same bot and receive the same updates.
- Only test systems you own or have explicit permission to test.
