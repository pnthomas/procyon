# Procyon

A Terran StarCraft II bot built with [ares-sc2](https://github.com/AresSC2/ares-sc2), targeting local play and [AI Arena](https://aiarena.net).

**Current status:** Phase 1 complete. The bot runs locally vs the built-in AI: trains SCVs, gathers minerals, and plays until the game ends.

## Prerequisites

- **StarCraft II** installed (Battle.net); launch the game at least once so SC2 creates its data folders.
- **Maps:** Bots need map files (`.SC2Map`). Put ladder or test maps in your SC2 Maps folder. Procyon looks for maps in **`~/Library/Application Support/Blizzard/StarCraft II/Maps`** on macOS (create the `Maps` folder if needed). Download map packs from e.g. [SC2AI.net](https://sc2ai.net) or the game’s map pool and place `.SC2Map` files (or subfolders) there.
- **Python 3.11+** (ares-sc2 requires 3.11–3.12). If your system only has an older Python, install 3.11 (e.g. `brew install python@3.11`) and use it to create the venv: `python3.11 -m venv venv`.

## Setup

1. Clone or open the repo and go to its root:
   ```bash
   cd /Users/pthomas/src/procyon
   ```

2. Create and activate a virtual environment (use Python 3.11 or 3.12):
   ```bash
   python3.11 -m venv venv   # or python3.12 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies (ares-sc2 is installed from GitHub):
   ```bash
   pip install -r requirements.txt
   ```

## Run the bot

With the venv activated:

```bash
python bot.py
```

This runs Procyon (Terran) vs the built-in Zerg Easy AI on the map `IncorporealAIE_v4` by default. Override the map with `PROCYON_MAP` to run others from your SC2 Maps folder.

You can override the map at runtime with `PROCYON_MAP`:

```bash
PROCYON_MAP=IncorporealAIE_v4 python bot.py
```

You can choose a build/strategy with `PROCYON_BUILD`:

```bash
PROCYON_BUILD=standard python bot.py
PROCYON_BUILD=claimjumper python bot.py
PROCYON_BUILD=claimjumper_marine_viking python bot.py
```

### Debug tags

Set `PROCYON_DEBUG` to a comma-separated list of tags to get extra terminal and in-game chat output for that behavior. Example:

```bash
PROCYON_DEBUG=build_order,macro python bot.py
```

Tags:
- `build_order`: opening / build runner
- `macro`: reserved for future use
- `claimjumper`: log claimjumper target position when computed
- `expand_baseline`: minimal baseline (suspend macro/build-order, keep mining, use built-in `expand_now()` to take natural, log started/completed)
- `claimjumper_location`: SCV telemetry for claimjumper behavior (orders, movement, distance, action errors)
  - Claimjumper itself is selected by `PROCYON_BUILD=claimjumper...` and is one-shot: after the first accepted CC order, it will not issue further claimjumper rebuild attempts.
  - Includes a pathing error report if the SCV repeatedly hits `result=208` / `ability=318` while stationary (suggesting map/pathing geometry issues).

### Vendored sc2_helper

The ares-sc2 PyPI wheel does not include the `sc2_helper` package (used for combat simulation). This repo vendors `sc2_helper` (Python files + the Python 3.11 Darwin `.so`) in `vendor/sc2_helper/` so the bot runs without a development install of ares-sc2. The bot adds `vendor` to `sys.path` before importing ares.

### Troubleshooting

- **"requires a different Python: 3.9 not in '>=3.11'"** — Create the venv with Python 3.11 or 3.12 (e.g. `brew install python@3.11` then `python3.11 -m venv venv`).
- **Map not found** / **FileNotFoundError: ... Maps** — Procyon uses `~/Library/Application Support/Blizzard/StarCraft II/Maps` on macOS. Put your `.SC2Map` files there and ensure the map name in `bot.py` matches (without the `.SC2Map` extension).
- **"No module named 'sc2_helper'"** — Ensure you run from the repo root so `vendor/sc2_helper` is found (the bot adds `vendor` to the path automatically).

## Project plan

| Phase | Description |
|-------|--------------|
| **1** | Setup + hello-world Terran bot *(done)* |
| **2** | Standard macro: workers, supply, one simple build, basic Marines |
| **3** | Ninja Turtle v0: Claimjumper, Larceny Ledger, turtlely expand w/ bunkers and floated CCs into PFs, marine waves |
| **4** | Ninja Turtle v1: Polish + extra modules (creep lawnmower, Viking squads, overlord denial, Marauder harass) |
| **5** | AI Arena readiness |
| **6** | Future work: repair strategies, Chill tanks, underexplored units, more strategies |

Full strategic roadmap and module details: [roadmap.md](roadmap.md).
