"""Fixtures for tests that run inside a real Home Assistant instance.

These tests live apart from ``tests/``, whose conftest replaces the
``homeassistant`` package with lightweight stand-ins.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load integrations from ``custom_components``."""
