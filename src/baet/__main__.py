from baet.config.loader import load_settings


def main() -> None:
    settings = load_settings()
    print(
        "BAET research scaffold ready "
        f"in {settings.app.mode} mode for {len(settings.market.symbols)} symbols"
    )


if __name__ == "__main__":
    main()
