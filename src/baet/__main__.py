from baet.config.loader import load_settings


def main() -> None:
    settings = load_settings()
    print(f"BAET scaffold ready in {settings.app.mode} mode")


if __name__ == "__main__":
    main()
