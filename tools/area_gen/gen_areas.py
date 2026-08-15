#!/usr/bin/env python3
"""
Generate Dragonfall Scar progression areas (ACK!MUD / Adesa).

Campaign: ascend the wound from the Great Spine Waystation through the
Wound-lands to the Axis-Heart Sanctum. Lore: docs/dragonfall-lore.md

Usage:
  python3 tools/area_gen/gen_areas.py [--out area] [--lst data/area.lst]

Emits valid #AREA files with rooms, mobiles, objects, and resets that boot
cleanly on Adesa (revision Z 3 mobile format).
"""
from __future__ import annotations

import argparse
import math
import os
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Wear / item constants (merc.h)
# ---------------------------------------------------------------------------
ITEM_TAKE = 1
ITEM_WEAR_FINGER = 2
ITEM_WEAR_NECK = 4
ITEM_WEAR_BODY = 8
ITEM_WEAR_HEAD = 16
ITEM_WEAR_LEGS = 32
ITEM_WEAR_FEET = 64
ITEM_WEAR_HANDS = 128
ITEM_WEAR_ARMS = 256
ITEM_WEAR_SHIELD = 512
ITEM_WEAR_ABOUT = 1024
ITEM_WEAR_WAIST = 2048
ITEM_WEAR_WRIST = 4096
ITEM_WIELD = 8192
ITEM_HOLD = 16384
ITEM_WEAR_FACE = 32768
ITEM_WEAR_EAR = 65536

ITEM_LIGHT = 1
ITEM_WEAPON = 5
ITEM_ARMOR = 9
ITEM_POTION = 10
ITEM_FOOD = 19
ITEM_MONEY = 20
ITEM_FOUNTAIN = 25

ITEM_GLOW = 1
ITEM_HUM = 2
ITEM_MAGIC = 64
ITEM_BLESS = 256

APPLY_STR = 1
APPLY_DEX = 2
APPLY_INT = 3
APPLY_WIS = 4
APPLY_CON = 5
APPLY_MANA = 12
APPLY_HIT = 13
APPLY_MOVE = 14
APPLY_AC = 17
APPLY_HITROLL = 18
APPLY_DAMROLL = 19

# Weapon damage types (value[3]) — common stock values
WPN_SWORD = 3
WPN_MACE = 7
WPN_DAGGER = 11
WPN_AXE = 1
WPN_FLAIL = 5
WPN_SPEAR = 9

ACT_NPC = 1
ACT_SENTINEL = 2
ACT_SCAVENGER = 4
ACT_AGGRESSIVE = 32
ACT_STAY_AREA = 64

DIR_NAMES = ["north", "east", "south", "west", "up", "down"]
OPPOSITE = [2, 3, 0, 1, 5, 4]


def tilde(s: str) -> str:
    return s.replace("~", "-") + "~\n"


def wear_for(slot: str) -> int:
    m = {
        "wield": ITEM_TAKE | ITEM_WIELD,
        "body": ITEM_TAKE | ITEM_WEAR_BODY,
        "head": ITEM_TAKE | ITEM_WEAR_HEAD,
        "legs": ITEM_TAKE | ITEM_WEAR_LEGS,
        "feet": ITEM_TAKE | ITEM_WEAR_FEET,
        "hands": ITEM_TAKE | ITEM_WEAR_HANDS,
        "arms": ITEM_TAKE | ITEM_WEAR_ARMS,
        "shield": ITEM_TAKE | ITEM_WEAR_SHIELD,
        "about": ITEM_TAKE | ITEM_WEAR_ABOUT,
        "waist": ITEM_TAKE | ITEM_WEAR_WAIST,
        "wrist": ITEM_TAKE | ITEM_WEAR_WRIST,
        "finger": ITEM_TAKE | ITEM_WEAR_FINGER,
        "neck": ITEM_TAKE | ITEM_WEAR_NECK,
        "hold": ITEM_TAKE | ITEM_HOLD,
        "ear": ITEM_TAKE | ITEM_WEAR_EAR,
        "face": ITEM_TAKE | ITEM_WEAR_FACE,
        "light": ITEM_TAKE,
    }
    return m[slot]


# Wear location numbers for equip resets (WEAR_*)
WEAR_LOC = {
    "light": 0,
    "finger": 1,
    "neck": 3,
    "body": 5,
    "head": 6,
    "legs": 7,
    "feet": 8,
    "hands": 9,
    "arms": 10,
    "shield": 11,
    "about": 12,
    "waist": 13,
    "wrist": 14,
    "wield": 16,
    "hold": 17,
    "face": 18,
    "ear": 19,
}


@dataclass
class Affect:
    location: int
    modifier: int


@dataclass
class ObjDef:
    vnum: int
    keywords: str
    short: str
    long: str
    item_type: int
    extra: int
    wear: int
    item_apply: int
    values: Tuple[int, int, int, int]
    weight: int
    level: int
    affects: List[Affect] = field(default_factory=list)
    slot: str = "hold"  # for equip resets


@dataclass
class MobDef:
    vnum: int
    keywords: str
    short: str
    long: str
    description: str
    level: int
    sex: int = 1
    align: int = -200
    act: int = ACT_NPC | ACT_AGGRESSIVE | ACT_STAY_AREA
    affected: int = 0
    ac: int = 0
    hr: int = 0
    dr: int = 0
    hp_mod: int = 0
    mana_mod: int = 0
    race: int = 0
    equip: List[int] = field(default_factory=list)  # object vnums
    inventory: List[int] = field(default_factory=list)


@dataclass
class RoomDef:
    vnum: int
    name: str
    desc: str
    flags: int = 0
    sector: int = 0
    exits: dict = field(default_factory=dict)  # dir -> target vnum
    x: int = 0
    y: int = 0


@dataclass
class ZoneSpec:
    filename: str
    title: str
    keyword: str
    label: str
    min_level: int
    max_level: int
    vbase: int
    vsize: int
    theme: str
    n_rooms: int
    reset_msg: str
    is_hub: bool = False


# ---------------------------------------------------------------------------
# Campaign definition
# ---------------------------------------------------------------------------
ZONES: List[ZoneSpec] = [
    ZoneSpec("realmroad.are", "@@WGreat Spine Waystation@@N", "spineway",
             "@@W{ @@yHUB@@W }@@N", 1, 90, 22500, 100,
             "hub", 36, "The Great Spine hums underfoot; expedition bells ring along the Scar.~", True),
    ZoneSpec("borderkeep.are", "@@yRib-Cage Outer Watch@@N", "ribcagewatch",
             "@@W{ @@r 1 10@@W }@@N", 1, 10, 22600, 100,
             "border", 49, "A Spinewarden horn echoes from rib-bone battlements.~"),
    ZoneSpec("caveschaos.are", "@@dClaw-Mark Ravines@@N", "clawravines",
             "@@W{ @@r 5 15@@W }@@N", 5, 15, 22700, 100,
             "caves", 49, "Stone still bears the First Wyrm's claw-scars.~"),
    ZoneSpec("hillgiant.are", "@@yBone-Bridge Canyons@@N", "bonebridge",
             "@@W{ @@r15 25@@W }@@N", 15, 25, 22800, 100,
             "hillgiant", 49, "A span of fused vertebrae groans under giant steps.~"),
    ZoneSpec("frosthold.are", "@@cWing-Shadow Valleys@@N", "wingshadow",
             "@@W{ @@r25 35@@W }@@N", 25, 35, 22900, 100,
             "frost", 49, "Permanent twilight pools where a wing once blotted the sun.~"),
    ZoneSpec("firepeak.are", "@@RDying-Fire Caldera@@N", "dyingfire",
             "@@W{ @@r35 45@@W }@@N", 35, 45, 23000, 100,
             "fire", 49, "Residual dragon-fire still cracks the caldera rim.~"),
    ZoneSpec("underdark.are", "@@mMarrow-River Depths@@N", "marrowdepths",
             "@@W{ @@r40 50@@W }@@N", 40, 50, 23100, 100,
             "underdark", 49, "Quicksilver marrow streams whisper below the Scar.~"),
    ZoneSpec("vaultshadow.are", "@@dStar-Metal Veins@@N", "starmetal",
             "@@W{ @@r50 60@@W }@@N", 50, 60, 23200, 100,
             "vault", 49, "Molten star-metal cools in galleries of scale.~"),
    ZoneSpec("elementaltemple.are", "@@eWill-Fragment Temples@@N", "willtemples",
             "@@W{ @@r55 65@@W }@@N", 55, 65, 23300, 100,
             "elemental", 49, "Shards of the Wyrm's will hum in fourfold shrines.~"),
    ZoneSpec("tombwhispers.are", "@@WMemory-Bone Catacombs@@N", "memorybone",
             "@@W{ @@r60 70@@W }@@N", 60, 70, 23400, 100,
             "tomb", 49, "Bones remember the Plunge and speak in dust.~"),
    ZoneSpec("demonweb.are", "@@RResidual-Dragonstorm@@N", "dragonstorm",
             "@@W{ @@r70 80@@W }@@N", 70, 80, 23500, 100,
             "demonweb", 49, "Storm-silk still falling from the firmament tears the air.~"),
    ZoneSpec("dragonspire.are", "@@RFossilized Wing Ruins@@N", "fossilwing",
             "@@W{ @@r75 85@@W }@@N", 75, 85, 23600, 100,
             "dragon", 49, "A fossil wing spans the sky like a broken cathedral.~"),
    ZoneSpec("astralcourt.are", "@@aAxis-Heart Sanctum@@N", "axisheart",
             "@@W{ @@r80 90@@W }@@N", 80, 90, 23700, 100,
             "astral", 49, "Here the new age can still be rewritten.~"),
]


THEME = {
    "hub": {
        "room_names": [
            "Spine Crossroads", "Expedition Yard", "Waystation Inn Court",
            "Scalewright Stalls", "Shrine of Safe Return", "Portal Circle of Bone",
            "Drake-Stable Yard", "Woundwalker Notice Board", "Heart-Pulse Fountain",
            "South Scar Gate", "North Scar Gate", "East Ravine Trailhead",
            "West Glass Cliffs Path", "Adventurer Camp", "Scale-Forge Yard",
            "Marrow-Circle Tent", "Provisioner's Cart", "Story-Fire Ring",
            "Spinewarden Post", "Signpost of the Plunge", "Wagon Ring of Ash",
            "Hitching Posts", "Map of the Wound", "Guild of Explorers Board",
            "Traveler's Rest", "Bone-Bench Alcove", "Aurora Lantern Row",
            "Spine Path", "Supply Depot", "Watchtower of Rib",
            "Old Milestone of Scale", "Copper Bell Tower", "Grain Silo of the Scar",
            "Rain Shelter", "Well of Welcome", "Roadside Heart-Chapel",
        ],
        "mob_names": [
            ("scalewright merchant", "a scalewright merchant", "A scalewright merchant weighs scale-shard."),
            ("spinewarden", "a spinewarden", "A spinewarden watches the traffic of the Scar."),
            ("stablehand", "a drake-stable hand", "A stable hand brushes a pack-drake."),
            ("marrow healer", "a marrow-circle healer", "A marrow-circle healer offers bandages."),
            ("storyteller", "a scar storyteller", "A storyteller speaks of the Sky-Breaker's fall."),
            ("porter", "a hired porter", "A hired porter waits for expedition work."),
            ("woundwalker scout", "a woundwalker scout", "A woundwalker scout studies the canyon rim."),
            ("scale-forge smith", "a scale-forge smith", "A smith hammers living-stone scale."),
        ],
        "boss": ("road warden", "the Spinewarden Captain", "The Spinewarden Captain surveys the waystation."),
        "terrain": "fused dragonbone underfoot and wagon ruts of ash-glass",
        "weapon": "spine shortsword",
        "set": "Waystation",
    },
    "border": {
        "room_names": [
            "Rib Courtyard", "Outer Bone Gatehouse", "Watch Barracks",
            "Scale Armory", "Rib Watchtower Stair", "Curtain of Vertebrae",
            "Pack-Drake Stables", "Mess Hall of Ash", "Heart-Chapel Nave", "Inner Bailey of Bone",
            "Well of Seeps", "Practice Yard", "North Rib Wall", "South Rib Wall",
            "East Bastion", "West Bastion", "Supply Cellar", "Captain's Office",
            "Recruit Quarters", "Postern of Glass", "Moat of Impact-Glass", "Drawbridge of Scale",
            "Guardroom", "Signal Aurora Platform", "Scale-Forge", "Tannery of Hide",
            "Marrow-Moss Garden", "Outer Ditch", "Palisade of Shard", "Scout Post",
            "Scar Trail", "Hill Overlook", "Fog Bank Edge", "Campfire Ring",
            "Wagon Barricade", "Ashy Approach", "Stone Arch of Claw", "Flagpole Court",
            "Cistern", "Kennel Run", "Siege Ladder Shed", "Arrow Slit Corridor",
            "Commander's Balcony", "Storage Loft", "Root Cellar", "Chapel Crypt",
            "Hidden Alcove", "Secret Stair", "Outer Watch",
        ],
        "mob_names": [
            ("ash-claimer scout", "an ash-claimer scout", "An ash-claimer scout hisses and flees then returns."),
            ("scar raider", "a scar raider", "A scar raider brandishes a rusty blade."),
            ("bone-thug", "a bone-thug", "A bone-thug glares hungrily."),
            ("bandit", "a ravine bandit", "A ravine bandit eyes your purse."),
            ("shard rat", "a shard-rat", "A shard-rat squeals among scale dust."),
            ("watch recruit", "a spinewarden recruit", "A recruit trains with a wooden sword."),
            ("wall archer", "a rib-wall archer", "A wall archer nocks an arrow."),
            ("echo-cult acolyte", "an echo-cult acolyte", "An acolyte mutters of a second plunge."),
        ],
        "boss": ("border chief", "the Outer Watch Castellan", "The Outer Watch Castellan stands ready."),
        "terrain": "rib-bone walls and trampled ash-grass",
        "weapon": "watch shortsword",
        "set": "OuterWatch",
    },
    "caves": {
        "room_names": [
            "Claw-Mark Mouth", "Dripping Score-Tunnel", "Bat Chamber", "Fungus Grotto",
            "Ash-Claimer Warren", "Raider Den", "Brute Barracks", "Tribal Shrine of Fall",
            "Bone Pit", "Underground Seep", "Stalactite Hall", "Collapsed Gallery",
            "Torchlit Cavern", "Slave Pens", "Storage Niche", "Mushroom Farm",
            "Chieftain's Cave", "Guard Post", "Narrow Crawl", "Echoing Dome",
            "Sooty Camp", "Weapon Cache", "Idol of the Plunge", "Sacrificial Altar",
            "Side Tunnel", "Dead End Crevasse", "Waterfall Cave", "Muddy Hollow",
            "Crystal Vein", "Root-choked Passage", "Fissure Bridge", "Lower Gallery",
            "Upper Ledge", "Smoke Hole", "Hidden Cache", "Watch Fissure",
            "Totem Circle", "Rubble Slope", "Damp Landing", "Cold Pool",
            "Pale Glow Room", "Ash Circle", "War Drum Hollow", "Meat Rack Cave",
            "Trophy Wall", "Thorn Barrier", "Oil Slick Floor", "Ambush Bend",
            "Escape Chimney",
        ],
        "mob_names": [
            ("claw ravine warrior", "a ravine warrior", "A ravine warrior snarls."),
            ("spearman", "a scar spearman", "A scar spearman jabs the air."),
            ("brute", "a scar brute", "A scar brute roars a challenge."),
            ("young trollkin", "a young cave troll", "A young cave troll sniffs hungrily."),
            ("ceiling hanger", "a darkmantle", "A darkmantle clings to the ceiling."),
            ("reeking crawler", "a reeking crawler", "A crawler reeks of marsh-marrow."),
            ("bugbear", "a deep thug", "A deep thug looms in the dark."),
            ("warpriest", "a fall-warpriest", "A warpriest raises a bloody idol of the Plunge."),
        ],
        "boss": ("chaos chieftain", "the Ravine Chieftain", "The Ravine Chieftain bellows from a claw-scored throne."),
        "terrain": "claw-scored stone and tribal refuse",
        "weapon": "notched claw-axe",
        "set": "ClawMark",
    },
    "hillgiant": {
        "room_names": [
            "Canyon Path", "Giant Footprint Mud", "Bone-Bridge Gates", "Courtyard Muck",
            "Great Hall of Vertebrae", "Feasting Table", "Kitchen Hearth", "Larder",
            "Barracks Bunks", "Weapon Rack Room", "Chief's Throne", "Trophy Hall",
            "Slave Pens", "Dog Kennels", "Outer Palisade", "Watch Platform",
            "Storage Barn", "Beer Vat Room", "Smokehouse", "Bridge Approach",
            "Boulder Field", "Sheep Pen", "Woodpile Yard", "Smith Corner",
            "Guard Nook", "Side Corridor", "Upper Gallery", "Lower Cellar",
            "Root Tunnel", "Hidden Crawl", "Chief's Bedchamber", "Side Chamber",
            "Map Room", "War Planning Hall", "Rubble Court", "Outer Ditch",
            "Signal Drum", "Loot Vault", "Armory", "Giant Boot Rack",
            "Messy Pantry", "Chimney Flue", "Mead Cellar", "Prison Pit",
            "Yard of Bones", "Canyon Crest", "Stone Circle", "Watch Cairn",
            "Back Gate",
        ],
        "mob_names": [
            ("bone giant", "a bone-bridge giant", "A bone-bridge giant brandishes a tree trunk."),
            ("ogre mercenary", "an ogre mercenary", "An ogre mercenary grins."),
            ("servant", "a canyon servant", "A servant scurries underfoot."),
            ("dire wolf", "a dire wolf", "A dire wolf growls."),
            ("thrall", "a giant thrall", "A battered thrall looks up."),
            ("giant guard", "a bridge giant guard", "A giant guard blocks the way."),
            ("stone thrower", "a stone-throwing giant", "A giant hefts a boulder."),
            ("ogre mage", "an ogre mage", "An ogre mage fingers a charm of scale."),
        ],
        "boss": ("hill giant chief", "the Bone-Bridge Chief", "The Bone-Bridge Chief fills a throne of fused vertebrae."),
        "terrain": "fused bone spans and churned canyon earth",
        "weapon": "vertebra club",
        "set": "BoneBridge",
    },
    "frost": {
        "room_names": [
            "Twilight Approach", "Frozen Membrane Gate", "Glacial Wing Hall", "Icicle Gallery",
            "Snowdrift Chamber", "Blue Ice Vault", "Shadow Barracks",
            "Throne of Rime", "Cold Larder", "Seal Meat Store", "Wolf Pens",
            "Armory of Ice", "Observatory Spire", "Wind Tunnel", "Mirror Lake Cave",
            "Sleet Bridge", "Northern Rampart", "Southern Crevasse", "Ice Smithy",
            "Runic Circle", "Prison of Ice", "Whiteout Courtyard", "Aurora Balcony",
            "Crystal Stair", "Subglacial Tunnel", "Frozen Well", "Trophy of Mammoths",
            "Chief's Chamber", "Shaman's Hut", "Bone Totem Hall", "Sled Yard",
            "Howling Gallery", "Frostbite Alcove", "Icefall Path", "Rim of the Shadow",
            "Snow Cave", "Pack Ice Room", "Whalebone Hall", "Rime Forge",
            "Cold Storage", "Guard Glacier", "Ice Prison Cell", "Hidden Crevasse",
            "Watch Cairn", "Sastrugi Field", "Pale Light Chamber", "Echoing Cold",
            "Frozen Chapel", "Last Fire Pit",
        ],
        "mob_names": [
            ("wing-shadow giant", "a wing-shadow giant", "A wing-shadow giant exhales frost."),
            ("winter wolf", "a winter wolf", "A winter wolf's eyes glow blue."),
            ("ice troll", "an ice troll", "An ice troll regenerates in the cold."),
            ("yeti", "a yeti", "A yeti bellows from the permanent twilight."),
            ("jarl guard", "a rime guard", "A rime guard stamps the ice."),
            ("heat worm", "a remorhaz", "A remorhaz radiates heat against the cold."),
            ("ice mephit", "an ice mephit", "An ice mephit cackles."),
            ("frost shaman", "a rime shaman", "A rime shaman rattles frozen bones."),
        ],
        "boss": ("frost giant jarl", "the Lord of Wing-Shadow", "The Lord of Wing-Shadow sits on a throne of ice and membrane-stone."),
        "terrain": "blue ice and permanent wing-cast twilight",
        "weapon": "glacial greataxe",
        "set": "WingShadow",
    },
    "fire": {
        "room_names": [
            "Ashen Approach", "Obsidian Gate", "Magma Gallery", "Lava Bridge",
            "Smoke Hall", "Ember Barracks", "Throne of Cinders", "Forge of Dying Fire",
            "Slave Mine", "Coal Vault", "Sulfur Chamber", "Caldera Armory",
            "Molten Overlook", "Basalt Stair", "Cinder Courtyard", "Hellhound Pens",
            "Iron Foundry", "War Drum Hall", "Obsidian Throne Room", "Heat Vent",
            "Ash Pit", "Glowing Cracks", "Red Glow Tunnel", "Smith's Anvil",
            "Treasure Hoard Approach", "Guard Post of Flames", "Scorched Gallery",
            "Boiling Pool", "Pumice Slope", "Charred Bridge", "King's Chamber",
            "Side Hall", "Map of Conquest", "Weapon Vault", "Iron Door Hall",
            "Soot Corridor", "Furnace Room", "Smelting Floor", "Lava View",
            "Blackened Chapel", "Sacrificial Ledge", "Chain Gallery", "Vent Chimney",
            "Cinder Stair", "Basalt Prison", "Molten Cell", "Escape Flue",
            "Outer Rampart", "Ash Field",
        ],
        "mob_names": [
            ("cinder giant", "a cinder giant", "A cinder giant's armor glows with residual dragon-fire."),
            ("hell hound", "a hell hound", "A hell hound breathes smoke."),
            ("salamander", "a salamander", "A salamander coils in the heat."),
            ("magma mephit", "a magma mephit", "A magma mephit drips lava."),
            ("fire smith", "a caldera smith", "A caldera smith hammers star-metal."),
            ("azer", "an azer", "An azer's beard sparks."),
            ("bound flame", "a bound flame-spirit", "A bound flame-spirit seethes."),
            ("fire priest", "a dying-fire priest", "A dying-fire priest chants to residual flame."),
        ],
        "boss": ("fire giant king", "the Caldera King", "The Caldera King rises in residual dragon-fire."),
        "terrain": "basalt, ash, and vents of dying dragon-fire",
        "weapon": "obsidian greatsword",
        "set": "DyingFire",
    },
    "underdark": {
        "room_names": [
            "Sunless Stair", "Marrow Mushroom Forest", "Webbed Tunnel", "Depth Patrol Path",
            "Mind Echo", "Crystal Fungus Grove", "Underground Lake Shore",
            "Stalactite Bridge", "Slave Caravan Rest", "Darkmantle Nest",
            "Myconid Circle", "Deep Outpost", "Silent Gallery", "Phosphor Cave",
            "Abyss of Roots", "Spore Cloud Room", "Chitin Passage", "Bone Cairn",
            "Watch Fissure", "Amethyst Vein", "Black Water Crossing", "Echo Well",
            "Spider Den", "Marrow Waystation", "Psionic Spire Base",
            "Psionic Residue Hall", "Glowcap Farm", "Rockslide Path",
            "Depth Crossroads", "Hanging Roots", "Blind Fish Pool",
            "Cave Fisher Ledge", "Silent Market Ruins", "Collapsed Temple",
            "Idol of Echo", "Guard Web", "Venom Cache", "Depth Barracks",
            "Torture Niche", "Map of the Depths", "Escape Shaft", "Air Shaft",
            "Lower Descent", "Upper Landing", "Fungal Stair", "Crystal Spire Room",
            "Still Air Chamber", "Whispering Crack", "Last Torchlight",
        ],
        "mob_names": [
            ("depth warrior", "a depth warrior", "A depth warrior smiles cruelly."),
            ("drider", "a drider", "A drider skitters forward on marrow silk."),
            ("mind flayer", "a mind flayer", "A mind flayer's tentacles writhe."),
            ("deep scout", "a deep scout", "A deep scout levels a crossbow."),
            ("hook horror", "a hook horror", "A hook horror clicks its claws."),
            ("quaggoth", "a quaggoth", "A quaggoth howls."),
            ("cave fisher", "a cave fisher", "A cave fisher waits above."),
            ("depth priestess", "a depth priestess", "A depth priestess raises an idol of falling stars."),
        ],
        "boss": ("matron mother", "the Matron of Marrow-Depths", "The Matron of Marrow-Depths regards you."),
        "terrain": "fungus, web, and quicksilver marrow dark",
        "weapon": "adamantine shortsword",
        "set": "MarrowDepths",
    },
    "vault": {
        "room_names": [
            "Vein Gates", "Shadow Portcullis", "Hall of Whispers", "Noble Gallery",
            "Star-Metal Cathedral", "Priestess Balcony", "Slave Market Ruins",
            "Poison Garden", "Velvet Chamber", "Assassin's Alley", "Noble Quarters",
            "War Council Room", "Arcane Laboratory", "Summoning Circle",
            "Treasure Antechamber", "Obsidian Mirror Hall", "Silent Library",
            "Torture Salon", "Arena of Blood", "Beast Pens", "Guard Barracks",
            "Fountain of Night", "Moonless Courtyard", "Balcony Over the Vein",
            "Web Bridge", "Secret Passage", "Crypt of Matrons", "Idol Sanctum",
            "High Priestess Chamber", "Armory of Envenomed Blades", "Wine Cellar",
            "Map Room of the Depths", "Scrying Pool", "Illusion Gallery",
            "False Treasure Room", "True Vault Door", "Gem Hoard", "Relic Pedestal",
            "Escape Tunnel", "Ambush Corridor", "Shadow Stair", "Upper Spire",
            "Lower Dungeon", "Prison of Light", "Warded Hall", "Rune Circle",
            "Last Defense", "Matron's Throne", "Heart of the Vein",
        ],
        "mob_names": [
            ("vein elite", "a star-metal elite guard", "A star-metal elite guard bows mockingly."),
            ("yochlol", "a shifting servant", "A shifting servant melts and reforms."),
            ("shadow demon", "a shadow demon", "A shadow demon bleeds darkness."),
            ("vein mage", "a vein mage", "A vein mage's hands crackle with star-metal light."),
            ("retriever", "a construct spider", "A construct spider eyes you."),
            ("assassin", "a vault assassin", "A vault assassin vanishes into gloom."),
            ("priestess", "a vault priestess", "A vault priestess chants."),
            ("noble", "a scar-depth noble", "A noble draws a fine star-metal blade."),
        ],
        "boss": ("queen of shadows", "the Queen of Star-Metal", "The Queen of Star-Metal smiles without warmth."),
        "terrain": "polished black scale-stone and cooling star-metal",
        "weapon": "venom-kissed rapier",
        "set": "StarMetal",
    },
    "elemental": {
        "room_names": [
            "Temple Approach", "Fourfold Gate of Will", "Hall of Balance", "Breath Shrine",
            "Bone Shrine", "Fire Shrine", "Blood Shrine", "Central Nexus",
            "Breath Gallery", "Bone Crypt", "Fire Sanctum", "Blood Cloister",
            "Will Crossroads", "Storm Balcony", "Stone Garden", "Magma Font",
            "Tidal Basin", "Whirlwind Chamber", "Crystal Cavern", "Ash Altar",
            "Ice Font", "Thunder Stair", "Root Cellar of Stone", "Ember Choir",
            "Mist Cloister", "Lightning Spire", "Quake Hall", "Inferno Aisle",
            "Flooded Crypt", "Balance Scale Room", "High Priest Quarters",
            "Novice Cells", "Scriptorium", "Relic Vault", "Guardian Circle",
            "Trial of Breath", "Trial of Bone", "Trial of Fire", "Trial of Blood",
            "Broken Seal Hall", "Rift Leak", "Containment Rune", "Observatory",
            "Outer Cloister", "Inner Sanctum", "Antechamber", "Processional",
            "Last Seal", "Heart of the Temples",
        ],
        "mob_names": [
            ("breath elemental", "a breath elemental", "A breath elemental howls."),
            ("bone elemental", "a bone elemental", "A bone elemental grinds forward."),
            ("fire elemental", "a fire elemental", "A fire elemental blazes with residual flame."),
            ("blood elemental", "a blood elemental", "A blood elemental surges like quicksilver."),
            ("will cultist", "a will-fragment cultist", "A will-fragment cultist chants."),
            ("templar", "a temple guardian", "A temple guardian bars the way."),
            ("mephit", "a mephit", "A mephit zips past your ear."),
            ("high cultist", "a high will-cultist", "A high will-cultist raises four symbols of the Wyrm."),
        ],
        "boss": ("elemental tyrant", "the Tyrant of Will-Fragments", "The Tyrant of Will-Fragments wears four broken crowns."),
        "terrain": "triumphal stone etched with will-runes of the First Wyrm",
        "weapon": "will-forged warblade",
        "set": "WillFragment",
    },
    "tomb": {
        "room_names": [
            "Catacomb Entrance", "False Corridor", "Pit Trap Room", "Spike Gallery",
            "Bone-strewn Hall", "Sarcophagus Chamber", "Mummy Niche", "Canopic Room",
            "Puzzle Door Hall", "Mirrored Passage", "Gas Trap Alcove", "Rolling Stone Path",
            "Crypt of Captains", "Ossuary of Memory", "Offering Room", "Cursed Treasury",
            "Guardian Statue Hall", "Glyph Chamber", "Silent Crypt", "Lower Catacombs",
            "Upper Gallery", "Funeral Barge Room", "Sand-filled Corridor", "Hidden Door Room",
            "Antechamber of Dust", "Priest's Tomb", "Warrior's Tomb", "Scholar's Tomb",
            "Throne of the Remembered", "False Treasure Room", "True Burial Vault", "Soul Well",
            "Shadow Stair", "Wrapping Room", "Incense Chamber", "Warding Circle",
            "Collapsed Wing", "Rubble Crawl", "Bone Chandelier Hall", "Whisper Gallery",
            "Last Torch", "Extinguished Shrine", "Door of Seals", "Seal Breaker's Hall",
            "Labyrinth Turn", "Dead End Niche", "Escape Crack", "Judgment Chamber",
            "Heart of Memory-Bone",
        ],
        "mob_names": [
            ("skeleton warrior", "a memory-bone warrior", "A memory-bone warrior raises a notched blade."),
            ("mummy", "a wrapped remnant", "Bandages stir with remembered fire."),
            ("wraith", "a plunge-wraith", "A plunge-wraith drains the warmth from the air."),
            ("ghoul", "a ghoul", "A ghoul licks cracked lips."),
            ("spectre", "a spectre", "A spectre phases through bone."),
            ("tomb guardian", "a catacomb guardian", "A stone guardian grinds awake."),
            ("lichling", "a lesser bone-lich", "A lesser bone-lich fingers a phylactery shard."),
            ("bone naga", "a bone naga", "A bone naga coils among urns of memory."),
        ],
        "boss": ("whispering lich", "the Whispering Memory", "The Whispering Memory speaks your name in the First Wyrm's tongue."),
        "terrain": "dust, memory-bone, and seals older than the new age",
        "weapon": "tomb-iron scimitar",
        "set": "MemoryBone",
    },
    "demonweb": {
        "room_names": [
            "Storm-Silk Approach", "Strand Bridge", "Storm Nexus", "Dragonstorm Landing",
            "Ivory Gate", "Spindle Gallery", "Venom Font", "Echo Shrine",
            "Hanging Cocoon Room", "Strand Maze", "Abyssal Overlook", "Storm Court",
            "Silk Throne Approach", "Shifter Chamber", "Hunters' Den",
            "Void Between Strands", "Floating Platform", "Broken Strand",
            "Web Cathedral", "Priestess Balcony", "Sacrificial Web", "Egg Sac Nursery",
            "Poison Mist Hall", "Black Silk Vault", "Storm Barracks", "War Spire",
            "Scrying Web", "Mirror of Planes", "Gate of Eight Storms", "Lower Web",
            "Upper Spindle", "Silk Stair", "Tremor Strand", "Hunter's Nest",
            "Cocoon Prison", "Escape Line", "Dead God Shrine", "Abyss Wind Platform",
            "Ivory Arch", "Shadow Spinner Room", "Venom Armory", "Web Map Room",
            "Last Strand", "Queen's Antechamber", "Court of Whispers", "Judgment Web",
            "Falling Silk", "Heart of the Dragonstorm", "Outer Void",
        ],
        "mob_names": [
            ("storm hunter", "a storm-silk hunter", "A storm-silk hunter stalks across the strands."),
            ("shifter", "a shifting servant", "A shifting servant melts and reforms."),
            ("vrock", "a storm-vrock", "A storm-vrock screeches."),
            ("glabrezu", "a false bargainer", "A false bargainer offers ruin dressed as mercy."),
            ("drider champion", "a storm-drider champion", "A storm-drider champion salutes."),
            ("storm spider", "a dragonstorm spider", "A dragonstorm spider drops from above."),
            ("marilith", "a blade-storm marilith", "A marilith's blades whirl."),
            ("storm priestess", "a residual-storm priestess", "A residual-storm priestess laughs."),
        ],
        "boss": ("web queen", "the Dragonstorm Queen", "The Dragonstorm Queen sits upon a throne of still-falling silk."),
        "terrain": "endless storm-silk over a hungry sky-wound",
        "weapon": "strandrazor",
        "set": "Dragonstorm",
    },
    "dragon": {
        "room_names": [
            "Mountain Path", "Fossil Wing Base", "Scorched Timberline", "Wyvern Roost",
            "Cave Mouth", "Hoard Foyer", "Treasure Shelf", "Bone Throne Approach",
            "Red Ember Gallery", "Black Mire Side", "Blue Spire",
            "Green Glade Cave", "White Ice Shelf", "Mixed Hoard Hall",
            "Gem Cascade", "Coin Beach", "Relic Pedestal", "Broken Lance Alcove",
            "Knight's Last Stand", "Charred Banner Hall", "Vent of Breath",
            "Molten Crack", "Frosted Ledge", "Acid-scarred Tunnel", "Lightning-split Hall",
            "Sleep Chamber", "Egg Clutch Room", "Hatchery", "Servitor Camp",
            "Minion Warrens", "Cultist Shrine", "Priest Quarters",
            "Observation Ledge", "High Roost", "Wing Stretch Platform", "Sky Breach",
            "Lower Hoard", "Upper Hoard", "False Nest", "True Nest", "Guardian Circle",
            "Chain of Captives", "Trophy of Heroes", "Map of the Scar", "Escape Chimney",
            "Final Approach", "Heart of the Fossil Wing", "Dragon's Eye Chamber", "Summit",
        ],
        "mob_names": [
            ("wyvern", "a wyvern", "A wyvern shrieks from fossil bone."),
            ("dragon cultist", "a sky-breaker cultist", "A cultist kneels then attacks."),
            ("half-dragon", "a half-dragon warrior", "A half-dragon warrior roars."),
            ("young red dragon", "a young red dragon", "A young red dragon uncoils among fossil spars."),
            ("drake", "a fire drake", "A fire drake spits embers."),
            ("kobold dragonshield", "a scale-shield kobold", "A scale-shield kobold stands firm."),
            ("dragon priest", "a fossil-wing priest", "A priest raises a scale idol of the First Wyrm."),
            ("dragon spawn", "a dragon spawn", "A dragon spawn flexes wings."),
        ],
        "boss": ("ancient red", "an ancient remnant-dragon", "An ancient remnant-dragon fills the fossil wing's summit."),
        "terrain": "fossil wing-bone and glittering hoard",
        "weapon": "dragonfang lance",
        "set": "FossilWing",
    },
    "astral": {
        "room_names": [
            "Axis Landing", "Silver Void Path", "Sanctum Gates", "Hall of Trials",
            "Trial of Strength", "Trial of Wit", "Trial of Will", "Trial of Mercy",
            "Trial of Courage", "Mirror of Selves", "Bridge of Stars", "Void Gallery",
            "Throne of Judgment", "Antechamber of Heroes", "Fallen Star Garden",
            "Constellation Hall", "Orbital Balcony", "Silent Choir", "Sky-Remnant Outpost",
            "Mind Storm", "Color Pool Shore", "Psychic Winds", "Floating Isle",
            "Crystal Spire", "Memory Archive", "Name Vault", "Oath Chamber",
            "Broken God Fragment", "Axis Wake", "Silver Cord Path",
            "Dreamer's Rest", "Nightmare Breach", "Portal Ring", "Gate of Return",
            "Watchers' Circle", "Scale of Souls", "Last Argument", "Final Gate",
            "Court Gallery", "Witness Stands", "Advocate's Desk", "Accuser's Pillar",
            "Champion's Mark", "Relic of Ages", "Star Forge", "Quiet Between",
            "End of Roads", "Heart of the Axis", "The New Axis Threshold",
        ],
        "mob_names": [
            ("sky-remnant", "a sky-remnant warrior", "A sky-remnant warrior salutes with a silver sword."),
            ("axis construct", "an axis construct", "An axis construct hums with residual will."),
            ("deva", "a stern deva", "A stern deva bars the path."),
            ("examiner", "an order examiner", "An order examiner ticks through laws of the new age."),
            ("psychic wind", "a psychic wind elemental", "A psychic wind elemental howls."),
            ("star reaver", "a star reaver", "A star reaver grins with too many teeth."),
            ("sanctum bailiff", "a sanctum bailiff", "A sanctum bailiff demands order."),
            ("fallen planetar", "a fallen planetar", "A fallen planetar weeps light."),
        ],
        "boss": ("astral judge", "the Axis Judge", "The Axis Judge opens the book of names—and of the Plunge."),
        "terrain": "silver nothingness and hard starlight over the Scar's true depth",
        "weapon": "starforged blade",
        "set": "AxisHeart",
    },
}




def tier_scale(mid_level: int) -> dict:
    """Scale combat stats from player/mob mid level."""
    t = max(1, mid_level)
    return {
        "mob_ac": -int(t * 2.2),
        "mob_hr": int(t * 1.1) + 2,
        "mob_dr": int(t * 0.9) + 1,
        "mob_hp": int(t * 8),
        "wep_hr": max(1, t // 3),
        "wep_dr": max(1, t // 3),
        "arm_ac": -max(5, t * 2),
        "arm_hit": max(5, t * 2),
        "arm_mana": max(5, t),
        "arm_hr": max(1, t // 4),
        "arm_dr": max(1, t // 4),
        "extra": ITEM_MAGIC if t >= 15 else 0,
    }


class AreaBuilder:
    def __init__(self, zone: ZoneSpec, rng: random.Random):
        self.z = zone
        self.rng = rng
        self.theme = THEME[zone.theme]
        self.rooms: List[RoomDef] = []
        self.mobs: List[MobDef] = []
        self.objs: List[ObjDef] = []
        self.mid = (zone.min_level + zone.max_level) // 2
        self.scale = tier_scale(self.mid if not zone.is_hub else 10)
        # Layout within each 100-vnum block:
        #   +0..+49  rooms
        #   +50..+69 mobiles
        #   +70..+99 objects
        self.entry_vnum = zone.vbase
        self._next_mob = zone.vbase + 50
        self._next_obj = zone.vbase + 70

    def alloc_obj(self) -> int:
        v = self._next_obj
        self._next_obj += 1
        if self._next_obj >= self.z.vbase + self.z.vsize:
            raise RuntimeError(f"object vnum overflow in {self.z.filename}")
        return v

    def alloc_mob(self) -> int:
        v = self._next_mob
        self._next_mob += 1
        if self._next_mob >= self.z.vbase + 70:
            raise RuntimeError(f"mobile vnum overflow in {self.z.filename}")
        return v

    def build(self) -> str:
        self._build_rooms()
        gear = self._build_gear_set()
        self._build_mobs(gear)
        return self._emit()

    def _build_rooms(self) -> None:
        z = self.z
        names = list(self.theme["room_names"])
        self.rng.shuffle(names)
        # grid size
        side = int(math.ceil(math.sqrt(z.n_rooms)))
        coords = [(x, y) for y in range(side) for x in range(side)][: z.n_rooms]
        room_at = {}
        for i, (x, y) in enumerate(coords):
            vnum = z.vbase + i
            name = names[i % len(names)]
            if i == 0:
                name = f"Entrance to {self._plain_title()}"
            terrain = self.theme["terrain"]
            desc = (
                f"{name}. Around you: {terrain}. "
                f"Residual magic of the Plunge lingers here. "
                f"Expeditions through this reach of the Scar suit roughly levels "
                f"{z.min_level}-{z.max_level}."
            )
            flags = 0
            sector = 0 if z.theme in ("caves", "underdark", "tomb", "vault") else 1
            if z.is_hub and i == 0:
                flags = 8  # safe-ish? use 0; SAFE is high bit. leave 0
            r = RoomDef(vnum=vnum, name=name, desc=desc, flags=flags, sector=sector, x=x, y=y)
            self.rooms.append(r)
            room_at[(x, y)] = r

        # link 4-way grid
        for r in self.rooms:
            for d, (dx, dy) in enumerate([(0, -1), (1, 0), (0, 1), (-1, 0)]):
                n = room_at.get((r.x + dx, r.y + dy))
                if n:
                    r.exits[d] = n.vnum

        # boss room = last room, ensure connected
        if len(self.rooms) > 1:
            boss = self.rooms[-1]
            prev = self.rooms[-2]
            if 0 not in boss.exits and 2 not in prev.exits:
                prev.exits[1] = boss.vnum  # east
                boss.exits[3] = prev.vnum  # west
            boss.name = f"Sanctum of {self.theme['boss'][1]}"
            boss.desc = (
                f"This is the heart of {self._plain_title()}. "
                f"{self.theme['boss'][2]} The stone carries the slow pulse of residual Wyrm-life."
            )

        self.entry_vnum = self.rooms[0].vnum

    def _plain_title(self) -> str:
        return re_sub_color(self.z.title)

    def _build_gear_set(self) -> dict:
        """Create a full set of gear + weapon + potion. Returns role->ObjDef."""
        sc = self.scale
        set_name = self.theme["set"]
        lvl = max(1, self.z.min_level)
        extra = sc["extra"] | (ITEM_GLOW if self.mid >= 40 else 0)

        def armor(slot: str, key: str, short: str, long: str) -> ObjDef:
            v = self.alloc_obj()
            aff = [
                Affect(APPLY_AC, sc["arm_ac"]),
                Affect(APPLY_HIT, sc["arm_hit"]),
                Affect(APPLY_HITROLL, sc["arm_hr"]),
                Affect(APPLY_DAMROLL, sc["arm_dr"]),
            ]
            if slot in ("body", "about"):
                aff.append(Affect(APPLY_MANA, sc["arm_mana"]))
            o = ObjDef(
                vnum=v,
                keywords=key,
                short=short,
                long=long,
                item_type=ITEM_ARMOR,
                extra=extra,
                wear=wear_for(slot),
                item_apply=1,
                values=(max(1, self.mid // 5), 0, 0, 0),
                weight=max(1, 5 if slot != "body" else 15),
                level=lvl,
                affects=aff,
                slot=slot,
            )
            self.objs.append(o)
            return o

        def weapon() -> ObjDef:
            v = self.alloc_obj()
            dice_sides = max(4, self.mid // 3)
            dice_num = max(1, self.mid // 15)
            o = ObjDef(
                vnum=v,
                keywords=self.theme["weapon"],
                short=f"@@y{self.theme['weapon']}@@N",
                long=f"@@y{self.theme['weapon'].capitalize()}@@N lies here, humming with power.",
                item_type=ITEM_WEAPON,
                extra=extra | ITEM_HUM if self.mid >= 30 else extra,
                wear=wear_for("wield"),
                item_apply=1,
                values=(dice_num, dice_sides, 0, WPN_SWORD),
                weight=10,
                level=lvl,
                affects=[
                    Affect(APPLY_HITROLL, sc["wep_hr"]),
                    Affect(APPLY_DAMROLL, sc["wep_dr"]),
                    Affect(APPLY_STR, max(1, self.mid // 20)),
                ],
                slot="wield",
            )
            self.objs.append(o)
            return o

        gear = {
            "weapon": weapon(),
            "body": armor(
                "body",
                f"{set_name.lower()} breastplate armor",
                f"@@W{set_name} breastplate@@N",
                f"A @@W{set_name} breastplate@@N rests here.",
            ),
            "head": armor(
                "head",
                f"{set_name.lower()} helm",
                f"@@W{set_name} helm@@N",
                f"A @@W{set_name} helm@@N lies on the ground.",
            ),
            "legs": armor(
                "legs",
                f"{set_name.lower()} greaves",
                f"@@W{set_name} greaves@@N",
                f"@@W{set_name} greaves@@N are discarded here.",
            ),
            "feet": armor(
                "feet",
                f"{set_name.lower()} boots",
                f"@@W{set_name} boots@@N",
                f"A pair of @@W{set_name} boots@@N sits here.",
            ),
            "hands": armor(
                "hands",
                f"{set_name.lower()} gauntlets",
                f"@@W{set_name} gauntlets@@N",
                f"@@W{set_name} gauntlets@@N lie in a pile.",
            ),
            "shield": armor(
                "shield",
                f"{set_name.lower()} shield",
                f"@@W{set_name} shield@@N",
                f"A @@W{set_name} shield@@N leans against the wall.",
            ),
            "about": armor(
                "about",
                f"{set_name.lower()} cloak",
                f"@@W{set_name} cloak@@N",
                f"A @@W{set_name} cloak@@N is folded here.",
            ),
            "finger": armor(
                "finger",
                f"{set_name.lower()} ring",
                f"@@W{set_name} ring@@N",
                f"A @@W{set_name} ring@@N glints on the ground.",
            ),
            "neck": armor(
                "neck",
                f"{set_name.lower()} amulet",
                f"@@W{set_name} amulet@@N",
                f"A @@W{set_name} amulet@@N hangs from a peg.",
            ),
        }

        # potion
        pv = self.alloc_obj()
        pot = ObjDef(
            vnum=pv,
            keywords="healing potion red",
            short="a red healing potion",
            long="A red healing potion sits here.",
            item_type=ITEM_POTION,
            extra=0,
            wear=ITEM_TAKE,
            item_apply=1,
            values=(max(5, self.mid), 0, 0, 0),  # level-ish; slots may be 0
            weight=1,
            level=1,
            affects=[],
            slot="hold",
        )
        self.objs.append(pot)
        gear["potion"] = pot

        # boss unique weapon (slightly better)
        if not self.z.is_hub:
            bv = self.alloc_obj()
            boss_w = ObjDef(
                vnum=bv,
                keywords=f"unique {self.theme['weapon']} legendary",
                short=f"@@R{self.theme['boss'][1]}'s weapon@@N",
                long=f"@@RThe legendary weapon of {self.theme['boss'][1]}@@N lies here.",
                item_type=ITEM_WEAPON,
                extra=ITEM_MAGIC | ITEM_GLOW | ITEM_HUM,
                wear=wear_for("wield"),
                item_apply=1,
                values=(max(2, self.mid // 12), max(6, self.mid // 2), 0, WPN_SWORD),
                weight=12,
                level=max(1, self.z.max_level - 5),
                affects=[
                    Affect(APPLY_HITROLL, sc["wep_hr"] + 5),
                    Affect(APPLY_DAMROLL, sc["wep_dr"] + 5),
                    Affect(APPLY_HIT, sc["arm_hit"]),
                    Affect(APPLY_STR, 2),
                ],
                slot="wield",
            )
            self.objs.append(boss_w)
            gear["boss_weapon"] = boss_w

        return gear

    def _build_mobs(self, gear: dict) -> None:
        sc = self.scale
        lo, hi = self.z.min_level, self.z.max_level
        names = self.theme["mob_names"]

        # trash / elite per room cluster
        for i, (kw, short, long) in enumerate(names):
            lvl = lo + (i * max(1, (hi - lo))) // max(1, len(names) - 1)
            v = self.alloc_mob()
            # equip 1-3 items
            slots = ["weapon", "body", "head", "shield", "feet", "hands", "about", "finger", "neck"]
            self.rng.shuffle(slots)
            n_eq = 2 if lvl < 30 else 3
            if self.z.is_hub:
                n_eq = 1
            eq = []
            for s in slots[:n_eq]:
                if s in gear:
                    eq.append(gear[s].vnum)
            m = MobDef(
                vnum=v,
                keywords=kw,
                short=short,
                long=long + "\n",
                description=f"{short[0].upper() + short[1:]} looks ready for battle.\n",
                level=max(1, min(95, lvl + self.rng.randint(-1, 2))),
                align=-300 if not self.z.is_hub else 0,
                act=ACT_NPC | (0 if self.z.is_hub else ACT_AGGRESSIVE) | ACT_STAY_AREA,
                ac=sc["mob_ac"] + (i - 4) * 5,
                hr=sc["mob_hr"] + i,
                dr=sc["mob_dr"] + i // 2,
                hp_mod=sc["mob_hp"] + i * 10,
                equip=eq,
                inventory=[gear["potion"].vnum] if self.rng.random() < 0.4 else [],
            )
            self.mobs.append(m)

        # boss
        bkw, bshort, blong = self.theme["boss"]
        bv = self.alloc_mob()
        boss_eq = [
            gear[s].vnum
            for s in ("weapon", "body", "head", "legs", "feet", "hands", "shield", "about", "neck", "finger")
            if s in gear
        ]
        if "boss_weapon" in gear:
            boss_eq[0] = gear["boss_weapon"].vnum
        boss = MobDef(
            vnum=bv,
            keywords=bkw,
            short=bshort,
            long=blong + "\n",
            description=f"{bshort[0].upper() + bshort[1:]} radiates terrible power.\n",
            level=min(95, hi + (0 if self.z.is_hub else 3)),
            align=-1000 if not self.z.is_hub else 500,
            act=ACT_NPC | ACT_SENTINEL | (0 if self.z.is_hub else ACT_AGGRESSIVE),
            ac=sc["mob_ac"] - 40,
            hr=sc["mob_hr"] + 15,
            dr=sc["mob_dr"] + 15,
            hp_mod=sc["mob_hp"] * 3,
            equip=boss_eq,
            inventory=[gear["potion"].vnum, gear["potion"].vnum],
        )
        self.mobs.append(boss)
        self.boss_vnum = bv
        self.boss_room = self.rooms[-1].vnum

    def _emit(self) -> str:
        z = self.z
        out: List[str] = []
        out.append("#AREA\n")
        out.append(tilde(z.title))
        out.append("Z 3\n")
        # C = area avnum (unique id), not room count
        out.append(f"C {9000 + (z.vbase // 100)}\n")
        out.append("K " + tilde(z.keyword))
        out.append("L " + tilde(z.label))
        out.append(f"N {len(self.rooms)}\n")
        out.append(f"I {z.min_level} {z.max_level}\n")
        out.append(f"V {z.vbase} {z.vbase + z.vsize - 1}\n")
        out.append("X 0\n")
        out.append("F 15\n")
        out.append("U " + tilde(z.reset_msg.rstrip("~")))
        out.append("O " + tilde("adesa-gen"))
        out.append("R " + tilde("all"))
        out.append("W " + tilde("all"))
        out.append("T You can teleport into here\n")

        # ROOMS
        out.append("#ROOMS\n")
        for r in self.rooms:
            out.append(f"#{r.vnum}\n")
            out.append(tilde(r.name))
            out.append(tilde(r.desc))
            out.append(f"{r.flags} {r.sector}\n")
            for d, dest in sorted(r.exits.items()):
                out.append(f"D{d}\n")
                out.append(tilde(DIR_NAMES[d].capitalize() + "."))
                out.append(tilde(""))
                out.append(f"0 -1 {dest}\n")
            out.append("S\n")
        out.append("#0\n")

        # MOBILES
        out.append("#MOBILES\n")
        for m in self.mobs:
            out.append(f"#{m.vnum}\n")
            out.append(tilde(m.keywords))
            out.append(tilde(m.short))
            out.append(tilde(m.long.rstrip("\n") + "\n"))
            out.append(tilde(m.description.rstrip("\n") + "\n"))
            # act aff align S
            out.append(f"{m.act} {m.affected} {m.align} S\n")
            out.append(f"{m.level} {m.sex}\n")
            out.append(f"{m.ac} {m.hr} {m.dr} {m.hp_mod} {m.mana_mod}\n")
            # ! class clan race pos skills cast def
            out.append(f"! 0 0 {m.race} 7 0 0 0\n")
        out.append("#0\n")

        # OBJECTS
        out.append("#OBJECTS\n")
        for o in self.objs:
            out.append(f"#{o.vnum}\n")
            out.append(tilde(o.keywords))
            out.append(tilde(o.short))
            out.append(tilde(o.long))
            out.append(f"{o.item_type} {o.extra} {o.wear} {o.item_apply}\n")
            out.append(f"{o.values[0]} {o.values[1]} {o.values[2]} {o.values[3]}\n")
            out.append(f"{o.weight}\n")
            for a in o.affects:
                out.append(f"A {a.location} {a.modifier}\n")
            out.append(f"L {o.level}\n")
        out.append("#0\n")

        # RESETS — place mobs in rooms, equip gear
        out.append("#RESETS\n")
        # map obj vnum -> ObjDef for wear loc
        obj_map = {o.vnum: o for o in self.objs}

        # distribute trash mobs across rooms (skip boss room for trash)
        non_boss_rooms = [r.vnum for r in self.rooms[:-1]] or [self.rooms[0].vnum]
        trash = self.mobs[:-1]
        for i, m in enumerate(trash):
            room = non_boss_rooms[i % len(non_boss_rooms)]
            limit = 3 if m.level < 40 else 2
            out.append(f"M 0 {m.vnum} {limit} {room}\n")
            for ov in m.equip:
                o = obj_map.get(ov)
                loc = WEAR_LOC.get(o.slot, 16) if o else 16
                out.append(f"E 0 {ov} 0 {loc}\n")
            for ov in m.inventory:
                out.append(f"G 0 {ov} 0\n")

        # boss in last room
        boss = self.mobs[-1]
        out.append(f"M 0 {boss.vnum} 1 {self.boss_room}\n")
        for ov in boss.equip:
            o = obj_map.get(ov)
            loc = WEAR_LOC.get(o.slot, 16) if o else 16
            out.append(f"E 0 {ov} 0 {loc}\n")
        for ov in boss.inventory:
            out.append(f"G 0 {ov} 0\n")

        # loose gear on entry for hub / first zone
        if self.z.is_hub or self.z.min_level <= 5:
            for key in ("weapon", "body", "potion"):
                if key in obj_map or any(o.slot == key or (key == "weapon" and o.slot == "wield") for o in self.objs):
                    pass
            # put a starter weapon on ground in entry
            wep = next((o for o in self.objs if o.slot == "wield"), None)
            if wep:
                out.append(f"O 0 {wep.vnum} 2 {self.entry_vnum}\n")

        out.append("S\n")
        out.append("#$\n")
        return "".join(out)


def re_sub_color(s: str) -> str:
    import re

    return re.sub(r"@@.", "", s)


def connect_chain(builders: List[AreaBuilder]) -> None:
    """Link each zone entrance to the previous zone east/west.

    Anchors the Great Spine hub (builders[0]) north to Scar west gate (3052)
    so the progression chain is walkable from the Heart-Pulse Sanctum (3001)
    after tools/world_connect.py adds the matching capital exit.
    """
    for i in range(1, len(builders)):
        prev = builders[i - 1]
        cur = builders[i]
        src = prev.rooms[min(1, len(prev.rooms) - 1)]
        dst = cur.rooms[0]
        src.exits[1] = dst.vnum  # east
        dst.exits[3] = src.vnum  # west
        src.desc += f" A trail leads east toward {re_sub_color(cur.z.title)}."
        dst.desc += f" The path west returns toward {re_sub_color(prev.z.title)}."

    # Hub entrance -> Scar west gate (must stay in sync with world_connect.py)
    if builders:
        hub_entry = builders[0].rooms[0]
        hub_entry.exits[0] = 3052  # north
        hub_entry.desc += " North lies the West Gate of the Scar."


def update_area_lst(lst_path: Path, filenames: List[str]) -> None:
    lines = lst_path.read_text().splitlines()
    # strip trailing $ and existing generated entries we own
    gen_set = set(filenames)
    kept = [ln for ln in lines if ln.strip() and ln.strip() != "$" and ln.strip() not in gen_set]
    kept.extend(filenames)
    kept.append("$")
    lst_path.write_text("\n".join(kept) + "\n")


def write_helps(helps_dir: Path, zones: List[ZoneSpec]) -> None:
    helps_dir.mkdir(parents=True, exist_ok=True)
    lst_path = helps_dir / "helps.lst"
    existing = lst_path.read_text() if lst_path.exists() else "0\n"
    # remove trailing 0
    if existing.rstrip().endswith("0"):
        base = existing.rstrip()[:-1].rstrip() + "\n"
    else:
        base = existing
    additions = []
    for z in zones:
        key = z.keyword
        rel = f"gen/{key}"
        path = helps_dir / "gen" / key
        path.parent.mkdir(parents=True, exist_ok=True)
        body = (
            f".\n@@W{re_sub_color(z.title)}@@N\n\n"
            f"Suggested levels: @@y{z.min_level}@@N-@@y{z.max_level}@@N.\n"
            f"Entry room vnum: @@a{z.vbase}@@N (imm @@ygoto {z.vbase}@@N).\n"
            f"Part of the Dragonfall Scar progression — ascend the wound.\n"
            f"From the Great Spine Waystation, travel the linked roads in band order.\n"
            f"See also: @@yhelp dragonfall@@N (if present).\n"
        )
        path.write_text(body)
        # only add to lst if keyword not already present
        if f"{key}~" not in base:
            additions.append(f"{key}~\n{rel}~\n")
    if "realmroad" not in base:
        pass
    new_lst = base + "".join(additions) + "0\n"
    lst_path.write_text(new_lst)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("area"))
    ap.add_argument("--lst", type=Path, default=Path("data/area.lst"))
    ap.add_argument("--helps", type=Path, default=Path("area/helps"))
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    builders: List[AreaBuilder] = []
    for z in ZONES:
        b = AreaBuilder(z, random.Random(rng.randint(0, 1_000_000)))
        b._build_rooms()
        builders.append(b)

    connect_chain(builders)

    files = []
    for b in builders:
        gear = b._build_gear_set()
        b._build_mobs(gear)
        text = b._emit()
        out_path = args.out / b.z.filename
        out_path.write_text(text)
        files.append(b.z.filename)
        print(
            f"wrote {out_path} rooms={len(b.rooms)} "
            f"mobs={len(b.mobs)} objs={len(b.objs)} entry={b.entry_vnum}"
        )

    update_area_lst(args.lst, files)
    print(f"updated {args.lst}")
    write_helps(args.helps, ZONES)
    print(f"updated helps under {args.helps}/gen/")
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
