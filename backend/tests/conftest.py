"""Pytest configuration for async tests."""

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "posix: tests that require POSIX process-group support (skipped on Windows)",
    )
