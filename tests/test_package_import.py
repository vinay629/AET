import baet


def test_package_version_exists() -> None:
    assert baet.__version__ == "0.1.0"
