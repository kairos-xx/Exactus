# Copyright (c) 2026
"""DemoApp demo package renamed by ``examples/run.py``."""

from typing import Final, final


@final
class Constants:
    """Group module-level constants.

    Attributes:
        demo_app_version: Grouped module constant.

    """

    demo_app_version: Final[str] = "0.1.0"


class DemoApp:
    """Tiny greeter demonstrating class-name restyling."""

    @staticmethod
    def greet(*, name: str) -> str:
        """Return the DemoApp greeting.

        Args:
            name: Whom to greet.

        Returns:
            Greeting text mentioning the demo_app name.

        """
        return f"demo_app says hello, {name}!"
