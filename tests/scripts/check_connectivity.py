#!/usr/bin/env python3
"""
Assert player-facing areas are walk-reachable from the Temple (vnum 3001).

System / builder zones may remain disconnected (listed in ALLOW_DISCONNECTED).
Exit 0 on success, 1 on failure.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from world_connect import load_world, reachable_from  # noqa: E402

# Intentionally not part of the mortal walk graph
ALLOW_DISCONNECTED = {
    "auction.are",  # imm auction storage
    "ceiling.are",  # system
    "enchant-eq.are",  # builder templates
    "limbo.are",  # death/limbo
    "micro_mob_generator.are",  # body parts factory
    "utility.are",  # system
}

# Realm Road progression — must all be reachable for campaign + quests
REQUIRED = {
    "midgaard.are",
    "realmroad.are",
    "borderkeep.are",
    "caveschaos.are",
    "hillgiant.are",
    "frosthold.are",
    "firepeak.are",
    "underdark.are",
    "vaultshadow.are",
    "elementaltemple.are",
    "tombwhispers.are",
    "demonweb.are",
    "dragonspire.are",
    "astralcourt.are",
    "school.are",
    "rocroad.are",
}


def main() -> int:
    rooms = load_world()
    vis = reachable_from(rooms, 3001)
    by = defaultdict(int)
    for v in vis:
        by[rooms[v]["file"]] += 1

    all_files = sorted({r["file"] for r in rooms.values()})
    disc = [f for f in all_files if f not in by]
    bad_disc = [f for f in disc if f not in ALLOW_DISCONNECTED]
    missing_req = sorted(REQUIRED - set(by))

    print(f"reachable rooms: {len(vis)} / {len(rooms)}")
    print(f"reachable areas: {len(by)} / {len(all_files)}")
    if disc:
        print("disconnected (allowed system zones only):")
        for f in disc:
            flag = "OK-system" if f in ALLOW_DISCONNECTED else "FAIL"
            print(f"  [{flag}] {f}")

    rc = 0
    if missing_req:
        print("FAIL: required areas not reachable:", ", ".join(missing_req))
        rc = 1
    if bad_disc:
        print("FAIL: unexpected disconnected areas:", ", ".join(bad_disc))
        rc = 1
    if rc == 0:
        print("connectivity: OK")
    return rc


if __name__ == "__main__":
    sys.exit(main())
