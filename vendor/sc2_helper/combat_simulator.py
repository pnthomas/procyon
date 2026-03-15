# Vendored from AresSC2/ares-sc2 (sc2_helper/combat_simulator.py)

from typing import Tuple

from .sc2_helper import CombatPredictor, CombatSettings


class CombatSimulator:
    def __init__(self):
        self.combat_predictor: CombatPredictor = CombatPredictor()
        self.combat_settings: CombatSettings = CombatSettings()

    def debug(self, value: bool):
        """Print debug information. Warning: Slow! Do not enable in production. Default: False."""
        self.combat_settings.debug = value

    def bad_micro(self, value: bool):
        """Set value of bad_micro for CombatSettings. Default: False."""
        self.combat_settings.bad_micro = value

    def enable_splash(self, value: bool):
        """TODO: Implement splash damage in combat simulator. Default: True."""
        self.combat_settings.enable_splash = value

    def enable_timing_adjustment(self, value: bool):
        """Take distance between units into account. Default: False."""
        self.combat_settings.enable_timing_adjustment = value

    def enable_surround_limits(self, value: bool):
        """Enable surround limits for melee units. Default: True."""
        self.combat_settings.enable_surround_limits = value

    def enable_melee_blocking(self, value: bool):
        """Melee units blocking each other. Default: True."""
        self.combat_settings.enable_melee_blocking = value

    def workers_do_no_damage(self, value: bool):
        """Don't take workers into account. Default: False."""
        self.combat_settings.workers_do_no_damage = value

    def assume_reasonable_positioning(self, value):
        """Assume units are decently split. Default: True."""
        self.combat_settings.assume_reasonable_positioning = value

    def max_time(self, value: float):
        """Max game time to spend in simulation. Default: 100 000.00."""
        self.combat_settings.max_time = value

    def start_time(self, value: float):
        """Start time of simulation. Default: 0.0."""
        self.combat_settings.start_time = value

    def predict_engage(
        self, own_units, enemy_units, optimistic: bool = False, defender_player: int = 0
    ) -> Tuple[bool, float]:
        """Predict an engagement; returns (winner_is_us, health_left)."""
        if optimistic:
            winner, health_left = self.combat_predictor.predict_engage(
                own_units, enemy_units, defender_player, self.combat_settings
            )
            return (winner == 1, health_left)
        else:
            if defender_player == 1:
                defender_player = 2
            elif defender_player == 2:
                defender_player = 1
            winner, health_left = self.combat_predictor.predict_engage(
                enemy_units, own_units, defender_player, self.combat_settings
            )
            return (winner == 2, health_left)
