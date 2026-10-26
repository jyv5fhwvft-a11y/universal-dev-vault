<DocumentationHub>
# Lab Manual: Transport Layer Performance & Socket Mechanics

**Document Identifier:** `socket_analyzer_wiki.md`  
**Course Module:** CS-4520: High-Performance Networking and Distributed Systems  
**Audience:** Undergraduate Computer Science & Systems Engineering Students  
**Subject:** Empirical Analysis of TCP Stream Dynamics vs. UDP Datagram Overhead  

---

## 1. Executive Summary & Learning Objectives

Network communication at the Transport Layer (OSI Layer 4) is governed by trade-offs between **reliability guarantees** and **transmission latency**. The Transmission Control Protocol (TCP) delivers a guaranteed, ordered byte stream at the cost of protocol state overhead, dynamic congestion control throttling, and connection setup/teardown latencies. Conversely, the User Datagram Protocol (UDP) exposes an uncoordinated, connectionless interface that maximizes transmission rate and minimizes processing overhead, while offloading loss detection, packet ordering, and flow control entirely to the user-space application.

Upon completion of this laboratory guide, students will be able to:
1. Explain the architectural mechanisms that differentiate TCP stream goodput from UDP datagram throughput.
2. Quantify the encapsulation and framing overhead across Layer 3 (IPv4) and Layer 4 (TCP vs. UDP).
3. Identify how the Bandwidth-Delay Product (BDP) and the TCP sliding window limit maximum theoretical throughput.
4. Execute empirical throughput and packet loss benchmarks across both protocols using native socket APIs.
5. Mathematically calculate packet loss rates, bandwidth saturation, and protocol efficiency under synthetic workloads.

---

## 2. Theoretical Framework: TCP vs. UDP Mechanics

### 2.1 Transport Layer Encapsulation & Header Overhead

Every byte transmitted across an Ethernet network traverses physical framing (Layer 2), packet routing (Layer 3), and transport segmentation (Layer 4) before reaching application logic.

```
+------------------------------------------------------------------------------------+
| Layer 2: Ethernet Frame Header (14 Bytes) + Preamble/FCS (10 Bytes) - MTU 1500 B  |
+------------------------------------------------------------------------------------+
| Layer 3: IPv4 Header (20 Bytes minimum, without IP Options)                        |
+------------------------------------------------------------------------------------+
| Layer 4: TCP Header (20-60 Bytes)        | Layer 4: UDP Header (8 Bytes Fixed)     |
+------------------------------------------+-----------------------------------------+
| Payload: Application Data (Goodput)      | Payload: Application Data (Goodput)     |
+------------------------------------------------------------------------------------+
```

#### Protocol Header Comparison

| Structural Metric | TCP (`SOCK_STREAM`) | UDP (`SOCK_DGRAM`) |
| :--- | :--- | :--- |
| **Minimum Header Size** | 20 Bytes (up to 60 Bytes with Options) | 8 Bytes (Strictly Fixed) |
| **Connection State** | Stateful (SYN, ESTABLISHED, FIN/RST) | Stateless (Fire-and-forget) |
| **Ordering Guarantees** | Strict (Sequence & Acknowledgment Nos) | None (Out-of-order possible) |
| **Reliability Mechanism**| Retransmission timers, SACK, Fast Retransmit | None (Silent drop at buffer saturation) |
| **Flow Control** | Dynamic (Receiver Advertised Window `rwnd`) | None (Kernel socket buffer overflow drops) |
| **Congestion Control** | Dynamic (AIMD: CUBIC, Reno, BBR) | None (Must be implemented in user space) |

#### Efficiency Ratio Formula
Protocol Efficiency ($\eta$) measures the ratio of user application data (goodput) relative to the total wire bytes transferred:

$$\eta = \frac{\text{Payload Size (Bytes)}}{\text{Payload Size} + \text{L4 Header} + \text{L3 Header} + \text{L2 Framing}}$$

*Example:* For a payload of 1400 bytes over IPv4 / Ethernet (MTU = 1500 bytes):
- **TCP Efficiency:** $\eta_{\text{TCP}} = \frac{1400}{1400 + 20 + 20 + 24} = \frac{1400}{1464} \approx 95.63\%$
- **UDP Efficiency:** $\eta_{\text{UDP}} = \frac{1400}{1400 + 8 + 20 + 24} = \frac{1400}{1452} \approx 96.42\%$

While header efficiency appears comparable at maximum transmission units (MTU), UDP throughput advantages emerge from the **absence of kernel-space congestion windows, acknowledgment round-trips, and Head-of-Line (HoL) blocking**.

---

### 2.2 TCP Stream Dynamics & Congestion Avoidance

TCP abstracts network transmission as an uninterrupted pipe of contiguous bytes (`SOCK_STREAM`). The rate at which TCP pumps data into the network is bounded by two variables:

$$\text{Max In-Flight Bytes} = \min(\text{cwnd}, \text{rwnd})$$

Where:
- $\text{cwnd}$ (Congestion Window): Calculated dynamically by the sender to avoid saturating network intermediate links.
- $\text{rwnd}$ (Receiver Advertised Window): Communicated by the receiver in TCP header flags to avoid saturating the local kernel receive buffer (`SO_RCVBUF`).

#### Bandwidth-Delay Product (BDP)
To fully saturate a physical link, the TCP socket window size must equal or exceed the Bandwidth-Delay Product:

$$\text{BDP (Bits)} = \text{Link Capacity (Bits/Sec)} \times \text{Round-Trip Time (RTT in Seconds)}$$

If the socket buffer size configured in the kernel is smaller than the BDP, the transmitter will run dry waiting for ACKs, resulting in underutilized link throughput regardless of available bandwidth.

---

### 2.3 UDP Datagram Dynamics & Packet Loss

UDP treats application writes as discrete, independent units (`SOCK_DGRAM`). The kernel encapsulates the payload with an 8-byte header and passes it immediately to the IP layer.

1. **No Throttling:** The transmitter sends datagrams at the exact rate dictated by the calling application loop.
2. **Buffer Exhaustion:** If the transmission rate exceeds the processing capability of intermediate switches, routers, or the receiver's socket buffer (`SO_RCVBUF`), incoming datagrams are dropped silently.
3. **Loss Metrics:** Because UDP headers provide no packet sequence tracking, user-space benchmarks must embed an explicit integer sequence counter into the application payload to detect:
   - **Absolute Packet Loss:** $\text{Loss \%} = \frac{\text{Packets Transmitted} - \text{Packets Received}}{\text{Packets Transmitted}} \times 100$
   - **Out-of-Order Delivery:** Where packet $N + k$ arrives before packet $N$.

---

## 3. Laboratory Setup & Test Execution

### 3.1 Network Topology Options

1. **Local Loopback (`lo` / `127.0.0.1`):** Tests raw kernel socket buffer throughput and CPU context-switching limits without physical interface constraints.
2. **Virtual Bridge / Container Topology (Recommended):** Uses two isolated network namespaces or virtual machines interconnected over a Linux virtual bridge (`veth` pairs) configured with synthetic delay and loss:
   ```bash
   # Add 25ms latency and 2% random packet drop to the experimental link
   sudo tc qdisc add dev veth0 root netem delay 25ms loss 2%
   ```

### 3.2 Executing the Benchmark Suite

Run the provided `socket_bench.py` utility in opposing roles:

#### Scenario A: High-Throughput TCP Stream Test
```bash
# Terminal 1: Receiver (Server Mode)
python3 socket_bench.py --mode server --protocol tcp --port 9999 --bind 0.0.0.0

# Terminal 2: Transmitter (Client Mode)
python3 socket_bench.py --mode client --protocol tcp --target 127.0.0.1 --port 9999 --duration 10 --buffer-size 65536
```

#### Scenario B: High-Rate UDP Datagram Loss & Throughput Test
```bash
# Terminal 1: Receiver (Server Mode)
python3 socket_bench.py --mode server --protocol udp --port 9999 --bind 0.0.0.0

# Terminal 2: Transmitter (Client Mode)
python3 socket_bench.py --mode client --protocol udp --target 127.0.0.1 --port 9999 --duration 10 --packet-count 50000 --buffer-size 1400
```

---

## 4. Student Post-Lab Review Questions

1. **Question 1 (Buffer Scaling):** Why does TCP stream goodput degrade dramatically when latency increases on a link with a high Bandwidth-Delay Product if `TCP Window Scaling` (RFC 1323) is disabled?
2. **Question 2 (Head-of-Line Blocking):** If a single TCP segment is dropped in transit, what happens to the subsequent segments that have already successfully arrived in the receiver's kernel buffer? How does UDP differ in this scenario?
3. **Question 3 (Datagram Sizing):** Why is sending UDP datagram payloads larger than 1472 bytes over standard Ethernet networks prone to catastrophic packet loss in congested environments? *(Hint: Consider IPv4 fragmentation and MTU boundaries).*
4. **Question 4 (CPU Overhead):** During high-throughput benchmarks, which configuration consumes more CPU cycles on the host machine: a single TCP stream transferring 1 GB via large 64 KB buffers, or UDP transferring 1 GB via small 512-byte datagrams? Justify your answer using system call frequency.
</DocumentationHub>
