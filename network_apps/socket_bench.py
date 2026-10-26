<ApplicationEngine>
import time
import random
import socket
import json
import threading
from datetime import datetime

class TelemetryDaemon:
    def __init__(self, host='127.0.0.1', port=9999):
        self.host = host
        self.port = port
        self.running = False
        self.lock = threading.Lock()
        
        # Initial Core Metrics (Matching CYBER_NET visual states)
        self.metrics = {
            "interface": "eth0",
            "capacity": "10 GbE Full-Duplex",
            "rtt_ms": 25.0,
            "congestion_algo": "TCP CUBIC",
            "buffer_size": "4MB",
            "throughput_mbs": 837.17,
            "packet_loss_pct": 0.049,
            "total_transferred_gb": 14.88,
            "active_latency_ms": 1.28,
            "timestamp": datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
        }

    def generate_live_telemetry(self):
        """Simulates real-world network fluctuations on low-level sockets."""
        base_gb = 14.88
        start_time = time.time()
        
        while self.running:
            time.sleep(1.0)  # 1Hz telemetry updates
            elapsed = time.time() - start_time
            
            with self.lock:
                # Add micro-fluctuations to mimic dynamic socket state machine updates
                self.metrics["throughput_mbs"] = round(837.17 + random.uniform(-15.5, 22.3), 2)
                self.metrics["packet_loss_pct"] = round(max(0.01, 0.049 + random.uniform(-0.012, 0.015)), 3)
                self.metrics["active_latency_ms"] = round(max(0.5, 1.28 + random.uniform(-0.15, 0.22)), 2)
                self.metrics["rtt_ms"] = round(25.0 + random.uniform(-2.0, 3.5), 1)
                
                # Accumulate data volume based on live throughput
                bytes_sent = (self.metrics["throughput_mbs"] * 1024 * 1024)
                base_gb += (bytes_sent / (1024 * 1024 * 1024))
                self.metrics["total_transferred_gb"] = round(base_gb, 2)
                self.metrics["timestamp"] = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
                
                # Print clean matrix dump directly to the system terminal view
                print(f"📟 [{self.metrics['timestamp']}] eth0 Pump Rate: {self.metrics['throughput_mbs']} MB/s | Loss: {self.metrics['packet_loss_pct']}% | Latency: {self.metrics['active_latency_ms']}ms")

    def start_server_socket(self):
        """Establishes an active endpoint for metrics collection or student API polls."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((self.host, self.port))
            server.listen(5)
            server.settimeout(1.0)
        except Exception as e:
            print(f"🚨 Socket Bind Error: {e}")
            return

        while self.running:
            try:
                client_sock, addr = server.accept()
                # Run connection thread pool handler
                threading.Thread(target=self.handle_client, args=(client_sock,), daemon=True).start()
            except socket.timeout:
                continue
            except Exception:
                break
        server.close()

    def handle_client(self, client_socket):
        """Flushes immediate structured metrics state payloads to network requests."""
        try:
            with self.lock:
                payload = json.dumps(self.metrics) + "\n"
            client_socket.sendall(payload.encode('utf-8'))
        except Exception:
            pass
        finally:
            client_socket.close()

    def run(self):
        self.running = True
        print(f"⚙️ Launching CYBER_NET Core Telemetry Engine on {self.host}:{self.port}...")
        
        # Orchestrate thread processes
        telemetry_worker = threading.Thread(target=self.generate_live_telemetry, daemon=True)
        socket_worker = threading.Thread(target=self.start_server_socket, daemon=True)
        
        telemetry_worker.start()
        socket_worker.start()

        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n🛑 Draining memory buffers and shutting down socket workers cleanly...")
            self.running = False
            time.sleep(1.5)
            print("🟢 System teardown complete.")

if __name__ == "__main__":
    daemon = TelemetryDaemon()
    daemon.run()
</ApplicationEngine>
