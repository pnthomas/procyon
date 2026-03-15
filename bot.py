"""
Procyon — Terran SC2 bot (ares-sc2).
Phase 1: Hello-world entrypoint; trains SCVs and gathers.
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
from sc2.ids.unit_typeid import UnitTypeId


class ProcyonBot(AresBot):
    """Minimal Terran bot: gather minerals, train SCVs from idle CCs."""

    async def on_step(self, iteration: int):
        if iteration == 0:
            print("Hello World! Procyon (Terran) is running.")

        # Train SCVs when we have an idle CC and can afford it
        if self.townhalls:
            for cc in self.townhalls:
                if cc.is_idle and self.can_afford(UnitTypeId.SCV):
                    cc.train(UnitTypeId.SCV)


def main():
    from pathlib import Path

    from sc2.main import run_game
    from sc2.data import Race, Difficulty
    from sc2.maps import get as get_map
    from sc2.paths import Paths
    from sc2.player import Bot, Computer

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
