"""
12-Factor App Configuration — all settings from environment variables.

Factor III: Store config in the environment.
Factor X: Dev/prod parity through shared config shape.
"""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ServerConfig:
    """Immutable server configuration loaded from environment."""

    name: str = field(default_factory=lambda: os.getenv("DICE_SERVER_NAME", "dice-server"))
    version: str = field(default_factory=lambda: os.getenv("DICE_SERVER_VERSION", "5.0.0"))

    # History
    history_max_size: int = field(
        default_factory=lambda: int(os.getenv("DICE_HISTORY_MAX_SIZE", "100"))
    )

    # Dice limits
    max_pool_size: int = field(
        default_factory=lambda: int(os.getenv("DICE_MAX_POOL_SIZE", "50"))
    )
    max_dice_count: int = field(
        default_factory=lambda: int(os.getenv("DICE_MAX_DICE_COUNT", "100"))
    )
    max_dice_sides: int = field(
        default_factory=lambda: int(os.getenv("DICE_MAX_DICE_SIDES", "1000"))
    )

    # Logging
    log_level: str = field(default_factory=lambda: os.getenv("DICE_LOG_LEVEL", "INFO"))


def load_config() -> ServerConfig:
    """Load configuration from environment. Factor III compliance."""
    return ServerConfig()
