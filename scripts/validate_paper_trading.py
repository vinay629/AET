"""Quick validation test for paper trading engine before starting M4.4 observation."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_paper_engine_startup():
    """Test that paper trading engine can initialize and run briefly."""
    print("Testing paper trading engine startup...")

    try:
        from baet.config.loader import load_settings
        from baet.paper.engine import PaperTradingEngine

        # Load paper config - just pass "paper" not full path
        print("1. Loading configuration...")
        settings = load_settings("paper")  # Just pass mode name
        print(f"   ✓ Loaded config for mode: {settings.app.mode}")

        # Initialize engine
        print("2. Initializing PaperTradingEngine...")
        engine = PaperTradingEngine(config=settings)
        print("   ✓ Engine initialized")

        # Check components
        print("3. Checking components...")
        print(f"   ✓ Portfolio: cash={engine.portfolio.cash}")
        print(f"   ✓ Order Simulator: fee_rate={engine.order_simulator.fee_rate}")
        print(f"   ✓ Logger: {'configured' if engine.paper_logger else 'not configured'}")

        # Test single iteration (with timeout)
        print("4. Testing single iteration...")
        try:
            # Monkey-patch _iteration to avoid infinite loop
            iteration_count = [0]

            def mock_iteration():
                iteration_count[0] += 1
                print(f"   ✓ Iteration {iteration_count[0]} completed (mock)")
                if iteration_count[0] >= 1:
                    engine.stop()

            engine._iteration = mock_iteration
            engine.start()
            print("   ✓ Engine ran successfully")

        except Exception as e:
            print(f"   ✗ Iteration failed: {e}")
            return False

        print("\n✓ All basic tests passed!")
        return True

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_logging_system():
    """Test that logging system works."""
    print("\nTesting logging system...")

    try:
        from baet.paper.logging import PaperTradingLogger

        logger = PaperTradingLogger(
            log_dir="logs/test_validation",
            level="INFO",
            rotation="size",
        )

        # Test log entries
        logger.log_engine_event("TEST_EVENT", {"test": True})
        logger.log_signal_received("BTCUSDT", {"signal": "BUY", "confidence": 0.8})
        logger.log_portfolio_update(
            action="TEST", symbol=None, cash=10000, positions={}, total_value=10000
        )

        # Check file was created
        log_files = list(Path("logs/test_validation").glob("*.log"))
        if log_files:
            print(f"   ✓ Log file created: {log_files[0].name}")
            print(f"   ✓ Log file size: {log_files[0].stat().st_size} bytes")

            # Cleanup
            import shutil

            shutil.rmtree("logs/test_validation", ignore_errors=True)

            return True
        else:
            print("   ✗ No log file created")
            return False

    except Exception as e:
        print(f"   ✗ Logging test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_dashboard_data_loading():
    """Test that dashboard can load data."""
    print("\nTesting dashboard data loading...")

    try:
        from baet.dashboard.data_loader import find_latest_log_file, parse_log_file

        # Create a test log file in the expected location
        test_dir = Path("logs/test_validation")
        test_dir.mkdir(parents=True, exist_ok=True)
        test_log = test_dir / "paper_trading_2026-05-07.log"
        test_log.write_text('{"timestamp": "2026-05-07T10:00:00", "event": "TEST"}\n')

        # Test finding log - use the test directory
        latest = find_latest_log_file(str(test_dir))
        if latest:
            print(f"   ✓ Found log file: {latest.name}")
        else:
            print("   ✗ Could not find log file")
            return False

        # Test parsing
        entries = parse_log_file(latest)
        if entries and len(entries) > 0:
            print(f"   ✓ Parsed {len(entries)} entries")
        else:
            print("   ✗ Could not parse log file")
            return False

        # Cleanup
        import shutil

        shutil.rmtree("logs/test_validation", ignore_errors=True)

        return True

    except Exception as e:
        print(f"   ✗ Data loading test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("BAET Paper Trading Validation Tests")
    print("=" * 60)

    results = []

    results.append(("Paper Engine Startup", test_paper_engine_startup()))
    results.append(("Logging System", test_logging_system()))
    results.append(("Dashboard Data Loading", test_dashboard_data_loading()))

    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n✓ All validation tests PASSED!")
        print("Ready to start M4.4 observation window.")
        sys.exit(0)
    else:
        print("\n✗ Some tests FAILED!")
        print("Fix issues before starting observation.")
        sys.exit(1)
