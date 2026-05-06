"""Tests for GPS attribute collection and Far Away logic."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from custom_components.better_presence.const import (
    CONF_AWAY_STATE,
    CONF_FAR_AWAY_DISTANCE,
    CONF_FAR_AWAY_STATE,
    CONF_HOME_STATE,
    CONF_JUST_ARRIVED_STATE,
    CONF_JUST_ARRIVED_TIME,
    CONF_JUST_LEFT_STATE,
    CONF_JUST_LEFT_TIME,
    CONF_PERSON_DEVICES,
    CONF_PERSON_FRIENDLY_NAME,
    CONF_PERSON_ID,
    CONF_PERSONS,
    CONF_TRACKING,
    DEFAULT_AWAY_STATE,
    DEFAULT_FAR_AWAY_STATE,
    DEFAULT_HOME_STATE,
    DEFAULT_JUST_ARRIVED_STATE,
    DEFAULT_JUST_ARRIVED_TIME,
    DEFAULT_JUST_LEFT_STATE,
    DEFAULT_JUST_LEFT_TIME,
)
from custom_components.better_presence.coordinator import BetterPresenceCoordinator


def make_hass_with_gps(
    state="not_home", lat=52.52, lon=13.40, accuracy=10, battery=80, stale=False
) -> MagicMock:
    hass = MagicMock()
    hass.config.latitude = 48.1351
    hass.config.longitude = 11.5820
    updated = (datetime.now(UTC) - timedelta(hours=2)) if stale else datetime.now(UTC)
    s = MagicMock()
    s.state = state
    s.attributes = {
        "source_type": "gps",
        "latitude": lat,
        "longitude": lon,
        "gps_accuracy": accuracy,
        "battery_level": battery,
    }
    s.last_changed = updated
    s.last_updated = updated
    hass.states.get = lambda _: s
    return hass


def make_coord(hass, far_away_distance=50) -> BetterPresenceCoordinator:
    config = {
        CONF_TRACKING: {
            CONF_JUST_ARRIVED_TIME: DEFAULT_JUST_ARRIVED_TIME,
            CONF_JUST_LEFT_TIME: DEFAULT_JUST_LEFT_TIME,
            CONF_HOME_STATE: DEFAULT_HOME_STATE,
            CONF_JUST_ARRIVED_STATE: DEFAULT_JUST_ARRIVED_STATE,
            CONF_JUST_LEFT_STATE: DEFAULT_JUST_LEFT_STATE,
            CONF_AWAY_STATE: DEFAULT_AWAY_STATE,
            CONF_FAR_AWAY_STATE: DEFAULT_FAR_AWAY_STATE,
            CONF_FAR_AWAY_DISTANCE: far_away_distance,
        },
        CONF_PERSONS: [
            {
                CONF_PERSON_ID: "thomas",
                CONF_PERSON_FRIENDLY_NAME: "Thomas",
                CONF_PERSON_DEVICES: ["device_tracker.thomas_gps"],
            }
        ],
    }
    return BetterPresenceCoordinator(hass, config)


def test_gps_attributes_collected():
    hass = make_hass_with_gps(lat=52.52, lon=13.40, accuracy=10, battery=80)
    coord = make_coord(hass)
    attrs = coord._get_gps_attributes(["device_tracker.thomas_gps"])
    assert attrs["latitude"] == 52.52
    assert attrs["longitude"] == 13.40
    assert attrs["gps_accuracy"] == 10
    assert attrs["battery_level"] == 80
    assert attrs["source_type"] == "gps"
    assert "distance" in attrs
    assert isinstance(attrs["distance"], (int, float))


def test_distance_calculated():
    # Berlin (52.52, 13.40) to Munich (48.14, 11.58) ≈ 504 km
    hass = make_hass_with_gps(lat=52.52, lon=13.40)
    coord = make_coord(hass)
    dist = coord._get_distance(["device_tracker.thomas_gps"])
    assert dist is not None
    assert 490 < dist < 520, f"Expected ~504 km, got {dist}"


def test_haversine_same_point_is_zero():
    assert BetterPresenceCoordinator._haversine(48.14, 11.58, 48.14, 11.58) == 0.0


def test_away_to_far_away_when_distance_exceeds_threshold():
    hass = make_hass_with_gps(state="not_home", lat=52.52, lon=13.40)
    coord = make_coord(hass, far_away_distance=50)
    coord._persons["thomas"].state = DEFAULT_AWAY_STATE
    with patch.object(coord, "_start_timer"):
        coord._evaluate_person("thomas")
    assert coord.get_person_state("thomas").state == DEFAULT_FAR_AWAY_STATE


def test_no_far_away_when_distance_below_threshold():
    hass = make_hass_with_gps(state="not_home", lat=48.20, lon=11.60)
    coord = make_coord(hass, far_away_distance=50)
    coord._persons["thomas"].state = DEFAULT_AWAY_STATE
    with patch.object(coord, "_start_timer"):
        coord._evaluate_person("thomas")
    assert coord.get_person_state("thomas").state == DEFAULT_AWAY_STATE


def test_far_away_disabled_when_distance_zero():
    hass = make_hass_with_gps(state="not_home", lat=52.52, lon=13.40)
    coord = make_coord(hass, far_away_distance=0)
    coord._persons["thomas"].state = DEFAULT_AWAY_STATE
    with patch.object(coord, "_start_timer"):
        coord._evaluate_person("thomas")
    assert coord.get_person_state("thomas").state == DEFAULT_AWAY_STATE


def test_no_gps_attributes_when_no_gps_tracker():
    hass = MagicMock()
    hass.config.latitude = 48.14
    hass.config.longitude = 11.58
    s = MagicMock()
    s.state = "not_home"
    s.attributes = {}  # No source_type
    s.last_changed = datetime.now(UTC)
    s.last_updated = datetime.now(UTC)
    hass.states.get = lambda _: s
    coord = make_coord(hass)
    attrs = coord._get_gps_attributes(["device_tracker.thomas_ping"])
    assert attrs == {}
