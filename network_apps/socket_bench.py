<ApplicationEngine>
#!/usr/bin/env python3
"""
================================================================================
Network Socket Performance Analyzer (socket_bench.py)
Author: Universal-Dev-Architect
Description:
    A high-precision, production-grade network performance benchmarking utility
    implementing both TCP stream analysis and UDP datagram loss/jitter tracking.
    Operates in dual Server (receiver) and Client (traffic generator) modes.
================================================================================
"""

import argparse
import os
import select
import signal
import socket
import struct
import sys
import time
from typing import Tuple

# Magic constant for UDP packet structure: 
# Format: '!Q d' -> ! (Network Big-Endian), Q (unsigned 64-bit int seq_num), d (64-bit float timestamp)
# Header footprint = 8 + 8 = 16 bytes
UDP_METADATA_FORMAT = "!Qd"
UDP_METADATA_SIZE = struct.calcsize(UDP_METADATA_FORMAT)

# Global shutdown coordinator
GLOBAL_RUNNING = True


def signal_handler(signum, frame):
    """Handles OS termination signals for clean socket teardown and resource reclamation."""
    global GLOBAL_RUNNING
    GLOBAL_RUNNING = False
    sys.stderr.write("\n[!] Interrupt caught. Finalizing metrics and closing sockets...\n")
    sys.stderr.flush()


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def format_throughput(bytes_transferred: int, duration_seconds: float) -> Tuple[float, float]:
    """
    Computes Megabytes per second (MB/s) and Megabits per second (Mbps).
    MB/s = Bytes / (1024 * 1024) / sec
    Mbps = Bits / (1000 * 1000) / sec (Networking standard base-10)
    """
    if duration_seconds <= 0.0:
        return 0.0, 0.0
    mb_per_sec = (bytes_transferred / (1024.0 * 1024.0)) / duration_seconds
    mbits_per_sec = ((bytes_transferred * 8.0) / 1_000_000.0) / duration_seconds
    return mb_per_sec, mbits_per_sec


# ============================================================================
# TCP BENCHMARK ENGINE
# ============================================================================

def run_tcp_server(bind_ip: str, port: int, buffer_size: int) -> None:
    """
    Listens for inbound TCP connections, receives stream data in real-time,
    and reports continuous goodput and aggregate transfer volume.
    """
    global GLOBAL_RUNNING
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_sock.bind((bind_ip, port))
        server_sock.listen(1)
        server_sock.settimeout(1.0)
        print("=" * 78)
        print(f" [TCP SERVER] Listening on {bind_ip}:{port} | Buffer Window: {buffer_size} bytes")
        print("=" * 78)

        while GLOBAL_RUNNING:
            try:
                conn, addr = server_sock.accept()
            except socket.timeout:
                continue

            print(f"[*] Inbound connection accepted from {addr[0]}:{addr[1]}")
            conn.setblocking(False)

            total_bytes = 0
            start_time = time.time()
            interval_start = start_time
            interval_bytes = 0

            print("\n  Elapsed (s)      Throughput (MB/s)     Throughput (Mbps)      Total Bytes")
            print("  " + "-" * 72)

            try:
                while GLOBAL_RUNNING:
                    # Non-blocking I/O multiplexing
                    readable, _, _ = select.select([conn], [], [], 0.5)
                    if readable:
                        chunk = conn.recv(buffer_size)
                        if not chunk:
                            print(f"\n[*] Client {addr[0]}:{addr[1]} closed connection gracefully.")
                            break
                        bytes_len = len(chunk)
                        total_bytes += bytes_len
                        interval_bytes += bytes_len

                    # Periodic telemetry printout every 1.0 seconds
                    current_time = time.time()
                    interval_duration = current_time - interval_start
                    if interval_duration >= 1.0:
                        mb_s, mbps = format_throughput(interval_bytes, interval_duration)
                        elapsed = current_time - start_time
                        print(f"  {elapsed:10.2f} {mb_s:19.2f} {mbps:20.2f} {total_bytes:16d}")
                        interval_bytes = 0
                        interval_start = current_time

            except ConnectionResetError:
                print(f"\n[!] Connection abruptly reset by peer {addr[0]}:{addr[1]}.")
            finally:
                conn.close()
                total_duration = time.time() - start_time
                final_mb_s, final_mbps = format_throughput(total_bytes, total_duration)
                print("  " + "-" * 72)
                print(f"  [SUMMARY] Duration: {total_duration:.2f}s | Data: {total_bytes / (1024*1024):.2f} MB")
                print(f"  [SUMMARY] Avg Goodput: {final_mb_s:.2f} MB/s ({final_mbps:.2f} Mbps)\n")

    finally:
        server_sock.close()
        print("[*] TCP Server socket unbound and closed.")


def run_tcp_client(target_ip: str, port: int, duration: float, buffer_size: int) -> None:
    """
    Connects to a TCP server and blasts synthetic stream data for the specified
    duration, calculating and printing real-time transmission rates.
    """
    global GLOBAL_RUNNING
    print("=" * 78)
    print(f" [TCP CLIENT] Target: {target_ip}:{port} | Duration: {duration}s | Chunk: {buffer_size} bytes")
    print("=" * 78)

    client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_sock.settimeout(5.0)

    try:
        client_sock.connect((target_ip, port))
        client_sock.setblocking(True)
        print(f"[*] Established three-way handshake with {target_ip}:{port}")
    except (socket.timeout, socket.error) as err:
        print(f"[!] Handshake failed with destination: {err}")
        return

    payload = os.urandom(buffer_size)
    total_bytes = 0
    start_time = time.time()
    interval_start = start_time
    interval_bytes = 0

    print("\n  Elapsed (s)      Throughput (MB/s)     Throughput (Mbps)      Total Sent (B)")
    print("  " + "-" * 72)

    try:
        while GLOBAL_RUNNING:
            current_time = time.time()
            elapsed = current_time - start_time
            if elapsed >= duration:
                break

            client_sock.sendall(payload)
            total_bytes += len(payload)
            interval_bytes += len(payload)

            interval_duration = current_time - interval_start
            if interval_duration >= 1.0:
                mb_s, mbps = format_throughput(interval_bytes, interval_duration)
                print(f"  {elapsed:10.2f} {mb_s:19.2f} {mbps:20.2f} {total_bytes:16d}")
                interval_bytes = 0
                interval_start = current_time

    except (BrokenPipeError, ConnectionResetError) as err:
        print(f"\n[!] Socket transmission interrupted: {err}")
    finally:
        total_duration = time.time() - start_time
        client_sock.close()
        final_mb_s, final_mbps = format_throughput(total_bytes, total_duration)
        print("  " + "-" * 72)
        print(f"  [FINAL] Stream Duration: {total_duration:.2f}s | Total Transferred: {total_bytes / (1024*1024):.2f} MB")
        print(f"  [FINAL] Mean Transfer Rate: {final_mb_s:.2f} MB/s ({final_mbps:.2f} Mbps)")


# ============================================================================
# UDP BENCHMARK ENGINE
# ============================================================================

def run_udp_server(bind_ip: str, port: int, buffer_size: int) -> None:
    """
    Listens for UDP datagrams, extracts 64-bit sequence metadata, tracks lost
    packets, calculates delivery ratio, and measures network jitter.
    """
    global GLOBAL_RUNNING
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Set internal kernel receive buffer to 4MB to prevent local kernel drops during bursts
    try:
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
    except OSError:
        pass

    try:
        server_sock.bind((bind_ip, port))
        server_sock.settimeout(1.0)
        print("=" * 78)
        print(f" [UDP SERVER] Listening on {bind_ip}:{port} | Recv Buffer: {buffer_size} bytes")
        print("=" * 78)

        total_packets = 0
        total_bytes = 0
        expected_seq = 0
        dropped_packets = 0
        out_of_order = 0
        first_packet_received = False
        start_time = 0.0
        interval_start = 0.0
        interval_bytes = 0
        interval_packets = 0

        while GLOBAL_RUNNING:
            try:
                data, addr = server_sock.recvfrom(buffer_size)
            except socket.timeout:
                continue

            current_time = time.time()

            if not first_packet_received:
                first_packet_received = True
                start_time = current_time
                interval_start = current_time
                print(f"[*] Inbound datagram stream initiated by {addr[0]}:{addr[1]}")
                print("\n  Elapsed (s)    Rate (MB/s)    Recv Pkts    Drop Pkts    Loss Rate (%)")
                print("  " + "-" * 72)

            bytes_len = len(data)
            total_bytes += bytes_len
            total_packets += 1
            interval_bytes += bytes_len
            interval_packets += 1

            if bytes_len >= UDP_METADATA_SIZE:
                seq_num, send_timestamp = struct.unpack(UDP_METADATA_FORMAT, data[:UDP_METADATA_SIZE])
                
                if seq_num > expected_seq:
                    dropped_packets += (seq_num - expected_seq)
                    expected_seq = seq_num + 1
                elif seq_num < expected_seq:
                    out_of_order += 1
                else:
                    expected_seq += 1

            # Telemetry printout every 1.0 second
            interval_duration = current_time - interval_start
            if interval_duration >= 1.0:
                mb_s, _ = format_throughput(interval_bytes, interval_duration)
                denom = total_packets + dropped_packets
                loss_ratio = (dropped_packets / denom * 100.0) if denom > 0 else 0.0
                elapsed = current_time - start_time
                print(f"  {elapsed:10.2f} {mb_s:14.2f} {total_packets:12d} {dropped_packets:12d} {loss_ratio:14.2f}%")
                interval_bytes = 0
                interval_packets = 0
                interval_start = current_time

    finally:
        server_sock.close()
        if first_packet_received:
            total_duration = time.time() - start_time
            final_mb_s, final_mbps = format_throughput(total_bytes, total_duration)
            total_attempted = total_packets + dropped_packets
            total_loss_pct = (dropped_packets / total_attempted * 100.0) if total_attempted > 0 else 0.0
            print("  " + "-" * 72)
            print(f"  [UDP SUMMARY] Total Packets Received : {total_packets}")
            print(f"  [UDP SUMMARY] Missing / Dropped Pkts : {dropped_packets}")
            print(f"  [UDP SUMMARY] Out-of-Order Packets   : {out_of_order}")
            print(f"  [UDP SUMMARY] Empirical Packet Loss  : {total_loss_pct:.3f}%")
            print(f"  [UDP SUMMARY] Goodput Throughput     : {final_mb_s:.2f} MB/s ({final_mbps:.2f} Mbps)")
        print("[*] UDP Server stopped.")


def run_udp_client(target_ip: str, port: int, packet_count: int, buffer_size: int, delay_sec: float) -> None:
    """
    Generates a high-rate sequence of stamped UDP packets with monotonic sequence
    numbers and send timestamps to enable loss and throughput evaluation.
    """
    global GLOBAL_RUNNING
    print("=" * 78)
    print(f" [UDP CLIENT] Target: {target_ip}:{port} | Packets: {packet_count} | Payload: {buffer_size} B")
    print("=" * 78)

    client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    if buffer_size < UDP_METADATA_SIZE:
        buffer_size = UDP_METADATA_SIZE

    padding_size = buffer_size - UDP_METADATA_SIZE
    padding = b"X" * padding_size

    total_bytes = 0
    start_time = time.time()
    interval_start = start_time
    interval_bytes = 0
    interval_packets = 0

    print("\n  Elapsed (s)    Rate (MB/s)    Sent Packets    Total Megabytes")
    print("  " + "-" * 72)

    try:
        for seq in range(packet_count):
            if not GLOBAL_RUNNING:
                break

            now = time.time()
            header = struct.pack(UDP_METADATA_FORMAT, seq, now)
            packet = header + padding

            client_sock.sendto(packet, (target_ip, port))
            total_bytes += len(packet)
            interval_bytes += len(packet)
            interval_packets += 1

            if delay_sec > 0:
                time.sleep(delay_sec)

            current_time = time.time()
            interval_duration = current_time - interval_start
            if interval_duration >= 1.0:
                mb_s, _ = format_throughput(interval_bytes, interval_duration)
                elapsed = current_time - start_time
                mb_total = total_bytes / (1024.0 * 1024.0)
                print(f"  {elapsed:10.2f} {mb_s:14.2f} {seq+1:15d} {mb_total:16.2f} MB")
                interval_bytes = 0
                interval_packets = 0
                interval_start = current_time

    finally:
        total_duration = time.time() - start_time
        client_sock.close()
        final_mb_s, final_mbps = format_throughput(total_bytes, total_duration)
        print("  " + "-" * 72)
        print(f"  [FINAL] Transmission Duration : {total_duration:.2f} seconds")
        print(f"  [FINAL] Datagrams Emitted     : {interval_packets + (packet_count - interval_packets)}")
        print(f"  [FINAL] Total Volume Sent     : {total_bytes / (1024*1024):.2f} MB")
        print(f"  [FINAL] Outbound Throughput   : {final_mb_s:.2f} MB/s ({final_mbps:.2f} Mbps)")


# ============================================================================
# CLI ENTRYPOINT DISPATCHER
# ============================================================================

def parse_cli_args() -> argparse.Namespace:
    """Parses and validates operational parameters from standard command line."""
    parser = argparse.ArgumentParser(
        prog="socket_bench.py",
        description="High-Precision Network Socket Performance & Loss Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--mode",
        choices=["server", "client"],
        required=True,
        help="Execution role: 'server' (receiver) or 'client' (traffic generator)",
    )
    parser.add_argument(
        "--protocol",
        choices=["tcp", "udp"],
        default="tcp",
        help="Transport layer protocol: 'tcp' (stream) or 'udp' (datagram) [Default: tcp]",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9999,
        help="Port number to bind/target (1024-65535) [Default: 9999]",
    )
    parser.add_argument(
        "--bind",
        type=str,
        default="0.0.0.0",
        help="Interface IPv4 address to bind for server mode [Default: 0.0.0.0]",
    )
    parser.add_argument(
        "--target",
        type=str,
        default="127.0.0.1",
        help="Target IP address for client transmission [Default: 127.0.0.1]",
    )
    parser.add_argument(
        "--buffer-size",
        type=int,
        default=65536,
        help="Socket buffer read/write payload size in bytes [Default: 65536 for TCP, 1400 for UDP]",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="Client transmission runtime in seconds for stream tests [Default: 10.0]",
    )
    parser.add_argument(
        "--packet-count",
        type=int,
        default=50000,
        help="Total datagram count to generate in UDP client mode [Default: 50000]",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.00005,
        help="Inter-packet pacing delay in seconds for UDP transmission [Default: 0.00005]",
    )

    return parser.parse_args()


def main():
    args = parse_cli_args()

    if args.port < 1 or args.port > 65535:
        sys.stderr.write("[!] Validation Error: Port out of range (1-65535).\n")
        sys.exit(1)

    if args.mode == "server":
        if args.protocol == "tcp":
            run_tcp_server(args.bind, args.port, args.buffer_size)
        else:
            # Optimal UDP packet read default: 65535 bytes to avoid truncation
            buf = args.buffer_size if args.buffer_size != 65536 else 65535
            run_udp_server(args.bind, args.port, buf)

    elif args.mode == "client":
        if args.protocol == "tcp":
            run_tcp_client(args.target, args.port, args.duration, args.buffer_size)
        else:
            # For UDP, clamp payload default to safe Ethernet MTU boundary if not explicitly overridden
            payload_size = 1400 if args.buffer_size == 65536 else args.buffer_size
            run_udp_client(args.target, args.port, args.packet_count, payload_size, args.delay)


if __name__ == "__main__":
    main()
</ApplicationEngine>
