"""Alpha-aware, timer-free click interaction for the desktop pet."""

from desktop_pet.interaction.click_reaction import click_reaction_transform
from desktop_pet.interaction.controller import InteractionController
from desktop_pet.interaction.hit_test import is_character_pixel, map_window_point_to_source

__all__ = [
    "InteractionController",
    "click_reaction_transform",
    "is_character_pixel",
    "map_window_point_to_source",
]
