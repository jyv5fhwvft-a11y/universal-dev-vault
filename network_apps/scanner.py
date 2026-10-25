
import socket
import threading
import argparse
import sys
from queue import Queue

# Thread-safe lock for printing console outputs cleanly
print_lock = threading.Lock()

def check_target_alive(host):
    """Verifies if the target host is reachable before launching the scan."""
    try:
        socket.gethostbyname(host)
        return True
    except socket.gaierror:
        return False

def scan_port(target, port, timeout, banner_grab, results):
    """Attempts to connect to a specific port and optionally grab the service banner."""
    try:
        # Create a standard TCP IPv4 streaming socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        
        # Attempt three-way handshake connection
        result = sock.connect_ex((target, port))
        
        if result == 0:
            banner = "Unknown Service"
            if banner_grab:
                try:
                    # Send a generic request payload to prompt a banner response
                    sock.sendall(b"HEAD / HTTP/1.1\r\n\r\n")
                    banner_raw = sock.recv(1024).decode('utf-8', errors='ignore').strip()
                    if banner_raw:
                        banner = banner_raw.split('\n')[0]
                except Exception:
                    pass
            
            with print_lock:
                print(f"  🟢 Port {port:<5} [OPEN]  -->  {banner}")
                results.append((port, "OPEN", banner))
                
        sock.close()
    except Exception:
        pass

def worker_thread(queue, target, timeout, banner_grab, results):
    """Worker loop that pulls target ports continuously from the shared execution queue."""
    while not queue.empty():
        port = queue.get()
        scan_port(target, port, timeout, banner_grab, results)
        queue.task_done()

def parse_port_range(port_str):
    """Parses standard comma-separated ranges or hyphenated port spans safely."""
    ports = []
    try:
        for part in port_str.split(','):
            if '-' in part:
                start, end = map(int, part.split('-'))
                if start < 1 or end > 65535 or start > end:
                    raise argparse.ArgumentTypeError(f"Invalid range bounds: {part}")
                ports.extend(range(start, end + 1))
            else:
                p = int(part)
                if p < 1 or p > 65535:
                    raise argparse.ArgumentTypeError(f"Port out of safe system limits: {p}")
                ports.append(p)
        return list(set(ports))
    except ValueError:
        raise argparse.ArgumentTypeError("Port specs must be integers or hyphenated ranges.")

def execute_scan(target, ports, num_threads, timeout, banner_grab):
    """Coordinates thread orchestration and starts the parallelized network engine."""
    with print_lock:
        print(f"\n📡 Initiating Multi-Threaded Scan Engine against: {target}")
        print(f"🚀 Threads Allocated: {num_threads} | Connection Timeout: {timeout}s\n" + "-"*60)
    
    if not check_target_alive(target):
        with print_lock:
            print(f"🚨 Connection Error: Host '{target}' is down or unresponsive.")
        return

    port_queue = Queue()
    results = []
    
    # Load all unique ports into the sync queue container
    for port in sorted(ports):
        port_queue.put(port)
        
    threads = []
    # Dynamic guard rails for thread-pool allocation
    active_workers = min(num_threads, len(ports))
    
    for _ in range(active_workers):
        t = threading.Thread(target=worker_thread, args=(port_queue, target, timeout, banner_grab, results))
        t.daemon = True
        t.start()
        threads.append(t)
        
    # Block parent thread context until queue is completely empty
    port_queue.join()
    
    with print_lock:
        print("-"*60 + f"\n⚙️ Scan finished. Identified {len(results)} open listening sockets.\n")

def main():
    parser = argparse.ArgumentParser(description="Multi-Threaded TCP Port Scanner Utility")
    parser.add_argument("-t", "--target", default="127.0.0.1", help="Target IP address or domain name resolution string.")
    parser.add_argument("-p", "--ports", default="1-1024", help="Target port bounds (e.g., '80,443' or '1-1024').")
    parser.add_argument("-w", "--workers", type=int, default=50, help="Maximum thread pool allocation limit.")
    parser.add_argument("--timeout", type=float, default=1.5, help="Socket socket timeout limit configuration (seconds).")
    parser.add_argument("-b", "--banner", action="store_true", help="Enable socket application banner grabbing signatures.")
    
    args = parser.parse_args()
    
    if args.workers < 1:
        parser.error("Thread pool size must be greater than or equal to 1.")
    if args.timeout <= 0.0:
        parser.error("Socket timeout must be a positive non-zero floating point value.")
        
    try:
        resolved_ports = parse_port_range(args.ports)
    except argparse.ArgumentTypeError as parse_err:
        parser.error(str(parse_err))
        
    execute_scan(
        target=args.target,
        ports=resolved_ports,
        num_threads=args.workers,
        timeout=args.timeout,
        banner_grab=args.banner,
    )

if __name__ == "__main__":
    main()
