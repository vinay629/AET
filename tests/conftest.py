"""Pytest configuration and fixtures for BAET tests."""

import os
from collections.abc import Generator
from pathlib import Path

import pytest

# ============================================================================
# Pytest Markers
# ============================================================================


def pytest_configure(config):
    """Register custom markers for test categorization."""
    config.addinivalue_line("markers", "unit: unit tests (fast, <1 second)")
    config.addinivalue_line("markers", "integration: integration tests (5-15 seconds)")
    config.addinivalue_line("markers", "e2e: end-to-end tests (30+ seconds)")
    config.addinivalue_line("markers", "skip_ci: skip this test in CI environment")


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def test_data_dir(project_root: Path) -> Path:
    """Return the test data directory."""
    test_data = project_root / "tests" / "data"
    test_data.mkdir(parents=True, exist_ok=True)
    return test_data


@pytest.fixture
def config_dir(project_root: Path) -> Path:
    """Return the config directory."""
    return project_root / "config"


@pytest.fixture
def temp_env() -> Generator[dict]:
    """Temporarily override environment variables for testing.

    Usage:
        def test_something(temp_env):
            temp_env['VAR_NAME'] = 'value'
            # test code
    """
    original_env = os.environ.copy()
    test_env = {}

    yield test_env

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_binance_credentials(temp_env: dict) -> dict:
    """Provide mock Binance API credentials for testing.

    Returns:
        Dictionary with mock API key and secret
    """
    credentials = {
        "api_key": "test_api_key_12345",
        "api_secret": "test_api_secret_67890",
    }
    temp_env["BINANCE_API_KEY"] = credentials["api_key"]
    temp_env["BINANCE_API_SECRET"] = credentials["api_secret"]

    return credentials


@pytest.fixture
def sample_portfolio() -> dict:
    """Provide sample portfolio data for testing.

    Returns:
        Dictionary with sample position data
    """
    return {
        "BTCUSDT": {
            "quantity": 0.5,
            "entry_price": 45000.0,
            "current_price": 46000.0,
        },
        "ETHUSDT": {
            "quantity": 5.0,
            "entry_price": 2500.0,
            "current_price": 2600.0,
        },
        "cash": 10000.0,
    }


@pytest.fixture
def sample_market_data() -> dict:
    """Provide sample market data (OHLCV) for testing.

    Returns:
        Dictionary with sample OHLCV data
    """
    return {
        "open": [100.0, 101.0, 102.0, 103.0],
        "high": [102.0, 103.0, 104.0, 105.0],
        "low": [99.0, 100.0, 101.0, 102.0],
        "close": [101.0, 102.0, 103.0, 104.0],
        "volume": [1000, 1200, 1100, 900],
    }


# ============================================================================
# Hooks
# ============================================================================


def pytest_collection_modifyitems(items):
    """Auto-mark tests based on their location/name.

    This hook categorizes tests automatically:
    - Files with 'integration' in name → integration marker
    - Files with 'e2e' in name → e2e marker
    - Everything else → unit marker (unless already marked)
    """
    for item in items:
        # Skip if already marked
        if any(item.iter_markers()):
            continue

        # Mark based on filename
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
        else:
            # Default to unit
            item.add_marker(pytest.mark.unit)


def pytest_runtest_setup(item):
    """Skip tests marked skip_ci when running in CI environment."""
    if "skip_ci" in item.keywords and (os.getenv("CI") or os.getenv("GITHUB_ACTIONS")):
        pytest.skip("Skipped in CI environment")


# ============================================================================
# Test Output Enhancement
# ============================================================================


def pytest_terminal_summary(terminalreporter):
    """Add custom summary to pytest output."""
    terminalreporter.section("Test Summary")

    # Count test markers
    stats = terminalreporter.stats
    if stats:
        total_passed = len(stats.get("passed", []))
        total_failed = len(stats.get("failed", []))
        total_skipped = len(stats.get("skipped", []))

        terminalreporter.write_line(
            f"✓ Passed: {total_passed} | ✗ Failed: {total_failed} | ⊘ Skipped: {total_skipped}\n"
        )
