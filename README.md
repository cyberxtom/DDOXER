<div align="center">
  <pre>
██████╗ ██████╗  ██████╗ ██╗  ██╗███████╗██████╗
██╔══██╗██╔══██╗██╔═══██╗╚██╗██╔╝██╔════╝██╔══██╗
██║  ██║██   ██╔██║   ██║ ╚███╔╝ █████╗  ██████╔╝
██║  ██║██   ██╗██║   ██║ ██╔██╗ ██╔══╝  ██╔══██╗
██████╔╝███████║╚██████╔╝██╔╝ ██╗███████╗██║  ██║
╚═════╝ ╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
  </pre>
  <p><strong>A simple Multi OSI layer DDOS tool </strong></p>
  <p>
    <a href="https://github.com/cyberxtom/DDOXER"><img src="https://img.shields.io/badge/python-3.8%2B-blue?style=flat-square&logo=python&logoColor=white"></a>
    <a href="https://github.com/cyberxtom/DDOXER"><img src="https://img.shields.io/badge/platform-linux-red?style=flat-square&logo=linux&logoColor=white"></a>
    <a href="https://github.com/cyberxtom/DDOXER"><img src="https://img.shields.io/badge/license-MIT-green?style=flat-square"></a>
    <a href="https://t.me/BotFather"><img src="https://img.shields.io/badge/telegram-bot-26A5E4?style=flat-square&logo=telegram&logoColor=white"></a>
  </p>
</div>

---


<details>
<summary><strong>How it works</strong></summary>
<br>
Each server runs <code>bot.py</code> with the same bot token. All instances poll Telegram independently — every command broadcast to the chat is received by every server. No master node, no coordination server, no single point of failure.
</details>

---

## Attack Modules

<table>
<thead>
<tr>
  <th width="140">Module</th>
  <th width="80">Layer</th>
  <th>Description</th>
  <th width="100">Root</th>
</tr>
</thead>
<tbody>
<tr>
  <td><strong>SYN Flood</strong></td>
  <td><code>L4</code></td>
  <td>Raw TCP SYN packet flood via Scapy (<code>sendpfast</code>)</td>
  <td><span style="color:#e74c3c">required</span></td>
</tr>
<tr>
  <td><strong>HTTP Flood</strong></td>
  <td><code>L7</code></td>
  <td>Concurrent GET request flood across multiple threads</td>
  <td><span style="color:#2ecc71">optional</span></td>
</tr>
<tr>
  <td><strong>ICMP Flood</strong></td>
  <td><code>L3</code></td>
  <td>Ping flood via multiprocessing workers</td>
  <td><span style="color:#e74c3c">required</span></td>
</tr>
<tr>
  <td><strong>Nmap Scan</strong></td>
  <td><code>Recon</code></td>
  <td>TCP Null scan (<code>-T5 -sN</code>) for reconnaissance</td>
  <td><span style="color:#f39c12">partial</span></td>
</tr>
<tr>
  <td><strong>Full Attack</strong></td>
  <td><code>All</code></td>
  <td>Launches SYN + HTTP + ICMP + Nmap simultaneously</td>
  <td><span style="color:#e74c3c">required</span></td>
</tr>
</tbody>
</table>

---

## Quick Start

### 1. Create a Telegram Bot

Talk to <a href="https://t.me/BotFather"><code>@BotFather</code></a> on Telegram and create a new bot. Copy the token.

### 2. Deploy on Each Server

```bash
# Install dependencies
sudo apt-get update
sudo apt-get install -y nmap python3 python3-venv git

# Clone the repository
git clone https://github.com/cyberxtom/DDOXER
cd DDOXER

# Setup virtual environment
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure

```bash
# Set your Telegram bot token and password
export DDOXER_BOT_TOKEN="your_token_from_botfather"
export DDOXER_BOT_PASSWORD="your_secret_password"

# Optional: restrict to specific Telegram user IDs
export DDOXER_ALLOWED_USERS="123456789,987654321"
```

### 4. Launch

On every server:

```bash
sudo venv/bin/python bot.py
```

---

## Bot Commands

<table>
<thead>
<tr>
  <th width="200">Command</th>
  <th>Description</th>
</tr>
</thead>
<tbody>
<tr>
  <td><code>/login &lt;password&gt;</code></td>
  <td>Authenticate with the bot password</td>
</tr>
<tr>
  <td><code>/target &lt;ip&gt; [port]</code></td>
  <td>Set target IP address and optional port</td>
</tr>
<tr>
  <td><code>/attack</code></td>
  <td>Open attack selection menu with inline buttons</td>
</tr>
<tr>
  <td><code>/stop</code></td>
  <td>Stop the current attack immediately</td>
</tr>
<tr>
  <td><code>/status</code></td>
  <td>Show target and attack state</td>
</tr>
<tr>
  <td><code>/config</code></td>
  <td>Display full configuration parameters</td>
</tr>
<tr>
  <td><code>/help</code></td>
  <td>Show help information</td>
</tr>
</tbody>
</table>

---


## Deployment Strategies

<table>
<thead>
<tr>
  <th>Strategy</th>
  <th>Description</th>
</tr>
</thead>
<tbody>
<tr>
  <td><strong>Identical config</strong></td>
  <td>Same target, same attack type on every server — maximum traffic volume</td>
</tr>
<tr>
  <td><strong>Split targets</strong></td>
  <td>Different targets per server group — attack multiple hosts</td>
</tr>
<tr>
  <td><strong>Layer separation</strong></td>
  <td>Some servers do SYN flood (L4), others do HTTP (L7) — cover both layers</td>
</tr>
<tr>
  <td><strong>Geographic spread</strong></td>
  <td>Servers across different regions — bypass geographic filtering</td>
</tr>
</tbody>
</table>

---

## Requirements

<p>
  <img src="https://img.shields.io/badge/python-3.8+-blue?style=flat-square&logo=python">
  <img src="https://img.shields.io/badge/nmap-required-orange?style=flat-square&logo=nmap">
  <img src="https://img.shields.io/badge/os-linux-red?style=flat-square&logo=linux">
  <img src="https://img.shields.io/badge/root-required_for_SYN/ICMP-red?style=flat-square">
</p>

- **Python 3.8+** — virtual environment recommended
- **Nmap** — install via `sudo apt-get install nmap`
- **Linux** — SYN flood requires raw socket access
- **Root** — required for SYN flood and ICMP flood modules

---

## Legal

> This tool is for authorized security testing and research only.
> You must own the target system or have explicit written permission.
> The authors are not responsible for any misuse or damage caused.

---

<div align="center">
  <sub>Built with Python, Scapy, and python-telegram-bot</sub>
</div>
