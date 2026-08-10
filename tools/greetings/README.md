# Dragonfall login greetings

Connection screen art for the fantasy name **Dragonfall**.

## Active install

**Selected:** fire-trail plunge (`dragonfall_f_plunge.mrt`)

Installed as `area/helps/g/greeting0.mrt` … `greeting2.mrt` (login picks `greeting0`–`2` at random in `comm.c`).

Originals (if present) under `tools/greetings/backup/`.

Helps are read from disk per request — reconnect after install (no full rebuild required unless the mud caches helps at boot; Adesa reloads from `helps.lst` paths on each `send_help`).

## Candidates

| File | Style |
|------|--------|
| `dragonfall_d_dive.mrt` | Full frontal diving dragon + title |
| `dragonfall_e_wyrm.mrt` | Side-on plunging wyrm into mist |
| `dragonfall_f_plunge.mrt` | **Active** — diagonal fall with fire trail |
| `dragonfall_a_stars.mrt` | Night sky / comet (landscape-ish) |
| `dragonfall_b_mountains.mrt` | Peaks & waterfall |
| `dragonfall_c_framed.mrt` | Framed portal |

Color codes: `@@e` light red, `@@R` red, `@@y` yellow, `@@c` cyan, `@@d` dark grey, `@@W` white, `@@N` normal.

Swap install:

```sh
cp tools/greetings/dragonfall_d_dive.mrt area/helps/g/greeting0.mrt
cp tools/greetings/dragonfall_d_dive.mrt area/helps/g/greeting1.mrt
cp tools/greetings/dragonfall_d_dive.mrt area/helps/g/greeting2.mrt
```
