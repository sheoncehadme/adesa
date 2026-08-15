# Dragonfall functional-test scripts (MUSHclient)

Three **separate** plugins for leveling a **named test character** via
immortal commands. These are **not** combat grinders — they are fast,
deterministic functional tests for the Dragonfall world.

## Prerequisites

1. An **immortal** character logged into Dragonfall (trust high enough for
   `setclass` / `mset`, typically implementor-level for max targets).
2. A **mortal test character** already created (school is fine).
3. Install plugins into MUSHclient’s `worlds/plugins` folder and enable them
   on the **immortal** world (or any world where you type imm commands).

## Commands

| Plugin | Alias | Example | Effect |
|--------|--------|---------|--------|
| Mortal class → 80 | `dfmortal` | `dfmortal Testchar Mag 80` | `setclass Testchar Mag 80` |
| Remort class → 80 | `dfremort` | `dfremort Testchar Sor 80` | `setclass Testchar Sor 80` |
| Adept → max (20) | `dfadept` | `dfadept Testchar` | make adept if needed, then `mset Testchar adept 20` |

Class abbreviations (case-insensitive; full names also accepted):

- **Mortal:** `Mag` `Cle` `Thi` `War` `Psi`
- **Remort:** `Sor` `Ass` `Kni` `Nec` `Mon`

Defaults (change with aliases below):

- Character: `Testchar`
- Mortal class: `Mag` · remort class: `Sor`
- Target level: `80` (mortal/remort only; cap is 80, just below `LEVEL_HERO`)
- Adept max: `20` (hard-coded to `do_mset` range)

Each plugin also `force <char> save` after the inject.

### Config aliases (all plugins)

```
dfconfig char Testchar
dfconfig class War
dfconfig level 80
dfshow
dfmortal help
dfremort help
dfadept help
```

## Typical smoke sequence (immortal window)

```
dfmortal Testchar War 80
dfremort Testchar Kni 80
dfadept Testchar
```

Then (optional) on the mortal:

```
score
look
goto 22500    (imm)  or walk Scar → Great Spine
```

## Server commands used

From `do_setclass` / `do_mset` in `src/act_wiz.c`:

```
setclass <player> <Mag|Cle|Thi|War|Psi> <level>
setclass <player> <Sor|Ass|Kni|Nec|Mon> <level>
setclass <player> ADEPT          (first adept only → level 1)
mset <player> adept 20           (set adept rank 1–20)
```

## Why not a combat bot?

Grinding school → multi-class 80 → remort 80 → adept 20 legitimately is
fragile (combat, death, economy, pathing). For Dragonfall regression, imm
level injects prove:

- character load/save
- multi-class / remort / adept fields
- who/score display
- endgame access after connect fixes

Pair with `python3 tests/scripts/check_connectivity.py` and
`python3 tests/scripts/check_quests.py` for world health.

## Python alternative (no MUSHclient)

```
python3 tools/mushclient/df_level_via_imm.py \
  --host 127.0.0.1 --port 6000 \
  --imm Ogma --imm-pass SECRET \
  --char Testchar --mode mortal --class War --level 80
```

Modes: `mortal`, `remort`, `adept`.

## Files

| File | Role |
|------|------|
| `df_level_mortal.xml` | Mortal class plugin |
| `df_level_remort.xml` | Remort class plugin |
| `df_level_adept.xml` | Adept plugin |
| `df_level_via_imm.py` | Telnet/CI helper |
