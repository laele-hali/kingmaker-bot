"""Randomness interfaces used by pure weather profiles."""

import random
from typing import Protocol


class DiceRoller(Protocol):
    """Minimal injectable interface for rolling an n-sided die."""

    def roll(self, sides: int) -> int:
        ...


class RandomDiceRoller:
    """Production dice roller backed by Python's standard random module."""

    def __init__(self, generator: random.Random | None = None) -> None:
        self._generator = generator or random.Random()

    def roll(self, sides: int) -> int:
        if sides < 1:
            raise ValueError("sides must be positive")
        return self._generator.randint(1, sides)


class ValidatedDiceRoller:
    """Reject invalid values from an injected dice source at the boundary."""

    def __init__(self, roller: DiceRoller) -> None:
        self._roller = roller

    def roll(self, sides: int) -> int:
        value = self._roller.roll(sides)
        if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= sides:
            raise ValueError(f"dice roller must return an integer from 1 to {sides}")
        return value
