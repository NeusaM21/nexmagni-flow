import pytest

from deterministic_intent import Action, Context, Intent, Interpretation, Reason, decide, interpret


@pytest.mark.parametrize("context", list(Context))
@pytest.mark.parametrize("message", [None, "", "   ", "\U0001F44D", "?!", "\n"])
def test_empty_input_is_unclear_and_asks(message, context):
    result = interpret(message, context)
    assert result == Interpretation(Intent.UNCLEAR, Reason.EMPTY)
    assert decide(result, context).action is Action.ASK_CLARIFICATION


@pytest.mark.parametrize("context", list(Context))
def test_very_long_input_is_handled(context):
    message = "please " * 2500 + "cancel"
    result = interpret(message, context)
    assert result.intent is not None
    decide(result, context)


def test_uppercase_and_accents_do_not_change_meaning():
    context = Context.BOOKING_CONFIRMATION
    assert interpret("YÉS", context) == interpret("yes", context)


def test_no_signal_in_open_conversation_is_no_intent():
    result = interpret("what time do you open on Saturday?", Context.OPEN_CONVERSATION)
    assert (result.intent, result.reason) == (Intent.NO_INTENT, Reason.NO_SIGNAL)


@pytest.mark.parametrize("bad_message", [123, b"yes", ["yes"]])
def test_non_string_message_is_a_programming_error(bad_message):
    with pytest.raises(TypeError):
        interpret(bad_message, Context.OPEN_CONVERSATION)


def test_non_context_is_a_programming_error():
    with pytest.raises(TypeError):
        interpret("yes", "booking")
    with pytest.raises(TypeError):
        decide(Interpretation(Intent.AFFIRM, Reason.EXPLICIT), "booking")
