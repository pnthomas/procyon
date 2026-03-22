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
- `larceny_ledger`: when the ninja claimjump townhall is destroyed, mirror the Larceny summary to in-game chat
- `claimjumper_location`: SCV telemetry for claimjumper behavior (orders, movement, distance, action errors)
  - Claimjumper is selected by `PROCYON_BUILD=claimjumper...`. Only one claimjumper CC order is issued per game. **Pioneer-only** for building refineries (no main SCV pulls). Depots/barracks/eBay anchor to the **main** townhall nearest your start. Pipeline: **both** refineries → staff gas-first and **queue SCVs from the CC** until PF is affordable → morph → then **normal** saturation (gas-first staffing), same pattern you’ll eventually share with other bases.
  - Includes a pathing error report if the SCV repeatedly hits `result=208` / `ability=318` while stationary (suggesting map/pathing geometry issues).

### Verification (self-evaluation milestones)

Set **`PROCYON_VERIFY`** to a comma-separated list of **strategy names** (lowercase). Each enabled strategy emits **one-shot** lines to the **terminal** and **in-game chat** when milestones pass, driven by **game state** (not timers). After the game, **`on_end`** prints a **summary** of which expected steps never fired.

```bash
PROCYON_VERIFY=claimjumper PROCYON_BUILD=claimjumper python bot.py
```

**Design (extensible to other builds):**

| Piece | Role |
|-------|------|
| `PROCYON_VERIFY` | Which strategies run milestone hooks (`claimjumper`, later e.g. `standard`). |
| `[VERIFY][strategy] step_id \| detail` | Stable prefix for grepping replays, logs, and chat. |
| `_verify_latched` | `(strategy, step_id)` pairs already reported — each milestone fires once. |
| `CLAIMJUMPER_VERIFY_EXPECTED_STEPS` | Checklist for **`on_end`** `missing=[...]` summary. |
| `_verify_warn_once` | Optional diagnostics (e.g. blocked path) without spamming. |
| **`on_end` TODO line** | Printed after the summary: known follow-up (e.g. pioneer vs Build Runner timing). |

Independent of **`PROCYON_DEBUG`** — use verify for pass/fail checklists; use debug for noisy traces.

**Claimjumper milestones (`PROCYON_VERIFY=claimjumper`)**

| Chat / log id | Trigger (game state) |
|---------------|----------------------|
| `cj_scv_dispatched` | Pioneer tag set and that SCV still exists. |
| `cj_scv_arrived` | Pioneer distance to claim target &lt; `CLAIMJUMPER_ARRIVAL_RADIUS`. |
| `cj_cc_order_issued` | `_claimjumper_cc_order_logged` (build accepted). |
| `cj_cc_under_construction` | Not-ready `COMMANDCENTER` within 9 of claim target (supplementary). |
| `cj_cc_built` | Ready `COMMANDCENTER` at claim (pre-PF). |
| `cj_ebay_ready` | At least one ready `ENGINEERINGBAY` (PF tech; useful when debugging walls). |
| `cj_refinery_1of2_order` | Pioneer issued `build_gas` for the first open geyser (one-shot). |
| `cj_refinery_2of2_order` | Same for the second geyser. |
| `cj_extractor_1of2` | ≥1 refinery structure near claim anchor (CC or building CC). |
| `cj_extractor_2of2` | ≥2 refineries near claim. |
| `cj_extractors_gas_saturated` | SCVs within 5 of each **ready** refinery ≥ 3×(number of ready refs). |
| `cj_bank_150gas` | `vespene >= 150` while claim townhall exists. |
| `cj_pf_order_issued` | `_claimjumper_pf_upgrade_logged`. |
| `cj_pf_morphing` | CC has PF morph ability in orders (supplementary). |
| `cj_pf_complete` | Claim townhall type is `PLANETARYFORTRESS`. |
| `WARN cj_warn_scv_blocked` | Once: dispatched &gt;50s game time and never `cj_scv_arrived` — often **Build Runner** still owning the SCV, not only walls. |

**End-of-game:** `[VERIFY][claimjumper] END game_result=... hit=N/M missing=[...]` plus a **`TODO:`** line for the next agreed fix (e.g. pioneer vs opener).

### Larceny Ledger (ninja base only)

When **`PROCYON_BUILD`** starts with `claimjumper`, the bot tracks **minerals and gas gathered that are deposited at the claimjump townhall** (CC or PF). It does **not** walk all bases: only SCVs and MULEs are checked, and only deposits inferred from **carrying → not carrying** transitions while the worker is near the ninja CC/PF (standard **8** minerals and **4** gas per trip).

- **Terminal:** `[Larceny] END — gathered=…` on every game end, with **net** vs static **~1700m ~150g** invest estimate.
- **Ninja base killed:** `[Larceny] Ninja base destroyed — …` once. Add **`larceny_ledger`** to **`PROCYON_DEBUG`** for a short in-game chat line as well.

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
