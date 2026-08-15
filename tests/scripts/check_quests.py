#!/usr/bin/env python3
"""
Verify auto-quest prerequisites against the current world files.

Mirrors generate_auto_quest() constraints from src/quest.c:
  - Quest object protos OBJ_VNUM_QUEST_MIN..MAX (66-80) must exist
  - Giver/target mobs: NPC, level in band, not SENTINEL/PET/shop,
    area not AREA_NOSHOW (area header 'S' line)
  - Path from ROOM_VNUM_TEMPLE (3001) to the mob's reset room must exist
    (HUNT_WORLD with doors treated as passable)

Exit 0 if quests can run for mid (p2) and high (p3) personality bands.
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AREA = ROOT / "area"
sys.path.insert(0, str(ROOT / "tools"))
from world_connect import load_world, reachable_from  # noqa: E402

TEMPLE = 3001
QUEST_OBJ_MIN, QUEST_OBJ_MAX = 66, 80
ACT_SENTINEL = 2
ACT_PET = 256

# Personality bands from quest.c (after commented-out low band)
BANDS = {
    "p2_mid": (40, 84),
    "p3_high": (100, 140),
}


def parse_area_noshow(path: Path) -> bool:
    t = path.read_text(encoding="latin-1", errors="replace")
    header = t.split("#ROOMS")[0] if "#ROOMS" in t else t[:800]
    return bool(re.search(r"^S\s", header, re.M))


def parse_object_vnums(path: Path) -> set[int]:
    t = path.read_text(encoding="latin-1", errors="replace")
    if "#OBJECTS" not in t:
        return set()
    sec = t.split("#OBJECTS", 1)[1]
    for mkr in ("#RESETS", "#SHOPS", "#SPECIALS", "#MOBPROGS", "#$"):
        if mkr in sec:
            sec = sec.split(mkr)[0]
            break
    return {int(x) for x in re.findall(r"^#(\d+)\s*$", sec, re.M) if int(x) > 0}


def parse_mobs(path: Path) -> list[dict]:
    t = path.read_text(encoding="latin-1", errors="replace")
    if "#MOBILES" not in t:
        return []
    sec = t.split("#MOBILES", 1)[1]
    for mkr in ("#OBJECTS", "#RESETS", "#SHOPS", "#$"):
        if mkr in sec:
            sec = sec.split(mkr)[0]
            break
    mobs = []
    parts = re.split(r"(?m)^#(\d+)\s*$", sec)
    i = 1
    while i + 1 < len(parts):
        vnum = int(parts[i])
        body = parts[i + 1]
        i += 2
        if vnum == 0:
            continue
        m = re.search(r"^(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+S\s*$", body, re.M)
        if not m:
            continue
        act = int(m.group(1))
        rest = body[m.end() :]
        lm = re.search(r"^\s*(-?\d+)\s+(-?\d+)\s*$", rest, re.M)
        if not lm:
            continue
        level = int(lm.group(1))
        fields = re.findall(r"([^~]*)~", body)
        short = fields[1].strip() if len(fields) > 1 else ""
        mobs.append(
            {
                "vnum": vnum,
                "level": level,
                "act": act,
                "short": short,
                "file": path.name,
            }
        )
    return mobs


def parse_shops(path: Path) -> set[int]:
    """Return mobile vnums that have shops (quest skips pShop)."""
    t = path.read_text(encoding="latin-1", errors="replace")
    if "#SHOPS" not in t:
        return set()
    sec = t.split("#SHOPS", 1)[1]
    for mkr in ("#SPECIALS", "#RESETS", "#MOBPROGS", "#$"):
        if mkr in sec:
            sec = sec.split(mkr)[0]
            break
    shops = set()
    for line in sec.splitlines():
        line = line.strip()
        if not line or line.startswith("*") or line.startswith("#"):
            continue
        toks = line.split()
        if toks and re.fullmatch(r"\d+", toks[0]):
            shops.add(int(toks[0]))
    return shops


def parse_resets(path: Path) -> list[tuple[int, int]]:
    """Return list of (mob_vnum, room_vnum) from M resets."""
    t = path.read_text(encoding="latin-1", errors="replace")
    if "#RESETS" not in t:
        return []
    sec = t.split("#RESETS", 1)[1]
    for mkr in ("#SHOPS", "#SPECIALS", "#MOBPROGS", "#$"):
        if mkr in sec:
            sec = sec.split(mkr)[0]
            break
    out = []
    for line in sec.splitlines():
        line = line.strip()
        if not line.startswith("M "):
            continue
        toks = line.split()
        # M 0 <mob> <limit> <room>
        if len(toks) >= 5 and toks[0] == "M":
            try:
                out.append((int(toks[2]), int(toks[4])))
            except ValueError:
                pass
    return out


def main() -> int:
    rc = 0
    print("=== Quest object protos (66-80) ===")
    found_objs: set[int] = set()
    for p in AREA.glob("*.are"):
        found_objs |= parse_object_vnums(p)
    missing = [v for v in range(QUEST_OBJ_MIN, QUEST_OBJ_MAX + 1) if v not in found_objs]
    if missing:
        print("FAIL: missing quest object vnums:", missing)
        rc = 1
    else:
        print(f"OK: all quest objects {QUEST_OBJ_MIN}-{QUEST_OBJ_MAX} defined")

    print("\n=== AREA_NOSHOW (header S) ===")
    noshow_files = set()
    for p in sorted(AREA.glob("*.are")):
        if parse_area_noshow(p):
            noshow_files.add(p.name)
            print(f"  NOSHOW  {p.name}")
    print(f"({len(noshow_files)} areas excluded from quest mob selection)")

    print("\n=== Load world graph from temple ===")
    rooms = load_world()
    vis = reachable_from(rooms, TEMPLE)
    print(f"rooms reachable from {TEMPLE}: {len(vis)} / {len(rooms)}")
    if TEMPLE not in rooms:
        print("FAIL: temple room missing")
        return 1

    # Build eligible live-spawn candidates from resets
    print("\n=== Eligible reset mobs by quest band (pathfindable, not NOSHOW) ===")
    all_mobs: dict[int, dict] = {}
    shops: set[int] = set()
    for p in AREA.glob("*.are"):
        for m in parse_mobs(p):
            all_mobs[m["vnum"]] = m
        shops |= parse_shops(p)

    for band_name, (lo, hi) in BANDS.items():
        eligible = []
        by_area: dict[str, int] = defaultdict(int)
        for p in AREA.glob("*.are"):
            if p.name in noshow_files:
                continue
            for mob_v, room_v in parse_resets(p):
                m = all_mobs.get(mob_v)
                if not m:
                    continue
                if m["level"] < lo or m["level"] > hi:
                    continue
                if m["act"] & ACT_SENTINEL or m["act"] & ACT_PET:
                    continue
                if mob_v in shops:
                    continue
                if room_v not in rooms or room_v not in vis:
                    continue
                eligible.append((m, room_v))
                by_area[p.name] += 1

        print(f"\n{band_name} levels {lo}-{hi}: {len(eligible)} reset placements pathfindable from temple")
        if not eligible:
            print(f"FAIL: no eligible quest mobs for {band_name}")
            rc = 1
        else:
            print("  top areas:", sorted(by_area.items(), key=lambda x: -x[1])[:10])
            # sample dragonfall gen areas
            gen = [a for a in by_area if a in {
                "realmroad.are", "borderkeep.are", "caveschaos.are", "hillgiant.are",
                "frosthold.are", "firepeak.are", "underdark.are", "vaultshadow.are",
                "elementaltemple.are", "tombwhispers.are", "demonweb.are",
                "dragonspire.are", "astralcourt.are",
            }]
            print("  Great Spine campaign areas with eligible mobs:", sorted(gen) or "(none in this band)")

    print("\n=== Campaign spine quest pathfind spot-check ===")
    spine = [
        ("borderkeep.are", 22600),
        ("firepeak.are", 23000),
        ("tombwhispers.are", 23400),
        ("astralcourt.are", 23700),
        ("midgaard.are", 3001),
        ("vecna_tomb.are", 20600),
        ("crimson_mist.are", 8350),
    ]
    for fname, entry in spine:
        ok = entry in vis
        print(f"  {'OK' if ok else 'FAIL'} temple -> {fname} entry {entry}")
        if not ok:
            rc = 1

    if rc == 0:
        print("\nquest check: OK (objects present, pathfindable pools for mid and high bands)")
    else:
        print("\nquest check: FAILED")
    return rc


if __name__ == "__main__":
    sys.exit(main())
