#!/usr/bin/env python3
"""
Connect isolated player-facing areas to the Midgaard walk graph, and repair
the Maze of Icarus (rooms had no exits).

Also updates gen_areas hub so regenerated Realm Road stays linked.

Quest note: auto-quests require h_find_dir() from ROOM_VNUM_TEMPLE (3001) to
the target mob. Areas reachable from the Temple become quest-eligible (unless
AREA_NOSHOW via header 'S'). System areas stay unlinked / NOSHOW.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT / "area"
DIR_NAMES = ("north", "east", "south", "west", "up", "down")
REV = (2, 3, 0, 1, 5, 4)


def parse_rooms(path: Path) -> Dict[int, dict]:
    text = path.read_text(encoding="latin-1", errors="replace")
    rooms: Dict[int, dict] = {}
    for rooms_m in re.finditer(r"#ROOMS\b", text):
        sec = text[rooms_m.end() :]
        m = re.search(r"\n#(MOBILES|OBJECTS|RESETS|SHOPS|SPECIALS|MOBPROGS|\$)\b", sec)
        if m:
            sec = sec[: m.start()]
        for rm in re.finditer(r"^#(\d+)\s*$", sec, re.M):
            vnum = int(rm.group(1))
            if vnum == 0:
                continue
            start = rm.end()
            nm = re.search(r"^#(\d+)\s*$", sec[start:], re.M)
            block = sec[start : start + nm.start()] if nm else sec[start:]
            exits = {}
            for dm in re.finditer(r"^D([0-5])\s*$", block, re.M):
                d = int(dm.group(1))
                rest = block[dm.end() :]
                for line in rest.splitlines():
                    line = line.strip()
                    nums = line.split()
                    if len(nums) >= 3 and all(re.fullmatch(r"-?\d+", x) for x in nums[:3]):
                        dest = int(nums[2])
                        if dest > 0:
                            exits[d] = dest
                        break
            rooms[vnum] = {"exits": exits, "file": path.name}
    return rooms


def load_world() -> Dict[int, dict]:
    all_rooms: Dict[int, dict] = {}
    for p in sorted(AREA.glob("*.are")):
        all_rooms.update(parse_rooms(p))
    return all_rooms


def reachable_from(all_rooms: Dict[int, dict], seed: int = 3001) -> Set[int]:
    if seed not in all_rooms:
        return set()
    vis = {seed}
    q = deque([seed])
    while q:
        v = q.popleft()
        for dest in all_rooms[v]["exits"].values():
            if dest in all_rooms and dest not in vis:
                vis.add(dest)
                q.append(dest)
    return vis


def add_exit(
    text: str,
    vnum: int,
    direction: int,
    dest: int,
    description: str = "",
    keyword: str = "",
) -> Tuple[str, bool]:
    """Insert or replace a door exit on room vnum. Returns (new_text, changed)."""
    # Match room block up to its terminating S (not followed by more room content care)
    pat = re.compile(rf"(^#{vnum}\s*\n)(.*?)(^S\s*$)", re.M | re.S)
    m = pat.search(text)
    if not m:
        return text, False

    body = m.group(2)
    # If this direction already points at dest, no-op
    existing = re.search(
        rf"^D{direction}\s*\n(?:.*\n)*?(-?\d+)\s+(-?\d+)\s+(-?\d+)\s*$",
        body,
        re.M,
    )
    if existing and int(existing.group(3)) == dest:
        return text, False

    # Remove existing door in that direction if present (full D-block)
    body2 = re.sub(
        rf"^D{direction}\s*\n(?:(?!^D[0-5]|^E\s*$|^S\s*$).*\n)*",
        "",
        body,
        count=1,
        flags=re.M,
    )

    desc = description or f"You see a path leading {DIR_NAMES[direction]}."
    door = (
        f"D{direction}\n"
        f"{desc}\n"
        f"~\n"
        f"{keyword}~\n"
        f"0 -1 {dest}\n"
    )

    # Insert before first extra-desc E or before end of body
    em = re.search(r"^E\s*$", body2, re.M)
    if em:
        body2 = body2[: em.start()] + door + body2[em.start() :]
    else:
        if body2 and not body2.endswith("\n"):
            body2 += "\n"
        body2 = body2 + door

    new_text = text[: m.start()] + m.group(1) + body2 + m.group(3) + text[m.end() :]
    return new_text, True


def link_bidirectional(
    files: Dict[str, str],
    a_file: str,
    a_vnum: int,
    a_dir: int,
    b_file: str,
    b_vnum: int,
    b_dir: Optional[int] = None,
    a_desc: str = "",
    b_desc: str = "",
) -> List[str]:
    if b_dir is None:
        b_dir = REV[a_dir]
    notes = []
    t, ch = add_exit(files[a_file], a_vnum, a_dir, b_vnum, a_desc)
    if ch:
        files[a_file] = t
        notes.append(f"{a_file}:{a_vnum} {DIR_NAMES[a_dir]} -> {b_vnum}")
    t, ch = add_exit(files[b_file], b_vnum, b_dir, a_vnum, b_desc)
    if ch:
        files[b_file] = t
        notes.append(f"{b_file}:{b_vnum} {DIR_NAMES[b_dir]} -> {a_vnum}")
    return notes


def repair_maze(files: Dict[str, str]) -> List[str]:
    """Give Maze of Icarus a walkable grid and entrance/exit."""
    fname = "maze_of_icarus.are"
    text = files[fname]
    sec_m = re.search(r"#ROOMS\b", text)
    if not sec_m:
        return ["maze: no #ROOMS"]
    sec = text[sec_m.end() :]
    end_m = re.search(r"\n#(MOBILES|OBJECTS|RESETS|SHOPS|\$)\b", sec)
    end_pos = end_m.start() if end_m else len(sec)
    room_sec = sec[:end_pos]

    vnums = sorted({int(x) for x in re.findall(r"^#(\d+)\s*$", room_sec, re.M) if int(x) > 0})
    if len(vnums) < 4:
        return [f"maze: too few rooms ({len(vnums)})"]

    # Place rooms on a roughly square grid in vnum order
    n = len(vnums)
    w = int(n ** 0.5 + 0.999)
    h = (n + w - 1) // w
    grid: List[List[Optional[int]]] = [[None] * w for _ in range(h)]
    for i, v in enumerate(vnums):
        grid[i // w][i % w] = v

    # Spanning path: serpentine through grid for guaranteed connectivity
    notes = []
    ordered = [v for row in grid for v in row if v is not None]
    # Clear all existing D* blocks in maze rooms first by rewriting exits only via add_exit after strip
    # Strip existing doors from each room
    for v in vnums:
        def strip_doors(match: re.Match) -> str:
            body = re.sub(r"^D[0-5]\s*\n(?:(?!^D[0-5]|^E\s*$|^S\s*$).*\n)*", "", match.group(2), flags=re.M)
            return match.group(1) + body + match.group(3)

        text, nsub = re.subn(rf"(^#{v}\s*\n)(.*?)(^S\s*$)", strip_doors, text, count=1, flags=re.M | re.S)
        files[fname] = text

    text = files[fname]
    # Connect consecutive rooms in serpentine order (east/west/south)
    for i in range(len(ordered) - 1):
        a, b = ordered[i], ordered[i + 1]
        # prefer east then south for variety
        row_a, col_a = divmod(i, w)
        row_b, col_b = divmod(i + 1, w)
        if row_a == row_b and col_b == col_a + 1:
            da, db = 1, 3  # E/W
        elif row_a == row_b and col_b == col_a - 1:
            da, db = 3, 1
        elif col_a == col_b and row_b == row_a + 1:
            da, db = 2, 0  # S/N
        else:
            da, db = 1, 3
        t, ch = add_exit(text, a, da, b, "A narrow stone corridor continues.")
        text = t
        t, ch2 = add_exit(text, b, db, a, "A narrow stone corridor continues.")
        text = t
        if ch or ch2:
            notes.append(f"maze link {a}<->{b}")

    # Add some cross-links for maze feel (every 3rd vertical if neighbor exists)
    for r in range(h - 1):
        for c in range(w):
            a, b = grid[r][c], grid[r + 1][c]
            if a is None or b is None:
                continue
            if (r + c) % 3 == 0:
                t, _ = add_exit(text, a, 2, b, "A dark passage opens south.")
                text = t
                t, _ = add_exit(text, b, 0, a, "A dark passage opens north.")
                text = t

    files[fname] = text

    # Entrance: midgaard west gate area / rocroad crossroads -> maze entrance (first room)
    entrance = ordered[0]
    exit_room = ordered[-1]
    # Link rocroad 3233 (CrossRoads) south -> maze entrance, reverse north
    notes += link_bidirectional(
        files,
        "rocroad.are",
        3233,
        2,  # south
        fname,
        entrance,
        0,  # north
        a_desc="A crumbling archway leads into the Maze of Icarus.",
        b_desc="Through the arch you glimpse Roc Road and freedom.",
    )
    # Ensure exit room also has way out (link east to entrance's reverse path already connected)
    # Add exit signpost room link back if last room not already connected out
    t, ch = add_exit(
        files[fname],
        exit_room,
        4,  # up
        3233,
        "A shaft of light leads up and out of the maze.",
    )
    if ch:
        files[fname] = t
        notes.append(f"maze exit {exit_room} up -> 3233")
    t, ch = add_exit(
        files["rocroad.are"],
        3233,
        5,  # down
        exit_room,
        "A dark shaft descends into the Maze of Icarus.",
    )
    if ch:
        files["rocroad.are"] = t
        notes.append("rocroad 3233 down -> maze exit")

    return notes


def ensure_noshow(files: Dict[str, str], fname: str) -> Optional[str]:
    """Ensure area header has 'S' NOSHOW line so quests ignore system zones."""
    text = files[fname]
    # Already has S line after #AREA before first #ROOMS/#MOBILES
    header_end = re.search(r"\n#(ROOMS|MOBILES|OBJECTS)\b", text)
    if not header_end:
        return None
    header = text[: header_end.start()]
    if re.search(r"^S\s", header, re.M):
        return None
    insert_at = header_end.start()
    new_text = text[:insert_at] + "\nS Title not shown on area list.\n" + text[insert_at:]
    files[fname] = new_text
    return f"{fname}: added AREA_NOSHOW (S)"


def apply_links(files: Dict[str, str]) -> List[str]:
    notes: List[str] = []

    # 1) Realm Road hub <-> Midgaard west gate (progression campaign entry)
    notes += link_bidirectional(
        files,
        "midgaard.are",
        3052,
        2,  # south
        "realmroad.are",
        22500,
        0,  # north
        a_desc="The Realm Road stretches south toward distant lands.",
        b_desc="North lies the West Gate of Midgaard.",
    )

    # 2) Mud School down <-> Giganthia temple (already has up to 3700)
    notes += link_bidirectional(
        files,
        "school.are",
        3700,
        5,  # down
        "gigant.are",
        3430,
        4,  # up
        a_desc="Stone steps descend into the cavern-city of Giganthia.",
        b_desc="Steps lead up into Adesa's Mud School.",
    )

    # 3) Midgaard Dump up -> Ethereal (exit portals already return to Midgaard)
    t, ch = add_exit(
        files["midgaard.are"],
        3030,
        4,
        3857,
        "A shimmering rift opens upward into the Ethereal Plane.",
    )
    if ch:
        files["midgaard.are"] = t
        notes.append("midgaard.are:3030 up -> 3857 (ethereal)")
    # reverse convenience: ethereal free up was available - also keep existing down to market
    t, ch = add_exit(
        files["ethereal.are"],
        3857,
        4,
        3030,
        "The ethereal mist thins; below you sense Midgaard's dump.",
    )
    if ch:
        files["ethereal.are"] = t
        notes.append("ethereal.are:3857 up -> 3030")

    # 4) Asylum stairwell attached to surgery hall
    notes += link_bidirectional(
        files,
        "asylum_inside.are",
        16026,
        5,  # down
        "asylum_inside.are",
        16030,
        4,  # up
        a_desc="A dark stairwell yawns downward beneath the asylum.",
        b_desc="Stairs climb back toward the surgery wing.",
    )

    # 5) Roc Road end -> Farmlands (jennluansol)
    notes += link_bidirectional(
        files,
        "rocroad.are",
        3243,
        2,  # south
        "jennluansol.are",
        7200,
        0,  # north
        a_desc="A cart path leads south into the Farmlands.",
        b_desc="The path north returns to Roc Road.",
    )

    # 6) Midgaard Dump east -> Moribund morgue
    notes += link_bidirectional(
        files,
        "midgaard.are",
        3030,
        1,  # east
        "moribund.are",
        3300,
        3,  # west
        a_desc="A grim alley leads east toward the Moribund Morgue.",
        b_desc="West returns to the refuse piles of Midgaard.",
    )
    # Moribund 3300 was an island; 3304 already goes up to 3300 — add down
    t, ch = add_exit(
        files["moribund.are"],
        3300,
        5,
        3304,
        "Stairs descend into Moribund's halls.",
    )
    if ch:
        files["moribund.are"] = t
        notes.append("moribund.are:3300 down -> 3304")

    # 7) School training / arena area -> old arena complex
    # school 3744 is arena room; give it east to oldarena preparation
    notes += link_bidirectional(
        files,
        "school.are",
        3744,
        1,  # east
        "oldarena.are",
        300,
        3,  # west
        a_desc="A heavy gate opens east into the old arena grounds.",
        b_desc="West leads back toward Mud School.",
    )

    # 8) Maze of Icarus repair + link
    notes += repair_maze(files)

    # System / builder areas: keep off quest lists
    for sys_area in (
        "limbo.are",
        "utility.are",
        "ceiling.are",
        "enchant-eq.are",
        "auction.are",
        "micro_mob_generator.are",
        "immort.are",
    ):
        if sys_area in files:
            n = ensure_noshow(files, sys_area)
            if n:
                notes.append(n)

    return notes


def report(all_rooms: Dict[int, dict], seed: int = 3001) -> None:
    vis = reachable_from(all_rooms, seed)
    by = defaultdict(int)
    for v in vis:
        by[all_rooms[v]["file"]] += 1
    all_files = sorted({r["file"] for r in all_rooms.values()})
    disc = [f for f in all_files if f not in by]
    print(f"Reachable rooms from {seed}: {len(vis)} / {len(all_rooms)}")
    print(f"Reachable areas: {len(by)} / {len(all_files)}")
    for f in sorted(by):
        print(f"  OK  {f} ({by[f]} rooms)")
    if disc:
        print("Still disconnected:")
        for f in disc:
            n = sum(1 for r in all_rooms.values() if r["file"] == f)
            print(f"  --  {f} ({n} rooms)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Report only, do not write")
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()

    if args.report_only:
        report(load_world())
        return 0

    files = {p.name: p.read_text(encoding="latin-1", errors="replace") for p in AREA.glob("*.are")}
    print("Before:")
    report(load_world())

    notes = apply_links(files)
    print("\nChanges:")
    for n in notes:
        print(" ", n)

    if args.dry_run:
        print("\n(dry-run: no files written)")
        return 0

    for name, text in files.items():
        path = AREA / name
        old = path.read_text(encoding="latin-1", errors="replace")
        if text != old:
            path.write_text(text, encoding="latin-1")
            print(f"wrote {path}")

    print("\nAfter:")
    report(load_world())
    return 0


if __name__ == "__main__":
    sys.exit(main())
