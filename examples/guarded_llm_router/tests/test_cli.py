import pytest

from guarded_llm_router.__main__ import DEMO, main


def test_demo_runs_without_arguments(capsys):
    assert main([]) == 0
    assert capsys.readouterr().out.count("intent=") == len(DEMO)


def test_model_route(capsys):
    assert main(["I was wondering about Saturday availability"]) == 0
    out = capsys.readouterr().out
    assert "intent=BOOKING source=MODEL attempts=1" in out


def test_simulated_failures_fall_back(capsys):
    assert main(["--fail", "3", "is the 14th any good"]) == 0
    out = capsys.readouterr().out
    assert "intent=SERVICE_INFO source=FALLBACK attempts=3" in out
    assert "failures=(TIMEOUT, TIMEOUT, TIMEOUT)" in out


def test_booking_flow_flag(capsys):
    assert main(["--booking-flow", "the second one"]) == 0
    assert "rule=active_booking_flow" in capsys.readouterr().out


def test_fail_count_is_bounded(capsys):
    with pytest.raises(SystemExit):
        main(["--fail", "9", "hi"])
