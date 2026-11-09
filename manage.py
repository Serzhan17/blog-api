import sys

from django.core.management import execute_from_command_line

from settings.bootstrap import configure_settings


def main() -> None:
    configure_settings()
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
