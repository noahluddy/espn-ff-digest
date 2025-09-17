"""Utility functions for ESPN Fantasy Football activity digest."""

import os
import re
from datetime import datetime
from typing import Any

from dateutil import tz

# Always display times in US Central Time (handles CST/CDT automatically)
CENTRAL_TIME = tz.gettz("America/Chicago")


def get_env(name: str, required: bool = True, default: str | None = None) -> str:
    """Get environment variable with optional validation.

    Args:
        name: Environment variable name
        required: Whether the variable is required
        default: Default value if not found

    Returns:
        Environment variable value

    Raises:
        RuntimeError: If required variable is missing or empty
    """
    val = os.environ.get(name, default)
    # If the value is empty string and we have a default, use the default
    if not val and default is not None:
        val = default
    if required and not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


def debug() -> bool:
    """Check if DEBUG is enabled.

    Returns:
        True if DEBUG environment variable is set to a truthy value
    """
    debug_val = get_env("DEBUG", default="", required=False)
    return debug_val.lower() in {"1", "true", "yes", "on"}


def strip_html_tags(text: str) -> str:
    """Remove simple HTML tags like <strong> from a string for plain-text extraction."""
    if not isinstance(text, str):
        return str(text)
    return re.sub(r"<[^>]+>", "", text)


def fmt_team(team_obj: Any) -> str:
    """Format team object to string, trying team_name, team_abbrev, then str()."""
    return (getattr(team_obj, "team_name", None) or
            getattr(team_obj, "team_abbrev", None) or
            str(team_obj))


def fmt_player(player_obj: Any) -> str:
    """Format player object to string with position and team info."""
    if hasattr(player_obj, "name"):
        name = player_obj.name
        # Don't add position/proTeam info if name already includes "D/ST"
        if "D/ST" in name:
            return name
        pos = getattr(player_obj, "position", "")
        pro = getattr(player_obj, "proTeam", "")
        extras = ", ".join([p for p in [pos, pro] if p])
        return f"{name} ({extras})" if extras else name
    return str(player_obj)


def is_dst_player(player_name: str) -> bool:
    """Check if a player name represents a Defense/Special Teams unit."""
    return "D/ST" in player_name or "DST" in player_name


def get_player_headshot_url(player_id: int) -> str:
    """Get ESPN headshot URL for a player.

    Args:
        player_id: ESPN player ID

    Returns:
        URL string for the player's headshot image
    """
    return f"https://a.espncdn.com/i/headshots/nfl/players/full/{player_id}.png"


def get_team_logo_url(team_abbrev: str) -> str:
    """Get ESPN team logo URL.

    Args:
        team_abbrev: Team abbreviation (e.g., 'GB', 'KC')

    Returns:
        URL string for the team's logo image
    """
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{team_abbrev.lower()}.png"


def fmt_local(dt_utc: datetime) -> str:
    """Format UTC datetime to local time string."""
    return dt_utc.astimezone(CENTRAL_TIME).strftime("%Y-%m-%d %I:%M %p")
