import pytest

from deterministic_intent.__main__ import DEMO, main


def test_single_message(capsys):
    assert main(["--context", "reminder", "I can't make it"]) == 0
    out = capsys.readouterr().out
    assert "intent=REQUEST_CANCEL" in out
    assert "action=START_CANCELLATION_FLOW" in out
    assert "destructive=False" in out


def test_demo_runs_without_arguments(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert out.count("action=") == len(DEMO)


def test_unknown_context_is_rejected(capsys):
    with pytest.raises(SystemExit):
        main(["--context", "unknown", "yes"])
