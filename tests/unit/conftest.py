# Unit tests: pure Python, no HA infrastructure.
#
# Problem: pytest-socket blocks socket.socket() globally. On Windows, asyncio
# event loop setup (required by pytest-asyncio even for sync tests) needs
# socket.socketpair(). The event_loop fixture fails because sockets are blocked.
#
# Fix: Re-enable sockets before pytest_socket disables them again, by hooking
# into pytest_fixture_setup with trylast=True so we run after pytest_socket
# has done its work but our enable_socket call overrides the block.
import pytest
import pytest_socket


@pytest.hookimpl(trylast=True)
def pytest_runtest_setup(item):
    """Re-enable sockets for all tests in this directory.

    Runs after pytest-socket disables them.
    """
    pytest_socket.enable_socket()
