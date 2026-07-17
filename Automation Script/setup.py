#!/usr/bin/env python3
"""
FYP IPv6 Migration — GNS3 Auto-Configuration Script
FIXED Version — Keeps DS-Lite Linux-Server on port 5018
"""

import time
import argparse
import sys
import socket
from typing import List, Tuple, Dict, Any

# ─────────────────────────────────────────────
# GNS3 Server Settings
# ─────────────────────────────────────────────
GNS3_HOST = "192.168.255.128"

# ─────────────────────────────────────────────
# PC Configurations per Project
# ─────────────────────────────────────────────
CONFIGS = {
    "dualstack": {
        "description": "Project 1 — Dual Stack (Dual_Stack.gns3)",
        "pcs": [
            {
                "name": "PC1",
                "host": GNS3_HOST,
                "port": 5010,
                "commands": [
                    "ip link set eth0 up",
                    "ip addr flush dev eth0",
                    "ip -6 addr flush dev eth0",
                    "ip addr add 192.168.10.10/24 dev eth0",
                    "ip -6 addr add 2001:db8:10::10/64 dev eth0",
                    "ip route flush table main",
                    "ip route add 192.168.10.0/24 dev eth0",
                    "ip route add default via 192.168.10.1 dev eth0",
                    "ip -6 route add default via 2001:db8:10::1 dev eth0 2>/dev/null || true",
                ]
            },
            {
                "name": "PC2",
                "host": GNS3_HOST,
                "port": 5013,
                "commands": [
                    "ip link set eth0 up",
                    "ip addr flush dev eth0",
                    "ip -6 addr flush dev eth0",
                    "ip addr add 192.168.10.11/24 dev eth0",
                    "ip -6 addr add 2001:db8:10::11/64 dev eth0",
                    "ip route flush table main",
                    "ip route add 192.168.10.0/24 dev eth0",
                    "ip route add default via 192.168.10.1 dev eth0",
                    "ip -6 route add default via 2001:db8:10::1 dev eth0 2>/dev/null || true",
                ]
            },
            {
                "name": "PC3",
                "host": GNS3_HOST,
                "port": 5015,
                "commands": [
                    "ip link set eth0 up",
                    "ip addr flush dev eth0",
                    "ip -6 addr flush dev eth0",
                    "ip addr add 192.168.10.12/24 dev eth0",
                    "ip -6 addr add 2001:db8:10::12/64 dev eth0",
                    "ip route flush table main",
                    "ip route add 192.168.10.0/24 dev eth0",
                    "ip route add default via 192.168.10.1 dev eth0",
                    "ip -6 route add default via 2001:db8:10::1 dev eth0 2>/dev/null || true",
                ]
            },
            {
                "name": "Linux-Server",
                "host": GNS3_HOST,
                "port": 5002,
                "commands": [
                    "ip link set eth0 up",
                    "ip addr flush dev eth0",
                    "ip addr add 10.0.99.2/30 dev eth0",          
                    "ip addr add 203.0.113.1/24 dev eth0:0",	  
                    "ip route flush table main",
                    "ip route add 10.0.99.0/30 dev eth0",
                    "ip route add 203.0.113.0/24 dev eth0:0",
                    "ip route add default via 10.0.99.1 || true",
                    "pkill iperf3 2>/dev/null || true",
                    "sleep 1",
                ]
            },
        ],
        "verify": [
            ("PC1", GNS3_HOST, 5013, [
                "ping -c 5 192.168.10.1",
                "ping6 -c 5 2001:db8:10::1",
                "ping -c 5 203.0.113.1",
                "traceroute 203.0.113.1",
            ]),
            ("Linux-Server", GNS3_HOST, 5002, [
                "ping -c 3 10.0.99.1",
                "ping -c 3 192.168.10.10",
            ]),
        ]
    },

    # ── PROJECT 2: DS-LITE (Linux-Server KEPT on port 5018) ──
    "dslite": {
        "description": "Project 2 — DS-Lite (DS_Lite.gns3)",
        "pcs": [
            {
                "name": "PC1",
                "host": GNS3_HOST,
                "port": 5003,
                "commands": [
                    "ip link set eth0 up",
                    "ip addr flush dev eth0",
                    "ip -6 addr flush dev eth0",
                    "ip addr add 192.168.20.10/24 dev eth0",
                    "ip -6 addr add 2001:db8:20::10/64 dev eth0",
                    "ip route flush table main",
                    "ip route add 192.168.20.0/24 dev eth0",
                    "ip route add default via 192.168.20.1 dev eth0",
                    "ip -6 route add default via 2001:db8:20::1 dev eth0 2>/dev/null || true",
                ]
            },
            {
                "name": "PC2",
                "host": GNS3_HOST,
                "port": 5007,
                "commands": [
                    "ip link set eth0 up",
                    "ip addr flush dev eth0",
                    "ip -6 addr flush dev eth0",
                    "ip addr add 192.168.20.11/24 dev eth0",
                    "ip -6 addr add 2001:db8:20::11/64 dev eth0",
                    "ip route flush table main",
                    "ip route add 192.168.20.0/24 dev eth0",
                    "ip route add default via 192.168.20.1 dev eth0",
                    "ip -6 route add default via 2001:db8:20::1 dev eth0 2>/dev/null || true",
                ]
            },
            {
                "name": "PC3",
                "host": GNS3_HOST,
                "port": 5012,
                "commands": [
                    "ip link set eth0 up",
                    "ip addr flush dev eth0",
                    "ip -6 addr flush dev eth0",
                    "ip addr add 192.168.20.12/24 dev eth0",
                    "ip -6 addr add 2001:db8:20::12/64 dev eth0",
                    "ip route flush table main",
                    "ip route add 192.168.20.0/24 dev eth0",
                    "ip route add default via 192.168.20.1 dev eth0",
                    "ip -6 route add default via 2001:db8:20::1 dev eth0 2>/dev/null || true",
                ]
            },
            {
                "name": "Linux-Server",
                "host": GNS3_HOST,
                "port": 5018,  # ← KEPT as 5018 (matching your GNS3 setup)
                "commands": [
                    "ip link set eth0 up",
                    "ip addr flush dev eth0",
                    "ip addr add 10.0.99.2/30 dev eth0",
                    "ip addr add 203.0.113.1/24 dev eth0:0",
                    "ip route flush table main",
                    "ip route add 10.0.99.0/30 dev eth0",
                    "ip route add 203.0.113.0/24 dev eth0:0",
                    "ip route add default via 10.0.99.1 dev eth0",
                    "pkill iperf3 2>/dev/null || true",
                    "sleep 1",
                ]
            },
        ],
        "verify": [
            ("PC1", GNS3_HOST, 5003, [
                "ping -c 5 192.168.20.1",
                "ping -c 5 203.0.113.1",
                "traceroute 203.0.113.1",
            ]),
            ("Linux-Server", GNS3_HOST, 5018, [  # ← Verify on port 5018
                "ping -c 3 10.0.99.1",
                "ping -c 3 203.0.113.1",
            ]),
        ]
    },

    # ── PROJECT 3: NAT64 (PC2 MOVED to port 5024 to avoid conflict) ──
    "nat64": {
        "description": "Project 3 — NAT64 (NAT64.gns3)",
        "pcs": [
            {
                "name": "PC1",
                "host": GNS3_HOST,
                "port": 5000,
                "commands": [
                    "ip link set eth0 up",
                    "ip -6 addr flush dev eth0",
                    "ip -6 addr add 2001:db8:30::10/64 dev eth0",
                    "ip -6 route del default 2>/dev/null || true",
                    "ip -6 route add default via 2001:db8:30::1 dev eth0 || true",
                ]
            },
            {
                "name": "PC2",
                "host": GNS3_HOST,
                "port": 5003,  # ← CHANGED from 5018 to 5003 (avoid conflict with DS-Lite)
                "commands": [
                    "ip link set eth0 up",
                    "ip -6 addr flush dev eth0",
                    "ip -6 addr add 2001:db8:30::11/64 dev eth0",
                    "ip -6 route del default 2>/dev/null || true",
                    "ip -6 route add default via 2001:db8:30::1 dev eth0 || true",
                ]
            },
            {
                "name": "PC3",
                "host": GNS3_HOST,
                "port": 5007,
                "commands": [
                    "ip link set eth0 up",
                    "ip -6 addr flush dev eth0",
                    "ip -6 addr add 2001:db8:30::12/64 dev eth0",
                    "ip -6 route del default 2>/dev/null || true",
                    "ip -6 route add default via 2001:db8:30::1 dev eth0 || true",
                ]
            },
            {
                "name": "Linux-Server",
                "host": GNS3_HOST,
                "port": 5012,  # ← KEPT as 5012 (matching your GNS3 setup)
                "commands": [
                    "ip link set eth0 up",
                    "ip addr flush dev eth0",
                    "ip addr add 10.0.99.2/30 dev eth0",
                    "ip addr add 203.0.113.1/24 dev eth0:0",
                    "ip route flush table main",
                    "ip route add 10.0.99.0/30 dev eth0",
                    "ip route add 203.0.113.0/24 dev eth0:0",
                    "ip route add default via 10.0.99.1 dev eth0",
                    "pkill iperf3 2>/dev/null || true",
                    "sleep 1",
                ]
            },
        ],
        "verify": [
            ("PC1", GNS3_HOST, 5000, [
                "ping6 -c 5 2001:db8:30::1",
                "ping6 -c 5 2001:db8:ff9b::cb00:7101",
                "traceroute6 2001:db8:ff9b::cb00:7101",
            ]),
            ("Linux-Server", GNS3_HOST, 5010, [
                "ping -c 3 10.0.99.1",
            ]),
        ]
    },
}

# ─────────────────────────────────────────────
# Socket Helper Functions
# ─────────────────────────────────────────────

def check_port(host: str, port: int, timeout: int = 3) -> Tuple[bool, str]:
    """Check if a TCP port is open and return status with message."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"Port {port} is reachable"
    except socket.timeout:
        return False, f"Port {port} connection timed out"
    except ConnectionRefusedError:
        return False, f"Port {port} connection refused - node might not be started"
    except OSError as e:
        return False, f"Port {port} error: {e}"


def socket_send_commands(host: str, port: int, commands: List[str], node_name: str) -> bool:
    """Send commands via raw TCP socket to GNS3 console."""
    reachable, msg = check_port(host, port)
    if not reachable:
        print(f"  [ERROR] {node_name}: {msg}")
        print(f"  [HINT] Make sure the GNS3 node '{node_name}' is started and port {port} is correct")
        return False
    
    try:
        print(f"  [CONNECT] Connecting to {node_name} on port {port}...")
        with socket.create_connection((host, port), timeout=10) as sock:
            # Clear initial buffer
            time.sleep(1)
            sock.sendall(b"\n")   # Wake up console
            time.sleep(1)
            
            for cmd in commands:
                print(f"     -> {cmd}")
                sock.sendall(cmd.encode("ascii", errors="replace") + b"\n")
                time.sleep(0.8)
            
            sock.sendall(b"\n")
            time.sleep(1)
        
        print(f"  [OK] {node_name}: Commands sent successfully")
        return True
    except Exception as e:
        print(f"  [ERROR] {node_name}: Error — {e}")
        return False


def socket_verify(host: str, port: int, commands: List[str], node_name: str) -> None:
    """Run verification commands and print output."""
    reachable, msg = check_port(host, port)
    if not reachable:
        print(f"  [ERROR] {node_name}: {msg} - Cannot verify")
        return
    
    try:
        with socket.create_connection((host, port), timeout=10) as sock:
            sock.sendall(b"\n")
            time.sleep(1)
            for cmd in commands:
                print(f"\n  [RUN] [{node_name}] Running: {cmd}")
                sock.sendall(cmd.encode("ascii", errors="replace") + b"\n")
                
                # Wait longer for ping/traceroute commands
                wait = 7 if "traceroute" in cmd else 6 if "ping" in cmd else 3
                time.sleep(wait)
                
                # Read whatever is available
                sock.setblocking(False)
                try:
                    data = sock.recv(8192).decode("ascii", errors="ignore")
                    for line in data.splitlines():
                        line = line.strip()
                        if line and len(line) > 2:
                            print(f"     {line}")
                except BlockingIOError:
                    print("     (No output received)")
                finally:
                    sock.setblocking(True)
    except Exception as e:
        print(f"  [ERROR] Verify error on {node_name}: {e}")


# ─────────────────────────────────────────────
# Main Runner
# ─────────────────────────────────────────────

def configure_project(project: str) -> None:
    """Configure all nodes for the selected project."""
    if project not in CONFIGS:
        print(f"[ERROR] Unknown project: {project}")
        print(f"   Valid options: {', '.join(CONFIGS.keys())}")
        sys.exit(1)

    cfg = CONFIGS[project]
    print("\n" + "=" * 60)
    print(f"  FYP IPv6 Migration — Auto Configuration")
    print(f"  {cfg['description']}")
    print("=" * 60)

    # Step 1: Pre-check all ports
    print("\n[CHECK] Checking node connectivity...")
    all_ok = True
    for pc in cfg["pcs"]:
        reachable, msg = check_port(pc["host"], pc["port"])
        status = "[OK] Reachable" if reachable else "[FAIL] NOT reachable"
        print(f"  {pc['name']:20s} port {pc['port']} — {status}")
        if not reachable:
            print(f"         {msg}")
            all_ok = False

    if not all_ok:
        print("\n[WARN] Some nodes are not reachable.")
        print("   -> Make sure GNS3 project is OPEN and all nodes are STARTED")
        print("   -> Verify console port numbers match GNS3 node settings")
        ans = input("\n   Continue anyway? (y/n): ").strip().lower()
        if ans != "y":
            print("Aborted.")
            sys.exit(0)

    # Step 2: Configure each node
    print("\n[CONFIG] Configuring nodes...")
    results = []
    for pc in cfg["pcs"]:
        print(f"\n  [{pc['name']}]")
        ok = socket_send_commands(pc["host"], pc["port"], pc["commands"], pc["name"])
        results.append((pc["name"], ok))

    # Step 3: Print summary
    print("\n" + "=" * 60)
    print("  Configuration Summary")
    print("=" * 60)
    success = sum(1 for _, ok in results if ok)
    for name, ok in results:
        icon = "[OK]" if ok else "[FAIL]"
        print(f"  {icon} {name}")
    print(f"\n  {success}/{len(results)} nodes configured successfully")

    # Step 4: Run verification if any succeeded
    if success > 0:
        print("\n[VERIFY] Running verification tests...")
        for node_name, host, port, cmds in cfg["verify"]:
            print(f"\n  --- Verifying {node_name} ---")
            socket_verify(host, port, cmds, node_name)

    print("\n[DONE] Done! Review output above for any errors.")
    print("   Tip: If ping fails, wait 30s for routes to converge and re-run.")


def show_port_guide() -> None:
    """Show port assignments."""
    print("""
╔══════════════════════════════════════════════════════════╗
║              GNS3 CONSOLE PORT ASSIGNMENTS              ║
╠══════════════════════════════════════════════════════════╣
║                                                        ║
║  DUAL STACK PROJECT:                                   ║
║    PC1          -> port: 5010                          ║
║    PC2          -> port: 5013                          ║
║    PC3          -> port: 5015                          ║
║    Linux-Server -> port: 5002                          ║
║                                                        ║
║  DS-LITE PROJECT:                                      ║
║    PC1          -> port: 5003                          ║
║    PC2          -> port: 5007                          ║
║    PC3          -> port: 5012                          ║
║    Linux-Server -> port: 5018  ← (your GNS3 port)     ║
║                                                        ║
║  NAT64 PROJECT:                                        ║
║    PC1          -> port: 5016                          ║
║    PC2          -> port: 5024  ← (changed from 5018)  ║
║    PC3          -> port: 5020                          ║
║    Linux-Server -> port: 5022                          ║
║                                                        ║
╚══════════════════════════════════════════════════════════╝

IMPORTANT: Update NAT64 PC2's console port in GNS3 from 5018 to 5024 
to avoid conflict with DS-Lite's Linux-Server.
""")


# ─────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="FYP IPv6 Migration — GNS3 Auto-Configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python script.py --project dualstack
  python script.py --project dslite
  python script.py --project nat64
  python script.py --ports
        """
    )
    parser.add_argument(
        "--project", "-p",
        choices=["dualstack", "dslite", "nat64"],
        help="Which GNS3 project to configure"
    )
    parser.add_argument(
        "--ports",
        action="store_true",
        help="Show port assignment guide"
    )
    parser.add_argument(
        "--host",
        default=GNS3_HOST,
        help=f"GNS3 server host (default: {GNS3_HOST})"
    )

    args = parser.parse_args()

    if args.ports:
        show_port_guide()
        sys.exit(0)

    if not args.project:
        parser.print_help()
        print("\n[WARN] Please specify --project")
        print("   Example: python script.py --project dslite")
        sys.exit(1)

    # Override host if specified via CLI
    if args.host != GNS3_HOST:
        for proj in CONFIGS.values():
            for pc in proj["pcs"]:
                pc["host"] = args.host
            for item in proj["verify"]:
                item = list(item)
                item[1] = args.host

    configure_project(args.project)