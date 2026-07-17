#!/usr/bin/env python3
"""
test4_rtt.py - TEST 4: RTT Consistency (100 packets)
Runs from PC1 only
"""

import time
import argparse
import socket
import json
import os
import re
import sys
import random

# Fix for Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ─────────────────────────────────────────────
# PATH & GNS3 CONFIGURATION
# ─────────────────────────────────────────────
GNS3_HOST = "192.168.255.128"
BASE_DIR = r"C:\Users\user\OneDrive\Documents\Abg Paeez\CSP 600\FYP_IPv6_Project"
PROJECT_DIR = os.path.join(BASE_DIR, "Project Directory")
DATA_DIR = os.path.join(PROJECT_DIR, "data")  # New data subfolder
JSON_PATH = os.path.join(DATA_DIR, "T3Rs.json")  # T3Rs.json inside data folder

CONFIGS = {
    "dualstack": {
        "pc1_port": 5018,
        "pc2_port": 5020,
        "server_port": 5003,
        "server_target": "203.0.113.1",      # iperf3 server binds to IPv4
        "client_target": "203.0.113.1",      # PC1 targets IPv4 directly
        "http_port": 8080,
        "ping_cmd": "ping",                  # Use regular ping for IPv4
        "extra": "",
        "mtu": 1500,
        "description": "Native IPv4 communication",
        "metric_prefix": "T4"                # Use T4 for Dual-Stack
    },
    "dslite": {
        "pc1_port": 5008,
        "pc2_port": 5010,
        "server_port": 5015,
        "server_target": "203.0.113.1",      # iperf3 server binds to IPv4
        "client_target": "203.0.113.1",      # PC1 targets IPv4 (goes through IPv6 tunnel)
        "http_port": 8080,
        "ping_cmd": "ping",                  # Use regular ping for IPv4
        "extra": "",
        "mtu": 1476,
        "description": "IPv4 over IPv6 tunnel (DS-Lite)",
        "metric_prefix": "T4"                # Use T4 for DS-Lite
    },
    "nat64": {
        "pc1_port": 5016,
        "pc2_port": 5018,
        "server_port": 5022,
        "server_target": "203.0.113.1",      # iperf3 server binds to IPv4
        "client_target": "2001:db8:ff9b::cb00:7101",  # PC1 targets IPv6 (NAT64 translates to IPv4)
        "http_port": 8080,
        "ping_cmd": "ping6",                 # Use ping6 for IPv6
        "extra": "-6",
        "mtu": 1500,
        "description": "IPv6 to IPv4 translation (NAT64)",
        "metric_prefix": "T3"                # Use T3 for NAT64
    }
}

def save_to_json(strategy, metric, run_number, value):
    """Writes the captured metric to T3Rs.json in the data folder."""
    # Ensure data directory exists
    if not os.path.exists(DATA_DIR): 
        os.makedirs(DATA_DIR)
        print(f"  [OK] Created data directory: {DATA_DIR}")
    
    # Load existing data if file exists
    data = []
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH, 'r', encoding='utf-8') as f: 
                data = json.load(f)
                print(f"  [LOAD] Loaded existing data from T3Rs.json ({len(data)} entries)")
        except Exception as e:
            print(f"  [WARN] Could not read existing T3Rs.json: {e}")
            data = []
    
    # Append new data entry
    data.append({
        "strategy": strategy.lower().strip(), 
        "metric": metric.strip(), 
        "run": run_number, 
        "value": float(value) if isinstance(value, (int, float)) else float(value),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })
    
    # Write back to T3Rs.json
    with open(JSON_PATH, 'w', encoding='utf-8') as f: 
        json.dump(data, f, indent=4)
    print(f"  [SAVED] {metric} = {value}")
    print(f"  [LOCATION] {JSON_PATH}")

def send_command_and_get_output(port, command, wait_time, description=""):
    """Send a command to a GNS3 node via telnet"""
    output_data = ""
    try:
        with socket.create_connection((GNS3_HOST, port), timeout=wait_time + 20) as sock:
            sock.sendall(b"\n")
            time.sleep(1)
            sock.sendall(command.encode("ascii") + b"\n")
            print(f"  ...Running {description} (waiting {wait_time}s)...")
            time.sleep(wait_time)
            sock.setblocking(False)
            time.sleep(2)
            try:
                output_data = sock.recv(524288).decode("ascii", errors="ignore")
            except:
                pass
    except Exception as e:
        print(f"  [ERROR] Socket Error on port {port}: {e}")
    return output_data

def start_iperf_server(project):
    """Start iperf3 server for a specific strategy"""
    cfg = CONFIGS[project]
    print(f"[START] Starting iperf3 Server for {project}...")
    print(f"  Server binds to: {cfg['server_target']} (IPv4 address)")
    # Always bind to IPv4 address 203.0.113.1 for all strategies
    cmd = f"pkill iperf3; iperf3 -s -B {cfg['server_target']} -D"
    send_command_and_get_output(cfg['server_port'], cmd, 5, "Start server")
    print(f"  [OK] iperf3 server started on {cfg['server_target']}")
    print(f"  [INFO] {cfg['description']}")
    return True

def stop_iperf_server(project):
    """Stop iperf3 server for a specific strategy"""
    cfg = CONFIGS[project]
    print(f"[STOP] Stopping iperf3 server for {project}...")
    send_command_and_get_output(cfg['server_port'], "pkill iperf3", 3, "Stop server")
    return True

def reset_results():
    """Delete the T3Rs.json file from data folder to start fresh"""
    if os.path.exists(JSON_PATH): 
        os.remove(JSON_PATH)
        print(f"[DELETED] {JSON_PATH}")
        print(f"[RESET] T3Rs.json has been reset for new data collection")
    else:
        print(f"[INFO] T3Rs.json does not exist at {JSON_PATH}")
        print(f"[INFO] No file to delete.")
    return True

def show_data_summary():
    """Display summary of collected data in T3Rs.json"""
    if not os.path.exists(JSON_PATH):
        print(f"[NO DATA] No data found in T3Rs.json at: {JSON_PATH}")
        return
    
    try:
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"\n{'='*60}")
        print(f"T3Rs.json DATA SUMMARY")
        print(f"{'='*60}")
        print(f"File Location: {JSON_PATH}")
        print(f"Total entries: {len(data)}")
        
        # Group by strategy
        strategies = {}
        for entry in data:
            strat = entry['strategy']
            if strat not in strategies:
                strategies[strat] = 0
            strategies[strat] += 1
        
        print(f"\nEntries per strategy:")
        for strat, count in strategies.items():
            print(f"  - {strat.upper()}: {count} entries")
        
        # Group by metric type
        metrics = {}
        for entry in data:
            metric = entry['metric']
            if metric not in metrics:
                metrics[metric] = 0
            metrics[metric] += 1
        
        print(f"\nMetric types collected:")
        for metric, count in metrics.items():
            print(f"  - {metric}: {count} measurements")
        
        # Show latest entries
        print(f"\nLatest 5 entries:")
        for entry in data[-5:]:
            print(f"  - [{entry['strategy'].upper()}] {entry['metric']}: {entry['value']} (Run {entry['run']}) at {entry['timestamp']}")
        
        # Calculate average RTT per strategy
        print(f"\nAverage RTT per strategy:")
        for strat in ['dualstack', 'dslite', 'nat64']:
            # Check both T3 and T4 prefixes for backward compatibility
            strat_data = [e for e in data if e['strategy'] == strat and 
                         (e['metric'] == 'T4_RTT_PC1_Avg_ms' or e['metric'] == 'T3_RTT_PC1_Avg_ms')]
            if strat_data:
                avg_rtt = sum(e['value'] for e in strat_data) / len(strat_data)
                metric_type = strat_data[0]['metric'].split('_')[0]
                print(f"  - {strat.upper()}: {avg_rtt:.2f} ms ({metric_type} metric, based on {len(strat_data)} runs)")
        
        print(f"{'='*60}\n")
    except Exception as e:
        print(f"[ERROR] Error reading T3Rs.json: {e}")

def list_data_directory():
    """List all files in the data directory"""
    if not os.path.exists(DATA_DIR):
        print(f"[INFO] Data directory does not exist yet: {DATA_DIR}")
        return
    
    print(f"\n{'='*60}")
    print(f"DATA DIRECTORY CONTENTS")
    print(f"{'='*60}")
    print(f"Location: {DATA_DIR}")
    
    files = os.listdir(DATA_DIR)
    if files:
        print(f"\nFiles found:")
        for file in files:
            file_path = os.path.join(DATA_DIR, file)
            size = os.path.getsize(file_path)
            mod_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(file_path)))
            print(f"  - {file} ({size} bytes) - modified: {mod_time}")
    else:
        print(f"\n  (Directory is empty)")
    
    print(f"{'='*60}\n")

def cooldown_timer(min_seconds=10, max_seconds=15):
    """Wait for router CPU to drop to idle and clear buffers"""
    wait_time = random.uniform(min_seconds, max_seconds)
    print(f"\n  [COOLDOWN] Waiting {wait_time:.1f} seconds for router CPU to idle and buffers to clear...")
    
    # Display countdown
    for i in range(int(wait_time), 0, -1):
        print(f"    ...{i} seconds remaining", end='\r')
        time.sleep(1)
    
    print(f"    [READY] Cooldown complete. Resuming tests...")
    time.sleep(0.5)  # Small extra delay

# ─────────────────────────────────────────────
# TEST 4 SPECIFIC FUNCTIONS
# ─────────────────────────────────────────────

def parse_rtt_output(output, strategy, run_num):
    """Parse RTT consistency test output"""
    if not output:
        print(f"  [WARN] No output received for RTT test")
        return None
    
    cfg = CONFIGS[strategy]
    metric_prefix = cfg['metric_prefix']  # Get the metric prefix (T4 or T3)
    
    lines = output.split('\n')
    rtt_values = None
    loss_pct = None
    
    for line in lines:
        if 'packet loss' in line:
            loss_match = re.search(r'(\d+)%\s+packet\s+loss', line)
            if loss_match:
                loss_pct = loss_match.group(1)
        
        if 'rtt min/avg/max/mdev' in line.lower():
            rtt_match = re.search(r'=\s*(\d+\.?\d*)/(\d+\.?\d*)/(\d+\.?\d*)/(\d+\.?\d*)', line)
            if rtt_match:
                rtt_values = rtt_match.groups()
                break
    
    if loss_pct:
        save_to_json(strategy, f"{metric_prefix}_RTT_PC1_Loss_Percent", run_num, loss_pct)
        print(f"      [OK] Loss: {loss_pct}%")
    
    if rtt_values:
        min_rtt, avg_rtt, max_rtt, mdev_rtt = rtt_values
        save_to_json(strategy, f"{metric_prefix}_RTT_PC1_Min_ms", run_num, min_rtt)
        save_to_json(strategy, f"{metric_prefix}_RTT_PC1_Avg_ms", run_num, avg_rtt)
        save_to_json(strategy, f"{metric_prefix}_RTT_PC1_Max_ms", run_num, max_rtt)
        save_to_json(strategy, f"{metric_prefix}_RTT_PC1_Mdev_ms", run_num, mdev_rtt)
        print(f"      [OK] RTT - Min: {min_rtt} ms, Avg: {avg_rtt} ms, Max: {max_rtt} ms")
        print(f"      [INFO] Metric prefix: {metric_prefix}")
    else:
        print(f"      [ERROR] Could not parse RTT values")
        for line in lines[-3:]:
            if line.strip():
                print(f"        Debug: {line[:100]}")
    
    return rtt_values

def run_test4(project, run_num):
    """TEST 4: RTT Consistency from PC1"""
    cfg = CONFIGS[project]
    client_port = cfg['pc1_port']
    
    print(f"\n{'='*60}")
    print(f"TEST 4: RTT Consistency - {project.upper()} (Run {run_num})")
    print(f"{'='*60}")
    print(f"Strategy: {project.upper()}")
    print(f"Description: {cfg['description']}")
    print(f"Client: PC1 (Port {client_port})")
    print(f"Server Target (bind): {cfg['server_target']}")
    print(f"Client Target (ping): {cfg['client_target']}")
    print(f"Ping Command: {cfg['ping_cmd']}")
    print(f"Metric Prefix: {cfg['metric_prefix']} (Using {cfg['metric_prefix']}_RTT_* metrics)")
    print(f"Data Directory: {DATA_DIR}")
    print(f"Saving to: {JSON_PATH}")
    print(f"{'='*60}")
    
    print(f"\n  Running RTT test (100 pings with 0.2s interval)...")
    ping_cmd = f"{cfg['ping_cmd']} -c 100 -i 0.2 {cfg['client_target']}"
    print(f"  Command: {ping_cmd}")
    output = send_command_and_get_output(client_port, ping_cmd, 25, "RTT Test")
    parse_rtt_output(output, project, run_num)
    
    print(f"\n[COMPLETE] TEST 4 Completed for {project.upper()} (Run {run_num})")
    print(f"[LOCATION] Results saved to: {JSON_PATH}")

def run_all_strategies(run_num):
    """Run TEST 4 for all strategies sequentially with cooldown periods"""
    print(f"\n{'#'*60}")
    print(f"RUNNING TEST 4 FOR ALL STRATEGIES (Run {run_num})")
    print(f"{'#'*60}")
    print(f"NOTE: Dual-Stack and DS-Lite will use T4_* metrics")
    print(f"      NAT64 will use T3_* metrics")
    print(f"      Cooldown period of 10-15 seconds between tests")
    print(f"      Data saved to: {DATA_DIR}")
    print(f"{'#'*60}")
    
    strategies = ["dualstack", "dslite", "nat64"]
    
    for idx, strategy in enumerate(strategies):
        run_test4(strategy, run_num)
        
        # Add cooldown period after each test except the last one
        if idx < len(strategies) - 1:
            cooldown_timer(10, 15)  # Random wait between 10-15 seconds
    
    print(f"\n{'#'*60}")
    print(f"ALL STRATEGIES COMPLETED FOR RUN {run_num}")
    print(f"{'#'*60}")

def run_multiple_runs(total_runs=3):
    """Run multiple complete test cycles with cooldown between runs"""
    print(f"\n{'#'*60}")
    print(f"RUNNING MULTIPLE TEST CYCLES ({total_runs} runs)")
    print(f"{'#'*60}")
    print(f"Data will be saved to: {DATA_DIR}")
    print(f"{'#'*60}")
    
    for run_num in range(1, total_runs + 1):
        print(f"\n{'='*60}")
        print(f"STARTING RUN {run_num} OF {total_runs}")
        print(f"{'='*60}")
        
        run_all_strategies(run_num)
        
        # Cooldown between complete runs (longer cooldown)
        if run_num < total_runs:
            wait_time = random.uniform(15, 20)
            print(f"\n  [INTER-RUN COOLDOWN] Waiting {wait_time:.1f} seconds before next run...")
            for i in range(int(wait_time), 0, -1):
                print(f"    ...{i} seconds remaining", end='\r')
                time.sleep(1)
            print(f"    [READY] Ready for run {run_num + 1}")
    
    print(f"\n{'#'*60}")
    print(f"ALL {total_runs} RUNS COMPLETED")
    print(f"Results saved in: {DATA_DIR}")
    print(f"{'#'*60}")

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TEST 4: RTT Consistency - Saves to T3Rs.json in Project Directory/data folder")
    parser.add_argument("--project", "-p", choices=["dualstack", "dslite", "nat64", "all"], default="all",
                        help="Strategy to test or 'all' for all strategies")
    parser.add_argument("--run", "-r", type=int, default=1,
                        help="Run number (default: 1)")
    parser.add_argument("--runs", "-R", type=int, default=None,
                        help="Number of complete test cycles to run (overrides --run)")
    parser.add_argument("--mode", "-m", choices=["start", "stop", "reset", "run", "summary", "list"], default="run",
                        help="Operation mode")
    parser.add_argument("--cooldown", "-c", action="store_true", default=True,
                        help="Enable cooldown periods between tests (default: True)")
    args = parser.parse_args()
    
    if args.mode == "start":
        if args.project == "all":
            for strategy in ["dualstack", "dslite", "nat64"]:
                start_iperf_server(strategy)
                time.sleep(2)
        else:
            start_iperf_server(args.project)
    elif args.mode == "stop":
        if args.project == "all":
            for strategy in ["dualstack", "dslite", "nat64"]:
                stop_iperf_server(strategy)
                time.sleep(2)
        else:
            stop_iperf_server(args.project)
    elif args.mode == "reset":
        reset_results()
    elif args.mode == "summary":
        show_data_summary()
    elif args.mode == "list":
        list_data_directory()
    elif args.mode == "run":
        if args.runs:
            # Run multiple complete test cycles
            run_multiple_runs(args.runs)
        elif args.project == "all":
            # Run all strategies once with cooldown between them
            run_all_strategies(args.run)
        else:
            # Run single strategy test
            run_test4(args.project, args.run)