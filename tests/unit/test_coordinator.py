"""Tests for BetterPresenceCoordinator state machine (no timers)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from custom_components.better_presence.const import (
    DEFAULT_AWAY_STATE,
    DEFAULT_FAR_AWAY_STATE,
    DEFAULT_HOME_STATE,
    DEFAULT_JUST_ARRIVED_STATE,
    DEFAULT_JUST_LEFT_STATE,
)
from custom_components.better_presence.coordinator import BetterPresenceCoordinator


def make_hass(tracker_states: dict) -> MagicMock:
    """Return a mock hass with preset device_tracker states."""
    hass = MagicMock()
    hass.config.latitude = 48.1351
    hass.config.longitude = 11.5820

    def get_state(entity_id):
        data = tracker_states.get(entity_id)
        if data is None:
            return None
        state = MagicMock()
        state.state = data["state"]
        state.attributes = data.get("attributes", {})
        state.last_changed = data.get("last_changed", datetime.now(UTC))
        state.last_updated = data.get("last_updated", datetime.now(UTC))
        return state

    hass.states.get = get_state
    return hass


def make_config(persons=None, tracking=None) -> dict:
    """Build a minimal config dict."""
    return {
        "tracking": tracking
        or {
            "just_arrived_time": 300,
            "just_left_time": 60,
            "home_state": DEFAULT_HOME_STATE,
            "just_arrived_state": DEFAULT_JUST_ARRIVED_STATE,
            "just_left_state": DEFAULT_JUST_LEFT_STATE,
            "away_state": DEFAULT_AWAY_STATE,
            "far_away_state": DEFAULT_FAR_AWAY_STATE,
            "far_away_distance": 0,
        },
        "persons": persons
        or [
            {
                "id": "thomas",
                "friendly_name": "Thomas",
                "devices": ["device_tracker.thomas_ping"],
            }
        ],
    }


def make_coordinator(hass, persons=None, tracking=None) -> BetterPresenceCoordinator:
    config = make_config(persons=persons, tracking=tracking)
    coord = BetterPresenceCoordinator(hass, config)
    return coord


# --- Initial state ---


def test_initial_state_is_empty():
    hass = make_hass({"device_tracker.thomas_ping": {"state": "not_home"}})
    coord = make_coordinator(hass)
    assert coord.get_person_state("thomas").state == ""


def test_evaluate_sets_away_when_not_home():
    hass = make_hass({"device_tracker.thomas_ping": {"state": "not_home"}})
    coord = make_coordinator(hass)
    with patch.object(coord, "_start_timer"):
        coord._evaluate_person("thomas")
    assert coord.get_person_state("thomas").state == DEFAULT_AWAY_STATE


def test_evaluate_sets_home_when_home():
    hass = make_hass({"device_tracker.thomas_ping": {"state": "home"}})
    coord = make_coordinator(hass)
    with patch.object(coord, "_start_timer"):
        coord._evaluate_person("thomas")
    assert coord.get_person_state("thomas").state == DEFAULT_HOME_STATE


# --- Leaving home ---


def test_home_to_not_home_sets_just_left():
    hass = make_hass({"device_tracker.thomas_ping": {"state": "not_home"}})
    coord = make_coordinator(hass)
    coord._persons["thomas"].state = DEFAULT_HOME_STATE
    with patch.object(coord, "_start_timer") as mock_timer:
        coord._evaluate_person("thomas")
    assert coord.get_person_state("thomas").state == DEFAULT_JUST_LEFT_STATE
    mock_timer.assert_called_once_with("thomas", 60)


def test_just_left_stays_on_update_before_timeout():
    hass = make_hass({"device_tracker.thomas_ping": {"state": "not_home"}})
    coord = make_coordinator(hass)
    coord._persons["thomas"].state = DEFAULT_JUST_LEFT_STATE
    with patch.object(coord, "_start_timer"):
        coord._evaluate_person("thomas", from_timer=False)
    assert coord.get_person_state("thomas").state == DEFAULT_JUST_LEFT_STATE


def test_just_left_transitions_to_away_on_timeout():
    hass = make_hass({"device_tracker.thomas_ping": {"state": "not_home"}})
    coord = make_coordinator(hass)
    coord._persons["thomas"].state = DEFAULT_JUST_LEFT_STATE
    with patch.object(coord, "_start_timer"):
        coord._evaluate_person("thomas", from_timer=True)
    assert coord.get_person_state("thomas").state == DEFAULT_AWAY_STATE


# --- Arriving home ---


def test_away_to_home_sets_just_arrived():
    hass = make_hass({"device_tracker.thomas_ping": {"state": "home"}})
    coord = make_coordinator(hass)
    coord._persons["thomas"].state = DEFAULT_AWAY_STATE
    with patch.object(coord, "_start_timer") as mock_timer:
        coord._evaluate_person("thomas")
    assert coord.get_person_state("thomas").state == DEFAULT_JUST_ARRIVED_STATE
    mock_timer.assert_called_once_with("thomas", 300)


def test_just_arrived_stays_on_update_before_timeout():
    hass = make_hass({"device_tracker.thomas_ping": {"state": "home"}})
    coord = make_coordinator(hass)
    coord._persons["thomas"].state = DEFAULT_JUST_ARRIVED_STATE
    with patch.object(coord, "_start_timer"):
        coord._evaluate_person("thomas", from_timer=False)
    assert coord.get_person_state("thomas").state == DEFAULT_JUST_ARRIVED_STATE


def test_just_arrived_transitions_to_home_on_timeout():
    hass = make_hass({"device_tracker.thomas_ping": {"state": "home"}})
    coord = make_coordinator(hass)
    coord._persons["thomas"].state = DEFAULT_JUST_ARRIVED_STATE
    with patch.object(coord, "_start_timer"):
        coord._evaluate_person("thomas", from_timer=True)
    assert coord.get_person_state("thomas").state == DEFAULT_HOME_STATE


# --- Quick return ---


def test_just_left_to_home_triggers_just_arrived():
    hass = make_hass({"device_tracker.thomas_ping": {"state": "home"}})
    coord = make_coordinator(hass)
    coord._persons["thomas"].state = DEFAULT_JUST_LEFT_STATE
    with (
        patch.object(coord, "_start_timer") as mock_timer,
        patch.object(coord, "_cancel_timer_for") as mock_cancel,
    ):
        coord._evaluate_person("thomas")
    assert coord.get_person_state("thomas").state == DEFAULT_JUST_ARRIVED_STATE
    mock_cancel.assert_called_once_with("thomas")
    mock_timer.assert_called_once_with("thomas", 300)


# --- Translate state ---


def test_translate_on_to_home():
    hass = MagicMock()
    coord = BetterPresenceCoordinator(hass, make_config())
    assert coord._translate_state("on") == "home"
    assert coord._translate_state("off") == "not_home"
    assert coord._translate_state("true") == "home"
    assert coord._translate_state("false") == "not_home"
    assert coord._translate_state("home") == "home"
    assert coord._translate_state("not_home") == "not_home"
    assert coord._translate_state("SomeZone") == "SomeZone"


# --- Multiple devices: WiFi beats GPS ---


def test_wifi_home_beats_gps_not_home():
    hass = make_hass(
        {
            "device_tracker.ping": {"state": "home", "attributes": {}},
            "device_tracker.gps": {
                "state": "not_home",
                "attributes": {"source_type": "gps"},
            },
        }
    )
    coord = make_coordinator(
        hass,
        persons=[
            {
                "id": "thomas",
                "friendly_name": "Thomas",
                "devices": ["device_tracker.ping", "device_tracker.gps"],
            }
        ],
    )
    assert (
        coord._get_aggregate_state(["device_tracker.ping", "device_tracker.gps"])
        == "home"
    )


def test_gps_stale_does_not_count_as_home():
    stale = datetime.now(UTC) - timedelta(hours=2)
    hass = make_hass(
        {
            "device_tracker.gps": {
                "state": "home",
                "attributes": {"source_type": "gps"},
                "last_updated": stale,
            },
        }
    )
    coord = make_coordinator(hass)
    assert coord._get_aggregate_state(["device_tracker.gps"]) == "not_home"


def test_gps_fresh_counts_as_home():
    fresh = datetime.now(UTC) - timedelta(minutes=10)
    hass = make_hass(
        {
            "device_tracker.gps": {
                "state": "home",
                "attributes": {"source_type": "gps"},
                "last_updated": fresh,
            },
        }
    )
    coord = make_coordinator(hass)
    assert coord._get_aggregate_state(["device_tracker.gps"]) == "home"


# --- Update callback ---


def test_update_callback_called_on_state_change():
    hass = make_hass({"device_tracker.thomas_ping": {"state": "not_home"}})
    coord = make_coordinator(hass)
    callback = MagicMock()
    coord.register_update_callback(callback)
    with patch.object(coord, "_start_timer"):
        coord._evaluate_person("thomas")
    callback.assert_called_with("thomas")
