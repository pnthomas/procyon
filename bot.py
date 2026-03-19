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

from typing import TYPE_CHECKING

from ares import AresBot
from ares.consts import UnitRole
from sc2.data import ActionResult
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId

if TYPE_CHECKING:
    from sc2.position import Point2


def _parse_debug_tags() -> set:
    """Parse PROCYON_DEBUG env (comma-separated), e.g. build_order,macro. Empty = no debug output."""
    raw = os.environ.get("PROCYON_DEBUG", "").strip()
    return set(filter(None, (s.strip() for s in raw.split(","))))


class ProcyonBot(AresBot):
    """Terran bot: Build Runner opener (2 depots, 2 barracks); then SCVs, marines, and supply."""
    # Claimjumper and baseline tuning constants (readability: avoid scattered magic numbers).
    CLAIMJUMPER_EXPANSION_RANK = 5
    CLAIMJUMPER_TRACE_INTERVAL_S = 3.0
    CLAIMJUMPER_MOVE_NUDGE_INTERVAL_S = 2.0
    CLAIMJUMPER_BUILD_RETRY_INTERVAL_S = 1.0
    CLAIMJUMPER_FAIL_LOG_INTERVAL_S = 5.0
    CLAIMJUMPER_ARRIVAL_RADIUS = 10.0
    CLAIMJUMPER_IDLE_NUDGE_RADIUS = 12.0
    CLAIMJUMPER_PATHING_STAGNANT_MOVE_DELTA = 0.35
    CLAIMJUMPER_PATHING_STAGNANT_TIME_S = 9.0
    CLAIMJUMPER_UNREACHABLE_STREAK_FOR_REPORT = 3

    def _debug_tags(self) -> set:
        if not hasattr(self, "_cached_debug_tags"):
            self._cached_debug_tags = _parse_debug_tags()
        return self._cached_debug_tags

    def _active_build(self) -> str:
        """
        Selected build/strategy name.
        Examples: standard, claimjumper, claimjumper_marine_viking, claimjumper_hellbat_bc
        """
        if not hasattr(self, "_cached_active_build"):
            self._cached_active_build = os.environ.get("PROCYON_BUILD", "standard").strip().lower()
        return self._cached_active_build

    def _claimjumper_enabled(self) -> bool:
        """Whether current selected build uses claimjumper opening behavior."""
        return self._active_build().startswith("claimjumper")

    def _claimjumper_trace_enabled(self) -> bool:
        """Trace-only flag for claimjumper SCV telemetry."""
        return self._claimjumper_location_debug_enabled()

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

    def _enemy_start_location(self) -> "Point2 | None":
        """Infer enemy start position (1v1: the start that is not ours). Returns None if unknown."""
        locations = getattr(self, "enemy_start_locations", None) or []
        if not locations:
            return None
        ours = self.start_location
        not_ours = [p for p in locations if p != ours]
        if not not_ours:
            return locations[0]
        # If multiple possible enemy starts (e.g. 4-player), use the one farthest from us.
        return max(not_ours, key=lambda p: p.distance_to(ours))

    def get_claimjumper_target(self, rank: int | None = None) -> "Point2 | None":
        """
        Expansion that is the N-th closest to the enemy start (claimjumper base location).
        Rank 4 = 4th base, rank 5 = 5th base. Cached after first call.
        """
        if rank is None:
            rank = self.CLAIMJUMPER_EXPANSION_RANK
        cache = getattr(self, "_claimjumper_target_cache", None)
        if cache is None:
            self._claimjumper_target_cache = {}
            cache = self._claimjumper_target_cache
        if rank in cache:
            return cache[rank]

        enemy_start = self._enemy_start_location()
        if enemy_start is None:
            return None
        expansions = getattr(self, "expansion_locations", None)
        if not expansions:
            return None
        positions = list(expansions.keys())

        # Prefer expansions on enemy side: closer to enemy start than to ours.
        ours = self.start_location
        enemy_side = [p for p in positions if p.distance_to(enemy_start) < p.distance_to(ours)]
        candidate_list = enemy_side if len(enemy_side) >= rank else positions

        # Sort by distance to enemy start; take N-th (1-based rank -> index rank-1).
        sorted_positions = sorted(candidate_list, key=lambda p: p.distance_to(enemy_start))
        if len(sorted_positions) < rank:
            target = sorted_positions[-1] if sorted_positions else None
        else:
            target = sorted_positions[rank - 1]
        cache[rank] = target
        return target

    def _claimjumper_location_debug_enabled(self) -> bool:
        """True when we should emit SCV trace telemetry for claimjumper location behavior."""
        return "claimjumper_location" in self._debug_tags()

    def _expand_baseline_enabled(self) -> bool:
        """True when we should run the minimal natural expansion baseline."""
        return "expand_baseline" in self._debug_tags()

    def _claimjumper_is_unreachable_cc_error(self, worker_tag: int) -> bool:
        """True if the latest action error is 'couldn't reach target' for this worker's CC build."""
        action_errors = getattr(self.state, "action_errors", []) or []
        if not action_errors:
            return False
        last = action_errors[-1]
        return (
            getattr(last, "unit_tag", None) == worker_tag
            and getattr(last, "result", None) == ActionResult.CouldntReachTarget
            and getattr(last, "ability_id", None) == AbilityId.TERRANBUILD_COMMANDCENTER
        )

    def _townhall_at_point(self, point: "Point2", radius: float = 6.0):
        """Return our townhall near a point, if any."""
        townhalls = self.townhalls.closer_than(radius, point) if self.townhalls else None
        return townhalls.first if townhalls else None

    def _claimjumper_keep_mining(self) -> None:
        """Keep economy alive during claimjumper-location debug mode."""
        if self.workers.idle and self.mineral_field:
            claimjumper_tag = getattr(self, "_claimjumper_debug_worker_tag", None)
            for worker in self.workers.idle:
                if claimjumper_tag is not None and worker.tag == claimjumper_tag:
                    continue
                try:
                    self.mediator.assign_role(tag=worker.tag, role=UnitRole.GATHERING)
                except Exception:
                    pass
                mineral = self.mineral_field.closest_to(worker.position)
                worker.gather(mineral)

    async def _run_claimjumper_build_logic(self, tag: str, trace: bool = False) -> None:
        """
        Shared claimjumper routine:
        1) identify target expansion
        2) assign one SCV as scout/claimer
        3) move SCV to target
        4) place and start Command Center
        """
        target = self.get_claimjumper_target()
        if target is None:
            if not getattr(self, "_claimjumper_target_miss_logged", False):
                self._claimjumper_target_miss_logged = True
                await self._log(
                    tag,
                    "No claimjumper target (enemy_start or expansion_locations missing)",
                    chat=True,
                )
            return

        if not getattr(self, "_claimjumper_target_logged", False):
            self._claimjumper_target_logged = True
            await self._log(
                tag,
                f"Location identified: target {target} (rank {self.CLAIMJUMPER_EXPANSION_RANK} from enemy start)",
                chat=True,
            )

        # Debug mode behavior is intentionally one-shot: attempt this location once only.
        if getattr(self, "_claimjumper_single_attempt_done", False):
            if not getattr(self, "_claimjumper_single_attempt_done_logged", False):
                self._claimjumper_single_attempt_done_logged = True
                await self._log(
                    tag,
                    "Single-attempt mode: no further claimjumper rebuild attempts will be made.",
                    chat=True,
                )
            return

        if self._townhall_at_point(target) is not None:
            if not getattr(self, "_claimjumper_cc_complete_logged", False):
                self._claimjumper_cc_complete_logged = True
                await self._log(
                    tag,
                    f"Townhall established near target at {target}",
                    chat=True,
                )
            return

        debug_tag = getattr(self, "_claimjumper_debug_worker_tag", None)
        worker = self.workers.find_by_tag(debug_tag) if (debug_tag is not None and self.workers) else None
        if worker is None and self.workers:
            worker = self.workers.closest_to(target)
            self._claimjumper_debug_worker_tag = worker.tag
            try:
                self.mediator.assign_role(tag=worker.tag, role=UnitRole.SCOUTING)
            except Exception:
                pass
            await self._log(
                tag,
                f"SCV dispatched: {worker.tag} toward {target}",
                chat=True,
            )
        if worker is None:
            return

        # Optional periodic telemetry for "what is the SCV thinking?".
        if trace:
        next_trace_time = getattr(self, "_claimjumper_next_trace_time", 0.0)
            if self.time >= next_trace_time:
            self._claimjumper_next_trace_time = self.time + self.CLAIMJUMPER_TRACE_INTERVAL_S
                order_summary = "idle"
                if worker.orders:
                    try:
                        first = worker.orders[0]
                        ability = getattr(first, "ability", None)
                        ability_id = getattr(ability, "id", ability)
                        target_obj = getattr(first, "target", None)
                        order_summary = f"ability={ability_id}, target={target_obj}"
                    except Exception:
                        order_summary = "orders_present_unreadable"
                error_hint = "none"
                try:
                    action_errors = getattr(self.state, "action_errors", []) or []
                    if action_errors:
                        last = action_errors[-1]
                        unit_tag = getattr(last, "unit_tag", None)
                        result = getattr(last, "result", None)
                        ability_id = getattr(last, "ability_id", None)
                        error_hint = (
                            f"unit={unit_tag}, result={result}, ability={ability_id}"
                        )
                except Exception:
                    pass
                cc_near_target = len(self.structures(UnitTypeId.COMMANDCENTER).closer_than(12, target))
                await self._log(
                    tag,
                    (
                        f"SCV trace: tag={worker.tag}, pos={worker.position}, "
                        f"dist_to_target={worker.position.distance_to(target):.1f}, "
                        f"orders={order_summary}, cc_near_target={cc_near_target}, "
                        f"last_action_error={error_hint}"
                    ),
                    chat=False,
                )
                # Track movement health for pathing diagnostics.
                last_pos = getattr(self, "_claimjumper_last_trace_pos", None)
                moved = (
                    worker.position.distance_to(last_pos) if last_pos is not None else 999.0
                )
                self._claimjumper_last_trace_pos = worker.position
            if moved < self.CLAIMJUMPER_PATHING_STAGNANT_MOVE_DELTA:
                    if not hasattr(self, "_claimjumper_stagnant_since"):
                        self._claimjumper_stagnant_since = self.time
                else:
                    self._claimjumper_stagnant_since = self.time

        # Informational only: exact expansion centers can be awkward for worker pathing.
        if worker.position.distance_to(target) < self.CLAIMJUMPER_ARRIVAL_RADIUS and not getattr(
            self, "_claimjumper_debug_arrived_logged", False
        ):
            self._claimjumper_debug_arrived_logged = True
            await self._log(
                tag,
                f"SCV arrived near target at {worker.position}",
                chat=True,
            )

        # If a CC is already being built near the target, report once and stop issuing orders.
        cc_pending = self.structures(UnitTypeId.COMMANDCENTER).not_ready.closer_than(9, target)
        if cc_pending:
            if not getattr(self, "_claimjumper_cc_started_logged", False):
                self._claimjumper_cc_started_logged = True
                await self._log(
                    tag,
                    f"Command Center started near target at {cc_pending.first.position}",
                    chat=True,
                )
            return

        # Try to start CC at target using the same path as the working baseline:
        # prefer expand_now(location=target), fallback to build(... near=target).
        if not self.can_afford(UnitTypeId.COMMANDCENTER):
            return

        # Keep the scout nudged toward target only when it is idle and far away.
        if worker.is_idle and worker.position.distance_to(target) > self.CLAIMJUMPER_IDLE_NUDGE_RADIUS:
            if self.time >= getattr(self, "_claimjumper_next_move_nudge_time", 0.0):
                self._claimjumper_next_move_nudge_time = self.time + self.CLAIMJUMPER_MOVE_NUDGE_INTERVAL_S
                worker.move(target)

        # Use a short retry cadence so we don't spam build requests every frame.
        if self.time < getattr(self, "_claimjumper_next_build_attempt_time", 0.0):
            return
        self._claimjumper_next_build_attempt_time = self.time + self.CLAIMJUMPER_BUILD_RETRY_INTERVAL_S

        issued = False
        issued_via = None
        try:
            # Works like natural expansion but at a custom location.
            await self.expand_now(location=target)
            issued = True
            issued_via = "expand_now"
        except Exception:
            issued = False

        if not issued:
            try:
                issued = await self.build(
                    UnitTypeId.COMMANDCENTER,
                    near=target,
                    max_distance=12,
                    random_alternative=True,
                    placement_step=1,
                )
                issued_via = "build_near_target" if issued else None
            except Exception:
                issued = False

        if issued:
            # Log once on initial accepted order. Construction start/complete is validated separately.
            if not getattr(self, "_claimjumper_cc_order_logged", False):
                self._claimjumper_cc_order_logged = True
                self._claimjumper_single_attempt_done = True
                await self._log(
                    tag,
                    f"Command Center order accepted near target {target} (via {issued_via})",
                    chat=True,
                )
            return

        # Emit a periodic failure breadcrumb with resource/action-error context.
        next_fail_log_time = getattr(self, "_claimjumper_next_fail_log_time", 0.0)
        if self.time >= next_fail_log_time:
            self._claimjumper_next_fail_log_time = self.time + self.CLAIMJUMPER_FAIL_LOG_INTERVAL_S
            error_hint = ""
            try:
                action_errors = getattr(self.state, "action_errors", []) or []
                if action_errors:
                    last = action_errors[-1]
                    code = getattr(last, "result", None)
                    error_hint = f", last_action_error={code}"
            except Exception:
                pass
            await self._log(
                tag,
                f"Command Center order not accepted near target {target} (minerals={self.minerals}{error_hint})",
                chat=True,
            )
        # If this is repeatedly the specific CC unreachable error while stationary, report likely map pathing issue.
        if trace:
            if self._claimjumper_is_unreachable_cc_error(worker.tag):
                self._claimjumper_unreachable_error_streak = (
                    getattr(self, "_claimjumper_unreachable_error_streak", 0) + 1
                )
            else:
                self._claimjumper_unreachable_error_streak = 0
            stagnant_since = getattr(self, "_claimjumper_stagnant_since", self.time)
            stagnant_for = self.time - stagnant_since
            if (
            getattr(self, "_claimjumper_unreachable_error_streak", 0)
            >= self.CLAIMJUMPER_UNREACHABLE_STREAK_FOR_REPORT
            and stagnant_for >= self.CLAIMJUMPER_PATHING_STAGNANT_TIME_S
                and not getattr(self, "_claimjumper_pathing_error_reported", False)
            ):
                self._claimjumper_pathing_error_reported = True
                await self._log(
                    tag,
                    (
                        "Pathing error report: SCV repeatedly gets CouldntReachTarget "
                        "(result=208, ability=318) while not moving. "
                        "This map may have problematic/blocked approach geometry for this expansion target."
                    ),
                    chat=True,
                )

    async def _run_expand_baseline(self, iteration: int) -> None:
        """
        Minimal baseline:
        - keep mining
        - wait for 400 minerals
        - expand to natural via built-in expand_now
        - confirm start/complete by state near natural target
        """
        self._claimjumper_keep_mining()

        if not getattr(self, "_expand_baseline_mode_logged", False):
            self._expand_baseline_mode_logged = True
            await self._log(
                "expand_baseline",
                "expand_baseline active: suspending macro/build-order, mining then expanding to natural",
                chat=True,
            )

        natural = getattr(self, "_expand_baseline_natural_target", None)
        if natural is None:
            try:
                natural = await self.get_next_expansion()
            except Exception:
                natural = None
            self._expand_baseline_natural_target = natural
            if natural is not None:
                await self._log(
                    "expand_baseline",
                    f"Natural target identified at {natural}",
                    chat=True,
                )
            elif iteration > 22 and not getattr(
                self, "_expand_baseline_target_miss_logged", False
            ):
                self._expand_baseline_target_miss_logged = True
                await self._log(
                    "expand_baseline",
                    "Could not identify natural expansion target",
                    chat=True,
                )
                return

        # Completion: any ready townhall near natural.
        if natural is not None:
            ready_near = self.townhalls.ready.closer_than(8, natural) if self.townhalls else None
            if ready_near and not getattr(self, "_expand_baseline_complete_logged", False):
                self._expand_baseline_complete_logged = True
                await self._log(
                    "expand_baseline",
                    f"Natural expansion complete at {ready_near.first.position}",
                    chat=True,
                )
                return

            not_ready_near = (
                self.structures(UnitTypeId.COMMANDCENTER).not_ready.closer_than(10, natural)
            )
            if not_ready_near and not getattr(
                self, "_expand_baseline_started_logged", False
            ):
                self._expand_baseline_started_logged = True
                await self._log(
                    "expand_baseline",
                    f"Natural Command Center started at {not_ready_near.first.position}",
                    chat=True,
                )

        # Issue built-in expansion order once affordable; rely on state checks above for confirmation.
        if (
            natural is not None
            and not getattr(self, "_expand_baseline_order_attempted", False)
            and self.can_afford(UnitTypeId.COMMANDCENTER)
            and not self.already_pending(UnitTypeId.COMMANDCENTER)
            and len(self.townhalls) == 1
        ):
            self._expand_baseline_order_attempted = True
            try:
                await self.expand_now()
                await self._log(
                    "expand_baseline",
                    f"expand_now issued toward natural target {natural}",
                    chat=True,
                )
            except Exception as e:
                self._expand_baseline_order_attempted = False
                await self._log(
                    "expand_baseline",
                    f"expand_now failed: {e}",
                    chat=True,
                )

    async def on_step(self, iteration: int):
        debug_expand_baseline = self._expand_baseline_enabled()
        if debug_expand_baseline:
            if iteration == 0:
                print("Hello World! Procyon (Terran) is running.")
            await self._run_expand_baseline(iteration)
            return
        await super().on_step(iteration)

        if iteration == 0:
            print("Hello World! Procyon (Terran) is running.")

        # Claimjumper opening behavior is build-selected (not a debug mode). The
        # claimjumper_location debug tag only enables SCV telemetry for this behavior.
        if self._claimjumper_enabled():
            log_tag = "claimjumper_location" if self._claimjumper_location_debug_enabled() else "claimjumper"
            await self._run_claimjumper_build_logic(tag=log_tag, trace=self._claimjumper_trace_enabled())

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
            debug_tag = getattr(self, "_claimjumper_debug_worker_tag", None)
            for worker in self.workers.idle:
                # Don't steal back the debug claimjumper worker while we are testing.
                if debug_tag is not None and worker.tag == debug_tag:
                    continue
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

    map_name = os.environ.get("PROCYON_MAP", "IncorporealAIE_v4").strip() or "IncorporealAIE_v4"
    game_map = get_map(map_name)
    # SC2 client resolves relative paths under the game install; pass absolute path so it finds the map in Blizzard folder
    game_map.relative_path = game_map.path

    run_game(
        game_map,
        [Bot(Race.Terran, ProcyonBot()), Computer(Race.Zerg, Difficulty.Easy)],
        realtime=False,
    )


if __name__ == "__main__":
    main()
