#!/usr/bin/env python3
"""
Socket smoke tests against a running Adesa instance.

Default: connect, read greeting, disconnect (no login required).

Optional authenticated scenarios (set env):
  ADESA_HOST, ADESA_PORT  (default 127.0.0.1:6000)
  ADESA_USER, ADESA_PASS  — if set, attempt login
  ADESA_RUN_SCHECK=1      — after login as imm, run scheck (requires trust)

Usage:
  python3 tests/scripts/smoke_telnet.py
  ADESA_PORT=6011 python3 tests/scripts/smoke_telnet.py
"""
from __future__ import annotations

import os
import re
import socket
import sys
import time


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def recv_until(sock: socket.socket, timeout: float = 3.0, min_bytes: int = 8) -> bytes:
    sock.settimeout(timeout)
    data = b""
    end = time.time() + timeout
    while time.time() < end:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
            if len(data) >= min_bytes:
                # small settle
                sock.settimeout(0.3)
                try:
                    while True:
                        more = sock.recv(4096)
                        if not more:
                            break
                        data += more
                except socket.timeout:
                    pass
                break
        except socket.timeout:
            if data:
                break
    return data


def strip_ansi_telnet(raw: bytes) -> str:
    # Drop telnet IAC sequences crudely
    out = bytearray()
    i = 0
    while i < len(raw):
        if raw[i] == 255 and i + 1 < len(raw):  # IAC
            cmd = raw[i + 1]
            if cmd in (251, 252, 253, 254) and i + 2 < len(raw):
                i += 3
                continue
            i += 2
            continue
        out.append(raw[i])
        i += 1
    text = out.decode("latin-1", errors="replace")
    # strip simple ANSI
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)
    # strip Adesa @@ color codes lightly
    text = re.sub(r"@@.", "", text)
    return text


def main() -> int:
    host = env("ADESA_HOST", "127.0.0.1")
    port = int(env("ADESA_PORT", "6000"))
    user = env("ADESA_USER")
    password = env("ADESA_PASS")
    run_scheck = env("ADESA_RUN_SCHECK") == "1"

    print(f"==> connect {host}:{port}")
    try:
        sock = socket.create_connection((host, port), timeout=5)
    except OSError as e:
        print(f"FAIL: cannot connect: {e}", file=sys.stderr)
        print("hint: start merc, or set ADESA_PORT; for CI use boot/selftest instead")
        return 1

    try:
        greeting = strip_ansi_telnet(recv_until(sock, timeout=4.0))
        print("--- greeting (truncated) ---")
        print(greeting[:500].replace("\r", ""))
        print("-------------------------")
        if len(greeting.strip()) < 3:
            print("FAIL: empty greeting", file=sys.stderr)
            return 1
        print("ok: received greeting")

        if not user:
            print("ok: connect-only smoke (set ADESA_USER/ADESA_PASS for login tests)")
            return 0

        # Login sequence: name, password (varies by nanny; best-effort)
        sock.sendall((user + "\n").encode())
        time.sleep(0.2)
        _ = recv_until(sock, timeout=2.0)
        sock.sendall((password + "\n").encode())
        time.sleep(0.5)
        body = strip_ansi_telnet(recv_until(sock, timeout=4.0, min_bytes=20))
        print("--- post-login (truncated) ---")
        print(body[:800].replace("\r", ""))
        print("----------------------------")

        if re.search(r"wrong password|already playing|Wrong password", body, re.I):
            print("FAIL: login rejected", file=sys.stderr)
            return 1

        print("ok: login sequence completed (best-effort)")

        if run_scheck:
            sock.sendall(b"scheck\n")
            time.sleep(1.0)
            sc = strip_ansi_telnet(recv_until(sock, timeout=5.0, min_bytes=10))
            print("--- scheck ---")
            print(sc[:1000].replace("\r", ""))
            print("--------------")
            if "leaks dumped" not in sc.lower() and "leak" not in sc.lower():
                print("WARN: scheck response unexpected (need imm level 90+)")
            else:
                print("ok: scheck ran")

        sock.sendall(b"quit\n")
        time.sleep(0.2)
        return 0
    finally:
        try:
            sock.close()
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
