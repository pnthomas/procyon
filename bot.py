"""
Procyon — Terran SC2 bot (ares-sc2).
Phase 2: Build Runner opener (2 depots, 2 barracks), then train marines and maintain supply.
"""

import os
import sys

# Project root (directory containing this file)
_here = os.path.dirname(os.path.abspath(__file__))
_vendor = os.path.join(_here, "vendor")
if os.path.isdir(_vendor):
    sys.path.insert(0, _vendor)

# ares-sc2 installs as site-packages/src/ares; ensure that path is visible
for _p in sys.path:
    if _p:
        _src = os.path.join(_p, "src")
        if os.path.isfile(os.path.join(_src, "ares", "__init__.py")):
            sys.path.insert(0, _src)
            break

from ares import AresBot
from ares.consts import UnitRole
from sc2.ids.unit_typeid import UnitTypeId


def _parse_debug_tags() -> set:
    """Parse PROCYON_DEBUG env (comma-separated), e.g. build_order,macro. Empty = no debug output."""
    raw = os.environ.get("PROCYON_DEBUG", "").strip()
    return set(filter(None, (s.strip() for s in raw.split(","))))


class ProcyonBot(AresBot):
    """Terran bot: Build Runner opener (2 depots, 2 barracks); then SCVs, marines, and supply."""

    def _debug_tags(self) -> set:
        if not hasattr(self, "_cached_debug_tags"):
            self._cached_debug_tags = _parse_debug_tags()
        return self._cached_debug_tags

    async def _log(self, tag: str, message: str, chat: bool = False) -> None:
        """If tag is in PROCYON_DEBUG (e.g. PROCYON_DEBUG=build_order,macro), print and optionally chat."""
        if tag not in self._debug_tags():
            return
        prefix = f"[Procyon][{tag}]"
        print(f"{prefix} {message}")
        if chat:
            try:
                client = getattr(self, "_client", None)
                if client and hasattr(client, "chat_send"):
                    await client.chat_send(f"{prefix} {message}", team_only=False)
            except Exception:
                pass

    def _base_saturated(self, cc) -> bool:
        """True if this CC's base has at least 16 workers on minerals and 6 on gas (2 geysers)."""
        try:
            wt = self.mediator.get_worker_tag_to_townhall_tag
            mineral_d = self.mediator.get_worker_to_mineral_patch_dict
            gas_d = self.mediator.get_worker_to_vespene_dict
        except Exception:
            wt = mineral_d = gas_d = {}
        worker_tags_at_cc = [tag for tag, th in wt.items() if th == cc.tag]
        mineral_count = sum(1 for tag in worker_tags_at_cc if tag in mineral_d)
        gas_count = sum(1 for tag in worker_tags_at_cc if tag in gas_d)
        # Fallback when mediator has no assignments (e.g. Mining not used): use workers near base
        if not worker_tags_at_cc and self.workers:
            nearby = self.workers.closer_than(25, cc.position)
            if len(nearby) >= 22:  # 16 + 6
                return True
            if len(nearby) < 16:
                return False
        refineries = self.structures(UnitTypeId.REFINERY).closer_than(15, cc.position)
        geyser_count = len(refineries)
        if geyser_count == 0:
            return mineral_count >= 16
        if geyser_count == 1:
            return mineral_count >= 16 and gas_count >= 3
        return mineral_count >= 16 and gas_count >= 6

    async def on_step(self, iteration: int):
        await super().on_step(iteration)

        if iteration == 0:
            print("Hello World! Procyon (Terran) is running.")

        # Tag when each opening building completes (so we can verify order vs build runner)
        planned_depots, planned_rax = 2, 2  # TwoRaxMarines opener
        actual_depots = len(self.structures(UnitTypeId.SUPPLYDEPOT).ready)
        actual_rax = len(self.structures(UnitTypeId.BARRACKS).ready)
        last_depots = getattr(self, "_last_tagged_depots", 0)
        last_rax = getattr(self, "_last_tagged_rax", 0)
        if actual_depots > last_depots and actual_depots <= planned_depots:
            self._last_tagged_depots = actual_depots
            await self._log(
                "build_order",
                f"Supply depot {actual_depots}/{planned_depots} complete",
                chat=True,
            )
        if actual_rax > last_rax and actual_rax <= planned_rax:
            self._last_tagged_rax = actual_rax
            await self._log(
                "build_order",
                f"Barracks {actual_rax}/{planned_rax} complete",
                chat=True,
            )

        # After the opening build order is done, run dynamic macro
        build_done = getattr(
            self, "build_order_runner", None
        ) and getattr(self.build_order_runner, "build_completed", False)
        if not build_done:
            return

        # Tag 1: Build runner considers itself done (all commands issued)
        runner = getattr(self, "build_order_runner", None)
        opening = getattr(runner, "chosen_opening", None) or "(no opening loaded)"
        if not getattr(self, "_build_runner_steps_issued_printed", False):
            self._build_runner_steps_issued_printed = True
            msg = (
                f"Build runner: all steps issued ({opening}). "
                f"Planned: {planned_depots} depots, {planned_rax} barracks. "
                f"Actual: {actual_depots} depots, {actual_rax} barracks. "
                "Switching to dynamic."
            )
            print(f"[Procyon] {msg}")
            try:
                client = getattr(self, "_client", None)
                if client and hasattr(client, "chat_send"):
                    await client.chat_send(msg, team_only=False)
            except Exception:
                pass

        # Tag 2: All buildings from the build order actually completed
        structures_ready = actual_depots >= planned_depots and actual_rax >= planned_rax
        if structures_ready and not getattr(self, "_build_order_buildings_complete_printed", False):
            self._build_order_buildings_complete_printed = True
            msg = (
                f"Build order: all buildings complete. "
                f"{actual_depots} depots, {actual_rax} barracks."
            )
            print(f"[Procyon] {msg}")
            try:
                client = getattr(self, "_client", None)
                if client and hasattr(client, "chat_send"):
                    await client.chat_send(msg, team_only=False)
            except Exception:
                pass

        # Send idle SCVs (e.g. finished building) back to gathering
        if self.workers.idle and self.mineral_field:
            for worker in self.workers.idle:
                self.mediator.assign_role(tag=worker.tag, role=UnitRole.GATHERING)
                mineral = self.mineral_field.closest_to(worker.position)
                worker.gather(mineral)

        # Train SCVs from idle CCs when we can afford and base is not saturated
        if self.townhalls:
            for cc in self.townhalls:
                if cc.is_idle and self.can_afford(UnitTypeId.SCV) and not self._base_saturated(cc):
                    cc.train(UnitTypeId.SCV)

        # Train marines from idle barracks when we can afford and have supply
        if self.supply_used < self.supply_cap and self.can_afford(UnitTypeId.MARINE):
            for rax in self.structures(UnitTypeId.BARRACKS).ready:
                if rax.is_idle:
                    rax.train(UnitTypeId.MARINE)

        # Build Supply Depot when approaching supply block.
        # Issue the order only once per depot; clear when we see one in progress (avoids
        # position jumping from re-issuing every frame). TODO: robustness if the assigned
        # SCV never starts construction (e.g. destroyed or blocked)—we may need a timeout
        # or retry and clear the pending flag.
        depot_pending = (
            self.structure_pending(UnitTypeId.SUPPLYDEPOT)
            if hasattr(self, "structure_pending")
            else self.mediator.get_building_counter.get(UnitTypeId.SUPPLYDEPOT, 0)
        )
        supply_depot_order_pending = getattr(
            self, "_supply_depot_order_pending", False
        )
        if depot_pending > 0:
            self._supply_depot_order_pending = False
        if (
            self.supply_used >= self.supply_cap - 2
            and self.can_afford(UnitTypeId.SUPPLYDEPOT)
            and depot_pending == 0
            and not supply_depot_order_pending
        ):
            base = self.townhalls.first.position if self.townhalls else self.start_location
            # Use ares pre-calculated placement so depots don't block the mineral line.
            # TODO: brittle—relies on map/base assumptions; add fallback to building
            # near a safe point (e.g. ramp) if placement fails or build never proceeds.
            pos = self.mediator.request_building_placement(
                base_location=base,
                structure_type=UnitTypeId.SUPPLYDEPOT,
                wall=False,
                find_alternative=True,
            )
            if pos is not None:
                worker = self.mediator.select_worker(target_position=pos)
                if worker is not None:
                    if self.mediator.build_with_specific_worker(
                        worker=worker,
                        structure_type=UnitTypeId.SUPPLYDEPOT,
                        pos=pos,
                    ):
                        self._supply_depot_order_pending = True

        # Fallback: build barracks if opening didn't produce them (e.g. Build Runner
        # failed or barracks steps didn't complete). Target 2 barracks; order one at a time.
        rax_count = len(self.structures(UnitTypeId.BARRACKS).ready) + (
            self.structure_pending(UnitTypeId.BARRACKS)
            if hasattr(self, "structure_pending")
            else self.mediator.get_building_counter.get(UnitTypeId.BARRACKS, 0)
        )
        barracks_order_pending = getattr(self, "_barracks_order_pending", False)
        if rax_count >= 2:
            self._barracks_order_pending = False
        if (
            rax_count < 2
            and self.can_afford(UnitTypeId.BARRACKS)
            and not barracks_order_pending
            and len(self.structures(UnitTypeId.SUPPLYDEPOT).ready) >= 1
        ):
            base = self.townhalls.first.position if self.townhalls else self.start_location
            pos = self.mediator.request_building_placement(
                base_location=base,
                structure_type=UnitTypeId.BARRACKS,
                wall=False,
                find_alternative=True,
            )
            if pos is not None:
                worker = self.mediator.select_worker(target_position=pos)
                if worker is not None:
                    if self.mediator.build_with_specific_worker(
                        worker=worker,
                        structure_type=UnitTypeId.BARRACKS,
                        pos=pos,
                    ):
                        self._barracks_order_pending = True
        if (
            hasattr(self, "structure_pending")
            and self.structure_pending(UnitTypeId.BARRACKS) > 0
        ):
            self._barracks_order_pending = False


def main():
    import os
    from pathlib import Path

    from sc2.main import run_game
    from sc2.data import Race, Difficulty
    from sc2.maps import get as get_map
    from sc2.paths import Paths
    from sc2.player import Bot, Computer

    # Ensure ares-sc2 Build Runner finds _builds.yml (it looks in current working directory)
    os.chdir(_here)

    # Use Blizzard Maps folder if it exists (macOS: ~/Library/Application Support/...)
    _blizzard_maps = Path.home() / "Library/Application Support/Blizzard/StarCraft II/Maps"
    if _blizzard_maps.is_dir():
        _ = Paths.MAPS  # trigger Paths setup
        Paths.MAPS = _blizzard_maps

    game_map = get_map("TorchesAIE_v4")
    # SC2 client resolves relative paths under the game install; pass absolute path so it finds the map in Blizzard folder
    game_map.relative_path = game_map.path

    run_game(
        game_map,
        [Bot(Race.Terran, ProcyonBot()), Computer(Race.Zerg, Difficulty.Easy)],
        realtime=False,
    )


if __name__ == "__main__":
    main()
