from __future__ import annotations

import sys

import pytest
from app.downloader import _run_command


def test_media_command_timeout_is_redacted_and_bounded() -> None:
    with pytest.raises(RuntimeError, match="^Media tool timed out$"):
        _run_command(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            timeout=0.05,
        )
