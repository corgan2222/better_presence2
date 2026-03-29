"""Tests for timer-triggered state transitions in BetterPresenceCoordinator."""

import pytest
from datetime import timedelta

from homeassistant.util.dt import utcnow
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.better_presence.coordinator import BetterPresenceCoordinator
from custom_components.better_presence.const import (
    DEFAULT_HOME_STATE,
    DEFAULT_JUST_ARRIVED_STATE,
    DEFAULT_JUST_LEFT_STATE,
    DEFAULT_AWAY_STATE,
)


def make_config(just_arrived_time=5, just_left_time=3) -> dict:
    return {
        "tracking": {
            "just_arrived_time": just_arrived_time,
            "just_left_time": just_left_time,
            "home_state": DEFAULT_HOME_STATE,
            "just_arrived_state": DEFAULT_JUST_ARRIVED_STATE,
            "just_left_state": DEFAULT_JUST_LEFT_STATE,
            "away_state": DEFAULT_AWAY_STATE,
            "far_away_state": "Far away",
            "far_away_distance": 0,
        },
        "persons": [
            {
                "id": "thomas",
                "friendly_name": "Thomas",
                "devices": ["device_tracker.thomas_ping"],
            }
        ],
    }


@pytest.fixture
def coordinator(hass):
    hass.states.async_set("device_tracker.thomas_ping", "home", {})
    coord = BetterPresenceCoordinator(hass, make_config())
    return coord


@pytest.fixture(autouse=True)
def cancel_timers_after_test(coordinator):
    """Cancel any pending timers after each test, regardless of pass/fail."""
    yield
    for pid in coordinator.get_person_ids():
        coordinator._cancel_timer_for(pid)


async def test_just_arrived_transitions_to_home_after_timer(hass, coordinator):
    coordinator._persons["thomas"].state = DEFAULT_JUST_ARRIVED_STATE
    hass.states.async_set("device_tracker.thomas_ping", "home", {})
    coordinator._start_timer("thomas", 5)

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=6))
    await hass.async_block_till_done()

    assert coordinator.get_person_state("thomas").state == DEFAULT_HOME_STATE


async def test_just_left_transitions_to_away_after_timer(hass, coordinator):
    coordinator._persons["thomas"].state = DEFAULT_JUST_LEFT_STATE
    hass.states.async_set("device_tracker.thomas_ping", "not_home", {})
    coordinator._start_timer("thomas", 3)

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=4))
    await hass.async_block_till_done()

    assert coordinator.get_person_state("thomas").state == DEFAULT_AWAY_STATE


async def test_timer_cancelled_on_quick_return(hass, coordinator):
    """Timer started for just_left must be cancelled when person returns."""
    coordinator._persons["thomas"].state = DEFAULT_JUST_LEFT_STATE
    hass.states.async_set("device_tracker.thomas_ping", "not_home", {})
    coordinator._start_timer("thomas", 3)

    # Quick return before timer fires
    hass.states.async_set("device_tracker.thomas_ping", "home", {})
    coordinator._evaluate_person("thomas")

    assert coordinator.get_person_state("thomas").state == DEFAULT_JUST_ARRIVED_STATE
    assert coordinator._persons["thomas"]._cancel_timer is not None

    # Original timer fires after cancellation — state must NOT change back
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=4))
    await hass.async_block_till_done()

    # just_arrived timer fires at +9s (arrived_time=5), but we only advanced +4s total
    assert coordinator.get_person_state("thomas").state == DEFAULT_JUST_ARRIVED_STATE


async def test_timer_not_fired_prematurely(hass, coordinator):
    coordinator._persons["thomas"].state = DEFAULT_JUST_LEFT_STATE
    hass.states.async_set("device_tracker.thomas_ping", "not_home", {})
    coordinator._start_timer("thomas", 3)

    # Only 1 second has passed
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()

    assert coordinator.get_person_state("thomas").state == DEFAULT_JUST_LEFT_STATE
