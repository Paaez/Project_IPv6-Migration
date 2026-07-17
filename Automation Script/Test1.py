#!/usr/bin/env python3
"""
test1_packet_size.py - TEST 1: Packet Size Performance (TCP, UDP, ICMP)
Runs from PC1 only
Results saved to: Project Directory/data/T1Rs.json
"""

import time
import argparse
import socket
import json
import os
import re
import traceback
from datetime import datetime

# ─────────────────────────────────────────────
# PATH & GNS3 CONFIGURATION
# ─────────────────────────────────────────────
GNS3_HOST = "192.168.255.128"
PROJECT_DIR = r"C:\Users\user\OneDrive\Documents\Abg Paeez\CSP 600\FYP_IPv6_Project\Project Directory\data"
JSON_PATH = os.path.join(PROJECT_DIR, "T1Rs.json")

# Create Project Directory if it doesn't exist
if not os.path.exists(PROJECT_DIR):
    os.makedirs(PROJECT_DIR)
    print(f"[INFO] Created directory: {PROJECT_DIR}")

CONFIGS = {
    "dualstack": {
        "pc1_port": 5013,
        "pc2_port": 5015,
        "server_port": 5002,
        "server_ip": "203.0.113.1",
        "target": "203.0.113.1",
        "ping_target": "203.0.113.1",
        "http_port": 8080,
        "ping_cmd": "ping", 
        "extra": "",
        "mss": 1460,   # 1500 MTU - 20 IP - 20 TCP = 1460
        "mtu": 1500,
        "udp_len": 1200  # UDP datagram size under MTU to avoid fragmentation
    },
    "dslite": {
        "pc1_port": 5003,
        "pc2_port": 5007,
        "server_port": 5018,
        "server_ip": "203.0.113.1",
        "target": "203.0.113.1",
        "ping_target": "203.0.113.1",
        "http_port": 8080,
        "ping_cmd": "ping", 
        "extra": "",
        "mss": 1396,   # 1436 MTU - 20 IP - 20 TCP = 1396 (GRE 24 + IPv6 40 overhead)
        "mtu": 1436,   # 1500 - 24 GRE - 40 IPv6 = 1436
        "udp_len": 1200
    },
    "nat64": {
        "pc1_port": 5000,
        "pc2_port": 5002,
        "server_port": 5010,
        "server_ip": "203.0.113.1",
        "target": "2001:db8:ff9b::cb00:7101",
        "ping_target": "2001:db8:ff9b::cb00:7101",
        "http_port": 8080,
        "ping_cmd": "ping6", 
        "extra": "-6",
        "mss": 1460,   # 1500 MTU - 20 IP - 20 TCP = 1460 (header translated, no extra overhead)
        "mtu": 1500,
        "udp_len": 1200
    }
}

# Test size tiers: 5M, 7M, 10M, 15M, 20M
TEST_SIZES = ["5M", "7M", "10M", "15M", "20M"]

def get_timestamp():
    """Get current timestamp in ISO format"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def save_to_json(strategy, metric, run_number, value):
    """Writes the captured metric to Project Directory/data/T1Rs.json with timestamp"""
    try:
        if not os.path.exists(PROJECT_DIR): 
            os.makedirs(PROJECT_DIR)
        
        data = []
        if os.path.exists(JSON_PATH):
            try:
                with open(JSON_PATH, 'r') as f: 
                    data = json.load(f)
            except Exception as e:
                print(f"  [WARN] Could not read existing JSON, creating new: {e}")
                data = []
        
        # Convert value to float if possible
        try:
            parsed_value = float(value)
        except (ValueError, TypeError):
            parsed_value = value
        
        timestamp = get_timestamp()
        
        data.append({
            "strategy": strategy.lower().strip(), 
            "metric": metric.strip(), 
            "run": run_number, 
            "value": parsed_value,
            "timestamp": timestamp
        })
        
        with open(JSON_PATH, 'w') as f: 
            json.dump(data, f, indent=4)
        print(f"  [SAVED] {metric} = {value} @ {timestamp}")
        return True
    except Exception as e:
        print(f"  [ERROR] Error saving to JSON: {e}")
        traceback.print_exc()
        return False

def send_command_and_get_output(port, command, wait_time, description=""):
    """Send a command to a GNS3 node via telnet"""
    output_data = ""
    try:
        print(f"  [CONNECT] Connecting to {GNS3_HOST}:{port} for {description}...")
        with socket.create_connection((GNS3_HOST, port), timeout=wait_time + 20) as sock:
            # Clear any existing output
            sock.sendall(b"\n")
            time.sleep(1)
            # Try to receive and discard any pending data
            sock.setblocking(False)
            try:
                sock.recv(4096)
            except:
                pass
            time.sleep(0.5)
            
            # Send the actual command
            sock.sendall(command.encode("ascii") + b"\n")
            print(f"  [RUNNING] {description}")
            print(f"  [COMMAND] {command[:100]}...")
            print(f"  [WAIT] Waiting {wait_time}s for completion...")
            
            # Wait for the command to complete
            time.sleep(wait_time)
            
            # Try to receive output
            sock.setblocking(False)
            time.sleep(2)
            
            all_data = []
            for attempt in range(3):  # Try 3 times to get data
                try:
                    chunk = sock.recv(524288).decode("ascii", errors="ignore")
                    if chunk:
                        all_data.append(chunk)
                        time.sleep(1)
                    else:
                        break
                except:
                    break
            
            output_data = "".join(all_data)
            
            if output_data:
                print(f"  [OK] Received {len(output_data)} bytes from {description}")
            else:
                print(f"  [WARN] Empty response from {description}")
                print(f"  [INFO] This may indicate the command failed or timed out")
    except socket.timeout:
        print(f"  [ERROR] Connection timeout to {GNS3_HOST}:{port}")
    except ConnectionRefusedError:
        print(f"  [ERROR] Connection refused - Is node {port} running?")
    except Exception as e:
        print(f"  [ERROR] Socket Error on port {port}: {e}")
    return output_data

def start_iperf_server(project):
    """Start iperf3 server - ALL strategies use 203.0.113.1"""
    cfg = CONFIGS[project]
    print(f"[SETUP] Starting iperf3 Server for {project}...")
    # Server always binds to 203.0.113.1
    cmd = f"pkill iperf3; sleep 1; iperf3 -s -B {cfg['server_ip']} -D; sleep 2"
    output = send_command_and_get_output(cfg['server_port'], cmd, 8, "Start server")
    print(f"  [OK] iperf3 server started on {cfg['server_ip']}")
    print(f"  [INFO] Waiting 5 seconds for server to fully initialize...")
    time.sleep(5)
    return True

def stop_iperf_server(project):
    """Stop iperf3 server for a specific strategy"""
    cfg = CONFIGS[project]
    print(f"[STOP] Stopping iperf3 server for {project}...")
    send_command_and_get_output(cfg['server_port'], "pkill iperf3", 3, "Stop server")
    return True

def reset_results():
    """Delete the T1Rs.json results file"""
    if os.path.exists(JSON_PATH): 
        os.remove(JSON_PATH)
        print(f"[DELETED] {JSON_PATH}")
    else:
        print(f"[INFO] No results file found at: {JSON_PATH}")
    return True

# ─────────────────────────────────────────────
# WARM-UP TEST FUNCTION
# ─────────────────────────────────────────────

def warmup_test(project):
    """Run a quick warm-up test to ensure connectivity"""
    cfg = CONFIGS[project]
    client_port = cfg['pc1_port']
    
    print(f"\n  [WARMUP] Testing connectivity at {get_timestamp()}...")
    
    # Quick TCP test with MSS clamping
    try:
        warmup_cmd = f"iperf3 -c {cfg['target']} {cfg['extra']} -t 5 -b 5M -M {cfg['mss']}"
        output = send_command_and_get_output(client_port, warmup_cmd, 10, "Warm-up TCP")
        if output and 'Mbits/sec' in output:
            print(f"  [OK] Warm-up TCP successful to {cfg['target']} (MSS={cfg['mss']})")
        else:
            print(f"  [WARN] Warm-up TCP may have failed - no throughput data")
    except Exception as e:
        print(f"  [WARN] Warm-up TCP error: {e}")
    
    time.sleep(2)
    
    # Quick ping test - use default 56-byte payload (no fragmentation)
    try:
        ping_cmd = f"{cfg['ping_cmd']} -c 3 {cfg['ping_target']}"
        output = send_command_and_get_output(client_port, ping_cmd, 8, "Warm-up ping")
        if output and 'packet loss' in output.lower():
            print(f"  [OK] Warm-up ping successful to {cfg['ping_target']}")
        else:
            print(f"  [WARN] Warm-up ping may have failed")
    except Exception as e:
        print(f"  [WARN] Warm-up ping error: {e}")
    
    print(f"  [INFO] Waiting 3 seconds before starting actual tests...")
    time.sleep(3)

# ─────────────────────────────────────────────
# TEST 1 PARSING FUNCTIONS
# ─────────────────────────────────────────────

def parse_iperf_tcp_final(output, strategy, run_num, size):
    """Parse TCP iperf3 output - capture FINAL summary line"""
    if not output:
        print(f"  [WARN] No output received for TCP {size}")
        return None
    
    try:
        lines = output.split('\n')
        final_throughput = None
        final_retransmissions = None
        
        # Look for the final summary line (process from end)
        for line in reversed(lines):
            if 'Mbits/sec' in line:
                if 'sender' in line.lower() or 'receiver' in line.lower():
                    if re.search(r'\d+\.?\d*\s+[GM]Bytes', line) and re.search(r'\d+\.?\d*\s+sec', line):
                        throughput_match = re.search(r'(\d+\.?\d*)\s+Mbits/sec', line)
                        if throughput_match:
                            final_throughput = throughput_match.group(1)
                        
                        retr_match = re.search(r'(\d+)\s+sender', line)
                        if retr_match:
                            final_retransmissions = retr_match.group(1)
                        break
                elif re.search(r'^\[' , line) and 'sec' in line and 'Bytes' in line:
                    throughput_match = re.search(r'(\d+\.?\d*)\s+Mbits/sec', line)
                    if throughput_match:
                        final_throughput = throughput_match.group(1)
                        break
        
        if not final_throughput:
            for line in reversed(lines):
                throughput_match = re.search(r'(\d+\.?\d*)\s+Mbits/sec', line)
                if throughput_match:
                    final_throughput = throughput_match.group(1)
                    print(f"  [INFO] Found throughput (fallback): {final_throughput} Mbps")
                    break
        
        if final_throughput:
            metric_name = f"T1_TCP_PC1_{size}_Throughput_Mbps"
            save_to_json(strategy, metric_name, run_num, final_throughput)
            print(f"      [OK] TCP Throughput: {final_throughput} Mbps")
        else:
            print(f"      [FAIL] Could not parse TCP Throughput for {size}")
        
        if final_retransmissions:
            metric_name = f"T1_TCP_PC1_{size}_Retransmissions"
            save_to_json(strategy, metric_name, run_num, final_retransmissions)
            print(f"      [OK] TCP Retransmissions: {final_retransmissions}")
        
        return final_throughput
    except Exception as e:
        print(f"  [ERROR] Error parsing TCP output: {e}")
        traceback.print_exc()
        return None

def parse_iperf_udp_final(output, strategy, run_num, size):
    """Parse UDP iperf3 output - capture ONLY RECEIVER summary line"""
    if not output:
        print(f"  [WARN] No output received for UDP {size}")
        return None
    
    try:
        lines = output.split('\n')
        final_jitter = None
        final_loss = None
        
        receiver_lines = []
        for i, line in enumerate(lines):
            if 'receiver' in line.lower():
                receiver_lines.append((i, line.strip()))
        
        if not receiver_lines:
            for i, line in enumerate(reversed(lines)):
                if 'ms' in line and '/' in line and ('Mbits/sec' in line or 'Kbits/sec' in line):
                    receiver_lines.append((len(lines) - 1 - i, line.strip()))
                    print(f"  [INFO] Using data line as receiver: {line.strip()}")
                    break
        
        if not receiver_lines:
            print(f"  [FAIL] No suitable UDP data lines found")
            return None
        
        last_receiver_idx, last_receiver_line = receiver_lines[-1]
        
        jitter_match = re.search(r'(\d+\.?\d*)\s+ms', last_receiver_line)
        if jitter_match:
            final_jitter = jitter_match.group(1)
            metric_name = f"T1_UDP_PC1_{size}_Jitter_ms"
            save_to_json(strategy, metric_name, run_num, final_jitter)
            print(f"      [OK] UDP Jitter: {final_jitter} ms")
        else:
            print(f"      [FAIL] Could not parse UDP Jitter for {size}")
        
        loss_match = re.search(r'\((\d+\.?\d*)%\)', last_receiver_line)
        if loss_match:
            final_loss = loss_match.group(1)
            metric_name = f"T1_UDP_PC1_{size}_Loss_Percent"
            save_to_json(strategy, metric_name, run_num, final_loss)
            print(f"      [OK] UDP Loss: {final_loss}%")
        else:
            lost_match = re.search(r'(\d+)/(\d+)', last_receiver_line)
            if lost_match:
                lost = int(lost_match.group(1))
                total = int(lost_match.group(2))
                if total > 0:
                    final_loss = str(round((lost / total) * 100, 1))
                    metric_name = f"T1_UDP_PC1_{size}_Loss_Percent"
                    save_to_json(strategy, metric_name, run_num, final_loss)
                    print(f"      [OK] UDP Loss (calculated): {final_loss}%")
        
        return final_jitter
    except Exception as e:
        print(f"  [ERROR] Error parsing UDP output: {e}")
        traceback.print_exc()
        return None

def parse_ping_final(output, strategy, run_num, size, test_type="T1_ICMP"):
    """Parse ping output - capture latency from summary line"""
    if not output:
        print(f"  [WARN] No output received for ICMP")
        return None
    
    try:
        lines = output.split('\n')
        rtt_values = None
        loss_pct = None
        
        for line in lines:
            if 'packet loss' in line.lower() or 'packets transmitted' in line.lower():
                loss_match = re.search(r'(\d+\.?\d*)%\s*(packet\s*)?loss', line, re.IGNORECASE)
                if loss_match:
                    loss_pct = loss_match.group(1)
                    break
                
                sent_match = re.search(r'(\d+)\s+packets?\s+transmitted', line, re.IGNORECASE)
                recv_match = re.search(r'(\d+)\s+received', line, re.IGNORECASE)
                if sent_match and recv_match:
                    sent = int(sent_match.group(1))
                    recv = int(recv_match.group(1))
                    if sent > 0:
                        loss_pct = str(round(((sent - recv) / sent) * 100, 1))
                        break
        
        for line in lines:
            line_lower = line.lower()
            
            if any(keyword in line_lower for keyword in ['rtt', 'round-trip', 'min/avg/max']):
                rtt_match = re.search(r'=\s*([\d.]+)\s*/\s*([\d.]+)\s*/\s*([\d.]+)\s*/\s*([\d.]+)', line)
                if rtt_match:
                    rtt_values = rtt_match.groups()
                    break
                
                rtt_match = re.search(r'([\d.]+)\s*/\s*([\d.]+)\s*/\s*([\d.]+)\s*/\s*([\d.]+)\s*ms', line)
                if rtt_match:
                    rtt_values = rtt_match.groups()
                    break
                
                rtt_match = re.search(r'=\s*([\d.]+)\s*/\s*([\d.]+)\s*/\s*([\d.]+)', line)
                if rtt_match:
                    groups = rtt_match.groups()
                    rtt_values = (groups[0], groups[1], groups[2], '0')
                    break
                
                rtt_match = re.search(r'([\d.]+)\s*/\s*([\d.]+)\s*/\s*([\d.]+)\s*ms', line)
                if rtt_match:
                    groups = rtt_match.groups()
                    rtt_values = (groups[0], groups[1], groups[2], '0')
                    break
        
        if loss_pct:
            metric_name = f"{test_type}_PC1_{size}_Loss_Percent"
            save_to_json(strategy, metric_name, run_num, loss_pct)
            print(f"      [OK] ICMP Loss: {loss_pct}%")
        else:
            print(f"      [FAIL] Could not parse ICMP Loss for {size}")
        
        if rtt_values:
            min_rtt, avg_rtt, max_rtt, mdev_rtt = rtt_values
            save_to_json(strategy, f"{test_type}_PC1_{size}_RTT_Min_ms", run_num, min_rtt)
            save_to_json(strategy, f"{test_type}_PC1_{size}_RTT_Avg_ms", run_num, avg_rtt)
            save_to_json(strategy, f"{test_type}_PC1_{size}_RTT_Max_ms", run_num, max_rtt)
            save_to_json(strategy, f"{test_type}_PC1_{size}_RTT_Mdev_ms", run_num, mdev_rtt)
            print(f"      [OK] ICMP RTT - Min: {min_rtt}, Avg: {avg_rtt}, Max: {max_rtt}, Mdev: {mdev_rtt} ms")
        else:
            print(f"      [FAIL] Could not parse ICMP RTT for {size}")
        
        return rtt_values
    except Exception as e:
        print(f"  [ERROR] Error parsing ICMP output: {e}")
        traceback.print_exc()
        return None

# ─────────────────────────────────────────────
# TEST 1 MAIN FUNCTION
# ─────────────────────────────────────────────

def run_test1(project, run_num):
    """TEST 1: Packet Size Performance from PC1"""
    try:
        cfg = CONFIGS[project]
        client_port = cfg['pc1_port']
        test_start_time = get_timestamp()
        
        print(f"\n{'='*60}")
        print(f"TEST 1: Packet Size Performance - {project.upper()} (Run {run_num})")
        print(f"Start Time: {test_start_time}")
        print(f"Client: PC1 (Port {client_port})")
        print(f"Server IP: {cfg['server_ip']}")
        print(f"Client Target: {cfg['target']}")
        print(f"Ping Target: {cfg['ping_target']}")
        print(f"MTU: {cfg['mtu']}, TCP MSS: {cfg['mss']}, UDP Datagram: {cfg['udp_len']} bytes")
        print(f"Test Sizes: {TEST_SIZES}")
        print(f"Results: {JSON_PATH}")
        print(f"{'='*60}")
        
        # Run warm-up test first
        warmup_test(project)
        
        # Test all packet sizes: 5M, 7M, 10M, 15M, 20M
        for idx, size in enumerate(TEST_SIZES):
            print(f"\n  {'='*50}")
            print(f"  PACKET SIZE: {size} ({idx+1}/{len(TEST_SIZES)}) - Started at {get_timestamp()}")
            print(f"  {'='*50}")
            
            # --- TCP Test (with MSS clamping) ---
            print(f"\n  [TCP] Starting {size} test (30 seconds) to {cfg['target']} with MSS={cfg['mss']}...")
            try:
                tcp_cmd = f"iperf3 -c {cfg['target']} {cfg['extra']} -t 30 -b {size} -M {cfg['mss']}"
                output = send_command_and_get_output(client_port, tcp_cmd, 38, f"TCP {size}")
                if output:
                    parse_iperf_tcp_final(output, project, run_num, size)
                else:
                    print(f"  [FAIL] No TCP output received for {size}")
                    save_to_json(project, f"T1_TCP_PC1_{size}_Throughput_Mbps", run_num, 0)
            except Exception as e:
                print(f"  [ERROR] TCP test error for {size}: {e}")
                save_to_json(project, f"T1_TCP_PC1_{size}_Throughput_Mbps", run_num, 0)
            print(f"  [TIME] TCP {size} completed at {get_timestamp()}")
            
            # 12-second cooldown between tests
            cooldown = 12
            print(f"  [COOLDOWN] Waiting {cooldown} seconds for router to idle and clear buffers...")
            time.sleep(cooldown)
            
            # --- UDP Test (with explicit datagram length to avoid fragmentation) ---
            print(f"\n  [UDP] Starting {size} test (30 seconds) to {cfg['target']} with datagram={cfg['udp_len']}...")
            try:
                udp_cmd = f"iperf3 -c {cfg['target']} {cfg['extra']} -u -b {size} -t 30 -l {cfg['udp_len']}"
                output = send_command_and_get_output(client_port, udp_cmd, 38, f"UDP {size}")
                if output:
                    parse_iperf_udp_final(output, project, run_num, size)
                else:
                    print(f"  [FAIL] No UDP output received for {size}")
                    save_to_json(project, f"T1_UDP_PC1_{size}_Jitter_ms", run_num, 0)
                    save_to_json(project, f"T1_UDP_PC1_{size}_Loss_Percent", run_num, 0)
            except Exception as e:
                print(f"  [ERROR] UDP test error for {size}: {e}")
                save_to_json(project, f"T1_UDP_PC1_{size}_Jitter_ms", run_num, 0)
                save_to_json(project, f"T1_UDP_PC1_{size}_Loss_Percent", run_num, 0)
            print(f"  [TIME] UDP {size} completed at {get_timestamp()}")
            
            # 12-second cooldown between tests
            print(f"  [COOLDOWN] Waiting {cooldown} seconds for router to idle and clear buffers...")
            time.sleep(cooldown)
            
            # --- ICMP Test (default 56-byte payload - no fragmentation) ---
            print(f"\n  [ICMP] Starting ping test to {cfg['ping_target']} (default 56-byte payload)...")
            try:
                # Use default 56-byte payload for clean latency measurement (no fragmentation)
                ping_cmd = f"{cfg['ping_cmd']} -c 30 {cfg['ping_target']}"
                output = send_command_and_get_output(client_port, ping_cmd, 35, f"ICMP {size}")
                if output:
                    parse_ping_final(output, project, run_num, size, "T1_ICMP")
                else:
                    print(f"  [FAIL] No ICMP output received for {size}")
                    save_to_json(project, f"T1_ICMP_PC1_{size}_Loss_Percent", run_num, 0)
            except Exception as e:
                print(f"  [ERROR] ICMP test error for {size}: {e}")
                save_to_json(project, f"T1_ICMP_PC1_{size}_Loss_Percent", run_num, 0)
            print(f"  [TIME] ICMP {size} completed at {get_timestamp()}")
            
            # 12-second cooldown between packet sizes (except after last)
            if idx < len(TEST_SIZES) - 1:
                print(f"  [COOLDOWN] Waiting {cooldown} seconds before next packet size...")
                time.sleep(cooldown)
        
        test_end_time = get_timestamp()
        
        # Final summary
        print(f"\n{'='*60}")
        print(f"TEST 1 COMPLETED for {project.upper()} (Run {run_num})")
        print(f"   Started: {test_start_time}")
        print(f"   Ended:   {test_end_time}")
        
        if os.path.exists(JSON_PATH):
            with open(JSON_PATH, 'r') as f:
                data = json.load(f)
            print(f"Total metrics in T1Rs.json: {len(data)}")
            
            metrics_by_type = {}
            for entry in data:
                metric = entry['metric']
                if 'TCP' in metric:
                    mtype = 'TCP'
                elif 'UDP' in metric:
                    mtype = 'UDP'
                elif 'ICMP' in metric:
                    mtype = 'ICMP'
                else:
                    mtype = 'Other'
                metrics_by_type[mtype] = metrics_by_type.get(mtype, 0) + 1
            
            for mtype, count in metrics_by_type.items():
                print(f"   {mtype}: {count} metrics")
            
            # Count by size
            for test_size in TEST_SIZES:
                count = len([d for d in data if test_size in d['metric']])
                print(f"   {test_size}: {count} metrics")
            
            if data:
                print(f"\nTimestamp range:")
                timestamps = [d.get('timestamp', 'N/A') for d in data]
                print(f"   First entry: {timestamps[0]}")
                print(f"   Last entry:  {timestamps[-1]}")
        else:
            print(f"[WARN] No results file found!")
        print(f"{'='*60}")
        
    except Exception as e:
        print(f"[FATAL] Fatal error in run_test1: {e}")
        traceback.print_exc()

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except:
            pass
    
    parser = argparse.ArgumentParser(
        description="TEST 1: Packet Size Performance (TCP, UDP, ICMP)"
    )
    parser.add_argument("--project", "-p", 
                       choices=["dualstack", "dslite", "nat64"], 
                       required=True,
                       help="Network strategy to test")
    parser.add_argument("--run", "-r", 
                       type=int, 
                       default=1,
                       help="Run number (1-10)")
    parser.add_argument("--mode", "-m", 
                       choices=["start", "stop", "reset", "run"], 
                       default="run",
                       help="Operation mode")
    args = parser.parse_args()
    
    if not os.path.exists(PROJECT_DIR):
        os.makedirs(PROJECT_DIR)
        print(f"[INFO] Created directory: {PROJECT_DIR}")
    
    print(f"[INFO] Results file: {JSON_PATH}")
    print(f"[TIME] Current time: {get_timestamp()}")
    
    try:
        if args.mode == "start":
            start_iperf_server(args.project)
        elif args.mode == "stop":
            stop_iperf_server(args.project)
        elif args.mode == "reset":
            reset_results()
        elif args.mode == "run":
            run_test1(args.project, args.run)
    except KeyboardInterrupt:
        print(f"\n[INTERRUPTED] Script interrupted by user at {get_timestamp()}")
    except Exception as e:
        print(f"\n[ERROR] Unexpected error at {get_timestamp()}: {e}")
        traceback.print_exc()