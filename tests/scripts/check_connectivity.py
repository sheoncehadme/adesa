#!/usr/bin/env python3
"""
Assert a new player can walk to every player-facing area.

New characters spawn at ROOM_VNUM_SCHOOL (3700). From there they must reach
the Heart-Pulse Sanctum (3001), the Scar, and every non-system area (including
the full Great Spine campaign). System / builder zones may stay disconnected.

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
    "immort.are",  # staff plane (may have one accidental link)
    "players.are",  # housing plane
}

# Seeds: new-player school entrance (primary) and temple (quest pathfinding)
SEED_SCHOOL = 3700
SEED_TEMPLE = 3001

# Campaign + hub must be on the new-player graph
REQUIRED = {
    "midgaard.are",
    "school.are",
    "rocroad.are",
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
}


def main() -> int:
    rooms = load_world()
    vis_school = reachable_from(rooms, SEED_SCHOOL)
    vis_temple = reachable_from(rooms, SEED_TEMPLE)

    by_school = defaultdict(int)
    for v in vis_school:
        by_school[rooms[v]["file"]] += 1

    all_files = sorted({r["file"] for r in rooms.values()})
    player_files = [f for f in all_files if f not in ALLOW_DISCONNECTED]

    disc_school = [f for f in player_files if f not in by_school]
    missing_req = sorted(REQUIRED - set(by_school))

    print(f"from school {SEED_SCHOOL}: {len(vis_school)} / {len(rooms)} rooms")
    print(f"from temple {SEED_TEMPLE}: {len(vis_temple)} / {len(rooms)} rooms")
    n_player_hit = sum(1 for f in player_files if f in by_school)
    print(f"player areas reachable from school: {n_player_hit} / {len(player_files)}")

    # school must reach temple (egress into the Scar)
    if SEED_TEMPLE not in vis_school:
        print(f"FAIL: school {SEED_SCHOOL} cannot reach temple {SEED_TEMPLE}")
        temple_ok = False
    else:
        print(f"OK: school {SEED_SCHOOL} -> temple {SEED_TEMPLE}")
        temple_ok = True

    # campaign end must be reachable from school
    endgame = [v for v, r in rooms.items() if r["file"] == "astralcourt.are"]
    end_ok = any(v in vis_school for v in endgame)
    print("OK: Axis-Heart / astralcourt reachable from school" if end_ok else "FAIL: astralcourt not reachable from school")

    if disc_school:
        print("FAIL: player areas not reachable from school:")
        for f in disc_school:
            print(f"  - {f}")
    else:
        print("OK: every player-facing area reachable from school")

    # orphan room report (warn only if >5% of an area missing)
    rc = 0
    if not temple_ok or not end_ok or missing_req or disc_school:
        rc = 1
    if missing_req:
        print("FAIL: required areas not reachable:", ", ".join(missing_req))

    orphans = []
    for f in player_files:
        total = sum(1 for r in rooms.values() if r["file"] == f)
        hit = by_school.get(f, 0)
        if total and hit < total and (total - hit) > max(2, total // 20):
            orphans.append((f, hit, total))
    if orphans:
        print("WARN: significant unreachable rooms within areas (from school):")
        for f, hit, total in sorted(orphans):
            print(f"  {f}: {hit}/{total}")

    if rc == 0:
        print("connectivity: OK (new-player graph)")
    return rc


if __name__ == "__main__":
    sys.exit(main())
