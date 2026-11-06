import math

import pytest

from guarded_llm_router import Failure, Intent, RouterConfig, ScriptedClient, Source, route


@pytest.mark.parametrize("message", [None, "", "   ", "\n\t", "​​"])
def test_empty_input_falls_back_without_calling_the_model(message):
    client = ScriptedClient(["BOOKING"])
    result = route(message, client=client, sleep=lambda _s: None)
    assert (result.intent, result.source, result.attempts, result.failures) == (
        Intent.SERVICE_INFO, Source.FALLBACK, 0, (Failure.EMPTY_INPUT,)
    )
    assert result.degraded
    assert client.calls == 0


@pytest.mark.parametrize("fallback", [Intent.SERVICE_INFO, Intent.HUMAN_HANDOFF, Intent.SMALL_TALK])
def test_configured_fallback_is_used(fallback):
    result = route(
        "something unusual",
        client=ScriptedClient(["nope"] * 3),
        config=RouterConfig(fallback=fallback),
        sleep=lambda _s: None,
    )
    assert (result.intent, result.source) == (fallback, Source.FALLBACK)


def test_booking_can_never_be_the_fallback():
    with pytest.raises(ValueError):
        RouterConfig(fallback=Intent.BOOKING)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_attempts": 0},
        {"max_attempts": 6},
        {"retry_delay_s": -1},
        {"retry_delay_s": math.inf},
        {"retry_delay_s": math.nan},
        {"max_input_chars": 0},
    ],
)
def test_invalid_config_values(kwargs):
    with pytest.raises(ValueError):
        RouterConfig(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [{"max_attempts": True}, {"max_attempts": 2.0}, {"fallback": "SMALL_TALK"}, {"retry_delay_s": "1"}],
)
def test_invalid_config_types(kwargs):
    with pytest.raises(TypeError):
        RouterConfig(**kwargs)


def test_programming_errors_raise():
    client = ScriptedClient([])
    with pytest.raises(TypeError):
        route(123, client=client)
    with pytest.raises(TypeError):
        route("hi", client=object())
    with pytest.raises(TypeError):
        route("hi", client=client, in_booking_flow="yes")
