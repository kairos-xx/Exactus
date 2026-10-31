# Copyright (c) 2026
"""Project demo package renamed by ``examples/run.py``."""

from typing import Final, final


@final
class Constants:
    """Group module-level constants.

    Attributes:
        project_version: Grouped module constant.

    """

    project_version: Final[str] = "0.1.0"


class Project:
    """Tiny greeter demonstrating class-name restyling."""

    @staticmethod
    def greet(*, name: str) -> str:
        """Return the Project greeting.

        Args:
            name: Whom to greet.

        Returns:
            Greeting text mentioning the project name.

        """
        return f"project says hello, {name}!"
