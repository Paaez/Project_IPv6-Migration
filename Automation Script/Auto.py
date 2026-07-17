#!/usr/bin/env python3
"""
auto.py - Main Menu for IPv6 Migration Testing Suite
Interactive menu to run setup, tests, and automation
All options now ask which strategy to run

Usage: python auto.py
"""

import subprocess
import time
import sys
import os
import json
import argparse
import socket
import shutil
import signal 
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# =============================================
# CONFIGURATION
# =============================================

GNS3_HOST = "192.168.255.128"
PROJECT_DIR = r"C:\Users\user\OneDrive\Documents\Abg Paeez\CSP 600\FYP_IPv6_Project\Project Directory"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Result files
RESULT_FILES = {
    "T1Rs.json": "Test1 - Packet Size Performance",
    "T2Rs.json": "Test2 - HTTP Performance",
    "T3Rs.json": "Test3 - RTT Consistency",
    "T5Rs.json": "Test5 - Fragmentation Test"
}

# Node ports
NODE_PORTS = {
    "dualstack": {"PC1": 5013, "PC2": 5015, "PC3": 50121, "Linux-Server": 5002},
    "dslite": {"PC1": 5003, "PC2": 5007, "PC3": 5012, "Linux-Server": 5018},
    "nat64": {"PC1": 5000, "PC2": 5003, "PC3": 5007, "Linux-Server": 5012}
}

SERVER_PORTS = {
    "dualstack": 5002,
    "dslite": 5018,
    "nat64": 5012,
}

# Strategy display names
STRATEGY_CONFIG = {
    "dualstack": {
        "name": "Dual Stack",
        "short_name": "DUAL",
        "iperf_ip": "203.0.113.1",
        "iperf_port": 5002
    },
    "dslite": {
        "name": "DS-Lite",
        "short_name": "DSLITE",
        "iperf_ip": "203.0.113.1",
        "iperf_port": 5018
    },
    "nat64": {
        "name": "NAT64",
        "short_name": "NAT64",
        "iperf_ip": "203.0.113.1",
        "iperf_port": 5012
    }
}

# Track status for all strategies
strategy_status = {}
for strat in STRATEGY_CONFIG.keys():
    strategy_status[strat] = {
        "setup_done": False,
        "iperf_running": False,
        "http_running": False,
        "test1_done": False,
        "test2_done": False,
        "test3_done": False,
        "test5_done": False
    }

# Current active strategy
current_strategy = "dualstack"
current_run = 1

# Wait times
WAIT_TIMES = {
    "after_setup": 15,
    "after_http": 10,
    "between_tests": 10,
    "for_server": 10,
    "for_data_collection": 15
}

# =============================================
# HELPER FUNCTIONS
# =============================================

def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    """Print main banner"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     IPv6 MIGRATION TEST AUTOMATION MENU                      ║
║                        Manual Control & Testing Suite                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

def print_status_bar():
    """Print current status bar"""
    config = STRATEGY_CONFIG[current_strategy]
    
    # Build setup status line
    setup_line = ""
    for strat, status in strategy_status.items():
        short = STRATEGY_CONFIG[strat]['short_name']
        icon = "[OK]" if status["setup_done"] else "[--]"
        setup_line += f"{short}={icon}  "
    
    # Build test status line
    test_line = ""
    for strat in STRATEGY_CONFIG.keys():
        s = strategy_status[strat]
        short = STRATEGY_CONFIG[strat]['short_name'][:4]
        t1 = "[OK]" if s['test1_done'] else "[--]"
        t2 = "[OK]" if s['test2_done'] else "[--]"
        t3 = "[OK]" if s['test3_done'] else "[--]"
        t5 = "[OK]" if s['test5_done'] else "[--]"
        test_line += f"{short}:T1{t1} T2{t2} T3{t3} T5{t5}  "
    
    # Current strategy servers
    s = strategy_status[current_strategy]
    iperf_status = "[ON]" if s['iperf_running'] else "[OFF]"
    http_status = "[ON]" if s['http_running'] else "[OFF]"
    
    print(f"""
┌──────────────────────────────────────────────────────────────────────────────┐
│ ACTIVE: {config['name']:<20} Run #{current_run:<5}                     │
│ Setup: {setup_line:<55}│
│ Active Servers: iperf3={iperf_status}  HTTP={http_status}                         │
│ Tests: {test_line:<72}│
└──────────────────────────────────────────────────────────────────────────────┘
""")

def print_header(text: str):
    """Print section header"""
    print(f"\n{'='*80}")
    print(f"  {text}")
    print(f"{'='*80}")

def print_info(message: str):
    """Print info message"""
    print(f"  [INFO] {message}")

def print_success(message: str):
    """Print success message"""
    print(f"  [ OK ] {message}")

def print_error(message: str):
    """Print error message"""
    print(f"  [FAIL] {message}")

def print_warning(message: str):
    """Print warning message"""
    print(f"  [WARN] {message}")

def press_enter():
    """Wait for user to press Enter"""
    input(f"\n  Press ENTER to continue...")

def countdown_timer(seconds: int, message: str = "Waiting"):
    """Show countdown timer"""
    print_info(f"{message}...")
    for i in range(seconds, 0, -1):
        if i % 5 == 0 or i <= 3:
            sys.stdout.write(f"\r  ... {i}s remaining   ")
            sys.stdout.flush()
        time.sleep(1)
    print()

def check_port(port: int, timeout: int = 3) -> bool:
    """Check if port is reachable"""
    try:
        with socket.create_connection((GNS3_HOST, port), timeout=timeout):
            return True
    except:
        return False

def send_telnet_command(port: int, command: str, wait: int = 2) -> bool:
    """Send command via telnet port"""
    try:
        with socket.create_connection((GNS3_HOST, port), timeout=10) as sock:
            sock.sendall(b"\n")
            time.sleep(0.5)
            sock.sendall(command.encode("ascii") + b"\n")
            time.sleep(wait)
        return True
    except Exception as e:
        print_error(f"Failed to send command to port {port}: {e}")
        return False

def run_command(cmd: List[str], description: str, timeout: int = 300) -> Tuple[bool, str]:
    """Run a command and return (success, output)"""
    print_info(f"Running: {description}")
    print(f"     Cmd: {' '.join(cmd)}")
    print(f"     {'-'*60}")
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=SCRIPT_DIR,
            encoding='utf-8',
            errors='replace',
            bufsize=1
        )
        
        output_lines = []
        try:
            for line in process.stdout:
                line = line.rstrip()
                if line:
                    output_lines.append(line)
                    if len(output_lines) <= 20:
                        print(f"     {line[:120]}")
            
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            print_error(f"Command timed out after {timeout}s")
            return False, "\n".join(output_lines)
        
        if process.returncode == 0:
            print_success(f"Command completed successfully")
            print()
            return True, "\n".join(output_lines)
        else:
            print_error(f"Command failed with code {process.returncode}")
            print()
            return False, "\n".join(output_lines)
            
    except Exception as e:
        print_error(f"Error: {e}")
        print()
        return False, ""

def select_strategy(prompt: str = "SELECT STRATEGY", allow_multiple: bool = False) -> List[str]:
    """Strategy selection menu - single or multiple"""
    strategies = list(STRATEGY_CONFIG.keys())
    selected = []
    
    while True:
        clear_screen()
        print_banner()
        print_header(prompt)
        print()
        
        for i, key in enumerate(strategies, 1):
            config = STRATEGY_CONFIG[key]
            s = strategy_status[key]
            
            setup_icon = "[OK]" if s["setup_done"] else "[--]"
            iperf_icon = "[ON]" if s["iperf_running"] else "[OFF]"
            http_icon = "[ON]" if s["http_running"] else "[OFF]"
            
            status_str = f"Setup={setup_icon} iperf3={iperf_icon} HTTP={http_icon}"
            marker = " [SELECTED]" if key in selected else ""
            
            print(f"  {i}. {config['name']}{marker}")
            print(f"     {status_str}")
        
        if allow_multiple:
            print(f"\n  A. Select ALL strategies")
            print(f"  D. Done selecting")
        print(f"  0. Cancel")
        print()
        
        if selected:
            names = [STRATEGY_CONFIG[s]['name'] for s in selected]
            print(f"  Selected: {', '.join(names)}")
        
        choice = input("\n  Choice: ").strip().lower()
        
        if choice == '0':
            return []
        elif allow_multiple and choice == 'd':
            if selected:
                return selected
            else:
                print_error("Select at least one strategy")
                time.sleep(1)
        elif allow_multiple and choice == 'a':
            return list(strategies)
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(strategies):
                    key = strategies[idx]
                    if allow_multiple:
                        if key in selected:
                            selected.remove(key)
                        else:
                            selected.append(key)
                        time.sleep(0.3)
                    else:
                        return [key]
                else:
                    print_error("Invalid choice")
                    time.sleep(1)
            except ValueError:
                print_error("Invalid input")
                time.sleep(1)

def execute_for_strategies(strategies: List[str], action_func, action_name: str):
    """Execute an action for multiple strategies"""
    if not strategies:
        return
    
    clear_screen()
    print_banner()
    print_header(f"{action_name}")
    
    names = [STRATEGY_CONFIG[s]['name'] for s in strategies]
    print_info(f"Will execute for: {', '.join(names)}")
    
    if len(strategies) > 1:
        print_warning("You may need to switch GNS3 projects between strategies")
    
    print()
    confirm = input(f"  Continue? (y/n): ").strip().lower()
    if confirm != 'y':
        return
    
    for i, strategy_key in enumerate(strategies, 1):
        if len(strategies) > 1:
            print_header(f"{action_name} {i}/{len(strategies)}: {STRATEGY_CONFIG[strategy_key]['name']}")
            
            if i > 1:
                print_warning("ACTION REQUIRED:")
                print_info(f"  1. Switch GNS3 to {STRATEGY_CONFIG[strategy_key]['name']} project")
                print_info("  2. Ensure all nodes are started")
                input("\n  Press ENTER when ready...")
        
        action_func(strategy_key)
        
        if i < len(strategies):
            print()
            cont = input(f"  Continue to next strategy? (y/n): ").strip().lower()
            if cont != 'y':
                print_info("Sequence stopped")
                break
    
    print_success(f"{action_name} completed")
    press_enter()

# =============================================
# STRATEGY-SPECIFIC ACTIONS
# =============================================

def do_setup(strategy_key: str):
    """Perform network setup for a strategy"""
    global strategy_status
    
    config = STRATEGY_CONFIG[strategy_key]
    
    success, _ = run_command(
        [sys.executable, "setup.py", "--project", strategy_key],
        f"Network setup for {config['name']}",
        timeout=120
    )
    
    if success:
        strategy_status[strategy_key]["setup_done"] = True
        strategy_status[strategy_key]["iperf_running"] = False
        strategy_status[strategy_key]["http_running"] = False
        strategy_status[strategy_key]["test1_done"] = False
        strategy_status[strategy_key]["test2_done"] = False
        strategy_status[strategy_key]["test3_done"] = False
        strategy_status[strategy_key]["test5_done"] = False
        
        print_success(f"{config['name']} setup complete")
        countdown_timer(WAIT_TIMES['after_setup'], "Network convergence")
    else:
        print_error(f"{config['name']} setup failed")
        strategy_status[strategy_key]["setup_done"] = False

def do_start_iperf(strategy_key: str):
    """Start iperf3 for a strategy"""
    global strategy_status
    
    config = STRATEGY_CONFIG[strategy_key]
    server_port = config["iperf_port"]
    target_ip = config["iperf_ip"]
    
    if not strategy_status[strategy_key]["setup_done"]:
        print_warning(f"Setup not done for {config['name']}!")
        response = input("  Run setup first? (y/n): ").strip().lower()
        if response == 'y':
            do_setup(strategy_key)
            if not strategy_status[strategy_key]["setup_done"]:
                return
        else:
            return
    
    # Kill existing
    send_telnet_command(server_port, "pkill -9 iperf3 2>/dev/null; pkill -9 iperf 2>/dev/null", wait=2)
    time.sleep(2)
    
    # Start server
    start_cmd = f"iperf3 -s -B {target_ip} -D --logfile /tmp/iperf3_server.log"
    
    if send_telnet_command(server_port, start_cmd, wait=3):
        time.sleep(2)
        if send_telnet_command(server_port, "pgrep -a iperf3", wait=1):
            strategy_status[strategy_key]["iperf_running"] = True
            print_success(f"iperf3 server started for {config['name']}")
            countdown_timer(WAIT_TIMES['for_server'], "Server initialization")
        else:
            print_warning("iperf3 server may not have started")
    else:
        print_error("Failed to start iperf3 server")

def do_stop_iperf(strategy_key: str):
    """Stop iperf3 for a strategy"""
    global strategy_status
    
    config = STRATEGY_CONFIG[strategy_key]
    server_port = config["iperf_port"]
    
    if send_telnet_command(server_port, "pkill -9 iperf3 2>/dev/null; pkill -9 iperf 2>/dev/null", wait=2):
        strategy_status[strategy_key]["iperf_running"] = False
        print_success(f"iperf3 server stopped for {config['name']}")
    else:
        print_error(f"Failed to stop iperf3 for {config['name']}")

def do_start_http(strategy_key: str):
    """Start HTTP server for a strategy"""
    global strategy_status
    
    config = STRATEGY_CONFIG[strategy_key]
    
    if not strategy_status[strategy_key]["setup_done"]:
        print_warning(f"Setup not done for {config['name']}!")
        response = input("  Run setup first? (y/n): ").strip().lower()
        if response == 'y':
            do_setup(strategy_key)
            if not strategy_status[strategy_key]["setup_done"]:
                return
        else:
            return
    
    success, _ = run_command(
        [sys.executable, "setup_https.py", "--strategy", strategy_key],
        f"HTTP server setup for {config['name']}",
        timeout=60
    )
    
    if success:
        strategy_status[strategy_key]["http_running"] = True
        print_success(f"HTTP server started for {config['name']}")
        countdown_timer(WAIT_TIMES['after_http'], "Server stabilization")
    else:
        print_error(f"HTTP server setup failed for {config['name']}")

def do_stop_http(strategy_key: str):
    """Stop HTTP server for a strategy"""
    global strategy_status
    
    config = STRATEGY_CONFIG[strategy_key]
    
    cleanup_script = os.path.join(SCRIPT_DIR, "cleanup_https.py")
    if os.path.exists(cleanup_script):
        success, _ = run_command(
            [sys.executable, cleanup_script, "--strategy", strategy_key],
            f"HTTP cleanup for {config['name']}",
            timeout=30
        )
    else:
        success, _ = run_command(
            [sys.executable, "setup_https.py", "--strategy", strategy_key, "--stop"],
            f"HTTP stop for {config['name']}",
            timeout=30
        )
    
    if success:
        strategy_status[strategy_key]["http_running"] = False
        print_success(f"HTTP server stopped for {config['name']}")
    else:
        print_warning(f"HTTP server may still be running for {config['name']}")

def do_test1(strategy_key: str):
    """Run Test1 for a strategy"""
    global strategy_status
    
    config = STRATEGY_CONFIG[strategy_key]
    s = strategy_status[strategy_key]
    
    print_info(f"Status: setup={s['setup_done']}, iperf3={s['iperf_running']}")
    
    if not s["setup_done"]:
        print_warning(f"Setup not done for {config['name']}!")
        response = input("  Run setup first? (y/n): ").strip().lower()
        if response == 'y':
            do_setup(strategy_key)
            if not strategy_status[strategy_key]["setup_done"]:
                return
        else:
            return
    
    if not s["iperf_running"]:
        print_warning(f"iperf3 not running for {config['name']}!")
        response = input("  Start iperf3 now? (y/n): ").strip().lower()
        if response == 'y':
            do_start_iperf(strategy_key)
            if not strategy_status[strategy_key]["iperf_running"]:
                return
        else:
            return
    
    success, _ = run_command(
        [sys.executable, "Test1.py", "--project", strategy_key, "--mode", "run", "--run", str(current_run)],
        f"Test1 - {config['name']}",
        timeout=300
    )
    
    if success:
        countdown_timer(WAIT_TIMES['for_data_collection'], "Collecting data")
        result_path = os.path.join(PROJECT_DIR, "T1Rs.json")
        if os.path.exists(result_path):
            strategy_status[strategy_key]["test1_done"] = True
            print_success(f"Test1 completed for {config['name']}")
        else:
            print_warning("Test1 completed but data file not found")
    else:
        print_error(f"Test1 failed for {config['name']}")

def do_test2(strategy_key: str):
    """Run Test2 for a strategy"""
    global strategy_status
    
    config = STRATEGY_CONFIG[strategy_key]
    s = strategy_status[strategy_key]
    
    print_info(f"Status: setup={s['setup_done']}, http={s['http_running']}")
    
    if not s["setup_done"]:
        print_warning(f"Setup not done for {config['name']}!")
        response = input("  Run setup first? (y/n): ").strip().lower()
        if response == 'y':
            do_setup(strategy_key)
            if not strategy_status[strategy_key]["setup_done"]:
                return
        else:
            return
    
    if not s["http_running"]:
        print_warning(f"HTTP server not running for {config['name']}!")
        response = input("  Start HTTP server now? (y/n): ").strip().lower()
        if response == 'y':
            do_start_http(strategy_key)
            if not strategy_status[strategy_key]["http_running"]:
                return
        else:
            return
    
    success, _ = run_command(
        [sys.executable, "Test2.py", "--project", strategy_key, "--mode", "run", "--run", str(current_run)],
        f"Test2 - {config['name']}",
        timeout=180
    )
    
    if success:
        countdown_timer(WAIT_TIMES['for_data_collection'], "Collecting data")
        result_path = os.path.join(PROJECT_DIR, "T2Rs.json")
        if os.path.exists(result_path):
            strategy_status[strategy_key]["test2_done"] = True
            print_success(f"Test2 completed for {config['name']}")
        else:
            print_warning("Test2 completed but data file not found")
    else:
        print_error(f"Test2 failed for {config['name']}")

def do_test3(strategy_key: str):
    """Run Test3 for a strategy"""
    global strategy_status
    
    config = STRATEGY_CONFIG[strategy_key]
    s = strategy_status[strategy_key]
    
    print_info(f"Status: setup={s['setup_done']}, iperf3={s['iperf_running']}")
    
    if not s["setup_done"]:
        print_warning(f"Setup not done for {config['name']}!")
        response = input("  Run setup first? (y/n): ").strip().lower()
        if response == 'y':
            do_setup(strategy_key)
            if not strategy_status[strategy_key]["setup_done"]:
                return
        else:
            return
    
    if not s["iperf_running"]:
        print_warning(f"iperf3 not running for {config['name']}!")
        response = input("  Start iperf3 now? (y/n): ").strip().lower()
        if response == 'y':
            do_start_iperf(strategy_key)
            if not strategy_status[strategy_key]["iperf_running"]:
                return
        else:
            return
    
    success, _ = run_command(
        [sys.executable, "test3.py", "--project", strategy_key, "--mode", "run", "--run", str(current_run)],
        f"Test3 - {config['name']}",
        timeout=120
    )
    
    if success:
        countdown_timer(WAIT_TIMES['for_data_collection'], "Collecting data")
        result_path = os.path.join(PROJECT_DIR, "T3Rs.json")
        if os.path.exists(result_path):
            strategy_status[strategy_key]["test3_done"] = True
            print_success(f"Test3 completed for {config['name']}")
        else:
            print_warning("Test3 completed but data file not found")
    else:
        print_error(f"Test3 failed for {config['name']}")

def do_test5(strategy_key: str):
    """Run Test5 for a strategy"""
    global strategy_status
    
    config = STRATEGY_CONFIG[strategy_key]
    s = strategy_status[strategy_key]
    
    print_info(f"Status: setup={s['setup_done']}, iperf3={s['iperf_running']}")
    
    if not s["setup_done"]:
        print_warning(f"Setup not done for {config['name']}!")
        response = input("  Run setup first? (y/n): ").strip().lower()
        if response == 'y':
            do_setup(strategy_key)
            if not strategy_status[strategy_key]["setup_done"]:
                return
        else:
            return
    
    if not s["iperf_running"]:
        print_warning(f"iperf3 not running for {config['name']}!")
        response = input("  Start iperf3 now? (y/n): ").strip().lower()
        if response == 'y':
            do_start_iperf(strategy_key)
            if not strategy_status[strategy_key]["iperf_running"]:
                return
        else:
            return
    
    success, _ = run_command(
        [sys.executable, "Test5.py", "--project", strategy_key, "--mode", "run", "--run", str(current_run)],
        f"Test5 - {config['name']}",
        timeout=240
    )
    
    if success:
        countdown_timer(WAIT_TIMES['for_data_collection'], "Collecting data")
        result_path = os.path.join(PROJECT_DIR, "T5Rs.json")
        if os.path.exists(result_path):
            strategy_status[strategy_key]["test5_done"] = True
            print_success(f"Test5 completed for {config['name']}")
        else:
            print_warning("Test5 completed but data file not found")
    else:
        print_error(f"Test5 failed for {config['name']}")

# =============================================
# MENU ACTIONS
# =============================================

def action_check_status():
    """Check system status"""
    clear_screen()
    print_banner()
    print_status_bar()
    print_header("SYSTEM STATUS CHECK")
    
    # Check GNS3
    print_info("Checking GNS3 host...")
    try:
        socket.create_connection((GNS3_HOST, 22), timeout=3)
        print_success(f"GNS3 host {GNS3_HOST} reachable")
    except:
        print_warning(f"GNS3 host {GNS3_HOST} not reachable")
    
    # Check nodes
    print()
    print_header("NODE STATUS")
    for strat, ports in NODE_PORTS.items():
        config = STRATEGY_CONFIG[strat]
        print(f"\n  {config['name']}:")
        for node, port in ports.items():
            if check_port(port):
                print(f"    {node:<15} port {port:<6} [OK]")
            else:
                print(f"    {node:<15} port {port:<6} [FAIL]")
    
    # Check result files
    print()
    print_header("RESULT FILES")
    for filename, desc in RESULT_FILES.items():
        filepath = os.path.join(PROJECT_DIR, filename)
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                counts = {}
                for strat in STRATEGY_CONFIG.keys():
                    counts[strat] = len([e for e in data if e.get('strategy', '').lower() == strat.lower()])
                count_str = ", ".join([f"{STRATEGY_CONFIG[k]['short_name']}:{v}" for k, v in counts.items()])
                print_success(f"{filename} ({desc}) - {size} bytes - {count_str}")
            except:
                print_success(f"{filename} - {size} bytes")
        else:
            print_warning(f"{filename} - Not found")
    
    # Strategy status table
    print()
    print_header("STRATEGY STATUS SUMMARY")
    print(f"  {'Strategy':<15} {'Setup':<8} {'iperf3':<8} {'HTTP':<8} {'T1':<5} {'T2':<5} {'T3':<5} {'T5':<5}")
    print(f"  {'-'*62}")
    for strat, status in strategy_status.items():
        name = STRATEGY_CONFIG[strat]['name']
        print(f"  {name:<15} {'[OK]' if status['setup_done'] else '[--]':<8} {'[ON]' if status['iperf_running'] else '[OFF]':<8} {'[ON]' if status['http_running'] else '[OFF]':<8} {'[OK]' if status['test1_done'] else '[--]':<5} {'[OK]' if status['test2_done'] else '[--]':<5} {'[OK]' if status['test3_done'] else '[--]':<5} {'[OK]' if status['test5_done'] else '[--]':<5}")
    
    press_enter()

def action_setup():
    """Run network setup"""
    strategies = select_strategy("NETWORK SETUP - SELECT STRATEGY", allow_multiple=True)
    if strategies:
        execute_for_strategies(strategies, do_setup, "NETWORK SETUP")

def action_start_iperf():
    """Start iperf3 server"""
    strategies = select_strategy("START IPERF3 - SELECT STRATEGY", allow_multiple=True)
    if strategies:
        execute_for_strategies(strategies, do_start_iperf, "START IPERF3")

def action_stop_iperf():
    """Stop iperf3 server"""
    strategies = select_strategy("STOP IPERF3 - SELECT STRATEGY", allow_multiple=True)
    if strategies:
        execute_for_strategies(strategies, do_stop_iperf, "STOP IPERF3")

def action_start_http():
    """Start HTTP server"""
    strategies = select_strategy("START HTTP - SELECT STRATEGY", allow_multiple=True)
    if strategies:
        execute_for_strategies(strategies, do_start_http, "START HTTP SERVER")

def action_stop_http():
    """Stop HTTP server"""
    strategies = select_strategy("STOP HTTP - SELECT STRATEGY", allow_multiple=True)
    if strategies:
        execute_for_strategies(strategies, do_stop_http, "STOP HTTP SERVER")

def action_cleanup():
    """Cleanup all servers"""
    strategies = select_strategy("CLEANUP - SELECT STRATEGY", allow_multiple=True)
    if strategies:
        for strat in strategies:
            do_stop_iperf(strat)
            do_stop_http(strat)
        print_success("Cleanup complete")
        press_enter()

def action_test1():
    """Run Test1"""
    strategies = select_strategy("TEST 1 - PACKET SIZE", allow_multiple=True)
    if strategies:
        execute_for_strategies(strategies, do_test1, "TEST 1")

def action_test2():
    """Run Test2"""
    strategies = select_strategy("TEST 2 - HTTP PERFORMANCE", allow_multiple=True)
    if strategies:
        execute_for_strategies(strategies, do_test2, "TEST 2")

def action_test3():
    """Run Test3"""
    strategies = select_strategy("TEST 3 - RTT CONSISTENCY", allow_multiple=True)
    if strategies:
        execute_for_strategies(strategies, do_test3, "TEST 3")

def action_test5():
    """Run Test5"""
    strategies = select_strategy("TEST 5 - FRAGMENTATION", allow_multiple=True)
    if strategies:
        execute_for_strategies(strategies, do_test5, "TEST 5")

def action_run_all():
    """Run all tests for selected strategies"""
    strategies = select_strategy("RUN ALL TESTS - SELECT STRATEGY", allow_multiple=True)
    
    if not strategies:
        return
    
    clear_screen()
    print_banner()
    print_header("RUN ALL TESTS")
    
    names = [STRATEGY_CONFIG[s]['name'] for s in strategies]
    print_info(f"Will test: {', '.join(names)}")
    print_info("Sequence: Setup -> iperf3 -> Test1 -> Test3 -> Test5 -> HTTP -> Test2")
    print_warning(f"Estimated: ~{len(strategies) * 20} minutes")
    
    confirm = input("\n  Continue? (y/n): ").strip().lower()
    if confirm != 'y':
        return
    
    for i, strat in enumerate(strategies, 1):
        config = STRATEGY_CONFIG[strat]
        
        if len(strategies) > 1:
            print_header(f"STRATEGY {i}/{len(strategies)}: {config['name']}")
            if i > 1:
                print_warning("ACTION: Switch GNS3 project and start all nodes!")
                input("\n  Press ENTER when ready...")
        
        # Run sequence
        if not strategy_status[strat]["setup_done"]:
            do_setup(strat)
            if not strategy_status[strat]["setup_done"]:
                continue
        
        if not strategy_status[strat]["iperf_running"]:
            do_start_iperf(strat)
        
        do_test1(strat)
        countdown_timer(WAIT_TIMES["between_tests"], "Cooling down")
        
        do_test3(strat)
        countdown_timer(WAIT_TIMES["between_tests"], "Cooling down")
        
        do_test5(strat)
        countdown_timer(WAIT_TIMES["between_tests"], "Cooling down")
        
        do_start_http(strat)
        do_test2(strat)
        
        print_success(f"All tests complete for {config['name']}")
        
        if i < len(strategies):
            cont = input(f"\n  Continue to next? (y/n): ").strip().lower()
            if cont != 'y':
                break
    
    print_header("ALL TESTS COMPLETE")
    for strat in strategies:
        s = strategy_status[strat]
        name = STRATEGY_CONFIG[strat]['name']
        print(f"  {name}: T1={'PASS' if s['test1_done'] else 'FAIL'} T2={'PASS' if s['test2_done'] else 'FAIL'} T3={'PASS' if s['test3_done'] else 'FAIL'} T5={'PASS' if s['test5_done'] else 'FAIL'}")
    
    press_enter()

def action_view_results():
    """View test results"""
    strategies = select_strategy("VIEW RESULTS - SELECT STRATEGY", allow_multiple=True)
    
    if not strategies:
        return
    
    clear_screen()
    print_banner()
    print_header("TEST RESULTS")
    
    for filename, desc in RESULT_FILES.items():
        filepath = os.path.join(PROJECT_DIR, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                print_success(f"\n{desc} ({filename})")
                
                for strat in strategies:
                    strategy_data = [e for e in data if e.get('strategy', '').lower() == strat.lower()]
                    name = STRATEGY_CONFIG[strat]['name']
                    
                    if strategy_data:
                        print_info(f"  {name}: {len(strategy_data)} entries")
                        entry = strategy_data[0]
                        for key in ['avg_throughput', 'avg_rtt', 'success_rate']:
                            if key in entry:
                                print_info(f"    {key}: {entry[key]}")
                    else:
                        print_warning(f"  {name}: No data")
            except Exception as e:
                print_warning(f"{filename}: Error - {e}")
        else:
            print_warning(f"{filename}: Not found")
    
    press_enter()

def action_export_csv():
    """Export results to CSV"""
    strategies = select_strategy("EXPORT CSV - SELECT STRATEGY", allow_multiple=True)
    
    if not strategies:
        return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    for strat in strategies:
        csv_path = os.path.join(PROJECT_DIR, f"summary_{strat}_{timestamp}.csv")
        try:
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Test', 'Status', 'Entries', 'Description', 'Strategy', 'Timestamp'])
                
                for filename, desc in RESULT_FILES.items():
                    filepath = os.path.join(PROJECT_DIR, filename)
                    if os.path.exists(filepath):
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        count = len([e for e in data if e.get('strategy', '').lower() == strat.lower()])
                        writer.writerow([filename, 'PASS' if count > 0 else 'FAIL', count, desc, strat.upper(), timestamp])
                    else:
                        writer.writerow([filename, 'FAIL', 0, desc, strat.upper(), timestamp])
            
            print_success(f"Exported: {os.path.basename(csv_path)}")
        except Exception as e:
            print_error(f"Export failed: {e}")
    
    press_enter()

def action_reset():
    """Reset results"""
    clear_screen()
    print_banner()
    print_header("RESET RESULTS")
    
    print_warning("This will backup and delete result files!")
    print()
    print("  1. Reset specific strategies")
    print("  2. Reset ALL")
    print("  0. Cancel")
    
    choice = input("\n  Choice: ").strip()
    
    if choice == "0":
        return
    elif choice == "1":
        strategies = select_strategy("SELECT STRATEGIES TO RESET", allow_multiple=True)
        if not strategies:
            return
    elif choice == "2":
        strategies = list(STRATEGY_CONFIG.keys())
    else:
        return
    
    confirm = input(f"\n  Confirm reset for: {', '.join([STRATEGY_CONFIG[s]['name'] for s in strategies])}? (yes/no): ").strip().lower()
    if confirm != 'yes':
        return
    
    for filename in RESULT_FILES.keys():
        filepath = os.path.join(PROJECT_DIR, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                remaining = [e for e in data if e.get('strategy', '').lower() not in strategies]
                
                backup = filepath + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(filepath, backup)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(remaining, f, indent=2)
                
                print_success(f"Reset {filename}")
            except Exception as e:
                print_error(f"Failed: {e}")
    
    for strat in strategies:
        strategy_status[strat] = {
            "setup_done": False, "iperf_running": False, "http_running": False,
            "test1_done": False, "test2_done": False, "test3_done": False, "test5_done": False
        }
    
    print_success("Reset complete")
    press_enter()

def action_change_strategy():
    """Change active strategy"""
    global current_strategy
    selected = select_strategy("SELECT ACTIVE STRATEGY", allow_multiple=False)
    if selected:
        current_strategy = selected[0]
        print_success(f"Active: {STRATEGY_CONFIG[current_strategy]['name']}")
        press_enter()

def action_change_run():
    """Change run number"""
    global current_run
    clear_screen()
    print_banner()
    print_header("CHANGE RUN NUMBER")
    print_info(f"Current: {current_run}")
    try:
        new_run = int(input("\n  New run number (1-99): ").strip())
        if 1 <= new_run <= 99:
            current_run = new_run
            print_success(f"Changed to {current_run}")
        else:
            print_error("Must be 1-99")
    except:
        print_error("Invalid number")
    press_enter()

def action_wait_times():
    """Configure wait times"""
    global WAIT_TIMES
    
    clear_screen()
    print_banner()
    print_header("WAIT TIMES")
    
    descriptions = {
        "after_setup": "After network setup",
        "after_http": "After HTTP server start",
        "between_tests": "Between tests",
        "for_server": "For iperf3 server start",
        "for_data_collection": "For data collection"
    }
    
    for i, (key, desc) in enumerate(descriptions.items(), 1):
        print(f"  {i}. {desc:<30} {WAIT_TIMES[key]}s")
    print(f"  0. Back")
    
    choice = input("\n  Choice: ").strip()
    if choice == '0':
        return
    
    try:
        idx = int(choice) - 1
        keys = list(descriptions.keys())
        if 0 <= idx < len(keys):
            key = keys[idx]
            new_val = int(input(f"  New value for {descriptions[key]} (0-300): ").strip())
            if 0 <= new_val <= 300:
                WAIT_TIMES[key] = new_val
                print_success(f"Updated to {new_val}s")
    except:
        print_error("Invalid")
    
    press_enter()

# =============================================
# MAIN MENU
# =============================================

def main_menu():
    """Display and handle main menu"""
    global current_strategy, current_run
    
    # Set UTF-8 for Windows
    if sys.platform == 'win32':
        os.system('chcp 65001 > nul 2>&1')
    
    # Signal handler
    def signal_handler(sig, frame):
        print(f"\n\n  Exiting... Goodbye!")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    while True:
        clear_screen()
        print_banner()
        print_status_bar()
        
        print("""
┌──────────────────────────────────────────────────────────────────────────────┐
│                           MAIN MENU OPTIONS                                   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  SETUP & SERVERS (asks which strategy first):                                │
│   1. Run Network Setup      2. Start iperf3 Server                           │
│   3. Stop iperf3 Server     4. Start HTTP Server                             │
│   5. Stop HTTP Server       6. Cleanup All Servers                           │
│                                                                              │
│  INDIVIDUAL TESTS (asks which strategy first):                               │
│   7. Test1 (Packet Size)    8. Test2 (HTTP)                                  │
│   9. Test3 (RTT)           10. Test5 (Fragmentation)                         │
│  11. RUN ALL TESTS                                                            │
│                                                                              │
│  UTILITIES:                                                                  │
│  12. Check Status          13. View Results          14. Export CSV          │
│  15. Reset Results         16. Change Strategy       17. Change Run Number  │
│  18. Configure Wait Times                                                    │
│                                                                              │
│   0. Exit                                                                    │
└──────────────────────────────────────────────────────────────────────────────┘
""")
        
        choice = input("  Choice (0-18): ").strip()
        
        if choice == "0":
            print("\n  Exiting... Goodbye!")
            break
        elif choice == "1":
            action_setup()
        elif choice == "2":
            action_start_iperf()
        elif choice == "3":
            action_stop_iperf()
        elif choice == "4":
            action_start_http()
        elif choice == "5":
            action_stop_http()
        elif choice == "6":
            action_cleanup()
        elif choice == "7":
            action_test1()
        elif choice == "8":
            action_test2()
        elif choice == "9":
            action_test3()
        elif choice == "10":
            action_test5()
        elif choice == "11":
            action_run_all()
        elif choice == "12":
            action_check_status()
        elif choice == "13":
            action_view_results()
        elif choice == "14":
            action_export_csv()
        elif choice == "15":
            action_reset()
        elif choice == "16":
            action_change_strategy()
        elif choice == "17":
            action_change_run()
        elif choice == "18":
            action_wait_times()
        else:
            print_error("Invalid choice! Enter 0-18")
            time.sleep(1)

# =============================================
# ENTRY POINT
# =============================================

if __name__ == "__main__":
    main_menu()