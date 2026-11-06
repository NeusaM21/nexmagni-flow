import pytest

from guarded_llm_router import Intent, ScriptedClient, Source, route


def routed(message, **kwargs):
    client = ScriptedClient([])  # any model call would raise "script exhausted"
    result = route(message, client=client, sleep=lambda _s: None, **kwargs)
    return result, client


@pytest.mark.parametrize(
    "message",
    [
        "Can I talk to a person about my booking?",
        "I want a human",
        "Please let me speak to someone",
        "Is there a real person there?",
        "Can the owner call me back?",
        "REPRESENTATIVE",
    ],
)
def test_human_request_wins_without_calling_the_model(message):
    result, client = routed(message)
    assert (result.intent, result.source, result.rule) == (
        Intent.HUMAN_HANDOFF, Source.RULE, "human_request"
    )
    assert client.calls == 0


def test_human_request_wins_even_inside_a_booking_flow():
    result, _ = routed("actually, can I talk to someone?", in_booking_flow=True)
    assert result.intent is Intent.HUMAN_HANDOFF


@pytest.mark.parametrize("message", ["tomorrow at 3", "the second one", "Saturday?"])
def test_active_booking_flow_keeps_booking(message):
    result, client = routed(message, in_booking_flow=True)
    assert (result.intent, result.source) == (Intent.BOOKING, Source.RULE)
    assert client.calls == 0


@pytest.mark.parametrize("message", ["hello", "Hi there!", "Good morning", "thank you"])
def test_greeting_only_is_small_talk(message):
    result, _ = routed(message)
    assert (result.intent, result.rule) == (Intent.SMALL_TALK, "greeting_only")


@pytest.mark.parametrize(
    "message",
    ["Hello there, how much is a haircut?", "What are your prices?", "Where are you located? address?"],
)
def test_service_questions(message):
    result, _ = routed(message)
    assert (result.intent, result.rule) == (Intent.SERVICE_INFO, "service_question")


@pytest.mark.parametrize("message", ["I'd like to book an appointment", "Can I reserve a spot?"])
def test_explicit_booking(message):
    result, _ = routed(message)
    assert (result.intent, result.rule) == (Intent.BOOKING, "explicit_booking")


@pytest.mark.parametrize("message", ["bookshelf", "humanity", "hello, is Saturday possible?"])
def test_rules_match_whole_words_only(message):
    client = ScriptedClient(["SMALL_TALK"])
    result = route(message, client=client, sleep=lambda _s: None)
    assert result.source is Source.MODEL
    assert client.calls == 1
