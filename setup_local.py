"""Create a local .env once; never overwrite existing secrets."""

from pathlib import Path
from secrets import token_urlsafe


def main() -> None:
    env = Path(__file__).resolve().parent / "settings" / ".env"
    if not env.exists():
        content = env.parent / ".env.example"
        text = content.read_text().replace("replace-with-a-long-random-secret", token_urlsafe(48))
        env.write_text(text)
        print("Created settings/.env with a random local secret.")
    else:
        print("Existing settings/.env preserved.")


if __name__ == "__main__":
    main()
