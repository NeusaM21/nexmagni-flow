import pytest

from hitl_fail_closed import (
    Actor,
    ControlRecord,
    ControlState,
    FaultyStore,
    StateReading,
    read_state,
)

from conftest import CONV


def test_confirmed_absence_is_active(store):
    assert read_state(store, CONV) == StateReading(ControlState.ACTIVE, 0)


def test_stored_states_are_read_back(store):
    store.compare_and_set(CONV, 0, ControlState.MUTED, Actor.AUTOMATION)
    assert read_state(store, CONV) == StateReading(ControlState.MUTED, 1)


def test_read_failure_is_unknown(store):
    faulty = FaultyStore(store)
    faulty.fail_get = True
    assert read_state(faulty, CONV) == StateReading(ControlState.UNKNOWN, None)


@pytest.mark.parametrize(
    "corrupted",
    [
        "MUTED",
        {"state": "active"},
        42,
        ControlRecord(ControlState.UNKNOWN, 3),
        ControlRecord("active", 1),
        ControlRecord(ControlState.ACTIVE, 0),
        ControlRecord(ControlState.ACTIVE, -1),
        ControlRecord(ControlState.ACTIVE, True),
        ControlRecord(ControlState.MUTED, "2"),
    ],
)
def test_corrupted_records_are_unknown(store, corrupted):
    faulty = FaultyStore(store)
    faulty.get_override = corrupted
    assert read_state(faulty, CONV).state is ControlState.UNKNOWN


def test_unknown_is_never_stored(store):
    with pytest.raises(ValueError):
        store.compare_and_set(CONV, 0, ControlState.UNKNOWN, Actor.HUMAN_OPERATOR)


def test_store_refuses_active_from_automation(store):
    store.compare_and_set(CONV, 0, ControlState.MUTED, Actor.AUTOMATION)
    with pytest.raises(PermissionError):
        store.compare_and_set(CONV, 1, ControlState.ACTIVE, Actor.AUTOMATION)
    assert read_state(store, CONV).state is ControlState.MUTED


def test_compare_and_set_rejects_wrong_version(store):
    assert store.compare_and_set(CONV, 5, ControlState.MUTED, Actor.AUTOMATION) is False
    assert store.history(CONV) == ()
