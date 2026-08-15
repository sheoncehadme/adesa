#!/usr/bin/env python3
"""Level a named test character via immortal commands over telnet.

Mirrors the three MUSHclient plugins in this directory. Not a combat
grinder — it injects levels with setclass / mset for Dragonfall
functional tests.

Usage:
  python3 tools/mushclient/df_level_via_imm.py \\
    --host 127.0.0.1 --port 6000 \\
    --imm Ogma --imm-pass SECRET \\
    --char Testchar --mode mortal --class War --level 80

Modes: mortal, remort, adept.
"""
from __future__ import annotations

import argparse
import re
import socket
import sys
import time
from typing import Iterable


MORTAL = {
    "mag": "Mag",
    "mage": "Mag",
    "cle": "Cle",
    "cleric": "Cle",
    "thi": "Thi",
    "thief": "Thi",
    "war": "War",
    "warrior": "War",
    "psi": "Psi",
    "psionicist": "Psi",
    "psion": "Psi",
}

REMORT = {
    "sor": "Sor",
    "sorcerer": "Sor",
    "ass": "Ass",
    "assassin": "Ass",
    "kni": "Kni",
    "knight": "Kni",
    "nec": "Nec",
    "necromancer": "Nec",
    "mon": "Mon",
    "monk": "Mon",
}

ADEPT_MAX = 20
DEFAULT_LEVEL = 80


def normalize_class(mode: str, token: str) -> str:
    table = MORTAL if mode == "mortal" else REMORT
    who = table.get(token.lower())
    if who is None:
        allowed = ", ".join(sorted(set(table.values())))
        raise SystemExit(f"unknown {mode} class '{token}' (want {allowed})")
    return who


def commands_for(mode: str, char: str, klass: str | None, level: int) -> list[str]:
    if mode == "mortal":
        if not klass:
            raise SystemExit("--class is required for mode=mortal")
        who = normalize_class("mortal", klass)
        return [f"setclass {char} {who} {level}", f"force {char} save"]
    if mode == "remort":
        if not klass:
            raise SystemExit("--class is required for mode=remort")
        who = normalize_class("remort", klass)
        return [f"setclass {char} {who} {level}", f"force {char} save"]
    if mode == "adept":
        return [
            f"setclass {char} ADEPT",
            f"mset {char} adept {ADEPT_MAX}",
            f"force {char} save",
        ]
    raise SystemExit(f"unknown mode '{mode}'")


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
                sock.settimeout(0.35)
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
    out = bytearray()
    i = 0
    while i < len(raw):
        if raw[i] == 255 and i + 1 < len(raw):
            cmd = raw[i + 1]
            if cmd in (251, 252, 253, 254) and i + 2 < len(raw):
                i += 3
                continue
            i += 2
            continue
        out.append(raw[i])
        i += 1
    text = out.decode("latin-1", errors="replace")
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)
    text = re.sub(r"@@.", "", text)
    return text


def send_line(sock: socket.socket, line: str) -> None:
    sock.sendall((line + "\n").encode("latin-1", errors="replace"))


def login(sock: socket.socket, name: str, password: str) -> str:
    greeting = strip_ansi_telnet(recv_until(sock, timeout=4.0))
    send_line(sock, name)
    _ = recv_until(sock, timeout=2.0)
    send_line(sock, password)
    body = strip_ansi_telnet(recv_until(sock, timeout=4.0, min_bytes=20))
    if re.search(r"wrong password|already playing|Wrong password|Challenge failed", body, re.I):
        raise SystemExit("login rejected:\n" + body[:800])
    # CON_READ_MOTD — empty line enters the game
    send_line(sock, "")
    entered = strip_ansi_telnet(recv_until(sock, timeout=4.0, min_bytes=10))
    return greeting + "\n" + body + "\n" + entered


def run_commands(sock: socket.socket, cmds: Iterable[str]) -> str:
    chunks: list[str] = []
    for cmd in cmds:
        print(f"-> {cmd}")
        send_line(sock, cmd)
        time.sleep(0.25)
        chunks.append(strip_ansi_telnet(recv_until(sock, timeout=3.0, min_bytes=4)))
    return "\n".join(chunks)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=6000)
    p.add_argument("--imm", required=True, help="immortal login name")
    p.add_argument("--imm-pass", required=True, help="immortal password")
    p.add_argument("--char", default="Testchar", help="mortal test character (must be online)")
    p.add_argument("--mode", required=True, choices=("mortal", "remort", "adept"))
    p.add_argument("--class", dest="klass", default=None, help="mortal or remort class")
    p.add_argument("--level", type=int, default=DEFAULT_LEVEL)
    p.add_argument("--dry-run", action="store_true", help="print commands and exit")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.mode != "adept" and (args.level < 1 or args.level > DEFAULT_LEVEL):
        print(f"--level must be 1–{DEFAULT_LEVEL}", file=sys.stderr)
        return 2

    cmds = commands_for(args.mode, args.char, args.klass, args.level)
    if args.dry_run:
        for cmd in cmds:
            print(cmd)
        return 0

    print(f"==> connect {args.host}:{args.port} as {args.imm}")
    try:
        sock = socket.create_connection((args.host, args.port), timeout=5)
    except OSError as e:
        print(f"FAIL: cannot connect: {e}", file=sys.stderr)
        return 1

    try:
        login_text = login(sock, args.imm, args.imm_pass)
        print("--- login (truncated) ---")
        print(login_text[:600].replace("\r", ""))
        print("-------------------------")
        reply = run_commands(sock, cmds)
        print("--- reply ---")
        print(reply[:2000].replace("\r", ""))
        print("-------------")
        send_line(sock, "quit")
        time.sleep(0.2)
        return 0
    finally:
        try:
            sock.close()
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
