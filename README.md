# DDOX

Network stress testing and web application security auditing tools.

## Tools

### DDOXER (main.py)

Multi-engine network stress testing tool with the following attack modules:

- **SYN Flood** - Raw packet flood via Scapy (requires root)
- **HTTP Layer 7 Flood** - Concurrent HTTP request flood via multiple threads
- **ICMP Flood** - ICMP ping flood via multiprocessing workers
- **Nmap Scan** - TCP Null scan (-T5 -sN) via subprocess

### Security Tester (test.py)

Web application security scanner that tests for:

- SSL/HTTPS configuration and HSTS headers
- Security headers (X-Frame-Options, CSP, XSS-Protection, etc.)
- CSRF protection (ASP.NET ViewState/EventValidation)
- SQL injection vulnerabilities
- Password field security
- Information disclosure (version leaks, error messages)
- Brute force protection / rate limiting
- Cross-site scripting (XSS)
- Session management (cookie security flags)
- HTML structure analysis (inline scripts, SRI)

## Installation

```bash
# Clone and enter the repository
git clone <repo-url>
cd DDOX

# Create Python virtual environment
python3 -m venv venv

# Activate virtual environment and install dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Usage

All tools should be run with **sudo** due to raw socket access and elevated permissions required by certain attack modules.

### DDOXER

```bash
sudo venv/bin/python main.py
```

Interactive menu options:
1. Start Full Attack (Nmap + SYN + HTTP + ICMP)
2. Run Nmap Scan Only (-T5 -sN)
3. Start HTTP Flood Only
4. Start SYN Flood Only (requires root)
5. Start ICMP Flood Only
6. Stop All Attacks
7. Show Status
8. Configure Target
9. Advanced Configuration
10. Exit

### Security Tester

```bash
sudo venv/bin/python test.py <target-url>
```

Example:
```bash
sudo venv/bin/python test.py https://example.com/login.aspx
```

## Requirements

- Python 3.8+
- Nmap (for scan functionality): `sudo apt-get install nmap`
- Linux environment recommended (SYN flood requires raw sockets)

## Dependencies

- requests, ping3, scapy, python-nmap, beautifulsoup4

## Notes

- SYN flood and ICMP flood modules require root privileges.
- HTTP-only mode runs automatically when not running as root.
- The security tester disables SSL verification for testing purposes.
- Only test systems you own or have explicit permission to test.
