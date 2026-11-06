from hitl_fail_closed.__main__ import main, run_demo


def test_demo_tells_the_whole_story():
    lines = "\n".join(run_demo())
    assert "operator mutes during generation   -> CHANGED" in lines
    assert "BLOCKED_AT_SEND, messages sent: 0" in lines
    assert "REJECTED_STALE" in lines
    assert "STORE_FAILURE (state still ACTIVE)" in lines
    assert "store unreadable                   -> BLOCKED_UNKNOWN" in lines
    assert "reactivate with a valid approval   -> CHANGED" in lines
    assert "next automated reply               -> SENT" in lines


def test_main_returns_zero(capsys):
    assert main([]) == 0
    assert "audit conv-001" in capsys.readouterr().out
