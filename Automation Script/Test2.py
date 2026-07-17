#!/usr/bin/env python3
"""
test2_http.py - TEST 2: HTTP Performance Testing
Runs from PC2 only
Clean metrics output with drop detection, MSS clamping, and cooldown timers
NOTE: HTTP server is managed by setup_https.py per strategy
FIXED: Multi-run data preservation (appends instead of overwrites)
"""

import time
import argparse
import socket
import json
import os
import re

# ─────────────────────────────────────────────
# PATH & GNS3 CONFIGURATION
# ─────────────────────────────────────────────
GNS3_HOST = "192.168.255.128"
PROJECT_DIR = r"C:\Users\user\OneDrive\Documents\Abg Paeez\CSP 600\FYP_IPv6_Project\Project Directory\data"
JSON_PATH = os.path.join(PROJECT_DIR, "T2Rs.json")

# Speed drop detection threshold (percentage)
DROP_THRESHOLD_PERCENT = 30

# Cooldown timer between runs (seconds)
COOLDOWN_BETWEEN_FILES = 12
COOLDOWN_BETWEEN_STRATEGIES = 15

# MSS Clamping values for TCP throughput optimization
MSS_CONFIGS = {
    "dualstack": {"mss": 1460, "description": "Standard Ethernet MSS (1500 MTU - 40 bytes)"},
    "dslite": {"mss": 1400, "description": "Reduced MSS for DS-Lite tunnel (1476 MTU - 40 - 36 bytes)"},
    "nat64": {"mss": 1440, "description": "Slightly reduced MSS for NAT64 translation (1500 MTU - 40 - 20 bytes)"}
}

CONFIGS = {
    "dualstack": {
        "pc1_port": 5013, "pc2_port": 5015, "server_port": 5002,
        "target": "203.0.113.1", "iperf_target": "203.0.113.1",
        "http_port": 8080, "iperf_port": 5201,
        "ping_cmd": "ping", "extra": "", "mtu": 1500, "mss_clamp": 1460
    },
    "dslite": {
        "pc1_port": 5008, "pc2_port": 5007, "server_port": 5018,
        "target": "203.0.113.1", "iperf_target": "203.0.113.1",
        "http_port": 8080, "iperf_port": 5201,
        "ping_cmd": "ping", "extra": "", "mtu": 1476, "mss_clamp": 1400
    },
    "nat64": {
        "pc1_port": 5000, "pc2_port": 5003, "server_port": 5012,
        "target": "203.0.113.1", "iperf_target": "2001:db8:ff9b::cb00:7101",
        "http_port": 8080, "iperf_port": 5201,
        "ping_cmd": "ping6", "extra": "-6", "mtu": 1500, "mss_clamp": 1440
    }
}

speed_history = {}

def ensure_project_dir():
    """Ensure the project directory exists"""
    if not os.path.exists(PROJECT_DIR):
        try:
            os.makedirs(PROJECT_DIR)
            print(f"[INFO] Created directory: {PROJECT_DIR}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to create directory: {e}")
            return False
    return True

def save_to_t2rs_json(strategy, metric, run_number, value):
    """Writes the captured metric to the T2Rs.json file - APPENDS data"""
    if not ensure_project_dir():
        return
    data = []
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH, 'r') as f:
                data = json.load(f)
        except:
            data = []
    data.append({
        "strategy": strategy.lower().strip(),
        "metric": metric.strip(),
        "run": run_number,
        "value": float(value) if isinstance(value, (int, float)) else float(value),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })
    try:
        with open(JSON_PATH, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"  [SAVED] {metric} = {value}")
    except Exception as e:
        print(f"  [ERROR] Failed to save: {e}")

def save_drop_analysis(strategy, drop_info):
    """Save speed drop analysis to JSON - APPENDS for multiple runs"""
    if not ensure_project_dir():
        return
    drop_file = os.path.join(PROJECT_DIR, f"T2_drop_analysis_{strategy}.json")
    
    # Load existing data if file exists
    existing_data = []
    if os.path.exists(drop_file):
        try:
            with open(drop_file, 'r') as f:
                existing_data = json.load(f)
                # Convert old single-run format (dict) to list format
                if isinstance(existing_data, dict):
                    existing_data = [existing_data]
        except:
            existing_data = []
    
    # Add timestamp and run number
    drop_info["run_timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
    drop_info["run_number"] = len(existing_data) + 1
    existing_data.append(drop_info)
    
    # Save all data
    try:
        with open(drop_file, 'w') as f:
            json.dump(existing_data, f, indent=4)
        print(f"  [SAVED] Drop analysis (Run {len(existing_data)}): {drop_file}")
    except Exception as e:
        print(f"  [ERROR] Failed to save drop analysis: {e}")

def analyze_speed_drop(strategy, file_size, current_speed, previous_speeds):
    """Analyze and detect speed drops"""
    if not previous_speeds:
        return None
    prev_size, prev_speed = previous_speeds[-1]
    if prev_speed > 0:
        drop_percent = ((prev_speed - current_speed) / prev_speed) * 100
        if drop_percent >= DROP_THRESHOLD_PERCENT:
            mss_info = MSS_CONFIGS.get(strategy, {})
            return {
                "strategy": strategy,
                "drop_detected": True,
                "previous_file": prev_size,
                "previous_speed_mbps": round(prev_speed, 2),
                "current_file": file_size,
                "current_speed_mbps": round(current_speed, 2),
                "drop_percentage": round(drop_percent, 2),
                "drop_size_range": f"{prev_size} → {file_size}",
                "threshold": DROP_THRESHOLD_PERCENT,
                "mss_clamping": mss_info.get('mss', 'N/A'),
                "possible_causes": analyze_drop_causes(strategy, prev_size, file_size, drop_percent)
            }
    return None

def analyze_drop_causes(strategy, prev_size, current_size, drop_percent):
    """Analyze possible causes for speed drop"""
    causes = []
    mss_info = MSS_CONFIGS.get(strategy, {})
    mss_value = mss_info.get('mss', 0)
    curr_bytes = parse_size_to_bytes(current_size)
    
    if strategy == "dslite":
        causes.append(f"DS-Lite encapsulation overhead (MTU 1476, MSS {mss_value})")
        causes.append(f"IPv6 tunnel fragmentation starting at ~{prev_size}")
    elif strategy == "nat64":
        causes.append(f"NAT64 protocol translation overhead (MSS {mss_value})")
        causes.append("IPv6-to-IPv4 address mapping latency")
    else:
        causes.append(f"TCP buffer threshold reached at {prev_size}")
    
    if curr_bytes:
        if curr_bytes >= 500000:
            causes.append(f"Buffer overflow threshold (~500KB) with MSS {mss_value}")
        elif curr_bytes >= 262144:
            causes.append(f"TCP congestion window threshold (~256KB) with MSS {mss_value}")
    
    if drop_percent > 50:
        causes.append("Severe packet loss or retransmission")
    
    causes.append(f"MSS Clamping: {mss_value} bytes - May need adjustment")
    return causes

def parse_size_to_bytes(size_str):
    """Convert size string to bytes"""
    size_str = size_str.upper().strip()
    if 'KB' in size_str:
        return float(size_str.replace('KB', '')) * 1024
    elif 'MB' in size_str:
        return float(size_str.replace('MB', '')) * 1048576
    return None

def send_command_and_get_output(port, command, wait_time, description=""):
    """Send a command to a GNS3 node via telnet"""
    output_data = ""
    try:
        with socket.create_connection((GNS3_HOST, port), timeout=wait_time + 20) as sock:
            sock.sendall(b"\n")
            time.sleep(1)
            sock.sendall(command.encode("ascii") + b"\n")
            print(f"  ...{description} ({wait_time}s)...")
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

def cooldown_timer(seconds, reason=""):
    """CPU cooldown timer"""
    if reason:
        print(f"\n[COOLDOWN] {reason}")
    print(f"[COOLDOWN] Waiting {seconds}s...")
    for i in range(seconds, 0, -1):
        if i % 5 == 0 or i <= 3:
            print(f"          {i}s...")
        time.sleep(1)
    print(f"[COOLDOWN] Done ✓")

def apply_mss_clamping(project):
    """Apply MSS clamping on the strategy's Linux-Server"""
    cfg = CONFIGS[project]
    mss_value = cfg['mss_clamp']
    server_port = cfg['server_port']
    
    print(f"\n[MSS] Applying {mss_value} bytes on {project.upper()} server (port {server_port})...")
    commands = [
        f"iptables -t mangle -F OUTPUT 2>/dev/null || true",
        f"iptables -t mangle -A OUTPUT -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --set-mss {mss_value}",
        f"echo 'MSS_APPLIED={mss_value}'"
    ]
    full_command = "; ".join(commands)
    output = send_command_and_get_output(server_port, full_command, 5, f"MSS Clamping")
    if f"MSS_APPLIED={mss_value}" in output:
        print(f"  [ OK ] MSS Clamping applied: {mss_value} bytes")
        save_to_t2rs_json(project, "T2_MSS_Clamping_Value", 1, mss_value)
        return True
    print(f"  [WARN] MSS Clamping may not have applied")
    return False

def start_iperf_server(project):
    """Start iperf3 server on the strategy's Linux-Server"""
    cfg = CONFIGS[project]
    server_port = cfg['server_port']
    target = cfg['target']
    iperf_port = cfg['iperf_port']
    
    print(f"\n[IPERF] Starting server on {target}:{iperf_port} (port {server_port})...")
    cmd = f"pkill iperf3; iperf3 -s -B {target} -p {iperf_port} -D"
    send_command_and_get_output(server_port, cmd, 5, "iperf3 Server Start")
    print(f"  [ OK ] iperf3 server ready on {target}:{iperf_port}")

def stop_iperf_server(project):
    """Stop iperf3 server on the strategy's Linux-Server"""
    cfg = CONFIGS[project]
    server_port = cfg['server_port']
    
    print(f"\n[IPERF] Stopping server on port {server_port}...")
    send_command_and_get_output(server_port, "pkill iperf3", 3, "iperf3 Server Stop")
    print(f"  [ OK ] iperf3 server stopped")

def create_intermediate_test_files(project):
    """Create intermediate test files on the strategy's Linux-Server"""
    cfg = CONFIGS[project]
    server_port = cfg['server_port']
    
    print(f"\n[FILES] Creating intermediate test files on {project.upper()} server (port {server_port})...")
    
    sizes = [200, 300, 400, 500, 600, 700, 800, 900]
    
    for size in sizes:
        cmd = (f"cd /tmp/http_test_files && "
               f"dd if=/dev/urandom of={size}KB.bin bs=1024 count={size} 2>/dev/null && "
               f"ls -la {size}KB.bin")
        output = send_command_and_get_output(server_port, cmd, 10, f"Create {size}KB.bin")
        if f"{size}KB.bin" in output:
            print(f"  [ OK ] {size}KB.bin created")
        else:
            print(f"  [WARN] {size}KB.bin may not exist")

def run_iperf3_test(project, run_num):
    """Run iperf3 throughput test from PC2"""
    cfg = CONFIGS[project]
    client_port = cfg['pc2_port']
    iperf_target = cfg['iperf_target']
    iperf_port = cfg['iperf_port']
    mss_value = cfg['mss_clamp']
    
    print(f"\n{'─'*60}")
    print(f"IPERF3 BASELINE TEST - {project.upper()} (Run {run_num})")
    print(f"{'─'*60}")
    
    if project == "nat64":
        iperf_cmd = f"iperf3 -c {iperf_target} -p {iperf_port} -6 -t 10 -P 4 -M {mss_value}"
    else:
        iperf_cmd = f"iperf3 -c {iperf_target} -p {iperf_port} -t 10 -P 4 -M {mss_value}"
    
    print(f"  Client: PC2 (Port {client_port})")
    print(f"  Target: {iperf_target}:{iperf_port}")
    print(f"  MSS: {mss_value} bytes")
    
    output = send_command_and_get_output(client_port, iperf_cmd, 15, "iperf3 Test")
    
    if output:
        sum_match = re.search(r'\[SUM\].*?(\d+\.?\d*)\s*(G|M)bits/sec', output, re.DOTALL)
        if sum_match:
            speed = float(sum_match.group(1))
            unit = sum_match.group(2)
            speed_mbps = speed * 1000 if unit == 'G' else speed
            save_to_t2rs_json(project, "T2_iperf3_Throughput_Mbps", run_num, speed_mbps)
            speed_history[f"{project}_iperf_baseline"] = speed_mbps
            print(f"  [ OK ] Throughput: {speed_mbps:.2f} Mbps")
    else:
        print(f"  [WARN] No output from iperf3")
    
    cooldown_timer(COOLDOWN_BETWEEN_FILES, "Cooldown after iperf3")

def parse_http_output(output, strategy, run_num, file_size):
    """Parse HTTP test output"""
    if not output:
        return None
    current_speed = None
    speed_match = re.search(r'Speed:\s*(\d+\.?\d*)', output)
    if speed_match:
        speed_bytes = float(speed_match.group(1))
        speed_mbps = (speed_bytes * 8) / 1000000
        current_speed = speed_mbps
        save_to_t2rs_json(strategy, f"T2_HTTP_PC2_{file_size}_Speed_Mbps", run_num, speed_mbps)
    http_match = re.search(r'HTTP:\s*(\d+)', output)
    if http_match:
        save_to_t2rs_json(strategy, f"T2_HTTP_PC2_{file_size}_HTTP_Code", run_num, http_match.group(1))
    return current_speed

def print_speed_summary(project, speeds, drops):
    """Print clean speed summary table"""
    cfg = CONFIGS[project]
    mss_value = cfg['mss_clamp']
    mtu_value = cfg['mtu']
    target = cfg['target']
    iperf_target = cfg['iperf_target']
    
    print(f"\n{'='*80}")
    print(f"TEST 2: HTTP PERFORMANCE METRICS - {project.upper()}")
    print(f"{'='*80}")
    print(f"Configuration:")
    print(f"  Server Port:      {cfg['server_port']}")
    print(f"  Target Server:    {target}:8080")
    print(f"  iperf3 Target:    {iperf_target}:5201")
    print(f"  MTU:              {mtu_value} bytes")
    print(f"  MSS Clamping:     {mss_value} bytes")
    print(f"  Drop Threshold:   {DROP_THRESHOLD_PERCENT}%")
    print(f"  Cooldown:         {COOLDOWN_BETWEEN_FILES}s between files")
    print(f"{'='*80}")
    
    # Speed Table
    print(f"\n┌{'─'*12}┬{'─'*18}┬{'─'*15}┬{'─'*22}┐")
    print(f"│ {'File Size':<10} │ {'Speed (Mbps)':<16} │ {'Change':<13} │ {'Status':<20} │")
    print(f"├{'─'*12}┼{'─'*18}┼{'─'*15}┼{'─'*22}┤")
    
    for i, (file_size, speed) in enumerate(speeds):
        if i == 0:
            change = "Baseline"
            status = "✅ OK"
        else:
            prev_speed = speeds[i-1][1]
            if prev_speed > 0:
                change_pct = ((speed - prev_speed) / prev_speed) * 100
                change = f"{change_pct:+.1f}%"
                if change_pct <= -DROP_THRESHOLD_PERCENT:
                    status = "🔴 CRITICAL DROP"
                elif change_pct < -10:
                    status = "🟡 Moderate Drop"
                elif change_pct < -5:
                    status = "🟠 Slight Drop"
                else:
                    status = "✅ OK"
            else:
                change = "N/A"
                status = "N/A"
        print(f"│ {file_size:<10} │ {speed:<16.2f} │ {change:<13} │ {status:<20} │")
    
    print(f"└{'─'*12}┴{'─'*18}┴{'─'*15}┴{'─'*22}┘")
    
    # Performance Summary
    baseline = speed_history.get(f"{project}_iperf_baseline")
    if speeds:
        max_speed = max(s[1] for s in speeds)
        min_speed = min(s[1] for s in speeds)
        avg_speed = sum(s[1] for s in speeds) / len(speeds)
        
        print(f"\n📈 Performance Summary:")
        if baseline:
            efficiency = (speeds[-1][1] / baseline) * 100
            print(f"   iperf3 Baseline:  {baseline:.2f} Mbps")
            print(f"   HTTP Efficiency:  {efficiency:.1f}%")
        print(f"   Max Speed:        {max_speed:.2f} Mbps")
        print(f"   Min Speed:        {min_speed:.2f} Mbps")
        print(f"   Avg Speed:        {avg_speed:.2f} Mbps")
    
    # Drop Analysis
    if drops:
        print(f"\n{'─'*80}")
        print(f"🔻 SPEED DROP ANALYSIS")
        print(f"{'─'*80}")
        for i, drop in enumerate(drops, 1):
            print(f"""
  Drop #{i}:
    📍 Drop Point:    {drop['previous_file']} → {drop['current_file']}
    📉 Speed Change:  {drop['previous_speed_mbps']:.2f} → {drop['current_speed_mbps']:.2f} Mbps
    📊 Drop:          {drop['drop_percentage']}%
""")
    else:
        print(f"\n✅ No significant speed drops detected")
    
    print(f"{'='*80}\n")

def run_http_test(project, run_num):
    """HTTP Performance test from PC2"""
    cfg = CONFIGS[project]
    client_port = cfg['pc2_port']
    target = cfg['target']
    http_port = cfg.get('http_port', 8080)
    mss_value = cfg['mss_clamp']
    
    print(f"\n{'#'*80}")
    print(f"TEST 2: HTTP PERFORMANCE TEST - {project.upper()} (Run {run_num})")
    print(f"{'#'*80}")
    print(f"Client: PC2 (Port {client_port})")
    print(f"Server: http://{target}:{http_port}")
    print(f"MSS: {mss_value} bytes")
    print(f"{'#'*80}")
    
    # Create intermediate files on the strategy's server
    create_intermediate_test_files(project)
    time.sleep(2)
    
    test_files = [
        {"name": "1KB", "path": "1KB.bin"},
        {"name": "10KB", "path": "10KB.bin"},
        {"name": "100KB", "path": "100KB.bin"},
        {"name": "200KB", "path": "200KB.bin"},
        {"name": "300KB", "path": "300KB.bin"},
        {"name": "400KB", "path": "400KB.bin"},
        {"name": "500KB", "path": "500KB.bin"},
        {"name": "600KB", "path": "600KB.bin"},
        {"name": "700KB", "path": "700KB.bin"},
        {"name": "800KB", "path": "800KB.bin"},
        {"name": "900KB", "path": "900KB.bin"},
        {"name": "1MB", "path": "1MB.bin"},
    ]
    
    speeds = []
    drops = []
    drop_found = False
    
    for i, file_info in enumerate(test_files):
        file_name = file_info["name"]
        file_path = file_info["path"]
        
        if drop_found and "KB" in file_name and int(file_name.replace("KB", "")) > 500:
            continue
        
        if i > 0:
            cooldown_timer(COOLDOWN_BETWEEN_FILES, f"Cooldown before {file_name}")
        
        print(f"\n  [TEST] Downloading {file_name}...")
        
        curl_cmd = f"curl -o /dev/null -s -w 'Speed: %{{speed_download}}, HTTP: %{{http_code}}' http://{target}:{http_port}/{file_path}"
        
        if project == "nat64":
            curl_cmd = f"curl -6 -o /dev/null -s -w 'Speed: %{{speed_download}}, HTTP: %{{http_code}}' http://[{cfg['iperf_target']}]:{http_port}/{file_path}"
        
        output = send_command_and_get_output(client_port, curl_cmd, 15, f"HTTP {file_name}")
        
        http_match = re.search(r'HTTP:\s*(\d+)', output)
        if http_match and http_match.group(1) == '200':
            print(f"  [ OK ] HTTP 200")
            current_speed = parse_http_output(output, project, run_num, file_name)
            
            if current_speed:
                speeds.append((file_name, current_speed))
                
                drop = analyze_speed_drop(project, file_name, current_speed, speeds[:-1])
                if drop:
                    drops.append(drop)
                    drop_found = True
                    print(f"  ⚠️  DROP: {drop['drop_size_range']} ({drop['drop_percentage']}%)")
        else:
            print(f"  [FAIL] HTTP request failed")
            speeds.append((file_name, 0))
    
    # Print clean metrics table
    print_speed_summary(project, speeds, drops)
    
    # Save drop analysis with APPEND mode
    if speeds:
        max_speed = max(s[1] for s in speeds)
        min_speed = min(s[1] for s in speeds)
        avg_speed = sum(s[1] for s in speeds) / len(speeds)
        
        baseline = speed_history.get(f"{project}_iperf_baseline", 0)
        efficiency = (speeds[-1][1] / baseline) * 100 if baseline else 0
        
        save_drop_analysis(project, {
            "strategy": project,
            "run_number": run_num,
            "mss_clamping": mss_value,
            "mtu": cfg['mtu'],
            "drops": drops,
            "exact_drop_range": drops[0]['drop_size_range'] if drops else "None",
            "speed_history": [{"file": s[0], "speed_mbps": s[1]} for s in speeds],
            "iperf_baseline_mbps": baseline,
            "performance_summary": {
                "max_speed_mbps": round(max_speed, 2),
                "min_speed_mbps": round(min_speed, 2),
                "avg_speed_mbps": round(avg_speed, 2),
                "speed_range_mbps": round(max_speed - min_speed, 2),
                "http_efficiency_percent": round(efficiency, 1)
            }
        })
    
    return speeds, drops

def run_test2(project, run_num):
    """Complete Performance Test - HTTP server managed by setup_https.py"""
    cfg = CONFIGS[project]
    mss_value = cfg['mss_clamp']
    server_port = cfg['server_port']
    
    print(f"\n{'█'*80}")
    print(f"█  TEST 2: COMPLETE PERFORMANCE TEST - {project.upper()} (Run {run_num})")
    print(f"█  Server Port: {server_port} | MSS: {mss_value} bytes")
    print(f"█  Cooldown: {COOLDOWN_BETWEEN_FILES}s | Drop Threshold: {DROP_THRESHOLD_PERCENT}%")
    print(f"█  Results: {PROJECT_DIR}")
    print(f"█  NOTE: HTTP server must be started via setup_https.py first")
    print(f"{'█'*80}")
    
    if not ensure_project_dir():
        return
    
    # Apply MSS clamping on the strategy's server
    apply_mss_clamping(project)
    
    # Initial cooldown
    cooldown_timer(5, "Initial cooldown before tests")
    
    # Start iperf3 server on the strategy's server
    start_iperf_server(project)
    time.sleep(2)
    
    # Run iperf3 test
    run_iperf3_test(project, run_num)
    
    # Cooldown between tests
    cooldown_timer(COOLDOWN_BETWEEN_FILES, "Cooldown between iperf3 and HTTP tests")
    
    # Run HTTP test
    speeds, drops = run_http_test(project, run_num)
    
    # Final cooldown
    cooldown_timer(5, "Final cooldown before stopping iperf3 server")
    
    # Stop iperf3 server
    stop_iperf_server(project)
    
    # HTTP server left running (managed by setup_https.py)
    
    print(f"\n{'█'*80}")
    print(f"█  TEST 2 COMPLETED - {project.upper()} (Run {run_num})")
    print(f"█  Results saved to: {PROJECT_DIR}")
    if drops:
        print(f"█  Drops detected: {len(drops)}")
        for drop in drops:
            print(f"█    📍 {drop['drop_size_range']} ({drop['drop_percentage']}%)")
    print(f"{'█'*80}")

def run_all_strategies(run_num):
    """Run all three strategies"""
    strategies = ["dualstack", "dslite", "nat64"]
    
    print(f"\n{'█'*80}")
    print(f"█  RUNNING ALL STRATEGIES - Run {run_num}")
    print(f"█  Results: {PROJECT_DIR}")
    print(f"█  IMPORTANT: Run setup_https.py for each strategy before testing!")
    print(f"█    python setup_https.py -s dualstack")
    print(f"█    python setup_https.py -s dslite")
    print(f"█    python setup_https.py -s nat64")
    print(f"{'█'*80}")
    
    for i, strategy in enumerate(strategies):
        if i > 0:
            cooldown_timer(COOLDOWN_BETWEEN_STRATEGIES, 
                         f"Strategy cooldown ({strategies[i-1].upper()} → {strategy.upper()})")
        run_test2(strategy, run_num)
    
    print(f"\n{'█'*80}")
    print(f"█  ALL STRATEGIES COMPLETED!")
    print(f"█  Results: {PROJECT_DIR}")
    print(f"{'█'*80}")
    
    print_comparative_summary()

def print_comparative_summary():
    """Print comparative summary - uses LATEST run for each strategy"""
    print(f"\n{'='*80}")
    print(f"COMPARATIVE SUMMARY - ALL STRATEGIES (Latest Runs)")
    print(f"{'='*80}")
    
    strategies_data = {}
    total_runs = {}
    
    for strategy in ["dualstack", "dslite", "nat64"]:
        drop_file = os.path.join(PROJECT_DIR, f"T2_drop_analysis_{strategy}.json")
        if os.path.exists(drop_file):
            try:
                with open(drop_file, 'r') as f:
                    data = json.load(f)
                    # If it's a list (multiple runs), use the LAST one
                    if isinstance(data, list) and len(data) > 0:
                        strategies_data[strategy] = data[-1]  # Latest run
                        total_runs[strategy] = len(data)
                    elif isinstance(data, dict):
                        strategies_data[strategy] = data  # Single run
                        total_runs[strategy] = 1
            except:
                pass
    
    if len(strategies_data) < 3:
        print("  Run all strategies first to see comparative summary")
        return
    
    headers = ["Metric", "DualStack", "DS-Lite", "NAT64"]
    rows = [
        ["MSS Clamping", "1460", "1400", "1440"],
        ["MTU", "1500", "1476", "1500"],
        ["Total Runs", str(total_runs.get("dualstack", "?")), 
                       str(total_runs.get("dslite", "?")), 
                       str(total_runs.get("nat64", "?"))],
        ["Drop Point", "", "", ""],
        ["Drop %", "", "", ""],
        ["Max Speed", "", "", ""],
        ["Min Speed", "", "", ""],
        ["Avg Speed", "", "", ""],
        ["iperf3 Baseline", "", "", ""],
        ["HTTP Efficiency", "", "", ""]
    ]
    
    for i, strategy in enumerate(["dualstack", "dslite", "nat64"]):
        if strategy in strategies_data:
            data = strategies_data[strategy]
            summary = data.get("performance_summary", {})
            drops = data.get("drops", [])
            
            if drops:
                rows[3][i+1] = drops[0].get("drop_size_range", "N/A")
                rows[4][i+1] = f"{drops[0].get('drop_percentage', 0)}%"
            
            rows[5][i+1] = f"{summary.get('max_speed_mbps', 0):.2f} Mbps"
            rows[6][i+1] = f"{summary.get('min_speed_mbps', 0):.2f} Mbps"
            rows[7][i+1] = f"{summary.get('avg_speed_mbps', 0):.2f} Mbps"
            rows[8][i+1] = f"{data.get('iperf_baseline_mbps', 0):.2f} Mbps"
            rows[9][i+1] = f"{summary.get('http_efficiency_percent', 0):.1f}%"
    
    print(f"\n┌{'─'*20}┬{'─'*18}┬{'─'*18}┬{'─'*18}┐")
    print(f"│ {headers[0]:<18} │ {headers[1]:<16} │ {headers[2]:<16} │ {headers[3]:<16} │")
    print(f"├{'─'*20}┼{'─'*18}┼{'─'*18}┼{'─'*18}┤")
    
    for row in rows:
        print(f"│ {row[0]:<18} │ {row[1]:<16} │ {row[2]:<16} │ {row[3]:<16} │")
    
    print(f"└{'─'*20}┴{'─'*18}┴{'─'*18}┴{'─'*18}┘")
    
    if strategies_data:
        best = max(strategies_data.items(), 
                  key=lambda x: x[1].get("performance_summary", {}).get("avg_speed_mbps", 0))
        print(f"\n🏆 Best Performance: {best[0].upper()}")
        print(f"   Avg Speed: {best[1].get('performance_summary', {}).get('avg_speed_mbps', 0):.2f} Mbps")
        print(f"   Based on {total_runs.get(best[0], '?')} run(s)")

def show_run_history():
    """Show run history for all strategies"""
    print(f"\n{'='*80}")
    print(f"RUN HISTORY - ALL STRATEGIES")
    print(f"{'='*80}")
    
    for strategy in ["dualstack", "dslite", "nat64"]:
        drop_file = os.path.join(PROJECT_DIR, f"T2_drop_analysis_{strategy}.json")
        if os.path.exists(drop_file):
            try:
                with open(drop_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        print(f"\n{strategy.upper()}: {len(data)} run(s)")
                        for run in data:
                            ts = run.get("run_timestamp", "Unknown")
                            avg = run.get("performance_summary", {}).get("avg_speed_mbps", "N/A")
                            drops = run.get("drops", [])
                            drop_info = drops[0].get("drop_size_range", "None") if drops else "None"
                            print(f"  {ts} | Avg: {avg} Mbps | Drop: {drop_info}")
                    elif isinstance(data, dict):
                        print(f"\n{strategy.upper()}: 1 run")
                        avg = data.get("performance_summary", {}).get("avg_speed_mbps", "N/A")
                        print(f"  Avg: {avg} Mbps")
            except:
                print(f"\n{strategy.upper()}: Error reading file")
        else:
            print(f"\n{strategy.upper()}: No data yet")

def reset_results():
    """Delete JSON files"""
    files_to_delete = [JSON_PATH]
    for strategy in CONFIGS.keys():
        drop_file = os.path.join(PROJECT_DIR, f"T2_drop_analysis_{strategy}.json")
        files_to_delete.append(drop_file)
    for file_path in files_to_delete:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"[DELETED] {file_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TEST 2: HTTP Performance Testing (Multi-Run Support)")
    parser.add_argument("--project", "-p", choices=["dualstack", "dslite", "nat64", "all"], required=True)
    parser.add_argument("--run", "-r", type=int, default=1)
    parser.add_argument("--mode", "-m", 
                       choices=["reset", "run", "iperf", "http", "iperf-server-start", "iperf-server-stop", "mss-apply", "history"],
                       default="run")
    parser.add_argument("--drop-threshold", "-d", type=int, default=30)
    parser.add_argument("--cooldown", "-c", type=int, default=12)
    args = parser.parse_args()
    
    if args.drop_threshold:
        DROP_THRESHOLD_PERCENT = args.drop_threshold
    if args.cooldown:
        COOLDOWN_BETWEEN_FILES = args.cooldown
    
    print(f"[INFO] Results Directory: {PROJECT_DIR}")
    print(f"[INFO] Main Results File: {JSON_PATH}")
    print(f"[INFO] HTTP server managed by setup_https.py per strategy")
    print(f"[INFO] Multi-run mode: Data APPENDS (not overwrites)")
    
    if args.mode == "reset":
        reset_results()
    elif args.mode == "history":
        show_run_history()
    elif args.mode == "mss-apply":
        apply_mss_clamping(args.project)
    elif args.mode == "iperf-server-start":
        start_iperf_server(args.project)
    elif args.mode == "iperf-server-stop":
        stop_iperf_server(args.project)
    elif args.mode == "iperf":
        run_iperf3_test(args.project, args.run)
    elif args.mode == "http":
        run_http_test(args.project, args.run)
    elif args.mode == "run":
        if args.project == "all":
            run_all_strategies(args.run)
        else:
            run_test2(args.project, args.run)