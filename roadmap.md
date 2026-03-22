# Procyon roadmap

Strategic roadmap for the bot: behaviors, modules, and strategies. (Setup and project structure are in the README.)

---

## Phase 1: Hello-world Terran bot

- ~~Minimal runnable bot: Terran, gathers minerals, trains SCVs, runs vs built-in AI.~~

---

## Phase 2: Turn minerals into marines

- ~~**Worker / economy:** Train SCVs from CCs when affordable; support multiple CCs; avoid supply blocks (depots in time).~~ *(Done: SCV training with saturation 16 mineral / 6 gas per base; depots via ares placement when supply low; idle SCVs sent back to gathering.)*
- ~~**Build order:** One simple build (e.g. 1–2 CCs, 2–3 barracks, depots, then sustain). No ninja expansion yet.~~ *(Done: TwoRaxMarines via ares Build Runner—2 depots @ ramp, 2 barracks @ ramp; fallback builds barracks if runner doesn’t.)*
- ~~**Basic army:** Produce Marines from barracks and group them; no complex micro.~~ *(Done: Marines from idle barracks when affordable and supply allows.)*
**Deliverable:** ~~Repeatable Terran opener, steady economy and supply, steady Marine production.~~ *(Done. Debug tags: PROCYON_DEBUG=build_order for per-building and “all steps issued” / “all buildings complete” messages; in-game chat for build-order reporting.)*

---

## Phase 3: Differentiate into a build (Ninja Turtle v0 core modules)

Only the modules Ninja Turtle v0 needs first.

### 3.1 Claimjumper (aggressive expansion to opponent’s side)

- ~~**Scout / map:** Identify enemy 4th (or equivalent expansion on opponent’s side).~~
- ~~**Send SCV:** Dispatch SCV(s) early; path to that base (avoid enemy if visible).~~
- **Build:** Planetary Fortress at that location; add extractors; saturate with SCVs (or partial + MULEs).
- **Defend / retreat:**
  - If enemy forces attack workers at the claim, **flee SCVs to the far side of the PF** (use the structure as cover / break contact) rather than fighting.
  - **Repair the PF** with nearby SCVs when it is taking damage.
  - **Missile turrets:** Once the base is **saturated**, build **3 missile turrets** near the PF. **Replace** turrets that are destroyed, only when it is **safe** to do so (no complex micro — defer if contested).
- **Integration:** Enabled only when Ninja Turtle (or another build) enables Claimjumper; build order leaves minerals/gas and an SCV available at the right time.
- **Polish:**
  - **Pioneer egress vs opener:** CC order can be accepted early, but the SCV often **does not actually leave** until **barracks and depots** from the Build Runner finish — integrate dispatch / worker ownership so the pioneer moves out as soon as we intend (not only when the wall is done building).
  - **Claimjump staffing (gas vs minerals):** Staffing currently **overfills gas** and leaves **minerals understaffed** at the claim. Fix so per-base gas follows the intended cap (e.g. 3 per refinery) without pulling excess SCVs onto gas, and **mineral patches** at the claim reach correct saturation relative to workers assigned there.

### 3.2 Larceny Ledger (ninja-base resource tracking)

- ~~**Purpose:** Track total resources collected by the ninja base to measure cost-effectiveness and how much we “steal” before it’s found.~~ *(Done in `bot.py`.)*
- ~~**Implementation:** Only SCVs/MULEs are scanned. Each step, units that transition from carrying minerals or gas to not carrying while within range of the **ready** claimjump CC/PF add **8 minerals** or **4 gas** per trip (standard loads; gold not distinguished). No global bank deltas — avoids mis-attributing spends.~~
- ~~**Ledger / output:** `_larceny_gathered_minerals`, `_larceny_gathered_vespene`; **`on_end`** prints `[Larceny] END — gathered=…` with net vs static est. invest **1700m + 150g**.~~
- ~~**When it runs:** `PROCYON_BUILD=claimjumper…`; `_larceny_tick()` after claimjumper staffing each frame (including during the opener branch once the ninja TH exists).~~
- ~~**Base lost:** `on_unit_destroyed` matching the ninja townhall tag → one-time `[Larceny] Ninja base destroyed — …`; optional in-game line if `PROCYON_DEBUG=larceny_ledger`.~~

### 3.3 Turtle on our side (bunkers, PF, float CCs)

- **Main + natural:** Main as “turtle”; natural with 2 bunkers and PF at chokes or in range of PF.
- **Marines in bunkers:** Fill bunkers; rally new Marines to bunkers or safe rally.
- **Float CCs:** Build CCs in main (or natural), lift and float to new expansion when money and map allow; land and convert to orbital or PF.

### 3.4 Marine waves and upgrades

- **Production:** Barracks (and later factory/starport if needed) producing mainly Marines; “increasingly large waves” = batch into groups and send on attack command at intervals.
- **Upgrades:** Infantry upgrades (e.g. +1 weapons, then armor) when engineering bay is available.

### 3.5 Build architecture (modular mix-and-match)

- **Goal:** Build definitions compose reusable modules, instead of hard-coding one monolithic on-step script.
- **Build config:** Each build declares: opening/build-runner name, enabled modules, and module params (timing, unit mix, expansion style).
- **Core modules (initial):** `claimjumper_opening`, `normal_expand`, `marine_core`, `viking_transition`, `hellbat_bc_transition`.
- **Execution model:** Keep one orchestrator that runs enabled modules in priority order each frame; modules own their own one-shot latches and state.
- **Debug model:** Debug tags report module telemetry (e.g. claimjumper SCV trace) but do not define strategy behavior.
- **Near-term build IDs:** `standard`, `claimjumper`, `claimjumper_marine_viking`, `claimjumper_hellbat_bc`.

**Deliverable:** Ninja Turtle v0 playable: turtle at home, Claimjumper at enemy 4th, Larceny Ledger tracking ninja income, marine waves with upgrades.

---

## Phase 4: Ninja Turtle v1 polish and extra modules

- **Ninja Turtle tuning:** When enemy finds the ninja base:  pull SCVs, try to hold, or abandon and rely on our-side economy. Adjust marine wave size/timing from game length and army size.
- **Creep lawnmower:** Raven + Marines (and/or Banshees); path along creep, clear tumors; avoid overcommitting. Enable in Zerg-facing builds.
- **Mass viking hit squads:** Vikings land at drone-heavy base, kill workers, lift and leave. Enable vs Zerg or when desired.
- **Aggressive overlord denial:** Viking(s) on patrol to shoot down overlords. Module for Zerg matchups.
- **Marauder harass:** Medivac + Marauders (stim, shield, concussive); hit one base then another; prioritize survivability (pickup, retreat).

---

## Phase 5: AI Arena readiness

- **Entrypoint:** Bot launchable by AI Arena (no interactive input; map/race from their config).
- **Maps:** Use ladder/Arena map names and paths; document map-specific assumptions (e.g. “enemy 4th” in Claimjumper).
- **Race matching:** Bot declares Terran; read opponent race from game or config for strategy selection (e.g. overlord denial vs Zerg only).
- **Stability:** Run many games locally; fix crashes and deadlocks (e.g. SCVs stuck, build order stalls).

---

## Phase 6: Future work (additional modules and strategies)

Strategy and build are synonomous. They represent the overall theory of the game, and dictate things like unit composition, build order, etc.

Strategies

- Claimjump
  - Marines
  - Reaper Viking

Modules/Behaviors: Micro

- **Repair strategies:** Quick fix (SCV repairs high-value damaged units); tactical repair bases (forward SCVs); Mules jump (MULEs with harassment BCs).
- **Chill tanks:** Siege/unsiege logic considering nearby enemies and other tank coverage; usable in mech builds.
- **Underexplored units:** Cyclone, Viking, BC, Mine, Thor, Ghost, Liberator (dual air/ground); in-building repair (Bunker, Medivac, CC); Hellbat + Medivac + SCV repair.
- Additional strategies beyond Ninja Turtle v0 as desired.

---

## Chores

- **Config:** Map name (and optionally race/difficulty) from config or env so the same code can later target AI Arena.
- **Build selection config:** Build/strategy name from config or env (`PROCYON_BUILD` now; later promote to a stable config surface for Arena/runtime).
- **Polish (later):** (1) Depot/barracks "order once" logic: add robustness when the assigned SCV never starts construction (e.g. destroyed or blocked)—e.g. timeout or retry and clear the pending flag. (2) Ares placement is brittle and relies on map assumptions; add fallback to building near a safe point (e.g. ramp) if request_building_placement fails or the build never proceeds.
- Ledger accounting is kinda fudgy; it can't track exact deposits so it tracks state changes of any SCVs nearby. It also doesn't track the exact value of a given base, it's just a static guess based on 20 SCVs, a PF, and 2 extractors.

