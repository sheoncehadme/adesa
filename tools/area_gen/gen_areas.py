#!/usr/bin/env python3
"""
Generate progressive D&D-inspired ACK!MUD / Adesa area files.

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
    ZoneSpec("realmroad.are", "@@WThe Realm Road@@N", "realmroad",
             "@@W{ @@yHUB@@W }@@N", 1, 90, 22500, 100,
             "hub", 36, "Caravan bells and hoofbeats echo along the Realm Road.~", True),
    ZoneSpec("borderkeep.are", "@@yKeep on the Borderlands@@N", "borderkeep",
             "@@W{ @@r 1 10@@W }@@N", 1, 10, 22600, 100,
             "border", 49, "A horn sounds from the Border Keep walls.~"),
    ZoneSpec("caveschaos.are", "@@dCaves of Chaos@@N", "caveschaos",
             "@@W{ @@r 5 15@@W }@@N", 5, 15, 22700, 100,
             "caves", 49, "Distant tribal drums thunder in the caves.~"),
    ZoneSpec("hillgiant.are", "@@ySteading of the Hill Giant Chief@@N", "hillgiant",
             "@@W{ @@r15 25@@W }@@N", 15, 25, 22800, 100,
             "hillgiant", 49, "The ground trembles under giant footfalls.~"),
    ZoneSpec("frosthold.are", "@@cGlacial Hold of the Frost Giants@@N", "frosthold",
             "@@W{ @@r25 35@@W }@@N", 25, 35, 22900, 100,
             "frost", 49, "Icy winds howl through the glacial halls.~"),
    ZoneSpec("firepeak.are", "@@RHall of the Fire Giant King@@N", "firepeak",
             "@@W{ @@r35 45@@W }@@N", 35, 45, 23000, 100,
             "fire", 49, "Magma cracks and the air tastes of ash.~"),
    ZoneSpec("underdark.are", "@@mDescent into the Underdark@@N", "underdark",
             "@@W{ @@r40 50@@W }@@N", 40, 50, 23100, 100,
             "underdark", 49, "Something scuttles in the lightless deep.~"),
    ZoneSpec("vaultshadow.are", "@@dVault of Shadows@@N", "vaultshadow",
             "@@W{ @@r50 60@@W }@@N", 50, 60, 23200, 100,
             "vault", 49, "Whispers in an elven tongue echo from below.~"),
    ZoneSpec("elementaltemple.are", "@@eTemple of the Four Elements@@N", "elementaltemple",
             "@@W{ @@r55 65@@W }@@N", 55, 65, 23300, 100,
             "elemental", 49, "The four elements roar in unnatural harmony.~"),
    ZoneSpec("tombwhispers.are", "@@WTomb of Whispering Bones@@N", "tombwhispers",
             "@@W{ @@r60 70@@W }@@N", 60, 70, 23400, 100,
             "tomb", 49, "A dry rattle of bones rolls down stone corridors.~"),
    ZoneSpec("demonweb.are", "@@RDemonweb Approaches@@N", "demonweb",
             "@@W{ @@r70 80@@W }@@N", 70, 80, 23500, 100,
             "demonweb", 49, "Silk threads vibrate with planar malice.~"),
    ZoneSpec("dragonspire.are", "@@RDragonspire Peaks@@N", "dragonspire",
             "@@W{ @@r75 85@@W }@@N", 75, 85, 23600, 100,
             "dragon", 49, "A great wing blots out the sun.~"),
    ZoneSpec("astralcourt.are", "@@aAstral Court of Trials@@N", "astralcourt",
             "@@W{ @@r80 90@@W }@@N", 80, 90, 23700, 100,
             "astral", 49, "Stars rearrange themselves into judgment.~"),
]


THEME = {
    "hub": {
        "room_names": [
            "Crossroads of Realms", "Caravan Square", "Wayfarer's Inn Yard",
            "Merchant Stalls", "Shrine of Safe Passage", "Portal Circle",
            "Stable Yard", "Message Board Plaza", "Fountain Court",
            "South Road Gate", "North Road Gate", "East Trailhead",
            "West Trailhead", "Adventurer Camp", "Smithy Yard",
            "Healer's Tent", "Provisioner's Cart", "Storyteller's Fire",
            "Guard Post", "Signpost Junction", "Dusty Wagon Ring",
            "Hitching Posts", "Mapmaker's Table", "Guild Notice Board",
            "Traveler's Rest", "Stone Bench Alcove", "Lantern Row",
            "Horse Path", "Supply Depot", "Watchtower Base",
            "Old Milestone", "Copper Bell Tower", "Grain Silo Path",
            "Rain Shelter", "Well of Welcome", "Roadside Chapel",
        ],
        "mob_names": [
            ("merchant caravan", "a caravan merchant", "A caravan merchant haggles loudly."),
            ("road guard", "a road guard", "A road guard watches the traffic."),
            ("stablehand", "a stablehand", "A stablehand brushes a horse."),
            ("healer pilgrim", "a pilgrim healer", "A pilgrim healer offers bandages."),
            ("storyteller", "an old storyteller", "An old storyteller spins a yarn."),
            ("porter", "a hired porter", "A hired porter waits for work."),
            ("scout ranger", "a trail scout", "A trail scout studies the horizon."),
            ("blacksmith", "a traveling blacksmith", "A blacksmith hammers a horseshoe."),
        ],
        "boss": ("road warden", "the Road Warden", "The Road Warden surveys the crossroads."),
        "terrain": "dusty packed earth and wagon ruts",
        "weapon": "traveler's shortsword",
        "set": "Wayfarer",
    },
    "border": {
        "room_names": [
            "Keep Courtyard", "Outer Gatehouse", "Barracks Hall",
            "Armory Alcove", "Watchtower Stair", "Curtain Wall Walk",
            "Stables", "Mess Hall", "Chapel Nave", "Inner Bailey",
            "Well Yard", "Practice Yard", "North Wall", "South Wall",
            "East Bastion", "West Bastion", "Supply Cellar", "Captain's Office",
            "Recruit Quarters", "Postern Gate", "Moat Bridge", "Drawbridge",
            "Guardroom", "Signal Fire Platform", "Smithy", "Tannery Yard",
            "Herb Garden", "Outer Ditch", "Palisade Path", "Scout Post",
            "Border Trail", "Hill Overlook", "Forest Edge", "Campfire Ring",
            "Wagon Barricade", "Muddy Approach", "Stone Arch", "Flagpole Court",
            "Cistern", "Kennel Run", "Siege Ladder Shed", "Arrow Slit Corridor",
            "Commander's Balcony", "Storage Loft", "Root Cellar", "Chapel Crypt",
            "Hidden Alcove", "Secret Stair", "Outer Watch",
        ],
        "mob_names": [
            ("kobold scout", "a kobold scout", "A kobold scout hisses and flees then returns."),
            ("goblin raider", "a goblin raider", "A goblin raider brandishes a rusty blade."),
            ("orc thug", "an orc thug", "An orc thug glares hungrily."),
            ("bandit", "a border bandit", "A border bandit eyes your purse."),
            ("giant rat", "a giant rat", "A giant rat squeals."),
            ("keep recruit", "a keep recruit", "A keep recruit trains with a wooden sword."),
            ("wall archer", "a wall archer", "A wall archer nocks an arrow."),
            ("orc shaman", "an orc shaman", "An orc shaman mutters dark words."),
        ],
        "boss": ("border chief", "Castellan of the Keep", "The Castellan of the Keep stands ready."),
        "terrain": "timber walls and trampled grass",
        "weapon": "border shortsword",
        "set": "Border",
    },
    "caves": {
        "room_names": [
            "Cave Mouth", "Dripping Tunnel", "Bat Chamber", "Fungus Grotto",
            "Kobold Warren", "Goblin Den", "Orc Barracks", "Tribal Shrine",
            "Bone Pit", "Underground Stream", "Stalactite Hall", "Collapsed Gallery",
            "Torchlit Cavern", "Slave Pens", "Storage Niche", "Mushroom Farm",
            "Chieftain's Cave", "Guard Post", "Narrow Crawl", "Echoing Dome",
            "Sooty Camp", "Weapon Cache", "Idol Chamber", "Sacrificial Altar",
            "Side Tunnel", "Dead End Crevasse", "Waterfall Cave", "Muddy Hollow",
            "Crystal Vein", "Root-choked Passage", "Fissure Bridge", "Lower Gallery",
            "Upper Ledge", "Smoke Hole", "Hidden Cache", "Watch Fissure",
            "Totem Circle", "Rubble Slope", "Damp Landing", "Cold Pool",
            "Pale Glow Room", "Ash Circle", "War Drum Hollow", "Meat Rack Cave",
            "Trophy Wall", "Thorn Barrier", "Oil Slick Floor", "Ambush Bend",
            "Escape Chimney",
        ],
        "mob_names": [
            ("kobold warrior", "a kobold warrior", "A kobold warrior snarls."),
            ("goblin spearman", "a goblin spearman", "A goblin spearman jabs the air."),
            ("orc brute", "an orc brute", "An orc brute roars a challenge."),
            ("cave trollkin", "a young cave troll", "A young cave troll sniffs hungrily."),
            ("darkmantle", "a darkmantle", "A darkmantle clings to the ceiling."),
            ("troglodyte", "a troglodyte", "A troglodyte reeks of swamp."),
            ("bugbear", "a bugbear", "A bugbear looms in the dark."),
            ("orc warpriest", "an orc warpriest", "An orc warpriest raises a bloody idol."),
        ],
        "boss": ("chaos chieftain", "the Chieftain of Chaos", "The Chieftain of Chaos bellows."),
        "terrain": "damp limestone and tribal refuse",
        "weapon": "notched cave axe",
        "set": "Chaos",
    },
    "hillgiant": {
        "room_names": [
            "Hill Path", "Giant Footprint Mud", "Steading Gates", "Courtyard Muck",
            "Great Hall", "Feasting Table", "Kitchen Hearth", "Larder",
            "Barracks Bunks", "Weapon Rack Room", "Chief's Throne", "Trophy Hall",
            "Slave Pens", "Dog Kennels", "Outer Palisade", "Watch Platform",
            "Storage Barn", "Beer Vat Room", "Smokehouse", "Hilltop Approach",
            "Boulder Field", "Sheep Pen", "Woodpile Yard", "Smith Corner",
            "Guard Nook", "Side Corridor", "Upper Gallery", "Lower Cellar",
            "Root Tunnel", "Hidden Crawl", "Chief's Bedchamber", "Concubine Room",
            "Map Room", "War Planning Hall", "Rubble Court", "Outer Ditch",
            "Signal Drum", "Loot Vault", "Armory", "Giant Boot Rack",
            "Messy Pantry", "Chimney Flue", "Mead Cellar", "Prison Pit",
            "Yard of Bones", "Hill Crest", "Stone Circle", "Watch Cairn",
            "Back Gate",
        ],
        "mob_names": [
            ("hill giant", "a hill giant", "A hill giant brandishes a tree trunk."),
            ("ogre mercenary", "an ogre mercenary", "An ogre mercenary grins."),
            ("orc servant", "an orc servant", "An orc servant scurries."),
            ("dire wolf", "a dire wolf", "A dire wolf growls."),
            ("giant thrall", "a giant thrall", "A battered thrall looks up."),
            ("hill giant guard", "a hill giant guard", "A hill giant guard blocks the way."),
            ("stone thrower", "a stone-throwing giant", "A giant hefts a boulder."),
            ("ogre mage", "an ogre mage", "An ogre mage fingers a charm."),
        ],
        "boss": ("hill giant chief", "the Hill Giant Chief", "The Hill Giant Chief fills the throne."),
        "terrain": "rough timber and churned earth",
        "weapon": "tree-trunk club",
        "set": "Steading",
    },
    "frost": {
        "room_names": [
            "Ice Approach", "Frozen Gate", "Glacial Hall", "Icicle Gallery",
            "Snowdrift Chamber", "Blue Ice Vault", "Frost Giant Barracks",
            "Throne of Rime", "Cold Larder", "Seal Meat Store", "Wolf Pens",
            "Armory of Ice", "Observatory Spire", "Wind Tunnel", "Mirror Lake Cave",
            "Sleet Bridge", "Northern Rampart", "Southern Crevasse", "Ice Smithy",
            "Runic Circle", "Prison of Ice", "Whiteout Courtyard", "Aurora Balcony",
            "Crystal Stair", "Subglacial Tunnel", "Frozen Well", "Trophy of Mammoths",
            "Chief's Chamber", "Shaman's Hut", "Bone Totem Hall", "Sled Yard",
            "Howling Gallery", "Frostbite Alcove", "Icefall Path", "Rim of the Glacier",
            "Snow Cave", "Pack Ice Room", "Whalebone Hall", "Rime Forge",
            "Cold Storage", "Guard Glacier", "Ice Prison Cell", "Hidden Crevasse",
            "Watch Cairn", "Sastrugi Field", "Pale Light Chamber", "Echoing Cold",
            "Frozen Chapel", "Last Fire Pit",
        ],
        "mob_names": [
            ("frost giant", "a frost giant", "A frost giant exhales a cloud of frost."),
            ("winter wolf", "a winter wolf", "A winter wolf's eyes glow blue."),
            ("ice troll", "an ice troll", "An ice troll regenerates in the cold."),
            ("yeti", "a yeti", "A yeti bellows."),
            ("frost giant jarl guard", "a jarl's guard", "A jarl's guard stamps the ice."),
            ("remorhaz", "a remorhaz", "A remorhaz radiates heat."),
            ("ice mephit", "an ice mephit", "An ice mephit cackles."),
            ("frost shaman", "a frost giant shaman", "A frost giant shaman rattles bones."),
        ],
        "boss": ("frost giant jarl", "the Frost Giant Jarl", "The Frost Giant Jarl sits on a throne of ice."),
        "terrain": "blue ice and biting wind",
        "weapon": "glacial greataxe",
        "set": "Rime",
    },
    "fire": {
        "room_names": [
            "Ashen Approach", "Obsidian Gate", "Magma Gallery", "Lava Bridge",
            "Smoke Hall", "Ember Barracks", "Throne of Cinders", "Forge of Kings",
            "Slave Mine", "Coal Vault", "Sulfur Chamber", "Fire Giant Armory",
            "Molten Overlook", "Basalt Stair", "Cinder Courtyard", "Hellhound Pens",
            "Iron Foundry", "War Drum Hall", "Obsidian Throne Room", "Heat Vent",
            "Ash Pit", "Glowing Cracks", "Red Glow Tunnel", "Smith's Anvil",
            "Treasure Hoard Approach", "Guard Post of Flames", "Scorched Gallery",
            "Boiling Pool", "Pumice Slope", "Charred Bridge", "King's Chamber",
            "Concubine Hall", "Map of Conquest", "Weapon Vault", "Iron Door Hall",
            "Soot Corridor", "Furnace Room", "Smelting Floor", "Lava View",
            "Blackened Chapel", "Sacrificial Ledge", "Chain Gallery", "Vent Chimney",
            "Cinder Stair", "Basalt Prison", "Molten Cell", "Escape Flue",
            "Outer Rampart", "Ash Field",
        ],
        "mob_names": [
            ("fire giant", "a fire giant", "A fire giant's armor glows with heat."),
            ("hell hound", "a hell hound", "A hell hound breathes smoke."),
            ("salamander", "a salamander", "A salamander coils in the heat."),
            ("magma mephit", "a magma mephit", "A magma mephit drips lava."),
            ("fire giant smith", "a fire giant smith", "A fire giant smith hammers iron."),
            ("azer", "an azer", "An azer's beard sparks."),
            ("efreeti minor", "a bound efreeti", "A bound efreeti seethes."),
            ("fire giant priest", "a fire giant priest", "A fire giant priest chants to flame."),
        ],
        "boss": ("fire giant king", "the Fire Giant King", "The Fire Giant King rises in flame."),
        "terrain": "basalt, ash, and open vents of fire",
        "weapon": "obsidian greatsword",
        "set": "Cinder",
    },
    "underdark": {
        "room_names": [
            "Sunless Stair", "Mushroom Forest", "Webbed Tunnel", "Drow Patrol Path",
            "Illithid Echo", "Crystal Fungus Grove", "Underground Lake Shore",
            "Stalactite Bridge", "Slave Caravan Rest", "Darkmantle Nest",
            "Myconid Circle", "Duergar Outpost", "Silent Gallery", "Phosphor Cave",
            "Abyss of Roots", "Spore Cloud Room", "Chitin Passage", "Bone Cairn",
            "Watch Fissure", "Amethyst Vein", "Black Water Crossing", "Echo Well",
            "Spider Den", "Drow Waystation", "Mind Flayer Spire Base",
            "Psionic Residue Hall", "Glowcap Farm", "Rockslide Path",
            "Underdark Crossroads", "Hanging Roots", "Blind Fish Pool",
            "Cave Fisher Ledge", "Silent Market Ruins", "Collapsed Temple",
            "Idol of Lolth", "Guard Web", "Venom Cache", "Dark Elf Barracks",
            "Torture Niche", "Map of the Depths", "Escape Shaft", "Air Shaft",
            "Lower Descent", "Upper Landing", "Fungal Stair", "Crystal Spire Room",
            "Still Air Chamber", "Whispering Crack", "Last Torchlight",
        ],
        "mob_names": [
            ("drow warrior", "a drow warrior", "A drow warrior smiles cruelly."),
            ("drider", "a drider", "A drider skitters forward."),
            ("mind flayer", "a mind flayer", "A mind flayer's tentacles writhe."),
            ("duergar", "a duergar scout", "A duergar scout levels a crossbow."),
            ("hook horror", "a hook horror", "A hook horror clicks its claws."),
            ("quaggoth", "a quaggoth", "A quaggoth howls."),
            ("cave fisher", "a cave fisher", "A cave fisher waits above."),
            ("drow priestess", "a drow priestess", "A drow priestess raises a spider idol."),
        ],
        "boss": ("matron mother", "the Matron of the Depths", "The Matron of the Depths regards you."),
        "terrain": "fungus, web, and absolute dark",
        "weapon": "adamantine shortsword",
        "set": "Underdark",
    },
    "vault": {
        "room_names": [
            "Vault Gates", "Shadow Portcullis", "Hall of Whispers", "Noble Gallery",
            "Spider Cathedral", "Priestess Balcony", "Slave Market Ruins",
            "Poison Garden", "Velvet Chamber", "Assassin's Alley", "Noble Quarters",
            "War Council Room", "Arcane Laboratory", "Summoning Circle",
            "Treasure Antechamber", "Obsidian Mirror Hall", "Silent Library",
            "Torture Salon", "Arena of Blood", "Beast Pens", "Guard Barracks",
            "Fountain of Night", "Moonless Courtyard", "Balcony Over the Vault",
            "Web Bridge", "Secret Passage", "Crypt of Matrons", "Idol Sanctum",
            "High Priestess Chamber", "Armory of Envenomed Blades", "Wine Cellar",
            "Map Room of the Underdark", "Scrying Pool", "Illusion Gallery",
            "False Treasure Room", "True Vault Door", "Gem Hoard", "Relic Pedestal",
            "Escape Tunnel", "Ambush Corridor", "Shadow Stair", "Upper Spire",
            "Lower Dungeon", "Prison of Light", "Warded Hall", "Rune Circle",
            "Last Defense", "Matron's Throne", "Heart of the Vault",
        ],
        "mob_names": [
            ("drow elite", "a drow elite guard", "A drow elite guard bows mockingly."),
            ("yochlol", "a yochlol", "A yochlol shifts between forms."),
            ("shadow demon", "a shadow demon", "A shadow demon bleeds darkness."),
            ("drow mage", "a drow mage", "A drow mage's hands crackle."),
            ("retriever", "a retriever", "A construct spider eyes you."),
            ("assassin", "a vault assassin", "A vault assassin vanishes into gloom."),
            ("priestess", "a vault priestess", "A vault priestess chants."),
            ("noble drow", "a drow noble", "A drow noble draws a fine blade."),
        ],
        "boss": ("queen of shadows", "the Queen of Shadows", "The Queen of Shadows smiles without warmth."),
        "terrain": "polished black stone and silk",
        "weapon": "venom-kissed rapier",
        "set": "Vault",
    },
    "elemental": {
        "room_names": [
            "Temple Approach", "Fourfold Gate", "Hall of Balance", "Air Shrine",
            "Earth Shrine", "Fire Shrine", "Water Shrine", "Central Nexus",
            "Air Gallery", "Earth Crypt", "Fire Sanctum", "Water Cloister",
            "Elemental Crossroads", "Storm Balcony", "Stone Garden", "Magma Font",
            "Tidal Basin", "Whirlwind Chamber", "Crystal Cavern", "Ash Altar",
            "Ice Font", "Thunder Stair", "Root Cellar of Stone", "Ember Choir",
            "Mist Cloister", "Lightning Spire", "Quake Hall", "Inferno Aisle",
            "Flooded Crypt", "Balance Scale Room", "High Priest Quarters",
            "Novice Cells", "Scriptorium", "Relic Vault", "Guardian Circle",
            "Trial of Air", "Trial of Earth", "Trial of Fire", "Trial of Water",
            "Broken Seal Hall", "Rift Leak", "Containment Rune", "Observatory",
            "Outer Cloister", "Inner Sanctum", "Antechamber", "Processional",
            "Last Seal", "Heart of the Temple",
        ],
        "mob_names": [
            ("air elemental", "an air elemental", "An air elemental howls."),
            ("earth elemental", "an earth elemental", "An earth elemental grinds forward."),
            ("fire elemental", "a fire elemental", "A fire elemental blazes."),
            ("water elemental", "a water elemental", "A water elemental surges."),
            ("elemental cultist", "an elemental cultist", "An elemental cultist chants."),
            ("templar", "a temple guardian", "A temple guardian bars the way."),
            ("mephit swarm", "a mephit", "A mephit zips past your ear."),
            ("high cultist", "a high cultist", "A high cultist raises four symbols."),
        ],
        "boss": ("elemental tyrant", "the Elemental Tyrant", "The Elemental Tyrant wears all four crowns."),
        "terrain": " triumphal stone etched with elemental runes",
        "weapon": "elemental warblade",
        "set": "Elemental",
    },
    "tomb": {
        "room_names": [
            "Tomb Entrance", "False Corridor", "Pit Trap Room", "Spike Gallery",
            "Bone-strewn Hall", "Sarcophagus Chamber", "Mummy Niche", "Canopic Room",
            "Puzzle Door Hall", "Mirrored Passage", "Gas Trap Alcove", "Rolling Stone Path",
            "Crypt of Captains", "Ossuary", "Offering Room", "Cursed Treasury",
            "Guardian Statue Hall", "Glyph Chamber", "Silent Crypt", "Lower Catacombs",
            "Upper Gallery", "Funeral Barge Room", "Sand-filled Corridor", "Hidden Door Room",
            "Antechamber of Dust", "Priest's Tomb", "Warrior's Tomb", "Scholar's Tomb",
            "Throne of the Dead", "False Treasure Room", "True Burial Vault", "Soul Well",
            "Shadow Stair", "Mummy Wrapping Room", "Incense Chamber", "Warding Circle",
            "Collapsed Wing", "Rubble Crawl", "Bone Chandelier Hall", "Whisper Gallery",
            "Last Torch", "Extinguished Shrine", "Door of Seals", "Seal Breaker's Hall",
            "Labyrinth Turn", "Dead End Niche", "Escape Crack", "Judgment Chamber",
            "Heart of the Tomb",
        ],
        "mob_names": [
            ("skeleton warrior", "a skeleton warrior", "A skeleton warrior raises a notched blade."),
            ("mummy", "a mummy", "A mummy's bandages stir."),
            ("wraith", "a wraith", "A wraith drains the warmth from the air."),
            ("ghoul", "a ghoul", "A ghoul licks cracked lips."),
            ("spectre", "a spectre", "A spectre phases through stone."),
            ("tomb guardian", "a tomb guardian construct", "A stone guardian grinds awake."),
            ("lichling", "a lesser lich", "A lesser lich fingers a phylactery shard."),
            ("bone naga", "a bone naga", "A bone naga coils among urns."),
        ],
        "boss": ("whispering lich", "the Whispering Lich", "The Whispering Lich speaks your name."),
        "terrain": "dust, bone, and ancient stone seals",
        "weapon": "tomb-iron scimitar",
        "set": "Sepulcher",
    },
    "demonweb": {
        "room_names": [
            "Silk Approach", "Strand Bridge", "Web Nexus", "Demonweb Landing",
            "Ivory Gate", "Spindle Gallery", "Venom Font", "Lolthite Shrine",
            "Hanging Cocoon Room", "Strand Maze", "Abyssal Overlook", "Spider Court",
            "Silk Throne Approach", "Yochlol Chamber", "Retrievers' Den",
            "Void Between Strands", "Floating Platform", "Broken Strand",
            "Web Cathedral", "Priestess Balcony", "Sacrificial Web", "Egg Sac Nursery",
            "Poison Mist Hall", "Black Silk Vault", "Demonic Barracks", "War Spire",
            "Scrying Web", "Mirror of Planes", "Gate of Eight Legs", "Lower Web",
            "Upper Spindle", "Silk Stair", "Tremor Strand", "Hunter's Nest",
            "Cocoon Prison", "Escape Line", "Dead God Shrine", "Abyss Wind Platform",
            "Ivory Arch", "Shadow Spinner Room", "Venom Armory", "Web Map Room",
            "Last Strand", "Queen's Antechamber", "Court of Whispers", "Judgment Web",
            "Falling Silk", "Heart of the Demonweb", "Outer Void",
        ],
        "mob_names": [
            ("bebilith", "a bebilith", "A bebilith hunts across the strands."),
            ("yochlol", "a yochlol servant", "A yochlol servant melts and reforms."),
            ("vrock", "a vrock", "A vrock screeches."),
            ("glabrezu", "a glabrezu", "A glabrezu offers a false bargain."),
            ("drider champion", "a drider champion", "A drider champion salutes."),
            ("demonweb spider", "a demonweb spider", "A demonweb spider drops from above."),
            ("marilith", "a marilith", "A marilith's blades whirl."),
            ("priestess of lolth", "a priestess of Lolth", "A priestess of Lolth laughs."),
        ],
        "boss": ("web queen", "the Web Queen", "The Web Queen sits upon a throne of silk."),
        "terrain": "endless silk over a hungry abyss",
        "weapon": "strandrazor",
        "set": "Demonweb",
    },
    "dragon": {
        "room_names": [
            "Mountain Path", "Dragonspire Base", "Scorched Timberline", "Wyvern Roost",
            "Cave Mouth", "Hoard Foyer", "Treasure Shelf", "Bone Throne Approach",
            "Red Dragon Gallery", "Black Dragon Mire Side", "Blue Dragon Spire",
            "Green Dragon Glade Cave", "White Dragon Ice Shelf", "Mixed Hoard Hall",
            "Gem Cascade", "Coin Beach", "Relic Pedestal", "Broken Lance Alcove",
            "Knight's Last Stand", "Charred Banner Hall", "Vent of Breath",
            "Molten Crack", "Frosted Ledge", "Acid-scarred Tunnel", "Lightning-split Hall",
            "Dragon Sleep Chamber", "Egg Clutch Room", "Hatchery", "Servitor Camp",
            "Kobold Minion Warrens", "Cultist Shrine", "Dragon Priest Quarters",
            "Observation Ledge", "High Roost", "Wing Stretch Platform", "Sky Breach",
            "Lower Hoard", "Upper Hoard", "False Nest", "True Nest", "Guardian Circle",
            "Chain of Captives", "Trophy of Heroes", "Map of Realms", "Escape Chimney",
            "Final Approach", "Heart of the Spire", "Dragon's Eye Chamber", "Summit",
        ],
        "mob_names": [
            ("wyvern", "a wyvern", "A wyvern shrieks."),
            ("dragon cultist", "a dragon cultist", "A dragon cultist kneels then attacks."),
            ("half-dragon", "a half-dragon warrior", "A half-dragon warrior roars."),
            ("young red dragon", "a young red dragon", "A young red dragon uncoils."),
            ("drake", "a fire drake", "A fire drake spits embers."),
            ("kobold dragonshield", "a kobold dragonshield", "A kobold dragonshield stands firm."),
            ("dragon priest", "a dragon priest", "A dragon priest raises a scale idol."),
            ("adult dragon spawn", "a dragon spawn", "A dragon spawn flexes wings."),
        ],
        "boss": ("ancient red", "an ancient red dragon", "An ancient red dragon fills the summit."),
        "terrain": "scorched rock and glittering hoard",
        "weapon": "dragonfang lance",
        "set": "Dragonspire",
    },
    "astral": {
        "room_names": [
            "Astral Landing", "Silver Void Path", "Star Court Gates", "Hall of Trials",
            "Trial of Strength", "Trial of Wit", "Trial of Will", "Trial of Mercy",
            "Trial of Courage", "Mirror of Selves", "Bridge of Stars", "Void Gallery",
            "Throne of Judgment", "Antechamber of Heroes", "Fallen Star Garden",
            "Constellation Hall", "Orbital Balcony", "Silent Choir", "Githyanki Outpost",
            "Mind Storm", "Color Pool Shore", "Psychic Winds", "Floating Isle",
            "Crystal Spire", "Memory Archive", "Name Vault", "Oath Chamber",
            "Broken God Fragment", "Astral Dreadnought Wake", "Silver Cord Path",
            "Dreamer's Rest", "Nightmare Breach", "Portal Ring", "Gate of Return",
            "Watchers' Circle", "Scale of Souls", "Last Argument", "Final Gate",
            "Court Gallery", "Witness Stands", "Advocate's Desk", "Accuser's Pillar",
            "Champion's Mark", "Relic of Ages", "Star Forge", "Quiet Between",
            "End of Roads", "Heart of the Court", "Beyond the Verdict",
        ],
        "mob_names": [
            ("githyanki", "a githyanki warrior", "A githyanki warrior salutes with a silver sword."),
            ("astral construct", "an astral construct", "An astral construct hums."),
            ("deva", "a stern deva", "A stern deva bars the path."),
            ("modron", "a modron examiner", "A modron examiner ticks."),
            ("psychic wind", "a psychic wind elemental", "A psychic wind elemental howls."),
            ("star reaver", "a star reaver", "A star reaver grins with too many teeth."),
            ("court bailiff", "a court bailiff", "A court bailiff demands order."),
            ("fallen planetar", "a fallen planetar", "A fallen planetar weeps light."),
        ],
        "boss": ("astral judge", "the Astral Judge", "The Astral Judge opens the book of names."),
        "terrain": "silver nothingness and hard starlight",
        "weapon": "starforged blade",
        "set": "Astral",
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
                f"You stand in {name.lower()}. The surroundings show {terrain}. "
                f"This place tests travelers of roughly levels {z.min_level}-{z.max_level}. "
                f"Paths lead onward through the {z.keyword}."
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
                f"{self.theme['boss'][2]} The air itself feels heavier here."
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
    """Link each zone entrance to the previous zone's last non-boss or boss room east/west.

    Also anchors the Realm Road hub (builders[0]) north to Midgaard west gate (3052)
    so the progression chain is walkable from the Temple after tools/world_connect.py
    adds the matching Midgaard exit (or if 3052 already links south).
    """
    # Hub (0) already standalone. Connect 1..n via synthetic exits on entry rooms.
    # Entry of zone i+1 westbound to a room in zone i.
    for i in range(1, len(builders)):
        prev = builders[i - 1]
        cur = builders[i]
        # link from prev rooms[1] east -> cur entry, and back
        src = prev.rooms[min(1, len(prev.rooms) - 1)]
        dst = cur.rooms[0]
        src.exits[1] = dst.vnum  # east
        dst.exits[3] = src.vnum  # west
        # flavor names
        src.desc += f" A trail leads east toward {re_sub_color(cur.z.title)}."
        dst.desc += f" The path west returns toward {re_sub_color(prev.z.title)}."

    # Hub entrance -> Midgaard west gate (must stay in sync with world_connect.py)
    if builders:
        hub_entry = builders[0].rooms[0]
        hub_entry.exits[0] = 3052  # north
        hub_entry.desc += " North lies the West Gate of Midgaard."


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
            f"Part of the Realm Road progression campaign.\n"
            f"From the hub, travel the linked roads in band order.\n"
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
