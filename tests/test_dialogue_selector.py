"""Dialogue random selection isolation and repeat-avoidance tests."""

from __future__ import annotations

import random

from desktop_pet.dialogue.selector import DialogueSelector


def test_fixed_seed_is_reproducible_without_mutating_input() -> None:
    source = ["一", "二", "三"]
    first = DialogueSelector(source, seed=42)
    second = DialogueSelector(source, seed=42)

    assert [first.choose() for _ in range(12)] == [second.choose() for _ in range(12)]
    assert source == ["一", "二", "三"]
    assert first.dialogues == tuple(source)


def test_selector_does_not_change_global_random_state() -> None:
    random.seed(891)
    before = random.getstate()
    selector = DialogueSelector(("甲", "乙", "丙"), seed=9)
    selector.choose()

    assert random.getstate() == before


def test_single_line_is_stable_and_multi_line_never_repeats_immediately() -> None:
    single = DialogueSelector(("唯一",), seed=1)
    assert [single.choose() for _ in range(4)] == ["唯一"] * 4

    multiple = DialogueSelector(("甲", "乙", "丙"), seed=2)
    selected = [multiple.choose() for _ in range(50)]
    assert all(left != right for left, right in zip(selected, selected[1:], strict=False))
    assert multiple.selection_count == 50


def test_selection_occurs_only_when_choose_is_called() -> None:
    selector = DialogueSelector(("甲", "乙"), seed=3)
    assert selector.selection_count == 0
    selector.choose()
    assert selector.selection_count == 1
