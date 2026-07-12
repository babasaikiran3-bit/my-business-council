"""Backend-specific pytest marker registration."""


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "posix: tests that require POSIX process-group support (skipped on Windows)",
    )
