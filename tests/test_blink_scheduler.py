"""Local-random, reproducible, event-driven blink scheduling."""

from __future__ import annotations

import random

from desktop_pet.blink.scheduler import BlinkScheduler
from desktop_pet.config import BlinkConfig


def test_fixed_seed_reproduces_due_times_without_touching_global_random() -> None:
    before = random.getstate()
    config = BlinkConfig(seed=20260806)
    first = BlinkScheduler(config)
    second = BlinkScheduler(config)
    first.start(0.0)
    second.start(0.0)
    assert first.next_due_seconds == second.next_due_seconds
    assert config.minimum_interval_seconds <= first.next_due_seconds <= config.maximum_interval_seconds
    assert random.getstate() == before


def test_due_checks_do_not_consume_random_values_per_frame() -> None:
    scheduler = BlinkScheduler(BlinkConfig(seed=7))
    scheduler.start(0.0)
    draws = scheduler.random_draw_count
    for tick in range(1000):
        scheduler.is_due(tick / 1000.0)
    assert scheduler.random_draw_count == draws


def test_double_blink_uses_short_gap_then_returns_to_regular_interval() -> None:
    scheduler = BlinkScheduler(BlinkConfig(seed=11, double_blink_probability=1.0))
    scheduler.start(0.0)
    due = scheduler.next_due_seconds
    assert due is not None
    scheduler.mark_started()
    scheduler.mark_finished(due + 0.195)
    follow_up = scheduler.next_due_seconds
    assert follow_up is not None
    gap = follow_up - (due + 0.195)
    assert 0.08 <= gap <= 0.16
    assert scheduler.follow_up_due
    scheduler.mark_started()
    scheduler.mark_finished(follow_up + 0.195)
    assert scheduler.next_due_seconds is not None
    assert 3.0 <= scheduler.next_due_seconds - (follow_up + 0.195) <= 8.0


def test_pause_resume_preserves_random_sequence_and_enforces_delay() -> None:
    scheduler = BlinkScheduler(BlinkConfig(seed=19))
    scheduler.start(0.0)
    draws = scheduler.random_draw_count
    scheduler.pause(1.0, minimum_resume_delay_seconds=1.5)
    scheduler.resume(0.0, minimum_delay_seconds=1.5)
    assert scheduler.next_due_seconds is not None and scheduler.next_due_seconds >= 1.5
    assert scheduler.random_draw_count == draws


def test_none_seed_is_materialized_once_as_64_bit_value() -> None:
    scheduler = BlinkScheduler(BlinkConfig())
    assert 0 <= scheduler.actual_seed < 2**64
