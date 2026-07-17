#!/usr/bin/env python3
"""
test5_fragmentation.py - TEST 5: Packet Fragmentation Boundary (MINIMIZED)
Runs from PC1 only - Essential metrics only
Includes sleep timer between tests to prevent router overload
"""

import time
import argparse
import socket
import json
import os
import re
from datetime import datetime

# ─────────────────────────────────────────────
# PATH & GNS3 CONFIGURATION
# ─────────────────────────────────────────────
GNS3_HOST = "192.168.255.128"
PROJECT_DIR = r"C:\Users\user\OneDrive\Documents\Abg Paeez\CSP 600\FYP_IPv6_Project\Project Directory\data"
JSON_PATH = os.path.join(PROJECT_DIR, "T5Rs.json")

# ─────────────────────────────────────────────
# TIMING CONFIGURATION
# ─────────────────────────────────────────────
SLEEP_BETWEEN_TESTS = 12        # Seconds between each packet size test
SLEEP_BETWEEN_PHASES = 15       # Seconds between Phase 1 and Phase 2
SLEEP_BETWEEN_STRATEGIES = 15   # Seconds between strategy runs (if running all)

CONFIGS = {
    "dualstack": {
        "pc1_port": 5018,
        "pc2_port": 5020,
        "server_port": 5003, 
        "target": "203.0.113.1",
        "iperf_target": "203.0.113.1",
        "http_port": 8080,
        "ping_cmd": "ping",
        "mtu": 1500,
        "ip_version": 4,
        "ip_header_size": 20,
        "icmp_header_size": 8
    },
    "dslite": {
        "pc1_port": 5008,
        "pc2_port": 5010,
        "server_port": 5015, 
        "target": "203.0.113.1",
        "iperf_target": "203.0.113.1",
        "http_port": 8080,
        "ping_cmd": "ping",
        "mtu": 1476,
        "ip_version": 4,
        "ip_header_size": 20,
        "icmp_header_size": 8
    },
    "nat64": {
        "pc1_port": 5016,
        "pc2_port": 5018,
        "server_port": 5022, 
        "target": "2001:db8:ff9b::cb00:7101",
        "iperf_target": "2001:db8:ff9b::cb00:7101",
        "http_port": 8080,
        "ping_cmd": "ping6",
        "mtu": 1500,
        "ip_version": 6,
        "ip_header_size": 40,
        "icmp_header_size": 8
    }
}

def calculate_max_payload(mtu, ip_version):
    """Calculate maximum ping payload without fragmentation"""
    return mtu - (40 + 8) if ip_version == 6 else mtu - (20 + 8)

def get_test_sizes(mtu, ip_version, phase):
    """Generate test sizes"""
    max_payload = calculate_max_payload(mtu, ip_version)
    
    if phase == 1:  # No fragmentation
        sizes = [64, 128, 256, 512, 768, 1024, 1280]
        # Add granular sizes near MTU
        for s in range(max(1280, max_payload - 100), max_payload + 30, 10):
            sizes.append(s)
        return sorted(list(set(sizes)))
    
    elif phase == 2:  # Allow fragmentation
        return [1500, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000,
                12000, 15000, 20000, 30000, 40000, 50000, 60000]
    return []

def save_metric(strategy, metric, run_num, value):
    """Save essential metric to T5Rs.json in data folder"""
    if not os.path.exists(PROJECT_DIR): 
        os.makedirs(PROJECT_DIR)
        print(f"📁 Created directory: {PROJECT_DIR}")
    
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
        "run": run_num, 
        "value": float(value) if isinstance(value, (int, float)) else value,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    with open(JSON_PATH, 'w') as f: 
        json.dump(data, f, indent=4)

def send_command(port, command, wait_time, description=""):
    """Send command via telnet and get output"""
    output = ""
    try:
        with socket.create_connection((GNS3_HOST, port), timeout=wait_time + 20) as sock:
            sock.sendall(b"\n")
            time.sleep(1)
            sock.setblocking(False)
            try: sock.recv(4096)
            except: pass
            sock.setblocking(True)
            
            sock.sendall(command.encode("ascii") + b"\n")
            print(f"  ...{description} ({wait_time}s)")
            time.sleep(wait_time)
            sock.setblocking(False)
            time.sleep(2)
            try:
                while True:
                    chunk = sock.recv(4096)
                    if not chunk: break
                    output += chunk.decode("ascii", errors="ignore")
            except: pass
    except Exception as e:
        print(f"  ❌ Error: {e}")
    return output

def start_iperf_server(project):
    """Start iperf3 server"""
    cfg = CONFIGS[project]
    if project == "nat64":
        cmd = f"pkill iperf3; sleep 2; iperf3 -s -B {cfg['iperf_target']} -6 -D"
    else:
        cmd = f"pkill iperf3; sleep 2; iperf3 -s -B {cfg['iperf_target']} -D"
    send_command(cfg['server_port'], cmd, 5, "Start iperf3")
    print(f"  ✅ Server started on {cfg['iperf_target']}")
    time.sleep(3)  # Let server initialize

def stop_iperf_server(project):
    """Stop iperf3 server"""
    send_command(CONFIGS[project]['server_port'], "pkill iperf3", 3, "Stop iperf3")
    time.sleep(2)  # Let processes clean up

def reset_results():
    """Delete T5Rs.json from data folder"""
    if os.path.exists(JSON_PATH): 
        os.remove(JSON_PATH)
        print(f"🗑️ Deleted: {JSON_PATH}")
    else:
        print(f"ℹ️ No file found at: {JSON_PATH}")

def parse_ping_result(output, cfg, df_flag):
    """Parse only essential metrics"""
    result = {
        "success": False,
        "loss_pct": 100,
        "rtt_avg": None,
        "frag_required": False,
        "fragmented": False
    }
    
    if not output:
        return result
    
    # Check fragmentation
    if "Frag needed" in output or "message too long" in output.lower():
        result["frag_required"] = True
        return result
    
    if "frag offset" in output.lower() or "more fragments" in output.lower():
        result["fragmented"] = True
    
    # Extract loss percentage
    loss_match = re.search(r'(\d+(?:\.\d+)?)%\s+packet\s+loss', output)
    if loss_match:
        result["loss_pct"] = float(loss_match.group(1))
    
    # Extract RTT average
    rtt_match = re.search(r'rtt\s+min/avg/max/mdev\s*=\s*[\d.]+/([\d.]+)/[\d.]+/[\d.]+\s*ms', output)
    if not rtt_match:
        rtt_match = re.search(r'round-trip\s+min/avg/max/stddev\s*=\s*[\d.]+/([\d.]+)/[\d.]+/[\d.]+\s*ms', output)
    
    if rtt_match:
        result["rtt_avg"] = float(rtt_match.group(1))
        result["success"] = (result["loss_pct"] == 0)
    
    # Detect fragmentation for large packets
    if not df_flag and (output.count("bytes from") > 0 or result["success"]):
        total_size = int(re.search(r'-s\s+(\d+)', output).group(1)) if re.search(r'-s\s+(\d+)', output) else 0
        if total_size > cfg["mtu"] - cfg["ip_header_size"] - cfg["icmp_header_size"]:
            result["fragmented"] = True
    
    return result

def run_phase(project, run_num, phase, test_sizes, df_flag, cfg, client_port, ping_cmd, target):
    """Run a single phase and return essential results"""
    max_payload = calculate_max_payload(cfg['mtu'], cfg['ip_version'])
    
    print(f"\n{'='*60}")
    print(f"PHASE {phase}: {'NO FRAG (DF Set)' if df_flag else 'ALLOW FRAGMENTATION'}")
    print(f"Strategy: {project.upper()} | MTU: {cfg['mtu']} | Max Payload: {max_payload}")
    print(f"Sleep between tests: {SLEEP_BETWEEN_TESTS}s | Estimated duration: ~{len(test_sizes) * (SLEEP_BETWEEN_TESTS + 8)}s")
    print(f"{'='*60}")
    print(f"{'Size(B)':<10} {'Status':<15} {'Loss%':<8} {'RTT Avg':<10} {'Frag':<8} {'Cooldown'}")
    print("-" * 65)
    
    results = {}
    max_success_size = None
    total_tests = len(test_sizes)
    
    for idx, size in enumerate(test_sizes, 1):
        print(f"{size:<10}", end=" ", flush=True)
        
        # Build command
        if df_flag:
            cmd = f"{ping_cmd} -c 4 -i 0.2 -M do -s {size} {target} 2>&1"
        else:
            cmd = f"{ping_cmd} -c 4 -i 0.2 -s {size} {target} 2>&1"
        
        wait_time = 12 if size <= 5000 else 20 if size <= 10000 else 30
        output = send_command(client_port, cmd, wait_time, f"Test {size}B")
        result = parse_ping_result(output, cfg, df_flag)
        
        # Save essential metrics
        prefix = f"T5_P{phase}_{size}B"
        save_metric(project, f"{prefix}_Success", run_num, 1 if result["success"] else 0)
        save_metric(project, f"{prefix}_Loss_Pct", run_num, result["loss_pct"])
        save_metric(project, f"{prefix}_Frag_Required", run_num, 1 if result["frag_required"] else 0)
        save_metric(project, f"{prefix}_Fragmented", run_num, 1 if result["fragmented"] else 0)
        
        if result["rtt_avg"] is not None:
            save_metric(project, f"{prefix}_RTT_Avg_ms", run_num, result["rtt_avg"])
        
        if result["success"]:
            max_success_size = size
        
        # Display
        status = "✅ SUCCESS" if result["success"] else "❌ FAILED" if result["loss_pct"] == 100 else "⚠️ PARTIAL"
        if result["frag_required"]: status = "❌ FRAG NEEDED"
        
        rtt_str = f"{result['rtt_avg']:.1f}" if result["rtt_avg"] else "N/A"
        frag_str = "YES" if result["fragmented"] else "NO"
        
        # Show progress
        progress = f"[{idx}/{total_tests}]"
        
        print(f"{status:<15} {result['loss_pct']:<8.0f} {rtt_str:<10} {frag_str:<8}", end=" ")
        
        results[size] = result
        
        # Sleep between tests (except after the last one)
        if idx < total_tests:
            print(f"💤 {SLEEP_BETWEEN_TESTS}s...", end="", flush=True)
            
            # Countdown for visibility
            for remaining in range(SLEEP_BETWEEN_TESTS, 0, -5):
                time.sleep(5)
                print(f"{remaining}", end="", flush=True)
                if remaining > 5:
                    print("", end="", flush=True)
            
            # Clear any remaining seconds
            remaining = SLEEP_BETWEEN_TESTS % 5
            if remaining > 0:
                time.sleep(remaining)
            
            print(f" ✓ ({SLEEP_BETWEEN_TESTS}s cooldown complete)")
        else:
            print(f"{progress}")
    
    print(f"\n📊 Phase {phase} Summary:")
    if max_success_size:
        print(f"   Max payload without fragmentation: {max_success_size} bytes")
    
    return results, max_success_size

def run_test5(project, run_num):
    """TEST 5: Fragmentation Boundary - Essential Version with Cooldown"""
    cfg = CONFIGS[project]
    client_port = cfg['pc1_port']
    ping_cmd = cfg['ping_cmd']
    target = cfg['target']
    max_payload = calculate_max_payload(cfg['mtu'], cfg['ip_version'])
    
    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    start_dt = datetime.now()
    
    print(f"\n{'='*60}")
    print(f"TEST 5: FRAGMENTATION BOUNDARY - {project.upper()} (Run {run_num})")
    print(f"Target: {target} | IPv{cfg['ip_version']} | MTU: {cfg['mtu']} | Max Payload: {max_payload}")
    print(f"Cooldown: {SLEEP_BETWEEN_TESTS}s between tests | Phase gap: {SLEEP_BETWEEN_PHASES}s")
    print(f"Results: {JSON_PATH}")
    print(f"Start: {start_time}")
    print(f"{'='*60}")
    
    save_metric(project, "T5_Test_Start", run_num, start_time)
    save_metric(project, "T5_Cooldown_Seconds", run_num, SLEEP_BETWEEN_TESTS)
    
    # ── PHASE 1: No Fragmentation ──
    phase1_sizes = get_test_sizes(cfg['mtu'], cfg['ip_version'], 1)
    print(f"\n🔬 PHASE 1: {len(phase1_sizes)} packet sizes to test")
    print(f"   Estimated time: ~{len(phase1_sizes) * (SLEEP_BETWEEN_TESTS + 8)} seconds")
    phase1_results, phase1_max = run_phase(project, run_num, 1, phase1_sizes, True, cfg, client_port, ping_cmd, target)
    
    # ── COOLDOWN BETWEEN PHASES ──
    print(f"\n{'─'*60}")
    print(f"⏸️  PHASE TRANSITION: Cooling down for {SLEEP_BETWEEN_PHASES}s...")
    print(f"   Letting router CPU idle and clear buffers...")
    for remaining in range(SLEEP_BETWEEN_PHASES, 0, -5):
        print(f"   ⏳ {remaining}s remaining...")
        time.sleep(min(5, remaining))
    time.sleep(SLEEP_BETWEEN_PHASES % 5)
    print(f"   ✅ Cooldown complete - Starting Phase 2")
    print(f"{'─'*60}")
    
    # ── PHASE 2: Allow Fragmentation ──
    phase2_sizes = get_test_sizes(cfg['mtu'], cfg['ip_version'], 2)
    print(f"\n🔬 PHASE 2: {len(phase2_sizes)} packet sizes to test")
    print(f"   Estimated time: ~{len(phase2_sizes) * (SLEEP_BETWEEN_TESTS + 12)} seconds")
    phase2_results, phase2_max = run_phase(project, run_num, 2, phase2_sizes, False, cfg, client_port, ping_cmd, target)
    
    # ── FINAL SUMMARY ──
    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    end_dt = datetime.now()
    duration = (end_dt - start_dt).total_seconds()
    
    print(f"\n{'='*60}")
    print(f"FINAL SUMMARY - {project.upper()}")
    print(f"End: {end_time} | Duration: {duration:.0f}s ({duration/60:.1f} min)")
    print(f"{'='*60}")
    print(f"📈 Max No-Frag Payload: {phase1_max} bytes")
    print(f"📈 Max Frag Allowed:    {phase2_max} bytes")
    print(f"📈 Total Tests:         {len(phase1_sizes) + len(phase2_sizes)}")
    print(f"📈 Cooldown Used:       {SLEEP_BETWEEN_TESTS}s per test")
    print(f"{'='*60}")
    
    # Save final summary
    save_metric(project, "T5_Final_Max_NoFrag_Payload", run_num, phase1_max or 0)
    save_metric(project, "T5_Final_Max_Frag_Allowed_Payload", run_num, phase2_max or 0)
    save_metric(project, "T5_Total_Duration_Seconds", run_num, duration)
    save_metric(project, "T5_Test_End", run_num, end_time)
    save_metric(project, "T5_Phase1_Tests_Count", run_num, len(phase1_sizes))
    save_metric(project, "T5_Phase2_Tests_Count", run_num, len(phase2_sizes))
    
    print(f"\n✅ TEST 5 Completed - {project.upper()}")
    print(f"📁 Results: {JSON_PATH}")
    
    return {"phase1_max": phase1_max, "phase2_max": phase2_max, "duration": duration}

# ─────────────────────────────────────────────
# RUN ALL STRATEGIES FUNCTION
# ─────────────────────────────────────────────
def run_all_strategies(run_num=1):
    """Run Test 5 for all three strategies with cooldown between each"""
    strategies = ["dualstack", "dslite", "nat64"]
    all_results = {}
    
    total_start = datetime.now()
    
    print(f"\n{'═'*60}")
    print(f"TEST 5: ALL STRATEGIES - SEQUENTIAL RUN")
    print(f"Strategies: {', '.join(s.upper() for s in strategies)}")
    print(f"Sleep between strategies: {SLEEP_BETWEEN_STRATEGIES}s")
    print(f"Results folder: {PROJECT_DIR}")
    print(f"{'═'*60}")
    
    for idx, strategy in enumerate(strategies, 1):
        print(f"\n{'█'*60}")
        print(f"█ [{idx}/3] STARTING: {strategy.upper()}")
        print(f"{'█'*60}")
        
        # Start iperf server for this strategy
        start_iperf_server(strategy)
        
        # Run the test
        result = run_test5(strategy, run_num)
        all_results[strategy] = result
        
        # Stop iperf server
        stop_iperf_server(strategy)
        
        # Cooldown between strategies (except after last)
        if idx < len(strategies):
            print(f"\n{'─'*60}")
            print(f"⏸️  STRATEGY TRANSITION: Cooling down for {SLEEP_BETWEEN_STRATEGIES}s...")
            print(f"   Letting GNS3 environment stabilize...")
            for remaining in range(SLEEP_BETWEEN_STRATEGIES, 0, -5):
                print(f"   ⏳ {remaining}s remaining...")
                time.sleep(min(5, remaining))
            time.sleep(SLEEP_BETWEEN_STRATEGIES % 5)
            print(f"   ✅ Ready for next strategy")
            print(f"{'─'*60}")
    
    # Final combined summary
    total_end = datetime.now()
    total_duration = (total_end - total_start).total_seconds()
    
    print(f"\n{'═'*60}")
    print(f"🏁 ALL STRATEGIES COMPLETED")
    print(f"{'═'*60}")
    print(f"Total Duration: {total_duration:.0f}s ({total_duration/60:.1f} min)")
    print(f"{'═'*60}")
    print(f"{'Strategy':<15} {'Max NoFrag':<15} {'Max Frag':<15} {'Duration'}")
    print(f"{'─'*60}")
    for strategy, result in all_results.items():
        p1 = result.get('phase1_max', 'N/A')
        p2 = result.get('phase2_max', 'N/A')
        dur = result.get('duration', 0)
        print(f"{strategy.upper():<15} {str(p1) + 'B':<15} {str(p2) + 'B':<15} {dur:.0f}s")
    print(f"{'═'*60}")
    print(f"📁 All results saved to: {JSON_PATH}")
    
    return all_results

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TEST 5: Fragmentation Boundary with Cooldown")
    parser.add_argument("--project", "-p", choices=["dualstack", "dslite", "nat64", "all"], default="all")
    parser.add_argument("--run", "-r", type=int, default=1)
    parser.add_argument("--mode", "-m", choices=["start", "stop", "reset", "run"], default="run")
    parser.add_argument("--sleep", "-s", type=int, default=12, 
                        help=f"Cooldown seconds between tests (default: {SLEEP_BETWEEN_TESTS})")
    args = parser.parse_args()
    
    # Override sleep time if specified
    if args.sleep:
        SLEEP_BETWEEN_TESTS = args.sleep
        SLEEP_BETWEEN_PHASES = args.sleep + 3
        SLEEP_BETWEEN_STRATEGIES = args.sleep + 3
    
    if args.mode == "start":
        if args.project == "all":
            for s in ["dualstack", "dslite", "nat64"]:
                start_iperf_server(s)
        else:
            start_iperf_server(args.project)
    
    elif args.mode == "stop":
        if args.project == "all":
            for s in ["dualstack", "dslite", "nat64"]:
                stop_iperf_server(s)
        else:
            stop_iperf_server(args.project)
    
    elif args.mode == "reset":
        reset_results()
    
    elif args.mode == "run":
        if args.project == "all":
            run_all_strategies(args.run)
        else:
            start_iperf_server(args.project)
            run_test5(args.project, args.run)
            stop_iperf_server(args.project)