#!/usr/bin/env python3
"""ck_analyzer reference collector: prints + persists JSONL from UDP."""
import socket, sys, json, datetime

port = int(sys.argv[1]) if len(sys.argv) > 1 else 9999
out = open(sys.argv[2], "a") if len(sys.argv) > 2 else None
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("0.0.0.0", port))
print(f"ck_analyzer collector on :{port}", flush=True)
while True:
    data, addr = s.recvfrom(2048)
    line = data.decode(errors="replace")
    stamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{stamp} {addr[0]}] {line}", flush=True)
    if out:
        out.write(line + "\n"); out.flush()
