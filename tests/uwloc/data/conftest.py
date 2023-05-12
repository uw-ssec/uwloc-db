import pytest

from uwloc.data.tile import init_tiledb


def pytest_sessionstart(session: pytest.Session) -> None:
    """
    Called after the Session object has been created and
    before performing collection and entering the run test loop.
    """
    init_tiledb()
