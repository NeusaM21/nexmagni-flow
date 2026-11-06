import pytest

from guarded_llm_router import Failure, Intent, RouterConfig, ScriptedClient, Source, route

NO_RULE = "I was wondering about Saturday"  # matches no deterministic rule


class SleepSpy:
    def __init__(self):
        self.delays = []

    def __call__(self, seconds):
        self.delays.append(seconds)


def run(script, **config):
    client = ScriptedClient(script)
    sleep = SleepSpy()
    result = route(NO_RULE, client=client, config=RouterConfig(**config), sleep=sleep)
    return result, client, sleep


def test_first_attempt_succeeds():
    result, client, sleep = run(["BOOKING"])
    assert (result.intent, result.source, result.attempts, result.failures) == (
        Intent.BOOKING, Source.MODEL, 1, ()
    )
    assert client.calls == 1
    assert sleep.delays == []


@pytest.mark.parametrize(
    ("script", "failures"),
    [
        ([RuntimeError("boom"), "BOOKING"], (Failure.ERROR,)),
        (["maybe booking?", "BOOKING"], (Failure.INVALID_OUTPUT,)),
        ([TimeoutError(), TimeoutError(), "BOOKING"], (Failure.TIMEOUT, Failure.TIMEOUT)),
        ([None, ValueError(), "booking."], (Failure.INVALID_OUTPUT, Failure.ERROR)),
    ],
)
def test_recovers_after_failures(script, failures):
    result, client, _ = run(script)
    assert (result.intent, result.source) == (Intent.BOOKING, Source.MODEL)
    assert result.failures == failures
    assert result.attempts == client.calls == len(failures) + 1


def test_exhausted_attempts_fall_back_with_linear_backoff():
    result, client, sleep = run([TimeoutError(), "garbage", RuntimeError()])
    assert (result.intent, result.source, result.attempts) == (
        Intent.SERVICE_INFO, Source.FALLBACK, 3
    )
    assert result.failures == (Failure.TIMEOUT, Failure.INVALID_OUTPUT, Failure.ERROR)
    assert client.calls == 3
    assert sleep.delays == [0.5, 1.0]  # no sleep after the last attempt


def test_single_attempt_never_sleeps():
    result, client, sleep = run([RuntimeError()], max_attempts=1)
    assert result.source is Source.FALLBACK
    assert client.calls == 1
    assert sleep.delays == []


@pytest.mark.parametrize("max_attempts", [1, 2, 3, 4, 5])
def test_never_more_calls_than_max_attempts(max_attempts):
    result, client, sleep = run([RuntimeError()] * 10, max_attempts=max_attempts)
    assert client.calls == result.attempts == max_attempts
    assert len(sleep.delays) == max_attempts - 1


def test_keyboard_interrupt_is_not_swallowed():
    with pytest.raises(KeyboardInterrupt):
        run([KeyboardInterrupt()])
