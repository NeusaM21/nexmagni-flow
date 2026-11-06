import threading

import pytest

from hitl_fail_closed import ConversationLocks, InMemoryControlStore, RecordingTransport
from hitl_fail_closed.fakes import WAIT_LIMIT_S

CONV = "conv-001"


@pytest.fixture
def store():
    return InMemoryControlStore()


@pytest.fixture
def locks():
    return ConversationLocks(timeout_s=2.0)


@pytest.fixture
def transport(store):
    return RecordingTransport(store)


def start(target):
    """Run `target` in a daemon thread and return (thread, results list)."""
    results = []
    thread = threading.Thread(target=lambda: results.append(target()), daemon=True)
    thread.start()
    return thread, results


def finish(thread):
    thread.join(WAIT_LIMIT_S)
    assert not thread.is_alive(), "thread did not finish in time"
