<ApplicationEngine>
import os
import sys
import socket
import struct
import time
import select

def calculate_checksum(source_string):
    """Calculates the mandatory 16-bit one's complement internet checksum for the raw ICMP header."""
    count_to = (len(source_string) // 2) * 2
    count = 0
    sum_val = 0
    
    while count < count_to:
        this_val = source_string[count + 1] * 256 + source_string[count]
        sum_val += this_val
        sum_val = sum_val & 0xffffffff
        count += 2
        
    if count_to < len(source_string):
        sum_val += source_string[len(source_string) - 1]
        sum_val = sum_val & 0xffffffff
        
    sum_val = (sum_val >> 16) + (sum_val & 0xffff)
    sum_val += (sum_val >> 16)
    answer = ~sum_val
    answer = answer & 0xffff
    answer = answer >> 8 | (answer << 8 & 0xff00)
    return answer

def create_stealth_packet(packet_id):
    """Constructs a raw stealth ICMP Echo Request header with a zeroed checksum field."""
    # ICMP Type: 8 (Echo Request), Code: 0, Checksum: 0 (Placeholder), ID: packet_id, Sequence: 1
    header = struct.pack("bbHHh", 8, 0, 0, packet_id, 1)
    
    # Minimal stealth payload chunk (32-bytes of anonymous filler data)
    payload = struct.pack("d", time.time()) + b"QA_STEALTH_NET_ENGINE_SCAN_VOIDS"
    
    # Calculate checksum across combined header and payload
    my_checksum = calculate_checksum(header + payload)
    
    # Reconstruct the finalized packet header with the authentic checksum token injected
    header = struct.pack("bbHHh", 8, 0, socket.htons(my_checksum), packet_id, 1)
    return header + payload

def send_stealth_ping(target_ip, timeout_sec=2.0):
    """Dispatches a single stealth ICMP request via raw sockets and waits for the echo reply."""
    try:
        # Request access to low-level raw internet network protocols
        raw_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    except PermissionError:
        print("🚨 Execution Access Error: Raw sockets require root level administrative credentials.")
        print("💡 Solution: Re-run this network application engine using: sudo python3 stealth_ping.py\n")
        sys.exit(1)
        
    # Bind process ID to packet fingerprint to parse matching reply streams safely
    packet_id = os.getpid() & 0xFFFF
    packet = create_stealth_packet(packet_id)
    
    try:
        # Route packet string matrix to destination target node
        send_time = time.time()
        raw_socket.sendto(packet, (target_ip, 1))
        
        # Monitor the incoming raw socket descriptor channel for updates before timeout ticks out
        ready = select.select([raw_socket], [], [], timeout_sec)
        
        if ready[0] == []:  # Socket queue remained completely dry during timeout window
            return None, "TIMEOUT"
            
        recv_time = time.time()
        recv_packet, addr = raw_socket.recvfrom(1024)
        
        # Parse standard 20-byte IPv4 Layer Header to isolate the interior ICMP matrix
        icmp_header = recv_packet[20:28]
        icmp_type, code, checksum, reply_id, sequence = struct.unpack("bbHHh", icmp_header)
        
        # Verify that the returned packet signature matches our active session process ID footprint
        if icmp_type == 0 and reply_id == packet_id:
            rtt_ms = (recv_time - send_time) * 1000
            return rtt_ms, addr[0]
            
        return None, "MISMATCH_PACKET"
        
    except Exception as err:
        return None, f"ERROR: {str(err)}"
    finally:
        raw_socket.close()

def run_stealth_monitor(target_host, loops=4):
    """Orchestrates loop context for the stealth network auditing sequence."""
    try:
        target_ip = socket.gethostbyname(target_host)
    except socket.gaierror:
        print(f"🚨 Host Resolution Fault: Unable to resolve string address domain: {target_host}")
        return

    print(f"\n🕵️ Initiating Stealth ICMP Audit Sequence against target node: {target_host} [{target_ip}]")
    print(f"🔒 Protocol: RAW_ICMP_ECHO_PUMP | Packet Size: 64 Bytes | Guard Timeout: 2.0s\n" + "-"*70)

    success_count = 0
    total_rtt = 0.0

    for i in range(loops):
        time.sleep(1.0)  # Gentle 1Hz probe pacing interval to maintain stealth integrity
        rtt, status = send_stealth_ping(target_ip)
        
        if rtt is not None:
            success_count += 1
            total_rtt += rtt
            print(f"  🟢 [PROBE #{i+1:02d}] Reply from {status}: connection=ACTIVE rtt={rtt:.2f}ms")
        else:
            print(f"  ❌ [PROBE #{i+1:02d}] Silent dropped packet node payload vector [Reason: {status}]")

    print("-"*70)
    print(f"⚙️ Stealth scan loop finalized.")
    if success_count > 0:
        avg_rtt = total_rtt / success_count
        print(f"📊 Integrity Metrics: {success_count}/{loops} probes matched safely | Average Node Delay: {avg_rtt:.2f}ms\n")
    else:
        print("🚨 Network Alert State: 100% packet loss detected. Target node is completely air-gapped or blocking ICMP.\n")

if __name__ == "__main__":
    # Target path defaults to standard loopback interface for local sandbox verification testing
    target = "127.0.0.1"
    if len(sys.argv) > 1:
        target = sys.argv[1]
    run_stealth_monitor(target)
</ApplicationEngine>
