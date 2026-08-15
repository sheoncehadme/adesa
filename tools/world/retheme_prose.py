#!/usr/bin/env python3
"""
Rewrite room (and optionally mobile) prose in stock .are files while preserving
vnums, exits, flags, resets, and structure.

Usage:
  python3 tools/world/retheme_prose.py area/confusn.are --pack bone_lattice
  python3 tools/world/retheme_prose.py --batch next   # crimson_*, confusn, vecna
"""
from __future__ import annotations

import argparse
import random
import re
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]


def split_sections(text: str) -> Tuple[str, str, str]:
    """Return (before_rooms, rooms_body, after_rooms)."""
    m = re.search(r"^#ROOMS\b", text, re.M)
    if not m:
        raise ValueError("no #ROOMS section")
    start = m.end()
    rest = text[start:]
    m2 = re.search(r"\n#(MOBILES|OBJECTS|RESETS|SHOPS|SPECIALS|MOBPROGS|\$)\b", rest)
    if m2:
        rooms = rest[: m2.start()]
        after = rest[m2.start() + 1 :]  # keep leading #SECTION
        # m2.start() points at \n before #; include that newline in rooms end
        after = rest[m2.start() + 1 :]
        if after.startswith("\n"):
            after = after[1:]
        # Actually rest[m2.start():] begins with \n#MOBILES
        after = rest[m2.start() + 1 :]  # strip one \n -> #MOBILES...
        return text[: start], rooms, after
    return text[:start], rest, ""


def parse_rooms(rooms_body: str) -> List[dict]:
    """Parse room blocks. Each has vnum, name, desc, tail (from flags line onward)."""
    rooms: List[dict] = []
    # split on room headers but keep
    parts = re.split(r"(?m)^#(\d+)\s*$", rooms_body)
    # parts[0] is preamble (often empty or whitespace)
    # then pairs: vnum, body
    i = 1
    while i + 1 < len(parts):
        vnum = int(parts[i])
        body = parts[i + 1]
        i += 2
        if vnum == 0:
            rooms.append({"vnum": 0, "raw": f"#{vnum}\n{body}", "is_end": True})
            continue
        # name~ at start
        nm = re.match(r"\s*(.*?)~", body, re.S)
        if not nm:
            rooms.append({"vnum": vnum, "raw": f"#{vnum}\n{body}", "passthrough": True})
            continue
        name = nm.group(1).replace("\r", "")
        rest = body[nm.end() :]
        # Description ends at a '~' (end of line or alone) followed by room flags
        # (exactly two integers) or D/E/S. Exit lines are "0 -1 vnum" (three ints)
        # and must not be treated as flags.
        end = None
        for cand in re.finditer(r"~", rest):
            after = rest[cand.end() :].lstrip(" \t\r\n")
            if not after:
                continue
            first = after.split("\n", 1)[0].strip()
            if re.match(r"D[0-5]\b", first) or first in ("E", "S"):
                end = cand
                break
            toks = first.split()
            if len(toks) == 2 and all(re.fullmatch(r"-?\d+", t) for t in toks):
                end = cand
                break
        if end is None:
            rooms.append({"vnum": vnum, "raw": f"#{vnum}\n{body}", "passthrough": True})
            continue
        desc = rest[: end.start()].strip("\n")
        tail = rest[end.end() :]
        if not tail.startswith("\n"):
            tail = "\n" + tail
        rooms.append(
            {
                "vnum": vnum,
                "name": name,
                "desc": desc,
                "tail": tail,
                "passthrough": False,
            }
        )
    return rooms


def emit_rooms(rooms: List[dict]) -> str:
    out: List[str] = []
    for r in rooms:
        if r.get("passthrough") or r.get("is_end") or r.get("raw"):
            if r.get("raw"):
                out.append(r["raw"] if r["raw"].startswith("#") else r["raw"])
            continue
        name = r["name"]
        if not name.endswith("\n"):
            # name is without trailing content after ~
            pass
        desc = r["desc"]
        # normalize desc: blank line between paragraphs if single newlines only
        # keep as multi-line with \n\n between sentences for mud readability
        out.append(f"#{r['vnum']}\n")
        out.append(f"{name}~\n")
        out.append(desc.rstrip() + "\n")
        out.append("~\n")
        # tail currently starts with \n after ~; strip one \n since we wrote ~\n
        tail = r["tail"]
        if tail.startswith("\n"):
            tail = tail[1:]
        out.append(tail)
    return "".join(out)


def wrap_desc(paragraphs: List[str], color: str = "@@g") -> str:
    """Build a mud description with optional color wrapper."""
    chunks = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        chunks.append(f"{color}{p}@@N" if not p.startswith("@@") else p)
    return "\n\n".join(chunks)


# ---------------------------------------------------------------------------
# Theme packs: (index, vnum, old_name) -> (new_name, new_desc)
# ---------------------------------------------------------------------------

def pack_bone_lattice(rng: random.Random, n: int, vnum: int, old_name: str) -> Tuple[str, str]:
    places = [
        "Lattice Threshold", "Bone Crossway", "Marrow Riddle Path", "Calcified Arch",
        "Whispering Lattice", "Spiral of Fingers", "Cage of Ribs", "Ivory Blind",
        "False Opening", "True Fracture", "Echo Chamber of Bone", "Dust of Ages",
        "Needle Corridor", "Joint of the Wyrm", "Clatter Gallery", "Sealed Socket",
        "Lattice Heart", "Mirror of Marrow", "Fallen Tooth Bridge", "Knuckle Stair",
        "Veil of Ossein", "Bleached Garden", "Rattle Court", "Hollow Coccyx",
        "Spine-Wire Tunnel", "Puzzle of Seven Bones", "Antechamber of Dust",
    ]
    name = places[n % len(places)]
    if n == 0:
        name = "Edge of the Bone-Lattice"
    aspects = [
        "Interlocked bone forms walls that almost make sense, then refuse to.",
        "Every step clicks as if walking on a vast dry instrument.",
        "Gaps in the lattice show only more lattice, receding forever.",
        "A slow residual pulse vibrates through the structure - Scar-echo, not a heart.",
        "Old explorers' marks are scored into ivory and half-overgrown with mineral marrow.",
        "The air tastes of chalk and old star-metal dust.",
        "Sometimes a corridor ends where it began; the lattice rearranges when unwatched.",
        "Light fails a few feet ahead, as if the bones drink it.",
    ]
    hooks = [
        "You feel the First Wyrm's fall still sorting itself into geometry.",
        "Something about this place is a wound that learned to maze.",
        "The Scar's memory of impact is written here in white architecture.",
        "Ash-Claimers have left scrap markers; few return the same way they left.",
    ]
    d1, d2 = rng.sample(aspects, 2)
    hook = hooks[n % len(hooks)]
    desc = wrap_desc(
        [
            f"{name}.",
            d1,
            d2,
            hook,
        ],
        "@@m",
    )
    return f"@@m{name}@@N", desc


def pack_blood_tide(rng: random.Random, n: int, vnum: int, old_name: str) -> Tuple[str, str]:
    places = [
        "Purple Seep", "Tide of Quicksilver Blood", "Fog of Arteries", "Marsh of Clot",
        "Reed-Bed of Iron", "Slick Causeway", "Blood-Glass Pool", "Listening Mud",
        "Aurora over the Marsh", "Stilt Path", "Drowned Scale", "Bubbling Font",
        "Leech-Grass Flat", "Crimson Horizon", "Stillwater of the Plunge",
        "Vapor Cathedral", "Soft Bottom", "Waderist of Veins", "Rusted Landing",
        "Heart-Echo Shallows", "Salt of Star-Metal", "Black Mirror Mere",
    ]
    name = places[n % len(places)]
    if n == 0:
        name = "Rim of the Blood-Tide"
    aspects = [
        "The fog is not weather - it is thinned dragon-blood held in air.",
        "Each step sinks into mud the color of old wine and molten copper.",
        "Reeds chime when the residual pulse of the Scar passes under the marsh.",
        "Reflections show the sky before the Plunge for a heartbeat, then vanish.",
        "Something large turns far under the surface without breaking it.",
        "Scale-shards stick up like gravestones, polished by endless damp.",
        "Your skin prickles with dragon-touched mana; breath tastes of iron.",
        "Will-o-wisps of dying fire drift and refuse to cast true shadows.",
    ]
    d1, d2 = rng.sample(aspects, 2)
    desc = wrap_desc(
        [
            f"{name}.",
            d1,
            d2,
            "The Blood-Tide Marshes are a Lower Wound remnant: arteries of the Sky-Breaker gone soft and wide.",
        ],
        "@@m",
    )
    return f"@@m{name}@@N", desc


def pack_rib_cathedral(rng: random.Random, n: int, vnum: int, old_name: str) -> Tuple[str, str]:
    places = [
        "Nave of the Ninth Rib", "Choir of Fractures", "Transept of Scale", "Apse of Ember",
        "Clerestory of Aurora", "Crypt Stair", "Pulpit of Bone", "Side Chapel of Breath",
        "Processional of Ash", "High Vault", "Flying Buttress of Ivory", "Rose Window of Glass-Fire",
        "Sacristy of Star-Metal", "Confessional Crack", "Bell-Empty Tower", "Ambulatory Mist",
        "Chapter House of Echoes", "Scriptorium Dust", "Reliquary Niche", "Outer Garth",
        "Gate of Folded Wings", "Sanctum Threshold", "Gallery of Murals", "Under-choir",
    ]
    name = places[n % len(places)]
    if n == 0:
        name = "Approach to the Rib-Cage Cathedrals"
    aspects = [
        "Ribs arch overhead like a nave built by impact rather than hands.",
        "Echoes return a half-second late, as if the stone still falls.",
        "Murals of the Plunge cover every flat surface - wings, fire, the wound.",
        "Residual godfire glows faintly in the joints of the architecture.",
        "Scalewright graffiti and Spinewarden seals compete on the pillars.",
        "Wind through bone-gaps sounds almost like a hymn, almost like a roar.",
        "The floor is impact-glass, smooth and cold, reflecting a sky that is not there.",
        "Somewhere deeper, a slow heart-pulse is felt more than heard.",
    ]
    d1, d2 = rng.sample(aspects, 2)
    desc = wrap_desc(
        [
            f"{name}.",
            d1,
            d2,
            "Civilizations have prayed here to the fall itself; some still do.",
        ],
        "@@R",
    )
    return f"@@R{name}@@N", desc


def pack_memory_vault(rng: random.Random, n: int, vnum: int, old_name: str) -> Tuple[str, str]:
    places = [
        "Vault Threshold", "Alabaster Memory Hall", "Platinum Vein Gallery", "Crypt of Unfinished Purpose",
        "Watch-Alcove of the Fall", "Seal of the First Age", "Library of Echoes", "False Phylactery Room",
        "True Name Vault", "Antechamber of Judgment", "Mirror of the Unfallen Sky", "Bone Pedestal Hall",
        "Relic of the Axis", "Whisper Corridor", "Door of Seven Seals", "Chamber of Last Breath",
        "Ossuary of Witnesses", "Star-Metal Coffers", "Silent Throne Approach", "Plunge-Mark Floor",
        "Guardian Circle", "Inner Vault", "Heart of Memory", "Outer Ward",
    ]
    name = places[n % len(places)]
    if n == 0 or "Lair" in old_name or "Final Crypt" in old_name:
        if n < 3:
            name = "Memory-of-the-Plunge Vault"
    # strip Vecna from identity entirely
    aspects = [
        "White stone and platinum veins remember a power that was never a man.",
        "This vault stores memory of the Plunge, not a lich's ego - though thieves once claimed otherwise.",
        "Light falls like judgment; dust hangs motionless until you move.",
        "Inscriptions shift between languages when you look away.",
        "The Scar's residual will presses on your thoughts: finish, prevent, become.",
        "Shelves hold scale-relics and sealed jars of breath-mist.",
        "A cold intelligence here is the Wyrm's unfinished purpose, not a necromancer's name.",
        "Doors seal with runes older than the new age and younger than the firmament.",
    ]
    d1, d2 = rng.sample(aspects, 2)
    desc = wrap_desc(
        [
            f"{name}.",
            d1,
            d2,
            "Echo-Cult graffiti has been scraped away by Spinewardens - and re-carved by someone else.",
        ],
        "@@d",
    )
    return f"@@d{name}@@N", desc


PACKS: Dict[str, Callable] = {
    "bone_lattice": pack_bone_lattice,
    "blood_tide": pack_blood_tide,
    "rib_cathedral": pack_rib_cathedral,
    "memory_vault": pack_memory_vault,
}

BATCH_NEXT = [
    ("area/confusn.are", "bone_lattice", 9601),
    ("area/crimson_mist.are", "blood_tide", 8350),
    ("area/crimson_castle.are", "rib_cathedral", None),
    ("area/vecna_tomb.are", "memory_vault", None),
]


def retheme_file(path: Path, pack: str, seed: int = 42) -> int:
    text = path.read_text(encoding="latin-1", errors="replace")
    before, rooms_body, after = split_sections(text)
    rooms = parse_rooms(rooms_body)
    rng = random.Random(seed ^ hash(path.name) & 0xFFFFFFFF)
    fn = PACKS[pack]
    count = 0
    idx = 0
    for r in rooms:
        if r.get("passthrough") or r.get("is_end") or r.get("raw") and "name" not in r:
            continue
        if "name" not in r:
            continue
        new_name, new_desc = fn(rng, idx, r["vnum"], r["name"])
        r["name"] = new_name
        r["desc"] = new_desc
        idx += 1
        count += 1
    new_rooms = emit_rooms(rooms)
    # reassemble
    if not before.endswith("\n"):
        before += "\n"
    # before includes through #ROOMS\n ideally
    if not before.rstrip().endswith("#ROOMS"):
        # split_sections left before ending at end of #ROOMS line content
        pass
    out = before + new_rooms
    if after:
        if not out.endswith("\n"):
            out += "\n"
        out += after if after.startswith("#") else after
    # ensure file ends reasonably
    path.write_bytes(out.encode("latin-1", errors="replace"))
    return count


def retheme_mobiles_vecna(path: Path) -> int:
    """Strip Vecna name from mobile short/long/keywords in vecna_tomb."""
    t = path.read_text(encoding="latin-1", errors="replace")
    reps = [
        ("Vecna's", "the Vault's"),
        ("Vecna", "the Remembered"),
        ("vecna", "remembered"),
        ("lich king", "memory-wraith lord"),
        ("Lich King", "Memory-Wraith Lord"),
    ]
    n = 0
    for a, b in reps:
        c = t.count(a)
        if c:
            t = t.replace(a, b)
            n += c
    path.write_bytes(t.encode("latin-1", errors="replace"))
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", type=Path)
    ap.add_argument("--pack", choices=sorted(PACKS.keys()))
    ap.add_argument("--batch", choices=["next"])
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    if args.batch == "next":
        total = 0
        for rel, pack, _ in BATCH_NEXT:
            p = ROOT / rel
            n = retheme_file(p, pack, args.seed)
            print(f"{rel}: rewrote {n} rooms ({pack})")
            total += n
            if "vecna" in rel:
                m = retheme_mobiles_vecna(p)
                print(f"{rel}: mobile string replacements {m}")
        return 0

    if not args.path or not args.pack:
        ap.error("path + --pack, or --batch next")
    n = retheme_file(args.path, args.pack, args.seed)
    print(f"rewrote {n} rooms in {args.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
