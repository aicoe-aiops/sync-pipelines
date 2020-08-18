"""Contest for solgate testsuite."""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def fixture_dir():
    """Locate fixtures directory in the test folder."""
    return Path(__file__).absolute().parent / "fixtures"
