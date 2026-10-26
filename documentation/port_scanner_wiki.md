# 📟 Multi-Threaded Port Scanner Lab Guide

## 🔬 Core Learning Objectives
* Understand the transport layer and the function of TCP/IP ports.
* Explore system-level connection handles using three-way handshakes.
* Analyze execution speed improvements from concurrent multithreading.

## 📡 What are Network Sockets & Ports?
A network socket acts as an endpoint handle for communication between distinct processes across an IP network. While an IP address routes traffic to a specific machine, **Port Numbers (0–65535)** act like doors to specific application workers.

### 🏢 The Analogy
Think of an IP address as a hotel's street address. The **Port Numbers** are the individual room numbers. If you want to check in, you go to the lobby (Port 80/443). If you want to deliver mail, you go to the back loading dock (Port 25).

## 🚀 Environment Execution Setup
To execute your custom Python scanner engine locally or inside your network sandbox container, trigger the application from your command-line workspace:

```bash
# Basic scan against localhost connections
python3 scanner.py --target 127.0.0.1 --ports 1-1024 --workers 100

# Scan specific web service socket layers with banner checking enabled
python3 scanner.py -t scanme.nmap.org -p 22,80,443 -b
```
