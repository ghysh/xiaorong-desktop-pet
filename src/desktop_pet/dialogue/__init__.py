"""Read-only click dialogue selection and presentation coordination."""

from desktop_pet.dialogue.controller import DialogueController
from desktop_pet.dialogue.repository import DialogueFileError, DialogueRepository
from desktop_pet.dialogue.selector import DialogueSelector

__all__ = [
    "DialogueController",
    "DialogueFileError",
    "DialogueRepository",
    "DialogueSelector",
]
