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

- **Scout / map:** Identify enemy 4th (or equivalent expansion on opponent’s side).
- **Send SCV:** Dispatch SCV(s) early; path to that base (avoid enemy if visible).
- **Build:** Planetary Fortress at that location; add extractors; saturate with SCVs (or partial + MULEs).
- **Defend / retreat:** Simple rule when base is under attack (pull SCVs or accept loss).
- **Integration:** Enabled only when Ninja Turtle (or another build) enables Claimjumper; build order leaves minerals/gas and an SCV available at the right time.

### 3.2 Larceny Ledger (ninja-base resource tracking)

- **Purpose:** Track total resources collected by the ninja base to measure cost-effectiveness and how much we “steal” before it’s found.
- **Implementation (delta check):** Store total minerals (and optionally gas) at iteration N; at N+1, if total increased, find workers that just finished GATHER/RETURN near a base; attribute the increase to the nearest base; if that base is the ninja CC/PF, add to the ledger.
- **Ledger state:** Running totals for the ninja base only; expose for logging or post-game analysis.
- **Integration:** Update only when Claimjumper is active and the ninja base exists; attribute by distance (worker finished return near this CC/PF).
- Add a tag when the base is destroyed to report how much that base gathered verus the total invested (use 1,700 minerals and 150 gas as static estimate for simplicity for now).

### 3.3 Turtle on our side (bunkers, PF, float CCs)

- **Main + natural:** Main as “turtle”; natural with 2 bunkers and PF at chokes or in range of PF.
- **Marines in bunkers:** Fill bunkers; rally new Marines to bunkers or safe rally.
- **Float CCs:** Build CCs in main (or natural), lift and float to new expansion when money and map allow; land and convert to orbital or PF.

### 3.4 Marine waves and upgrades

- **Production:** Barracks (and later factory/starport if needed) producing mainly Marines; “increasingly large waves” = batch into groups and send on attack command at intervals.
- **Upgrades:** Infantry upgrades (e.g. +1 weapons, then armor) when engineering bay is available.

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

- **Repair strategies:** Quick fix (SCV repairs high-value damaged units); tactical repair bases (forward SCVs); Mules jump (MULEs with harassment BCs).
- **Chill tanks:** Siege/unsiege logic considering nearby enemies and other tank coverage; usable in mech builds.
- **Underexplored units:** Cyclone, Viking, BC, Mine, Thor, Ghost, Liberator (dual air/ground); in-building repair (Bunker, Medivac, CC); Hellbat + Medivac + SCV repair.
- Additional strategies beyond Ninja Turtle v0 as desired.

---

## Chores

- **Config:** Map name (and optionally race/difficulty) from config or env so the same code can later target AI Arena.
- **Polish (later):** (1) Depot/barracks "order once" logic: add robustness when the assigned SCV never starts construction (e.g. destroyed or blocked)—e.g. timeout or retry and clear the pending flag. (2) Ares placement is brittle and relies on map assumptions; add fallback to building near a safe point (e.g. ramp) if request_building_placement fails or the build never proceeds.
- Ledger accounting is kinda fudgy; it can't track exact deposits so it tracks state changes of any SCVs nearby. It also doesn't track the exact value of a given base, it's just a static guess based on 20 SCVs, a PF, and 2 extractors.

