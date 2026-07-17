#!/usr/bin/env python3
"""
setup_https.py - Automated HTTP Server Setup for IPv6 Migration
UPDATED: Added MSS Clamping, saves config to data directory
"""

import time
import socket
import json
import os
import re
from typing import Dict, List

# =============================================
# GNS3 CONFIGURATION
# =============================================
GNS3_HOST = "192.168.255.128"
PROJECT_DATA_DIR = r"C:\Users\user\OneDrive\Documents\Abg Paeez\CSP 600\FYP_IPv6_Project\Project Directory\data"

# MSS Clamping values for TCP throughput optimization
MSS_CONFIGS = {
    "dualstack": {
        "mss": 1460,
        "description": "Standard Ethernet MSS (1500 MTU - 40 bytes TCP/IP headers)"
    },
    "dslite": {
        "mss": 1400, 
        "description": "Reduced MSS for DS-Lite tunnel (1476 MTU - 40 bytes - 36 bytes tunnel overhead)"
    },
    "nat64": {
        "mss": 1440,
        "description": "Slightly reduced MSS for NAT64 translation (1500 MTU - 40 bytes - 20 bytes translation)"
    }
}

# Port mappings for each migration strategy
MIGRATION_CONFIGS = {
    "dualstack": {
        "pc2": {
            "name": "PC2",
            "host": GNS3_HOST,
            "port": 5015,
            "description": "Dual Stack Client"
        },
        "linux_server": {
            "name": "Linux-Server",
            "host": GNS3_HOST,
            "port": 5002,
            "description": "Dual Stack HTTP Server"
        },
        "target_ipv4": "203.0.113.1",
        "target_ipv6": "2001:db8:ffff::1",
        "http_target": "203.0.113.1",
        "use_ipv6_curl": False,
        "http_port": 8080,
        "mss_clamp": 1460
    },
    "dslite": {
        "pc2": {
            "name": "PC2",
            "host": GNS3_HOST,
            "port": 5007,
            "description": "DS-Lite Client"
        },
        "linux_server": {
            "name": "Linux-Server",
            "host": GNS3_HOST,
            "port": 5018,
            "description": "DS-Lite HTTP Server"
        },
        "target_ipv4": "203.0.113.1",
        "target_ipv6": "2001:db8:ffff::1",
        "http_target": "203.0.113.1",
        "use_ipv6_curl": False,
        "http_port": 8080,
        "mss_clamp": 1400
    },
    "nat64": {
        "pc2": {
            "name": "PC2",
            "host": GNS3_HOST,
            "port": 5003,
            "description": "NAT64 Client (IPv6-only)"
        },
        "linux_server": {
            "name": "Linux-Server",
            "host": GNS3_HOST,
            "port": 5012,
            "description": "NAT64 HTTP Server"
        },
        "target_ipv4": "203.0.113.1",
        "target_ipv6": "2001:db8:ff9b::cb00:7101",
        "http_target": "2001:db8:ff9b::cb00:7101",
        "use_ipv6_curl": True,
        "http_port": 8080,
        "mss_clamp": 1440
    }
}

def ensure_data_dir():
    """Ensure the data directory exists"""
    if not os.path.exists(PROJECT_DATA_DIR):
        try:
            os.makedirs(PROJECT_DATA_DIR)
            print(f"[INFO] Created data directory: {PROJECT_DATA_DIR}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to create data directory: {e}")
            return False
    return True

def save_setup_config(strategy, config_info):
    """Save setup configuration to data directory"""
    if not ensure_data_dir():
        return
    
    config_file = os.path.join(PROJECT_DATA_DIR, f"setup_config_{strategy}.json")
    
    try:
        with open(config_file, 'w') as f:
            json.dump(config_info, f, indent=4)
        print(f"  [SAVED] Setup config: {config_file}")
    except Exception as e:
        print(f"  [ERROR] Failed to save config: {e}")

def send_command(port: int, command: str, wait_time: int = 5, capture_output: bool = True) -> str:
    """Send a command to a GNS3 node via socket"""
    output = ""
    try:
        with socket.create_connection((GNS3_HOST, port), timeout=wait_time + 10) as sock:
            sock.sendall(b"\n")
            time.sleep(0.5)
            sock.sendall(command.encode("ascii") + b"\n")
            time.sleep(wait_time)
            
            if capture_output:
                sock.setblocking(False)
                time.sleep(1)
                try:
                    chunks = []
                    while True:
                        chunk = sock.recv(4096)
                        if not chunk:
                            break
                        chunks.append(chunk.decode("ascii", errors="ignore"))
                    output = "".join(chunks)
                except (socket.error, BlockingIOError):
                    pass
                    
    except Exception as e:
        print(f"  [ERROR] Socket Error on port {port}: {e}")
    
    return output

def send_commands(port: int, commands: List[str], wait_time: int = 5) -> str:
    """Send multiple commands to a GNS3 node"""
    output = ""
    try:
        with socket.create_connection((GNS3_HOST, port), timeout=wait_time + 10) as sock:
            sock.sendall(b"\n")
            time.sleep(0.5)
            
            for cmd in commands:
                sock.sendall(cmd.encode("ascii") + b"\n")
                time.sleep(0.5)
            
            time.sleep(wait_time)
            
            sock.setblocking(False)
            time.sleep(1)
            try:
                chunks = []
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    chunks.append(chunk.decode("ascii", errors="ignore"))
                output = "".join(chunks)
            except (socket.error, BlockingIOError):
                pass
                
    except Exception as e:
        print(f"  [ERROR] Socket Error on port {port}: {e}")
    
    return output

def apply_mss_clamping(port: int, mss_value: int, strategy: str) -> bool:
    """Apply MSS clamping for TCP throughput optimization"""
    mss_info = MSS_CONFIGS.get(strategy, {"mss": mss_value, "description": "Custom MSS"})
    
    print(f"\n  [MSS] Configuring TCP MSS Clamping")
    print(f"        Strategy: {strategy.upper()}")
    print(f"        MSS Value: {mss_value} bytes")
    print(f"        {mss_info['description']}")
    
    commands = [
        "iptables -t mangle -F OUTPUT 2>/dev/null || true",
        "iptables -t mangle -F FORWARD 2>/dev/null || true",
        f"iptables -t mangle -A OUTPUT -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --set-mss {mss_value}",
        f"iptables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --set-mss {mss_value}",
        "iptables -t mangle -A OUTPUT -p tcp --tcp-flags SYN,RST SYN,RST -j TCPMSS --clamp-mss-to-pmtu",
        "iptables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN,RST -j TCPMSS --clamp-mss-to-pmtu",
        f"echo 'MSS_CLAMPING_APPLIED={mss_value}'"
    ]
    
    full_command = "; ".join(commands)
    output = send_command(port, full_command, 8, f"Apply MSS Clamping ({mss_value} bytes)")
    
    if f"MSS_CLAMPING_APPLIED={mss_value}" in output:
        print(f"  [ OK ] MSS Clamping applied: {mss_value} bytes")
        return True
    else:
        print(f"  [WARN] MSS Clamping may not have been applied")
        return False

def verify_mss_clamping(port: int, strategy: str) -> bool:
    """Verify MSS clamping rules are active"""
    print(f"\n  [MSS] Verifying MSS Clamping rules...")
    
    check_cmds = [
        "iptables -t mangle -L OUTPUT -n -v 2>/dev/null | grep -i tcpmss",
        "iptables -t mangle -L FORWARD -n -v 2>/dev/null | grep -i tcpmss",
    ]
    
    rules_found = False
    for cmd in check_cmds:
        output = send_command(port, cmd, 3)
        if "TCPMSS" in output:
            rules_found = True
            for line in output.split('\n'):
                if 'TCPMSS' in line:
                    print(f"       {line.strip()}")
    
    if rules_found:
        print(f"  [ OK ] MSS Clamping rules active")
        return True
    else:
        print(f"  [WARN] No MSS Clamping rules found")
        return False

def check_server_status(port: int) -> tuple:
    """Check if HTTP server is already running"""
    print("  [INFO] Checking current HTTP server status...")
    
    check_cmd = "ps aux | grep -E 'python3?.*http.server' | grep -v grep"
    output = send_command(port, check_cmd, 3, capture_output=True)
    
    if "http.server" in output:
        pid_match = re.search(r'^(\S+)\s+(\d+)', output, re.MULTILINE)
        if pid_match:
            pid = pid_match.group(2)
            print(f"  [WARN] HTTP server already running (PID: {pid})")
            return True, pid
        else:
            print("  [WARN] HTTP server already running")
            return True, None
    
    print("  [ OK ] No existing HTTP server found")
    return False, None

def stop_existing_server(port: int, pid: str = None):
    """Stop existing HTTP server gracefully"""
    if pid:
        print(f"  [STOP] Stopping existing HTTP server (PID: {pid})...")
        send_command(port, f"kill {pid}", 2, capture_output=False)
    else:
        print(f"  [STOP] Stopping existing HTTP server...")
        send_command(port, "pkill -f 'python3 -m http.server'", 2, capture_output=False)
        send_command(port, "pkill -f 'python -m http.server'", 2, capture_output=False)
    
    time.sleep(2)
    
    verify = send_command(port, "ps aux | grep -E 'python3?.*http.server' | grep -v grep", 2)
    if "http.server" in verify:
        print("  [WARN] Server still running, forcing kill...")
        send_command(port, "killall -9 python3 2>/dev/null || true", 2, capture_output=False)
        time.sleep(1)
    else:
        print("  [ OK ] Server stopped successfully")

def create_test_files(port: int) -> bool:
    """Create test files for HTTP server"""
    print("  [FILE] Creating test files...")
    
    commands = [
        "mkdir -p /tmp/http_test_files",
        "cd /tmp/http_test_files",
        "rm -f *.bin 2>/dev/null || true",
        "dd if=/dev/urandom of=1KB.bin bs=1024 count=1 2>/dev/null",
        "dd if=/dev/urandom of=10KB.bin bs=1024 count=10 2>/dev/null",
        "dd if=/dev/urandom of=100KB.bin bs=1024 count=100 2>/dev/null",
        "dd if=/dev/urandom of=200KB.bin bs=1024 count=200 2>/dev/null",
        "dd if=/dev/urandom of=300KB.bin bs=1024 count=300 2>/dev/null",
        "dd if=/dev/urandom of=400KB.bin bs=1024 count=400 2>/dev/null",
        "dd if=/dev/urandom of=500KB.bin bs=1024 count=500 2>/dev/null",
        "dd if=/dev/urandom of=600KB.bin bs=1024 count=600 2>/dev/null",
        "dd if=/dev/urandom of=700KB.bin bs=1024 count=700 2>/dev/null",
        "dd if=/dev/urandom of=800KB.bin bs=1024 count=800 2>/dev/null",
        "dd if=/dev/urandom of=900KB.bin bs=1024 count=900 2>/dev/null",
        "dd if=/dev/urandom of=1MB.bin bs=1048576 count=1 2>/dev/null",
        "dd if=/dev/urandom of=10MB.bin bs=1048576 count=10 2>/dev/null",
        "ls -lh *.bin | head -15",
    ]
    
    output = send_commands(port, commands, 15)
    
    if "1KB.bin" in output and "1MB.bin" in output:
        print("  [ OK ] Test files created successfully")
        return True
    else:
        print("  [WARN] Some test files may not have been created")
        return False

def start_http_server(port: int, http_port: int = 8080, bind_address: str = "0.0.0.0") -> bool:
    """Start HTTP server in background"""
    print(f"  [START] Starting HTTP server on {bind_address}:{http_port}...")
    
    commands = [
        f"cd /tmp/http_test_files",
        f"nohup python3 -m http.server {http_port} --bind {bind_address} > /tmp/http_server.log 2>&1 &",
        "sleep 2",
        "ps aux | grep -E 'python3?.*http.server' | grep -v grep"
    ]
    
    output = send_commands(port, commands, 5)
    
    if "http.server" in output and str(http_port) in output:
        print(f"  [ OK ] HTTP server started successfully on port {http_port}")
        return True
    else:
        print(f"  [FAIL] Failed to start HTTP server")
        return False

def verify_server(port: int, http_target: str, http_port: int, use_ipv6: bool = False) -> bool:
    """Verify HTTP server is accessible"""
    print(f"  [VERIFY] Checking HTTP server accessibility...")
    print(f"    Target: http://{http_target}:{http_port}/1KB.bin")
    
    if use_ipv6:
        curl_cmd = f"curl -6 -s -o /dev/null -w '%{{http_code}}' http://[{http_target}]:{http_port}/1KB.bin --max-time 5"
    else:
        curl_cmd = f"curl -s -o /dev/null -w '%{{http_code}}' http://{http_target}:{http_port}/1KB.bin --max-time 5"
    
    output = send_command(port, curl_cmd, 8)
    
    if "200" in output:
        print(f"  [ OK ] HTTP server verified (HTTP 200 OK)")
        return True
    else:
        print(f"  [WARN] HTTP server verification returned: {output[:50]}")
        return False

def setup_http_server(strategy: str, config: Dict, force_restart: bool = False, apply_mss: bool = True) -> bool:
    """Setup HTTP server on Linux-Server for a specific migration strategy"""
    print(f"\n{'='*60}")
    print(f"[HTTP] Setting up HTTP Server for {strategy.upper()}")
    print(f"       {config['linux_server']['description']}")
    print(f"       HTTP Target: {config['http_target']}:{config['http_port']}")
    print(f"       IPv6 Mode: {config['use_ipv6_curl']}")
    print(f"       MSS Clamping: {config['mss_clamp']} bytes")
    print(f"       Data Directory: {PROJECT_DATA_DIR}")
    print(f"{'='*60}")
    
    server_port = config['linux_server']['port']
    http_port = config.get('http_port', 8080)
    http_target = config.get('http_target', '203.0.113.1')
    use_ipv6 = config.get('use_ipv6_curl', False)
    mss_value = config.get('mss_clamp', 1460)
    
    # Apply MSS Clamping
    if apply_mss:
        apply_mss_clamping(server_port, mss_value, strategy)
        verify_mss_clamping(server_port, strategy)
    
    # Check existing server status
    is_running, pid = check_server_status(server_port)
    
    if is_running and not force_restart:
        print("  [INFO] HTTP server already running, using existing server")
        
        if verify_server(server_port, http_target, http_port, use_ipv6):
            print("  [ OK ] Existing HTTP server is working correctly")
            
            # Save setup config
            save_setup_config(strategy, {
                "strategy": strategy,
                "status": "using_existing",
                "mss_clamping": mss_value,
                "http_target": http_target,
                "http_port": http_port,
                "use_ipv6": use_ipv6,
                "data_directory": PROJECT_DATA_DIR
            })
            
            return True
        else:
            print("  [WARN] Existing server not responding, restarting...")
            force_restart = True
    
    # Stop existing server if needed
    if is_running and force_restart:
        stop_existing_server(server_port, pid)
        time.sleep(2)
    
    # Create test files
    if not create_test_files(server_port):
        print("  [WARN] Warning: Test file creation had issues")
    
    # Start HTTP server
    bind_address = "0.0.0.0"
    if not start_http_server(server_port, http_port, bind_address):
        print("  [FAIL] Failed to start HTTP server")
        return False
    
    time.sleep(3)
    
    # Verify server
    if verify_server(server_port, http_target, http_port, use_ipv6):
        print(f"\n  [ OK ] HTTP Server Setup Complete for {strategy.upper()}")
        
        # Show IP information
        ip_output = send_command(server_port, "ip addr show eth0 | grep inet | head -2", 3)
        print(f"\n  [INFO] Server IP Information:")
        for line in ip_output.split('\n'):
            if 'inet ' in line or 'inet6' in line:
                print(f"     {line.strip()}")
        
        # Show test URLs
        print(f"\n  [INFO] HTTP Test URLs:")
        if use_ipv6:
            print(f"     curl -6 http://[{http_target}]:{http_port}/1KB.bin")
        else:
            print(f"     curl http://{http_target}:{http_port}/1KB.bin")
        
        print(f"\n  [INFO] Data saved to: {PROJECT_DATA_DIR}")
        
        # Save setup config
        save_setup_config(strategy, {
            "strategy": strategy,
            "status": "setup_complete",
            "mss_clamping": mss_value,
            "http_target": http_target,
            "http_port": http_port,
            "use_ipv6": use_ipv6,
            "data_directory": PROJECT_DATA_DIR,
            "server_ip": http_target,
            "available_files": ["1KB", "10KB", "100KB", "200KB", "300KB", "400KB", 
                              "500KB", "600KB", "700KB", "800KB", "900KB", "1MB", "10MB"]
        })
        
        return True
    else:
        print("  [FAIL] HTTP server setup failed verification")
        return False

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Setup HTTP Server - Saves config to data directory")
    parser.add_argument("--strategy", "-s", choices=["dualstack", "dslite", "nat64"], 
                       help="Specific strategy to setup")
    parser.add_argument("--force", "-f", action="store_true",
                       help="Force restart even if server is running")
    parser.add_argument("--auto-detect", "-a", action="store_true",
                       help="Auto-detect which strategy is currently running")
    parser.add_argument("--no-mss", action="store_true",
                       help="Skip MSS clamping configuration")
    parser.add_argument("--mss-only", action="store_true",
                       help="Only apply MSS clamping without restarting server")
    
    args = parser.parse_args()
    
    print("="*80)
    print("[HTTP] HTTP Server Setup Tool")
    print(f"       Data Directory: {PROJECT_DATA_DIR}")
    print("="*80)
    
    # Ensure data directory exists
    ensure_data_dir()
    
    print("\n[MSS] TCP MSS Clamping Values:")
    for s, cfg in MIGRATION_CONFIGS.items():
        print(f"      {s.upper()}: {cfg['mss_clamp']} bytes")
    
    strategy = None
    
    if args.strategy:
        strategy = args.strategy
    elif args.auto_detect:
        print("\n[INFO] Auto-detecting active strategy...")
        for test_strategy, config in MIGRATION_CONFIGS.items():
            server_port = config['linux_server']['port']
            try:
                with socket.create_connection((GNS3_HOST, server_port), timeout=2):
                    print(f"  [ OK ] Detected {test_strategy.upper()} (port {server_port} is open)")
                    strategy = test_strategy
                    break
            except:
                continue
        
        if not strategy:
            print("  [FAIL] Could not auto-detect active strategy")
            return
    else:
        strategy = "dualstack"
        print(f"\n[INFO] Using default strategy: {strategy.upper()}")
    
    if strategy not in MIGRATION_CONFIGS:
        print(f"[FAIL] Unknown strategy: {strategy}")
        return
    
    if args.mss_only:
        config = MIGRATION_CONFIGS[strategy]
        server_port = config['linux_server']['port']
        mss_value = config['mss_clamp']
        apply_mss_clamping(server_port, mss_value, strategy)
        verify_mss_clamping(server_port, strategy)
        return
    
    success = setup_http_server(
        strategy, 
        MIGRATION_CONFIGS[strategy], 
        force_restart=args.force,
        apply_mss=not args.no_mss
    )
    
    if success:
        print("\n" + "="*80)
        print("[DONE] HTTP SERVER SETUP COMPLETE!")
        print(f"       Strategy: {strategy.upper()}")
        print(f"       Data saved to: {PROJECT_DATA_DIR}")
        print("="*80)
    else:
        print("\n" + "="*80)
        print("[FAIL] HTTP SERVER SETUP FAILED!")
        print("="*80)

if __name__ == "__main__":
    main()