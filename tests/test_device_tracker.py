"""Tests for BetterPresenceEntity (device_tracker platform)."""

from unittest.mock import MagicMock

from custom_components.better_presence.device_tracker import BetterPresenceEntity
from custom_components.better_presence.coordinator import (
    BetterPresenceCoordinator,
    PersonTrackingState,
)


def make_coordinator_mock(state="Home", attributes=None) -> MagicMock:
    ps = PersonTrackingState("thomas", "Thomas")
    ps.state = state
    ps.attributes = attributes or {"friendly_name": "Thomas"}

    coord = MagicMock(spec=BetterPresenceCoordinator)
    coord.get_person_state.return_value = ps
    coord.register_update_callback = MagicMock()
    coord.unregister_update_callback = MagicMock()
    return coord


def test_entity_unique_id():
    coord = make_coordinator_mock()
    entity = BetterPresenceEntity(coord, "thomas")
    assert entity.unique_id == "better_presence_thomas"


def test_entity_name():
    coord = make_coordinator_mock()
    entity = BetterPresenceEntity(coord, "thomas")
    assert entity.name == "Thomas"


def test_entity_state_reflects_coordinator():
    coord = make_coordinator_mock(state="Just arrived")
    entity = BetterPresenceEntity(coord, "thomas")
    assert entity.location_name == "Just arrived"


def test_entity_attributes_include_friendly_name():
    coord = make_coordinator_mock(
        state="Away", attributes={"friendly_name": "Thomas", "battery_level": 72}
    )
    entity = BetterPresenceEntity(coord, "thomas")
    attrs = entity.extra_state_attributes
    assert attrs["friendly_name"] == "Thomas"
    assert attrs["battery_level"] == 72


def test_entity_latitude_from_attributes():
    coord = make_coordinator_mock(
        state="Away",
        attributes={"friendly_name": "Thomas", "latitude": 52.5, "longitude": 13.4},
    )
    entity = BetterPresenceEntity(coord, "thomas")
    assert entity.latitude == 52.5
    assert entity.longitude == 13.4


def test_entity_latitude_none_without_gps():
    coord = make_coordinator_mock(state="Away", attributes={"friendly_name": "Thomas"})
    entity = BetterPresenceEntity(coord, "thomas")
    assert entity.latitude is None
    assert entity.longitude is None


async def test_update_callback_registered_on_added_to_hass():
    coord = make_coordinator_mock()
    entity = BetterPresenceEntity(coord, "thomas")
    entity.hass = MagicMock()
    entity.async_write_ha_state = MagicMock()

    await entity.async_added_to_hass()

    coord.register_update_callback.assert_called_once_with(
        entity._handle_coordinator_update
    )


async def test_update_callback_triggers_write_ha_state():
    coord = make_coordinator_mock()
    entity = BetterPresenceEntity(coord, "thomas")
    entity.hass = MagicMock()
    entity.async_write_ha_state = MagicMock()

    registered_cb = None

    def capture_cb(cb):
        nonlocal registered_cb
        registered_cb = cb

    coord.register_update_callback = capture_cb

    await entity.async_added_to_hass()

    registered_cb("thomas")
    entity.async_write_ha_state.assert_called_once()
